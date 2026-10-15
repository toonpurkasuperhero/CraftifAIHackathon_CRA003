"""OFFLINE reference only - NOT part of the live closed loop.

Pre-hackathon ONNX Runtime (CPU) detector, kept to compare accuracy/boxes against the
PipeGen TensorRT engines (FP32/FP16/INT8). The live system runs perception in PipeGen.

Usage:
    pip install onnxruntime opencv-python-headless numpy
    python training/onnx_reference.py training/BRA_YOLO/images/test --limit 20 --save out_dir
"""
import argparse
import base64
import json
from pathlib import Path

import cv2
import numpy as np
import onnxruntime as ort

HERE = Path(__file__).resolve().parent
MODEL_PATH = str(HERE / "runs" / "detect" / "train3" / "weights" / "best.onnx")
CLASS_NAMES = ["tapir", "jaguarundi", "maned_wolf", "puma", "giant_anteater"]
INPUT_SIZE = 640
CONF_THRESHOLD = 0.35
IOU_THRESHOLD = 0.45
AGNOSTIC_NMS = False

# Color palette per class (BGR for OpenCV)
CLASS_COLORS = {
    "tapir":          (0, 165, 255),    # orange
    "jaguarundi":     (0, 0, 255),      # red
    "maned_wolf":     (0, 255, 128),    # green
    "puma":           (128, 0, 255),    # purple
    "giant_anteater": (255, 200, 0),    # cyan
}


