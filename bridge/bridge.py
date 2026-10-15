#!/usr/bin/env python3
"""WildGuard perception bridge: PipeGen/DeepStream output  ->  contract v1 detection events.

  PipeGen MQTT sink (raw, per frame/object)            ESP32 sensor topic
                \\                                            /
                 v                                          v
       parse (DeepStream full / minimal schema, generic JSON, JSON metadata files)
       -> keep 5 target classes -> per-class confidence threshold
       -> K consecutive frames per track -> road-zone check -> cool-down per track
       -> sensor_confirmed (ESP32 ARMED in the last N s) -> event_id
                 |
                 v
     wildguard/perception/detections  (QoS 1, < 256 bytes)  -> ESP32 + backend

Run `python bridge/bridge.py --sniff` first to print what PipeGen really publishes.
Configuration: environment variables (see bridge/.env.example) or CLI flags.
"""
from __future__ import annotations

import argparse
import itertools
import json
import os
import signal
import sys
import threading
import time
from collections import deque
from datetime import datetime
from pathlib import Path

import paho.mqtt.client as mqtt

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "shared"))
from wg_contract import CONTRACT_VERSION, MAX_PAYLOAD_BYTES, SPECIES, TOPICS, normalise_class  # noqa: E402

UNTRACKED_IDS = {-1, 0xFFFFFFFFFFFFFFFF, 18446744073709551615}


def now_ms() -> int:
    return int(time.time() * 1000)


def _load_dotenv(path: Path):
    if path.exists():
        for line in path.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())


_load_dotenv(HERE / ".env")


# ============================================================================ config
class Config:
    def __init__(self, a):
        e = os.getenv
        self.host = a.host or e("MQTT_HOST", "localhost")
        self.port = int(a.port or e("MQTT_PORT", "1883"))
        self.user = e("MQTT_USERNAME") or None
        self.password = e("MQTT_PASSWORD") or None
        self.pipegen_topic = a.pipegen_topic or e("PIPEGEN_TOPIC", "wildguard/pipegen/raw")
        self.json_path = a.json_path or e("PIPEGEN_JSON_PATH") or None
        self.camera_id = e("CAMERA_ID", "cam01")
        self.k_frames = int(e("K_FRAMES", "3"))
        self.max_gap_s = float(e("MAX_GAP_S", "0.7"))
        self.cooldown_s = float(e("COOLDOWN_S", "5"))
        self.min_conf = float(e("MIN_CONF", "0.50"))
        # per-class override: CONF_PUMA=0.6
        defaults = {"puma": 0.60}  # from the validation threshold sweep (docs/evidence/model)
        self.class_conf = {c: float(e(f"CONF_{c.upper()}", max(defaults.get(c, 0), self.min_conf))) for c in SPECIES}
        # road zone, normalised x1,y1,x2,y2 (bottom-centre of the box must be inside)
        z = [float(v) for v in e("ROAD_ZONE", "0,0,1,1").split(",")]
        self.road_zone = tuple(z) if len(z) == 4 else (0, 0, 1, 1)
        self.require_road_zone = e("REQUIRE_ROAD_ZONE", "true").lower() == "true"
        self.sensor_window_s = float(e("SENSOR_CONFIRM_WINDOW_S", "3"))
        # an animal must persist this long (and >= K frames) before it becomes an event
        self.confirm_min_s = float(e("CONFIRM_MIN_S", "0.5"))
        # Look-alike veto: PipeGen also runs the stock COCO YOLOv8n. A target track is suppressed when most of
        # its frames are overlapped by a confident person/cat/dog box (measured on the test videos:
        # 92-94 % on cat/dog clips vs 0-25 % on real species - see docs/evidence/video_test/).
        self.veto_classes = {c.strip().lower() for c in e("VETO_CLASSES", "person,cat,dog").split(",") if c.strip()}
        self.veto_conf = float(e("VETO_CONF", "0.5"))
        self.veto_overlap = float(e("VETO_OVERLAP", "0.5"))   # intersection / smaller box
        self.veto_ratio = float(e("VETO_RATIO", "0.5"))       # share of a track's frames that must be vetoed
        # veto boxes are matched to targets of the SAME frame (frame timestamp / number); this window is
        # only the fallback when a producer sends neither
        self.veto_window_ms = int(e("VETO_WINDOW_MS", "30"))
        self.frame_w = int(e("FRAME_W", "1920"))
        self.frame_h = int(e("FRAME_H", "1080"))
        self.log_dir = Path(e("BRIDGE_LOG_DIR", str(HERE / "logs")))


