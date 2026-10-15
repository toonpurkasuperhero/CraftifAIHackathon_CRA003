#!/usr/bin/env python3
"""REHEARSAL ONLY - stands in for the PipeGen pipeline when no GPU/camera is available.

Plays BRA test images as "scenes" (each held for a few seconds, then an empty road), runs the
trained YOLOv8n via ONNX Runtime on CPU once per image, and publishes per-frame JSON messages to
`wildguard/pipegen/raw` in the same shape the bridge parses from PipeGen. Also serves the annotated
frames as MJPEG (http://<host>:8090/stream.mjpg) for the dashboard's Live Loop page.

Every message carries "replay": true. The bridge, backend and dashboard use that to show a
REHEARSAL badge, and the evidence pack labels the data as simulated. Never submit it as PipeGen evidence.

    pip install onnxruntime opencv-python-headless numpy paho-mqtt
    python tools/pipegen_replay.py                       # BRA test images, 10 FPS
    python tools/pipegen_replay.py --source /home/me/clip.mp4
"""
from __future__ import annotations

import argparse
import json
import random
import sys
import threading
import time
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import cv2
import numpy as np
import paho.mqtt.client as mqtt

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "training"))
sys.path.insert(0, str(ROOT / "shared"))
import onnx_reference as ref  # noqa: E402

FRAME_W, FRAME_H = 1280, 720
DET = None
_latest = {"jpg": None}
_cond = threading.Condition()


