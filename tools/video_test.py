#!/usr/bin/env python3
"""Video test: run the model on every frame of the test clips and push the detections through the
REAL bridge logic (K-frames, per-class thresholds, road zone, cool-down) on a frame-accurate clock.

Answers, per clip: would WildGuard alert, with the right species, how fast, and how often would it
false-alarm (negative clips). Writes docs/evidence/video_test/{report.md, results.json, frames/*.jpg}.

The detector here is the ONNX FP32 reference on CPU (the same weights PipeGen compiles to TensorRT).
With PipeGen (the real path): point PipeGen's file source at /home/$USER/wildguard_media/wildguard_demo_reel.mp4,
enable its JSON metadata output, then score that output with the same bridge logic:

    python perception/test_videos/fetch_test_videos.py      # once: clips + demo reel + reel_index.json
    python tools/video_test.py                               # offline reference (ONNX on CPU)
    python tools/video_test.py --pipegen-json <PipeGen metadata .jsonl or folder>   # PipeGen TensorRT output
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from collections import Counter
from datetime import datetime
from pathlib import Path

import cv2

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "training"))
sys.path.insert(0, str(ROOT / "bridge"))
sys.path.insert(0, str(ROOT / "shared"))
import bridge as br_mod  # noqa: E402
import onnx_reference as ref  # noqa: E402

OUT = ROOT / "docs" / "evidence" / "video_test"
LOG_DIR = Path(tempfile.gettempdir()) / "wildguard_video_test_logs"
MEDIA = Path(os.environ.get("WG_MEDIA_DIR", f"/home/{os.environ.get('USER', 'user')}/wildguard_media"))


class Clock:
    t = 0


def make_bridge(log_dir: Path):
    class A:
        host = port = pipegen_topic = json_path = None
    os.environ["BRIDGE_LOG_DIR"] = str(log_dir)
    br_mod.now_ms = lambda: Clock.t  # frame clock instead of wall clock
    b = br_mod.Bridge(br_mod.Config(A()))
    return b


def run_clip(det, path: Path, expect: str, frames_dir: Path, coco=None, track_iou=0.3):
    cap = cv2.VideoCapture(str(path))
    fps = cap.get(cv2.CAP_PROP_FPS) or 30
    b = make_bridge(LOG_DIR)                 # bridge with the look-alike veto (default config)
    b_nov = make_bridge(LOG_DIR)             # same bridge, veto disabled - for comparison
    b_nov.cfg.veto_classes = set()
    events_nov = []
    tracks = {}  # naive IoU tracker so the bridge sees stable track ids (PipeGen uses NvTracker)
    next_id = [1]

    def assign(dets):
        out = []
        for d in dets:
            best, bid = 0, None
            for tid, (cls, box) in tracks.items():
                if cls != d["animal"]:
                    continue
                v = iou(box, d["bbox"])
                if v > best:
                    best, bid = v, tid
            if best < track_iou:
                bid = next_id[0]
                next_id[0] += 1
            tracks[bid] = (d["animal"], d["bbox"])
            out.append({**d, "track_id": bid})
        return out

    n = 0
    frame_hits = Counter()           # frames where class appears at >= its alert threshold
    any_frame_hits = Counter()       # frames where class appears at all (>= detector conf)
    events = []
    best_frame = None
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        n += 1
        Clock.t = int(n * 1000 / fps)
        dets = assign(det.detect_from_array(frame))
        h, w = frame.shape[:2]
        for d in dets:
            any_frame_hits[d["animal"]] += 0  # ensure key
        for cls in {d["animal"] for d in dets}:
            any_frame_hits[cls] += 1
        for cls in {d["animal"] for d in dets if d["confidence"] >= b.cfg.class_conf.get(d["animal"], 0.5)}:
            frame_hits[cls] += 1
        veto = [v for v in (coco.detect_from_array(frame) if coco else []) if v["animal"] in b.cfg.veto_classes]
        payload = {"frame_num": n, "frame_width": w, "frame_height": h, "objects": [
            {"label": d["animal"], "confidence": d["confidence"], "track_id": d.get("track_id"),
             "bbox": {"left": d["bbox"][0], "top": d["bbox"][1],
                      "width": d["bbox"][2] - d["bbox"][0], "height": d["bbox"][3] - d["bbox"][1]}} for d in dets + veto]}
        events_nov += [e["class"] for e in b_nov.on_raw(payload)]
        for e in b.on_raw(payload):
            events.append({"t_s": round(Clock.t / 1000, 2), "class": e["class"], "conf": e["confidence"],
                           "track": e["track_id"]})
            if best_frame is None or (e["class"] == expect and best_frame[0] != expect):
                best_frame = (e["class"], det.draw_detections(frame, dets + veto), Clock.t)
    cap.release()
    if best_frame is None and n:
        # no event: keep a representative middle frame with whatever was detected
        cap = cv2.VideoCapture(str(path))
        cap.set(cv2.CAP_PROP_POS_FRAMES, n // 2)
        ok, frame = cap.read()
        cap.release()
        if ok:
            best_frame = (None, det.draw_detections(frame, det.detect_from_array(frame)), 0)
    if best_frame is not None:
        cv2.imwrite(str(frames_dir / f"{path.stem}.jpg"), best_frame[1], [cv2.IMWRITE_JPEG_QUALITY, 80])

    ev_classes = Counter(e["class"] for e in events)
    first_correct = next((e["t_s"] for e in events if e["class"] == expect), None)
    wrong = sum(v for k, v in ev_classes.items() if k != expect)
    if expect == "none":
        verdict = "PASS (no alert)" if not events else f"FALSE ALARM x{len(events)}"
    else:
        verdict = ("PASS" if first_correct is not None and wrong == 0 else
                   "PASS, with wrong-class alerts" if first_correct is not None else
                   "MISSED" if not events else "WRONG SPECIES")
    nov = Counter(events_nov)
    return {
        "event_classes_without_veto": dict(nov),
        "clip": path.stem, "expect": expect, "frames": n, "fps": round(fps, 1), "duration_s": round(n / fps, 1),
        "frames_with_expected_at_alert_conf": round(frame_hits[expect] / n, 3) if expect != "none" and n else None,
        "frames_with_each_class_at_alert_conf": dict(frame_hits),
        "events": events, "event_classes": dict(ev_classes),
        "time_to_first_correct_alert_s": first_correct, "wrong_class_events": wrong if expect != "none" else len(events),
        "verdict": verdict, "bridge_drops": {k: v for k, v in b.stats.items() if k.startswith("dropped")},
    }


def iou(a, b):
    ix1, iy1, ix2, iy2 = max(a[0], b[0]), max(a[1], b[1]), min(a[2], b[2]), min(a[3], b[3])
    inter = max(0, ix2 - ix1) * max(0, iy2 - iy1)
    u = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter
    return inter / u if u > 0 else 0


def iter_json(path: Path):
    files = sorted(path.glob("*.json")) if path.is_dir() else [path]
    for f in files:
        text = f.read_text()
        try:
            doc = json.loads(text)  # one JSON document per file
            if isinstance(doc, dict) and isinstance(doc.get("frames"), list):
                yield from doc["frames"]  # PipeGen video_json_export: {"frames": [{frame, objects: [...]}, ...]}
            else:
                yield doc
            continue
        except ValueError:
            pass
        for line in text.splitlines():  # JSON lines
            line = line.strip()
            if line:
                try:
                    yield json.loads(line)
                except ValueError:
                    pass


def run_pipegen_json(path: Path, index: list, fps: float):
    """Score PipeGen's JSON metadata for the demo reel, clip by clip, through the bridge."""
    b = make_bridge(LOG_DIR)
    events, t0, n = [], None, 0
    for msg in iter_json(path):
        n += 1
        fn = msg.get("frame_num", msg.get("frame")) if isinstance(msg, dict) else None
        if isinstance(fn, (int, float)):
            t_s = fn / fps
        else:
            ts = br_mod._ts_ms(msg.get("@timestamp") or msg.get("timestamp")) if isinstance(msg, dict) else None
            t0 = t0 if t0 is not None else ts
            t_s = (ts - t0) / 1000 if ts is not None and t0 is not None else n / fps
        Clock.t = int(t_s * 1000)
        events += [{"t_s": round(t_s, 2), "class": e["class"], "conf": e["confidence"]} for e in b.on_raw(msg)]
    results = []
    for c in index:
        ev = [e for e in events if c["start_s"] <= e["t_s"] < c["end_s"]]  # clips are back to back: no overlap
        cls = Counter(e["class"] for e in ev)
        expect = c["expect"]
        first = next((round(e["t_s"] - c["start_s"], 2) for e in ev if e["class"] == expect), None)
        wrong = sum(v for k, v in cls.items() if k != expect)
        verdict = (("PASS (no alert)" if not ev else f"FALSE ALARM x{len(ev)}") if expect == "none" else
                   "PASS" if first is not None and not wrong else
                   "PASS, with wrong-class alerts" if first is not None else "MISSED" if not ev else "WRONG SPECIES")
        results.append({"clip": c["id"], "expect": expect, "duration_s": round(c["end_s"] - c["start_s"], 1),
                        "frames_with_expected_at_alert_conf": None, "event_classes": dict(cls),
                        "event_classes_without_veto": None, "time_to_first_correct_alert_s": first,
                        "verdict": verdict, "events": ev})
    print(f"{n} PipeGen messages, {len(events)} events, bridge stats {b.stats}")
    return results


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--media", default=str(MEDIA))
    ap.add_argument("--conf", type=float, default=0.30, help="detector threshold (bridge applies alert thresholds)")
    ap.add_argument("--coco", default=str(ROOT / "perception" / "export" / "coco_yolov8n.onnx"),
                    help="COCO YOLOv8n ONNX for the look-alike veto ('' to disable); made by perception/export_onnx.sh")
    ap.add_argument("--pipegen-json", help="score PipeGen's JSON metadata for the demo reel instead of running ONNX")
    ap.add_argument("--fps", type=float, default=30.0, help="reel FPS, to turn frame numbers into time")
    a = ap.parse_args()
    if a.pipegen_json:
        index = json.loads((Path(a.media) / "reel_index.json").read_text())
        results = run_pipegen_json(Path(a.pipegen_json), index, a.fps)
        write_report(results, "PipeGen TensorRT pipeline (JSON metadata)", OUT / "pipegen")
        return
    manifest = json.loads((ROOT / "perception" / "test_videos" / "manifest.json").read_text())["clips"]
    ref.CONF_THRESHOLD = a.conf
    det = ref.AnimalDetector()
    coco = None
    if a.coco and Path(a.coco).exists():
        names = Path(a.coco).with_name("coco_yolov8n_labels.txt").read_text().split("\n")[:80]
        coco = ref.AnimalDetector(a.coco, names)
    else:
        print("no COCO model - look-alike veto not exercised (run perception/export_onnx.sh)")
    frames_dir = OUT / "frames"
    frames_dir.mkdir(parents=True, exist_ok=True)
    results = []
    for c in manifest:
        p = Path(a.media) / f"{c['id']}.mp4"
        if not p.exists():
            print(f"missing {p} - run perception/test_videos/fetch_test_videos.py")
            continue
        r = run_clip(det, p, c["expect"], frames_dir, coco)
        results.append(r)
        print(f"{r['clip']:<22} expect={r['expect']:<15} events={r['event_classes']}  first={r['time_to_first_correct_alert_s']}s  -> {r['verdict']}", flush=True)

    write_report(results, "ONNX FP32 reference on CPU (same weights PipeGen compiles to TensorRT)", OUT)