# ============================================================================ parsing
def _num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _bbox_from(o: dict):
    """Return (x1, y1, x2, y2) in whatever units the producer used, or None."""
    b = o.get("bbox") or o.get("rect_params") or o.get("box")
    if isinstance(b, dict):
        if "topleftx" in b:
            return (_num(b["topleftx"]), _num(b["toplefty"]), _num(b["bottomrightx"]), _num(b["bottomrighty"]))
        l, t = _num(b.get("left", b.get("x"))), _num(b.get("top", b.get("y")))
        w, h = _num(b.get("width", b.get("w"))), _num(b.get("height", b.get("h")))
        if None not in (l, t, w, h):
            return (l, t, l + w, t + h)
    if isinstance(b, (list, tuple)) and len(b) == 4:
        x, y, w, h = map(_num, b)
        if None in (x, y, w, h):
            return None
        fmt = str(o.get("bbox_format", "xywh")).lower()
        return (x, y, w, h) if fmt == "xyxy" else (x, y, x + w, y + h)
    l, t = _num(o.get("left")), _num(o.get("top"))
    w, h = _num(o.get("width")), _num(o.get("height"))
    if None not in (l, t, w, h):
        return (l, t, l + w, t + h)
    return None


_DS_STRUCT_KEYS = {"bbox", "rect_params", "box", "location", "coordinate", "pose", "embedding", "signature"}


def _label_from(o: dict):
    for k in ("label", "obj_label", "objLabel", "class", "class_name", "type", "objType", "obj_type"):
        if o.get(k) not in (None, ""):
            return o[k]
    for k in ("class_id", "classId", "obj_class_id", "class_index"):
        if k in o:
            return o[k]
    # DeepStream full schema puts the object type as a key, e.g. "puma": {...} or "person": {...}
    type_keys = [k for k, v in o.items() if isinstance(v, dict) and k not in _DS_STRUCT_KEYS]
    for k in type_keys:
        if normalise_class(k):
            return k
    return type_keys[0] if type_keys else None


def _ts_ms(v):
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return int(v if v > 1e12 else v * 1000)
    try:
        s = str(v).replace("Z", "+00:00")
        return int(datetime.fromisoformat(s).timestamp() * 1000)
    except ValueError:
        return None


def parse_minimal_object(s: str) -> dict | None:
    """DeepStream minimal schema: 'trackId|left|top|right|bottom|label[|...attrs][|confidence]'."""
    parts = s.split("|")
    if len(parts) < 6:
        return None
    conf = None
    for p in reversed(parts[6:]):
        f = _num(p)
        if f is not None and 0 <= f <= 1:
            conf = f
            break
    return {"track_id": parts[0], "bbox_xyxy": tuple(_num(p) for p in parts[1:5]),
            "label": parts[5], "confidence": conf}