class MJPEG(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_GET(self):
        if not self.path.startswith("/stream.mjpg"):
            self.send_response(404)
            self.end_headers()
            return
        self.send_response(200)
        self.send_header("Content-Type", "multipart/x-mixed-replace; boundary=frame")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        try:
            while True:
                with _cond:
                    _cond.wait(timeout=2)
                    jpg = _latest["jpg"]
                if jpg is None:
                    continue
                self.wfile.write(b"--frame\r\nContent-Type: image/jpeg\r\nContent-Length: "
                                 + str(len(jpg)).encode() + b"\r\n\r\n" + jpg + b"\r\n")
        except (BrokenPipeError, ConnectionResetError):
            pass


def letterbox(img):
    """Fit any image into a fixed 1280x720 'camera' frame."""
    h, w = img.shape[:2]
    s = min(FRAME_W / w, FRAME_H / h)
    nw, nh = int(w * s), int(h * s)
    canvas = np.full((FRAME_H, FRAME_W, 3), 30, np.uint8)
    x0, y0 = (FRAME_W - nw) // 2, (FRAME_H - nh) // 2
    canvas[y0:y0 + nh, x0:x0 + nw] = cv2.resize(img, (nw, nh))
    return canvas


def overlay(frame, dets, frame_num, fps, road_y):
    out = frame.copy()
    cv2.line(out, (0, road_y), (FRAME_W, road_y), (0, 200, 255), 2)
    cv2.putText(out, "road zone", (10, road_y + 26), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 200, 255), 2)
    out = DET.draw_detections(out, dets) if dets else out
    cv2.rectangle(out, (0, 0), (FRAME_W, 40), (0, 0, 0), -1)
    cv2.putText(out, f"REHEARSAL REPLAY - not PipeGen | ONNX CPU | frame {frame_num} | {fps} FPS",
                (12, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.75, (0, 215, 255), 2)
    ok, jpg = cv2.imencode(".jpg", out, [cv2.IMWRITE_JPEG_QUALITY, 75])
    return jpg.tobytes() if ok else None


def scenes_from_images(folder: Path, det, n, seed):
    files = sorted(folder.glob("*.jpg"))
    random.Random(seed).shuffle(files)
    for f in files[:n] if n else files:
        img = cv2.imread(str(f))
        if img is None:
            continue
        frame = letterbox(img)
        yield f.name, frame, det.detect_from_array(frame)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--host", default="localhost")
    ap.add_argument("--port", type=int, default=1883)
    ap.add_argument("--topic", default="wildguard/pipegen/raw")
    ap.add_argument("--source", default=str(ROOT / "training" / "archive" / "Dataset" / "images" / "test"),
                    help="folder of images or a video file")
    ap.add_argument("--fps", type=float, default=10)
    ap.add_argument("--hold-s", type=float, default=3.0, help="seconds each image is shown")
    ap.add_argument("--gap-s", type=float, default=2.0, help="empty-road seconds between images")
    ap.add_argument("--conf", type=float, default=0.30, help="detector threshold (the bridge applies the alert threshold)")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--http-port", type=int, default=8090)
    ap.add_argument("--road-zone-y", type=float, default=0.0, help="draw a road line at this normalised y")
    a = ap.parse_args()

    global DET
    ref.CONF_THRESHOLD = a.conf
    det = DET = ref.AnimalDetector()
    srv = ThreadingHTTPServer(("0.0.0.0", a.http_port), MJPEG)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    stream_url = f"http://{{host}}:{a.http_port}/stream.mjpg"
    print(f"[REPLAY] MJPEG on :{a.http_port}/stream.mjpg  MQTT {a.host}:{a.port} -> {a.topic}", flush=True)

    c = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=f"wg-replay-{random.randint(0, 9999)}")
    c.connect(a.host, a.port, keepalive=15)
    c.loop_start()

    period = 1 / a.fps
    frame_num = 0
    road_y = int(a.road_zone_y * FRAME_H)
    blank = np.full((FRAME_H, FRAME_W, 3), 30, np.uint8)
    cv2.putText(blank, "empty road", (FRAME_W // 2 - 90, FRAME_H // 2), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (90, 90, 90), 2)
    scene_no = 0
    rnd = random.Random(a.seed)

    def emit(frame, dets, scene):
        nonlocal frame_num
        frame_num += 1
        objs = []
        for k, d in enumerate(dets):
            x1, y1, x2, y2 = d["bbox"]
            conf = min(1.0, max(0.0, d["confidence"] + rnd.uniform(-0.03, 0.03)))  # live-like jitter
            objs.append({"label": d["animal"], "confidence": round(conf, 3), "track_id": scene * 10 + k,
                         "bbox": {"left": x1, "top": y1, "width": x2 - x1, "height": y2 - y1}})
        msg = {"frame_num": frame_num, "@timestamp": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
               "sensorId": "replay", "frame_width": FRAME_W, "frame_height": FRAME_H,
               "objects": objs, "replay": True, "stream_url": stream_url}
        c.publish(a.topic, json.dumps(msg, separators=(",", ":")), qos=0)
        jpg = overlay(frame, dets, frame_num, a.fps, road_y)
        with _cond:
            _latest["jpg"] = jpg
            _cond.notify_all()

    try:
        while True:
            src = Path(a.source)
            if src.is_dir():
                scenes = scenes_from_images(src, det, a.limit, a.seed + scene_no)
                for name, frame, dets in scenes:
                    scene_no += 1
                    print(f"[REPLAY] scene {scene_no}: {name} -> {[(d['animal'], d['confidence']) for d in dets]}", flush=True)
                    t_end = time.time() + a.hold_s
                    while time.time() < t_end:
                        t0 = time.time()
                        emit(frame, dets, scene_no)
                        time.sleep(max(0, period - (time.time() - t0)))
                    t_end = time.time() + a.gap_s
                    while time.time() < t_end:
                        t0 = time.time()
                        emit(blank, [], scene_no)
                        time.sleep(max(0, period - (time.time() - t0)))
            else:
                cap = cv2.VideoCapture(str(src))
                while True:
                    ok, img = cap.read()
                    if not ok:
                        break
                    t0 = time.time()
                    frame = letterbox(img)
                    emit(frame, det.detect_from_array(frame), 0)
                    time.sleep(max(0, period - (time.time() - t0)))
                cap.release()
    except KeyboardInterrupt:
        pass
    finally:
        c.loop_stop()
        srv.shutdown()


if __name__ == "__main__":
    main()