class AnimalDetector:
    def __init__(self, model_path: str = MODEL_PATH, class_names=None):
        self.model_path = model_path
        self.names = list(class_names or CLASS_NAMES)
        self.session = None
        self.input_name = None
        self.load_model()

    def load_model(self):
        providers = ["CPUExecutionProvider"]
        self.session = ort.InferenceSession(self.model_path, providers=providers)
        self.input_name = self.session.get_inputs()[0].name
        print(f"[Model] Loaded: {self.model_path}")
        print(f"[Model] Input: {self.input_name}")

    def preprocess(self, image_bgr: np.ndarray):
        """Letterbox resize + normalize to [0,1], CHW float32."""
        h, w = image_bgr.shape[:2]
        scale = INPUT_SIZE / max(h, w)
        new_w, new_h = int(w * scale), int(h * scale)
        resized = cv2.resize(image_bgr, (new_w, new_h))
        # Pad to square
        pad_top = (INPUT_SIZE - new_h) // 2
        pad_left = (INPUT_SIZE - new_w) // 2
        padded = np.full((INPUT_SIZE, INPUT_SIZE, 3), 114, dtype=np.uint8)
        padded[pad_top:pad_top + new_h, pad_left:pad_left + new_w] = resized
        # Normalize and transpose
        img = padded[:, :, ::-1].astype(np.float32) / 255.0  # BGR->RGB
        img = np.transpose(img, (2, 0, 1))[np.newaxis]        # NCHW
        return img, scale, pad_top, pad_left

    def postprocess(self, outputs, scale, pad_top, pad_left, orig_h, orig_w):
        """Decode YOLOv8 output tensor (1, 9, 8400) -> detections list."""
        pred = outputs[0][0]  # shape: (9, 8400)  or (8400, 9)
        # YOLOv8 ONNX output: (1, 4+nc, 8400)
        if pred.shape[0] < pred.shape[1]:
            # shape is (9, 8400) — columns are anchors
            cx, cy, bw, bh = pred[0], pred[1], pred[2], pred[3]
            class_scores = pred[4:]  # (nc, 8400)
        else:
            # shape is (8400, 9) 
            pred = pred.T
            cx, cy, bw, bh = pred[0], pred[1], pred[2], pred[3]
            class_scores = pred[4:].T  # (nc, 8400)

        # Confidence per anchor: max class score
        if class_scores.ndim == 2 and class_scores.shape[0] == len(self.names):
            confidences = np.max(class_scores, axis=0)
            class_ids = np.argmax(class_scores, axis=0)
        else:
            class_scores_t = class_scores.T if class_scores.shape[1] == len(self.names) else class_scores
            confidences = np.max(class_scores_t, axis=1)
            class_ids = np.argmax(class_scores_t, axis=1)

        mask = confidences >= CONF_THRESHOLD
        cx, cy, bw, bh = cx[mask], cy[mask], bw[mask], bh[mask]  # fixed: w/h were swapped
        confidences = confidences[mask]
        class_ids = class_ids[mask]

        # Convert cx,cy,bw,bh -> x1,y1,x2,y2 in padded image coords
        x1 = cx - bw / 2
        y1 = cy - bh / 2
        x2 = cx + bw / 2
        y2 = cy + bh / 2

        # Remove padding offset and rescale back to original image
        x1 = (x1 - pad_left) / scale
        y1 = (y1 - pad_top) / scale
        x2 = (x2 - pad_left) / scale
        y2 = (y2 - pad_top) / scale

        # Clip to image bounds
        x1 = np.clip(x1, 0, orig_w)
        y1 = np.clip(y1, 0, orig_h)
        x2 = np.clip(x2, 0, orig_w)
        y2 = np.clip(y2, 0, orig_h)

        # NMS
        boxes = np.stack([x1, y1, x2, y2], axis=1).tolist()
        scores = confidences.tolist()
        class_ids = class_ids.tolist()

        xywh = [[b[0], b[1], b[2]-b[0], b[3]-b[1]] for b in boxes]
        if AGNOSTIC_NMS:
            indices = cv2.dnn.NMSBoxes(xywh, scores, CONF_THRESHOLD, IOU_THRESHOLD)
        else:  # per-class NMS, the Ultralytics / DeepStream default
            indices = cv2.dnn.NMSBoxesBatched(xywh, scores, class_ids, CONF_THRESHOLD, IOU_THRESHOLD)

        detections = []
        if len(indices) > 0:
            indices = indices.flatten()
            for i in indices:
                cid = int(class_ids[i])
                label = self.names[cid] if cid < len(self.names) else "unknown"
                detections.append({
                    "animal": label,
                    "confidence": round(float(scores[i]), 4),
                    "bbox": [int(boxes[i][0]), int(boxes[i][1]), int(boxes[i][2]), int(boxes[i][3])],
                    "class_id": cid,
                })
        return detections

    def detect_from_array(self, image_bgr: np.ndarray):
        """Run detection on a numpy BGR image, return detections list."""
        orig_h, orig_w = image_bgr.shape[:2]
        blob, scale, pad_top, pad_left = self.preprocess(image_bgr)
        outputs = self.session.run(None, {self.input_name: blob})
        return self.postprocess(outputs, scale, pad_top, pad_left, orig_h, orig_w)

    def draw_detections(self, image_bgr: np.ndarray, detections: list) -> np.ndarray:
        """Draw bounding boxes on image and return annotated copy."""
        img = image_bgr.copy()
        for det in detections:
            x1, y1, x2, y2 = det["bbox"]
            label = det["animal"].replace("_", " ").title()
            conf = det["confidence"]
            color = CLASS_COLORS.get(det["animal"], (255, 255, 255))
            # Box
            cv2.rectangle(img, (x1, y1), (x2, y2), color, 2)
            # Label background
            text = f"{label}: {conf:.0%}"
            (tw, th), baseline = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2)
            cv2.rectangle(img, (x1, y1 - th - 10), (x1 + tw + 6, y1), color, -1)
            cv2.putText(img, text, (x1 + 3, y1 - 5),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 0), 2)
        return img

    def image_to_b64(self, image_bgr: np.ndarray, quality: int = 85) -> str:
        _, buffer = cv2.imencode(".jpg", image_bgr, [cv2.IMWRITE_JPEG_QUALITY, quality])
        return base64.b64encode(buffer).decode("utf-8")

    def detect_and_annotate(self, image_bgr: np.ndarray):
        """Full pipeline: detect + draw. Returns (detections, annotated_b64)."""
        detections = self.detect_from_array(image_bgr)
        annotated = self.draw_detections(image_bgr, detections)
        annotated_b64 = self.image_to_b64(annotated)
        return detections, annotated_b64


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("images", help="image file or folder")
    ap.add_argument("--model", default=MODEL_PATH)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--save", help="folder for annotated images")
    ap.add_argument("--json", help="write all detections to this JSON file")
    a = ap.parse_args()
    det = AnimalDetector(a.model)
    src = Path(a.images)
    files = sorted(p for p in (src.iterdir() if src.is_dir() else [src]) if p.suffix.lower() in {".jpg", ".jpeg", ".png"})
    if a.limit:
        files = files[: a.limit]
    out = {}
    if a.save:
        Path(a.save).mkdir(parents=True, exist_ok=True)
    for f in files:
        img = cv2.imread(str(f))
        if img is None:
            continue
        d = det.detect_from_array(img)
        out[f.name] = d
        print(f.name, [(x["animal"], x["confidence"]) for x in d])
        if a.save:
            cv2.imwrite(str(Path(a.save) / f.name), det.draw_detections(img, d))
    if a.json:
        Path(a.json).write_text(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