def extract_objects(payload, default_w: int, default_h: int):
    """Normalise any supported PipeGen/DeepStream payload into a list of objects.

    Returns (objects, frame_key). Each object: label, confidence, bbox_xyxy (raw units),
    track_id, in_roi (bool|None), ts_ms, camera_id, frame_w, frame_h.
    """
    if isinstance(payload, list):
        objs = []
        for p in payload:
            o, _ = extract_objects(p, default_w, default_h)
            objs += o
        return objs, None
    if not isinstance(payload, dict):
        return [], None

    ts = _ts_ms(payload.get("@timestamp") or payload.get("timestamp") or payload.get("ts") or payload.get("ts_ms"))
    cam = (payload.get("sensor") or {}).get("id") if isinstance(payload.get("sensor"), dict) else None
    cam = cam or payload.get("sensorId") or payload.get("camera_id") or payload.get("source_id")
    fw = _num(payload.get("frame_width") or payload.get("width")) or default_w
    fh = _num(payload.get("frame_height") or payload.get("height")) or default_h
    frame_key = payload.get("frame_num", payload.get("frame", payload.get("id")))

    raw = []
    if isinstance(payload.get("object"), dict):  # DeepStream full schema: one object per message
        o = payload["object"]
        raw.append({
            "label": _label_from(o), "confidence": _num(o.get("confidence")),
            "bbox_xyxy": _bbox_from(o), "track_id": o.get("id"),
            "in_roi": bool((payload.get("analyticsModule") or {}).get("roiStatus")) or None,
        })
        frame_key = (payload.get("event") or {}).get("id", frame_key)
    else:
        lst = payload.get("objects") or payload.get("detections") or payload.get("objs") or []
        for o in lst:
            if isinstance(o, str):
                m = parse_minimal_object(o)
                if m:
                    raw.append(m)
            elif isinstance(o, dict):
                roi = o.get("in_roi", o.get("roi", o.get("roiStatus")))
                raw.append({
                    "label": _label_from(o),
                    "confidence": _num(o.get("confidence", o.get("conf", o.get("score", o.get("detector_confidence"))))),
                    "bbox_xyxy": _bbox_from(o),
                    "track_id": o.get("track_id", o.get("object_id", o.get("trackingId", o.get("id")))),
                    "in_roi": (bool(roi) if roi is not None else None),
                })
    for r in raw:
        r.update(ts_ms=ts, camera_id=cam, frame_w=fw, frame_h=fh)
    return raw, frame_key


def normalise_bbox(xyxy, fw, fh):
    """-> [x, y, w, h] normalised to 0..1 (accepts pixel or already-normalised input)."""
    if not xyxy or None in xyxy:
        return None
    x1, y1, x2, y2 = xyxy
    if max(abs(x1), abs(y1), abs(x2), abs(y2)) > 1.5:
        x1, x2, y1, y2 = x1 / fw, x2 / fw, y1 / fh, y2 / fh
    clamp = lambda v: round(min(max(v, 0.0), 1.0), 3)  # noqa: E731
    x1, y1, x2, y2 = map(clamp, (x1, y1, x2, y2))
    return [x1, y1, round(x2 - x1, 3), round(y2 - y1, 3)]


def in_zone(bbox_n, zone) -> bool:
    """Bottom-centre of the box (where the animal touches the ground) inside the road zone."""
    if not bbox_n:
        return True
    x, y, w, h = bbox_n
    cx, by = x + w / 2, y + h
    zx1, zy1, zx2, zy2 = zone
    return zx1 <= cx <= zx2 and zy1 <= by <= zy2


def overlap(a, b) -> float:
    """Intersection over the smaller box, for normalised [x, y, w, h] boxes."""
    ix = max(0.0, min(a[0] + a[2], b[0] + b[2]) - max(a[0], b[0]))
    iy = max(0.0, min(a[1] + a[3], b[1] + b[3]) - max(a[1], b[1]))
    small = min(a[2] * a[3], b[2] * b[3])
    return ix * iy / small if small > 0 else 0.0


def _track_int(t):
    try:
        v = int(float(t))
    except (TypeError, ValueError):
        return None
    return None if v in UNTRACKED_IDS or v > 2**31 else v


