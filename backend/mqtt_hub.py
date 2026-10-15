"""MQTT subscriber + live state cache + WebSocket fan-out.

The backend is an *observer and controller* of the loop, not part of the critical path:
PipeGen -> (bridge) -> broker -> ESP32 works even if this process is down.
"""
from __future__ import annotations

import asyncio
import itertools
import json
import threading
import time
import uuid

import paho.mqtt.client as mqtt

import config
import database as db
from wg_contract import CONTRACT_VERSION, SPECIES, TOPICS, normalise_class


def now_ms() -> int:
    return int(time.time() * 1000)


def _parse(payload: bytes):
    text = payload.decode("utf-8", errors="replace").strip()
    try:
        return json.loads(text)
    except ValueError:
        return text  # e.g. plain "offline" LWT


class Hub:
    def __init__(self):
        self.client: mqtt.Client | None = None
        self.loop: asyncio.AbstractEventLoop | None = None
        self._subs: set[asyncio.Queue] = set()
        self._lock = threading.Lock()
        self._pending: dict[str, int] = {}  # event_id -> time seen (ms), awaiting ACK
        self._syn_counter = itertools.count(1)
        self.state = {
            "broker": {"connected": False, "host": config.MQTT_HOST, "port": config.MQTT_PORT, "since_ms": None},
            "node": {"id": TOPICS.node, "online": False, "status": None, "last_seen_ms": None,
                     "fw": None, "rssi": None, "uptime_s": None},
            "sensor": None,
            "telemetry": None,
            "bridge": None,
            "mode": None,
            "last_detection": None,
            "last_ack": None,
            "recent_acks": [],
            "counters": {"detections": 0, "acks": 0, "timeouts": 0, "malformed": 0},
        }
        self._last_logged_sensor = None

    # ------------------------------------------------------------------ lifecycle
    def start(self, loop: asyncio.AbstractEventLoop):
        self.loop = loop
        c = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=f"wg-backend-{uuid.uuid4().hex[:6]}")
        if config.MQTT_USERNAME:
            c.username_pw_set(config.MQTT_USERNAME, config.MQTT_PASSWORD)
        c.on_connect = self._on_connect
        c.on_disconnect = self._on_disconnect
        c.on_message = self._on_message
        c.reconnect_delay_set(min_delay=1, max_delay=10)
        self.client = c
        try:
            c.connect_async(config.MQTT_HOST, config.MQTT_PORT, keepalive=15)
        except Exception as e:  # DNS errors etc. - keep the API up anyway
            print(f"[MQTT] connect_async failed: {e}")
        c.loop_start()
        threading.Thread(target=self._watchdog, daemon=True).start()

    def stop(self):
        if self.client:
            self.client.loop_stop()
            self.client.disconnect()

    # --------------------------------------------------------------- websockets
    def subscribe(self) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue(maxsize=500)
        self._subs.add(q)
        return q

    def unsubscribe(self, q: asyncio.Queue):
        self._subs.discard(q)

    def _emit(self, kind: str, data):
        msg = {"type": kind, "ts": now_ms(), "data": data}
        if not self.loop:
            return
        for q in list(self._subs):
            def _put(q=q):
                if q.full():
                    try:
                        q.get_nowait()
                    except asyncio.QueueEmpty:
                        pass
                q.put_nowait(msg)
            self.loop.call_soon_threadsafe(_put)

    # ------------------------------------------------------------------- mqtt cb
    def _on_connect(self, client, userdata, flags, reason_code, properties=None):
        ok = not reason_code.is_failure
        self.state["broker"].update(connected=ok, since_ms=now_ms())
        print(f"[MQTT] connected={ok} rc={reason_code}")
        if ok:
            client.subscribe(TOPICS.all, qos=1)
        self._emit("broker", self.state["broker"])

    def _on_disconnect(self, client, userdata, flags, reason_code, properties=None):
        self.state["broker"].update(connected=False, since_ms=now_ms())
        print(f"[MQTT] disconnected rc={reason_code}")
        self._emit("broker", self.state["broker"])

    def _on_message(self, client, userdata, msg):
        try:
            self._dispatch(msg.topic, _parse(msg.payload))
        except Exception as e:  # never let one bad message kill the network thread
            print(f"[MQTT] error handling {msg.topic}: {e}")

    def _dispatch(self, topic: str, p):
        t = TOPICS
        if topic == t.detections:
            self._on_detection(p)
        elif topic == t.ack:
            self._on_ack(p)
        elif topic == t.sensor:
            self._on_sensor(p)
        elif topic == t.status:
            self._on_status(p)
        elif topic == t.telemetry:
            self.state["telemetry"] = p
            self._touch_node()
            self._emit("telemetry", p)
        elif topic == t.mode:
            self.state["mode"] = p if isinstance(p, str) else (p or {}).get("mode")
            self._emit("mode", self.state["mode"])
        elif topic == t.bridge_status:
            self.state["bridge"] = p if isinstance(p, dict) else {"state": p}
            self.state["bridge"]["received_ms"] = now_ms()
            self._emit("bridge", self.state["bridge"])

    # ---------------------------------------------------------------- handlers
    def _on_detection(self, p):
        if not isinstance(p, dict) or "event_id" not in p:
            self.state["counters"]["malformed"] += 1
            return
        source = "synthetic" if p.get("synthetic") else "replay" if p.get("replay") else "pipegen"
        rid = db.insert_event(p, source=source)
        if rid is None:  # duplicate event_id (QoS1 redelivery) - already handled
            return
        seen = now_ms()
        with self._lock:
            self._pending[p["event_id"]] = seen
        self.state["counters"]["detections"] += 1
        self.state["last_detection"] = {**p, "id": rid, "source": source, "seen_ms": seen}
        self._emit("detection", self.state["last_detection"])

    def _on_ack(self, p):
        if not isinstance(p, dict) or "event_id" not in p:
            self.state["counters"]["malformed"] += 1
            return
        t_ack = now_ms()
        eid = p["event_id"]
        with self._lock:
            seen = self._pending.pop(eid, None)
        last = self.state["last_detection"] or {}
        ts_capture = last.get("ts_capture") if last.get("event_id") == eid else None
        if ts_capture is None:
            ts_capture = db.get_ts_capture(eid)
        ref = ts_capture or seen
        acted = p.get("state") in ("ALERT", "EXTEND")  # IGNORED ACKs prove receipt, not actuation
        latency = float(t_ack - ref) if (ref and acted) else None
        if latency is not None and (latency < 0 or latency > 60_000):
            latency = None  # clock skew / stale ACK; do not pollute the stats
        db.apply_ack(eid, p, t_ack, latency)
        onboard = None
        if isinstance(p.get("t_rx_ms"), (int, float)) and isinstance(p.get("t_act_ms"), (int, float)):
            onboard = p["t_act_ms"] - p["t_rx_ms"]
        ack = {**p, "ack_ts_ms": t_ack, "latency_ms": latency, "onboard_ms": onboard}
        self.state["counters"]["acks"] += 1
        self.state["last_ack"] = ack
        self.state["recent_acks"] = ([ack] + self.state["recent_acks"])[:10]
        self._touch_node()
        self._emit("ack", ack)

    def _on_sensor(self, p):
        if not isinstance(p, dict):
            return
        p = {**p, "received_ms": now_ms()}
        self.state["sensor"] = p
        self._touch_node()
        key = (p.get("armed"), p.get("pir"), p.get("state"))
        if key != self._last_logged_sensor:  # log transitions only, not the 1 Hz heartbeat
            self._last_logged_sensor = key
            db.insert_sensor_event(p.get("distance_cm"), p.get("pir"), p.get("armed"), p.get("state"))
        self._emit("sensor", p)

    def _on_status(self, p):
        node = self.state["node"]
        if isinstance(p, str):
            p = {"state": p}
        st = str(p.get("state", "")).lower()
        node.update(online=(st == "online"), status=st, fw=p.get("fw", node["fw"]),
                    rssi=p.get("rssi", node["rssi"]), uptime_s=p.get("uptime_s", node["uptime_s"]))
        if st == "online":
            node["last_seen_ms"] = now_ms()
        db.insert_node_status(node["id"], st, p.get("fw"), p.get("rssi"))
        self._emit("status", node)

    def _touch_node(self):
        n = self.state["node"]
        n["last_seen_ms"] = now_ms()
        if not n["online"] and n["status"] != "offline":
            n["online"] = True

    # ---------------------------------------------------------------- watchdog
    def _watchdog(self):
        while True:
            time.sleep(0.5)
            t = now_ms()
            with self._lock:
                expired = [e for e, s in self._pending.items() if t - s > config.ACK_TIMEOUT_S * 1000]
                for e in expired:
                    del self._pending[e]
            for e in expired:
                db.mark_ack_timeout(e)
                self.state["counters"]["timeouts"] += 1
                self._emit("timeout", {"event_id": e})

    # ----------------------------------------------------------------- publish
    def publish(self, topic: str, payload, qos=1, retain=False) -> bool:
        if not self.client or not self.state["broker"]["connected"]:
            return False
        data = payload if isinstance(payload, str) else json.dumps(payload, separators=(",", ":"))
        info = self.client.publish(topic, data, qos=qos, retain=retain)
        return info.rc == mqtt.MQTT_ERR_SUCCESS

    def publish_synthetic(self, species: str, confidence: float, in_road_zone: bool = True) -> dict:
        cls = normalise_class(species) or species
        evt = {
            "v": CONTRACT_VERSION,
            "event_id": f"syn-{int(time.time()) % 100000:05d}-{next(self._syn_counter)}",
            "ts_capture": now_ms(),
            "camera_id": "synthetic",
            "class": cls,
            "class_id": SPECIES[cls][0] if cls in SPECIES else -1,
            "confidence": round(confidence, 3),
            "track_id": -1,
            "in_road_zone": in_road_zone,
            "synthetic": True,
        }
        return evt if self.publish(TOPICS.detections, evt) else {}

    # ---------------------------------------------------------------- snapshot
    def snapshot(self) -> dict:
        t = now_ms()
        s = json.loads(json.dumps(self.state, default=str))
        node = s["node"]
        stale = node["last_seen_ms"] is None or t - node["last_seen_ms"] > config.NODE_STALE_S * 1000
        node["reachable"] = node["online"] and not stale
        node["simulated"] = str(node.get("fw") or "").startswith("sim")
        b = s["bridge"] or {}
        last_pipe = b.get("pipeline_last_ms")
        s["pipeline"] = {
            "alive": bool(last_pipe and b.get("received_ms")
                          and t - last_pipe < config.PIPELINE_STALE_S * 1000
                          and t - b["received_ms"] < config.PIPELINE_STALE_S * 1000),
            "last_message_ms": last_pipe,
            "msgs_per_s": b.get("raw_msgs_per_s"),
            "fps": b.get("fps"),
            "simulated": bool(b.get("replay")),
            "stream_url": b.get("stream_url"),
        }
        s["rehearsal"] = node["simulated"] or s["pipeline"]["simulated"]
        s["server_time_ms"] = t
        return s


hub = Hub()