def write_report(results, detector, out: Path):
    out.mkdir(parents=True, exist_ok=True)
    doc = {"generated": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
           "detector": detector,
           "bridge": "bridge/bridge.py logic, frame clock, default thresholds", "results": results}
    (out / "results.json").write_text(json.dumps(doc, indent=2))
    md = ["# Video test - model + bridge on real wildlife footage", "",
          f"_Generated {doc['generated']} by `tools/video_test.py`. Detector: {doc['detector']}. "
          "Clips: `perception/test_videos/manifest.json` (Wikimedia Commons, see ATTRIBUTION.md)._", "",
          "Detectors: our 5-species model + the stock COCO YOLOv8n as look-alike veto (person/cat/dog), "
          "exactly the two models the PipeGen pipeline runs. \"Without veto\" shows the same bridge with the veto off.", "",
          "| Clip | Expected | Duration | Frames with expected species ≥ alert conf | Alerts without veto | Alerts with veto | First correct alert | Verdict (with veto) |",
          "|---|---|---|---|---|---|---|---|"]
    for r in results:
        fh = "—" if r["frames_with_expected_at_alert_conf"] is None else f"{r['frames_with_expected_at_alert_conf']:.0%}"
        ev = ", ".join(f"{k} ×{v}" for k, v in r["event_classes"].items()) or "none"
        ft = "—" if r["time_to_first_correct_alert_s"] is None else f"{r['time_to_first_correct_alert_s']} s"
        nv = ("—" if r["event_classes_without_veto"] is None else
              ", ".join(f"{k} ×{v}" for k, v in r["event_classes_without_veto"].items()) or "none")
        md.append(f"| {r['clip']} | {r['expect']} | {r['duration_s']} s | {fh} | {nv} | {ev} | {ft} | **{r['verdict']}** |")
    md += ["", "Annotated frame per clip (first alert, or middle frame if none): `frames/`.", ""]
    (out / "report.md").write_text("\n".join(md) + "\n")
    print(f"\n-> {out / 'report.md'}")




if __name__ == "__main__":
    main()