# ============================================================================ engine
class Bridge:
    def __init__(self, cfg: Config):
        self.cfg = cfg
        self.tracks: dict = {}
        self.sensor = {"armed": False, "armed_ms": None}  # None = never armed
        self.seq = itertools.count(1)
        self.run_tag = datetime.now().strftime("%H%M")
        self.stats = {"raw_msgs": 0, "objects": 0, "events_published": 0, "dropped_not_target": 0,
                      "dropped_low_conf": 0, "dropped_outside_zone": 0, "dropped_streak": 0,
                      "dropped_cooldown": 0, "dropped_veto": 0, "veto_boxes": 0, "parse_errors": 0}
        self.veto_boxes: deque = deque(maxlen=500)
        self.msg_times: deque = deque(maxlen=2000)
        self.frame_times: deque = deque(maxlen=2000)
        self._last_frame = None
        self.pipeline_last_ms = None
        self.replay_last_ms = 0
        self.stream_url = None
        self.lock = threading.Lock()
        cfg.log_dir.mkdir(parents=True, exist_ok=True)
        self.logf = open(cfg.log_dir / f"bridge-{datetime.now():%Y%m%d}.jsonl", "a", buffering=1)
        self.client: mqtt.Client | None = None

    def log(self, kind, data):
        self.logf.write(json.dumps({"t": now_ms(), "kind": kind, "data": data}, default=str) + "\n")

    # ---------------------------------------------------------------- input
    def on_sensor(self, p):
        if isinstance(p, dict) and "armed" in p:
            armed = bool(p["armed"])
            with self.lock:
                self.sensor["armed"] = armed
                if armed:
                    self.sensor["armed_ms"] = now_ms()

    def sensor_confirmed(self) -> bool:
        s = self.sensor
        if s["armed"]:
            return True
        return s["armed_ms"] is not None and now_ms() - s["armed_ms"] <= self.cfg.sensor_window_s * 1000

    def on_raw(self, payload) -> list[dict]:
        """Process one raw PipeGen message; returns the events published (for tests)."""
        t = now_ms()
        self.stats["raw_msgs"] += 1
        self.msg_times.append(t)
        self.pipeline_last_ms = t
        if isinstance(payload, dict):
            if payload.get("replay"):
                self.replay_last_ms = t
            if payload.get("stream_url"):
                self.stream_url = str(payload["stream_url"])[:200]
        try:
            objs, frame_key = extract_objects(payload, self.cfg.frame_w, self.cfg.frame_h)
        except Exception as e:  # never die on unexpected input
            self.stats["parse_errors"] += 1
            self.log("parse_error", {"err": str(e)})
            return []
        if frame_key is not None and frame_key != self._last_frame:
            self._last_frame = frame_key
            self.frame_times.append(t)
        # 1) collect look-alike (veto) boxes from the COCO detector, keyed by frame
        fkey = (objs[0].get("ts_ms") if objs else None) or frame_key
        for o in objs:
            lbl = str(o.get("label") or "").strip().lower()
            if lbl in self.cfg.veto_classes and (o.get("confidence") or 1.0) >= self.cfg.veto_conf:
                vb = normalise_bbox(o.get("bbox_xyxy"), o["frame_w"], o["frame_h"])
                if vb:
                    self.veto_boxes.append((t, fkey, vb))
                    # per-object producers: the target of this frame may have arrived first - count it now
                    with self.lock:
                        for tr in self.tracks.values():
                            if (tr.get("last_fkey") == fkey and fkey is not None and not tr.get("vetoed_frame")
                                    and tr.get("last_bbox") and overlap(tr["last_bbox"], vb) >= self.cfg.veto_overlap):
                                tr["vetoed"] += 1
                                tr["vetoed_frame"] = True
        while self.veto_boxes and t - self.veto_boxes[0][0] > 2000:
            self.veto_boxes.popleft()
        frame_veto = [vb for vt, vk, vb in self.veto_boxes
                      if (vk == fkey if fkey is not None else t - vt <= self.cfg.veto_window_ms)]
        # 2) consider target objects
        out = []
        for o in objs:
            self.stats["objects"] += 1
            if str(o.get("label") or "").strip().lower() in self.cfg.veto_classes:
                self.stats["veto_boxes"] += 1
                continue
            evt = self._consider(o, t, replay=isinstance(payload, dict) and bool(payload.get("replay")),
                                 frame_veto=frame_veto, fkey=fkey)
            if evt:
                out.append(evt)
        return out

    def _consider(self, o: dict, t: int, replay: bool = False, frame_veto=(), fkey=None) -> dict | None:
        cfg = self.cfg
        cls = normalise_class(o.get("label"))
        if cls is None:
            self.stats["dropped_not_target"] += 1
            return None
        conf = o.get("confidence")
        conf = 1.0 if conf is None else float(conf)  # some schemas omit confidence after NMS
        if conf < cfg.class_conf[cls]:
            self.stats["dropped_low_conf"] += 1
            return None
        bbox = normalise_bbox(o.get("bbox_xyxy"), o["frame_w"], o["frame_h"])
        zone_ok = o["in_roi"] if o.get("in_roi") is not None else in_zone(bbox, cfg.road_zone)
        if cfg.require_road_zone and not zone_ok:
            self.stats["dropped_outside_zone"] += 1
            return None

        tid = _track_int(o.get("track_id"))
        key = (cls, tid if tid is not None else "untracked")
        with self.lock:
            tr = self.tracks.get(key)
            if tr is None or t - tr["last_ms"] > cfg.max_gap_s * 1000:
                tr = {"hits": 0, "vetoed": 0, "first_ms": t, "published_ms": None,
                      "published_ms_prev": tr["published_ms"] if tr else None}
                self.tracks[key] = tr
            tr["hits"] += 1
            tr["last_ms"] = t
            tr["last_fkey"], tr["last_bbox"] = fkey, bbox
            tr["vetoed_frame"] = bool(bbox and any(overlap(bbox, vb) >= cfg.veto_overlap for vb in frame_veto))
            if tr["vetoed_frame"]:
                tr["vetoed"] += 1
            if tr["hits"] < cfg.k_frames or t - tr["first_ms"] < cfg.confirm_min_s * 1000:
                self.stats["dropped_streak"] += 1
                return None
            if tr["vetoed"] / tr["hits"] >= cfg.veto_ratio:
                self.stats["dropped_veto"] += 1
                return None
            last_pub = tr["published_ms"] or tr.get("published_ms_prev")
            if last_pub and t - last_pub < cfg.cooldown_s * 1000:
                self.stats["dropped_cooldown"] += 1
                return None
            tr["published_ms"] = t
            # drop tracks not seen for a minute
            for k in [k for k, v in self.tracks.items() if t - v["last_ms"] > 60_000]:
                del self.tracks[k]

        evt = {
            "v": CONTRACT_VERSION,
            "event_id": f"wg-{self.run_tag}-{next(self.seq):05d}",
            "ts_capture": o.get("ts_ms") or t,
            "camera_id": str(o.get("camera_id") or cfg.camera_id)[:16],
            "class": cls,
            "class_id": SPECIES[cls][0],
            "confidence": round(conf, 3),
            "track_id": tid if tid is not None else -1,
            "bbox": bbox,
            "in_road_zone": bool(zone_ok),
            "sensor_confirmed": self.sensor_confirmed(),
        }
        if replay:
            evt["replay"] = True  # rehearsal source: stored separately, never counted as PipeGen evidence
        data = json.dumps(evt, separators=(",", ":"))
        if len(data) > MAX_PAYLOAD_BYTES:
            evt.pop("bbox")
            data = json.dumps(evt, separators=(",", ":"))
        self.stats["events_published"] += 1
        if self.client:
            self.client.publish(TOPICS.detections, data, qos=1)
        self.log("event_out", evt)
        print(f"[BRIDGE] -> {evt['event_id']} {cls} conf={evt['confidence']} track={evt['track_id']} "
              f"zone={evt['in_road_zone']} sensor={evt['sensor_confirmed']}")
        return evt

    # ---------------------------------------------------------------- status
    def status(self) -> dict:
        t = now_ms()
        rate = lambda dq: round(sum(1 for x in dq if t - x <= 5000) / 5, 1)  # noqa: E731
        return {"state": "online", "pipeline_last_ms": self.pipeline_last_ms,
                "raw_msgs_per_s": rate(self.msg_times),
                "fps": rate(self.frame_times) if self.frame_times else None,
                "k_frames": self.cfg.k_frames, "cooldown_s": self.cfg.cooldown_s,
                "confirm_min_s": self.cfg.confirm_min_s, "veto_classes": sorted(self.cfg.veto_classes),
                "min_conf": self.cfg.min_conf, "road_zone": self.cfg.road_zone,
                "replay": bool(self.replay_last_ms and t - self.replay_last_ms < 10_000),
                "stream_url": self.stream_url, **self.stats}


# ============================================================================ runtime
def _parse_payload(b: bytes):
    try:
        return json.loads(b.decode("utf-8", errors="replace"))
    except ValueError:
        return None


def tail_json(path: Path, handle, stop: threading.Event):
    """Follow PipeGen JSON metadata output: a JSON-lines file, or a folder of *.json files."""
    if path.is_dir():
        seen = set(p.name for p in path.glob("*.json"))
        while not stop.is_set():
            for p in sorted(path.glob("*.json")):
                if p.name not in seen:
                    seen.add(p.name)
                    try:
                        handle(json.loads(p.read_text()))
                    except ValueError:
                        pass
            time.sleep(0.05)
    else:
        while not path.exists() and not stop.is_set():
            time.sleep(0.5)
        with open(path) as f:
            f.seek(0, 2)
            buf = ""
            while not stop.is_set():
                chunk = f.readline()
                if not chunk:
                    time.sleep(0.02)
                    continue
                buf += chunk
                if buf.endswith("\n"):
                    line, buf = buf.strip(), ""
                    if line:
                        p = _parse_payload(line.encode())
                        if p is not None:
                            handle(p)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--host")
    ap.add_argument("--port")
    ap.add_argument("--pipegen-topic", help="MQTT topic PipeGen's MQTT sink publishes to")
    ap.add_argument("--json-path", help="instead of MQTT, follow PipeGen JSON metadata (file or folder)")
    ap.add_argument("--sniff", action="store_true", help="print raw PipeGen messages + parsed objects; publish nothing")
    a = ap.parse_args()
    sys.stdout.reconfigure(line_buffering=True)
    cfg = Config(a)
    br = Bridge(cfg)
    stop = threading.Event()

    c = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=f"wg-bridge-{os.getpid()}")
    if cfg.user:
        c.username_pw_set(cfg.user, cfg.password)
    c.will_set(TOPICS.bridge_status, json.dumps({"state": "offline"}), qos=1, retain=True)
    c.reconnect_delay_set(1, 10)

    def on_connect(client, userdata, flags, rc, props=None):
        print(f"[BRIDGE] broker {cfg.host}:{cfg.port} rc={rc}")
        if rc.is_failure:
            return
        client.subscribe(TOPICS.sensor, qos=0)
        if not cfg.json_path:
            client.subscribe(cfg.pipegen_topic, qos=0)
        client.publish(TOPICS.bridge_status, json.dumps({"state": "online"}), qos=1, retain=True)

    def on_message(client, userdata, msg):
        p = _parse_payload(msg.payload)
        if msg.topic == TOPICS.sensor:
            br.on_sensor(p)
            return
        if a.sniff:
            print(f"\n[RAW] {msg.topic}: {msg.payload[:600]!r}")
            print("[PARSED]", extract_objects(p, cfg.frame_w, cfg.frame_h)[0] if p is not None else "not JSON")
            return
        if p is None:
            br.stats["parse_errors"] += 1
            return
        br.log("raw_in", {"topic": msg.topic, "bytes": len(msg.payload)})
        br.on_raw(p)

    c.on_connect = on_connect
    c.on_message = on_message
    if not a.sniff:
        br.client = c
    c.connect_async(cfg.host, cfg.port, keepalive=15)
    c.loop_start()

    if cfg.json_path:
        threading.Thread(target=tail_json, args=(Path(cfg.json_path), br.on_raw, stop), daemon=True).start()
        print(f"[BRIDGE] following JSON metadata at {cfg.json_path}")
    else:
        print(f"[BRIDGE] listening on MQTT topic {cfg.pipegen_topic}")

    def _stop(*_):
        stop.set()
    signal.signal(signal.SIGINT, _stop)
    signal.signal(signal.SIGTERM, _stop)

    while not stop.wait(2):
        if not a.sniff:
            c.publish(TOPICS.bridge_status, json.dumps(br.status()), qos=0)
    c.publish(TOPICS.bridge_status, json.dumps({"state": "offline"}), qos=1, retain=True).wait_for_publish(2)
    c.loop_stop()
    c.disconnect()


if __name__ == "__main__":
    main()
