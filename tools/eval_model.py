#!/usr/bin/env python3
"""Offline accuracy baseline: ONNX FP32 (CPU) on the labelled BRA validation split.

Gives per-class AP50 / AP50-95 and precision/recall at the 0.50 alert threshold, plus CPU latency.
These are the reference numbers to compare PipeGen's TensorRT FP32/FP16/INT8 engines against
(Edge Optimization bonus). This script is NOT part of the live system.

    pip install onnxruntime opencv-python-headless numpy
    python tools/eval_model.py                      # val split -> docs/evidence/model/
    python tools/eval_model.py --split test
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "training"))
import onnx_reference as ref  # noqa: E402

DATA = ROOT / "training" / "archive" / "Dataset"
OUT = ROOT / "docs" / "evidence" / "model"
CLASSES = ref.CLASS_NAMES
IOUS = np.linspace(0.5, 0.95, 10)


def load_gt(lbl: Path, w: int, h: int):
    boxes = []
    if lbl.exists():
        for line in lbl.read_text().split("\n"):
            p = line.split()
            if len(p) == 5:
                c, cx, cy, bw, bh = int(p[0]), *map(float, p[1:])
                boxes.append((c, (cx - bw / 2) * w, (cy - bh / 2) * h, (cx + bw / 2) * w, (cy + bh / 2) * h))
    return boxes


def iou(a, b):
    ix1, iy1, ix2, iy2 = max(a[0], b[0]), max(a[1], b[1]), min(a[2], b[2]), min(a[3], b[3])
    inter = max(0.0, ix2 - ix1) * max(0.0, iy2 - iy1)
    union = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter
    return inter / union if union > 0 else 0.0


def ap_from(tp: np.ndarray, conf: np.ndarray, n_gt: int) -> float:
    """All-point interpolated AP (VOC 2010+/COCO-style area under the PR curve)."""
    if n_gt == 0 or len(conf) == 0:
        return 0.0
    order = np.argsort(-conf)
    tp = tp[order]
    ctp = np.cumsum(tp)
    cfp = np.cumsum(1 - tp)
    rec = ctp / n_gt
    prec = ctp / np.maximum(ctp + cfp, 1e-9)
    mrec = np.concatenate(([0.0], rec, [1.0]))
    mpre = np.concatenate(([1.0], prec, [0.0]))
    mpre = np.flip(np.maximum.accumulate(np.flip(mpre)))
    idx = np.where(mrec[1:] != mrec[:-1])[0]
    return float(np.sum((mrec[idx + 1] - mrec[idx]) * mpre[idx + 1]))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--split", default="val", choices=["val", "test"])
    ap.add_argument("--alert-conf", type=float, default=0.50)
    a = ap.parse_args()

    ref.CONF_THRESHOLD = 0.001  # low threshold for mAP, like `yolo val`
    ref.IOU_THRESHOLD = 0.7     # `yolo val` NMS IoU
    ref.AGNOSTIC_NMS = False
    det = ref.AnimalDetector()
    imgs = sorted((DATA / "images" / a.split).glob("*.jpg"))
    # per class, per IoU threshold: list of (conf, tp)
    records = {c: [] for c in range(len(CLASSES))}
    n_gt = np.zeros(len(CLASSES), int)
    times = []
    confusion = np.zeros((len(CLASSES) + 1, len(CLASSES) + 1), int)  # rows=pred(+bg), cols=gt(+bg)

    for i, f in enumerate(imgs):
        img = cv2.imread(str(f))
        if img is None:
            continue
        h, w = img.shape[:2]
        gt = load_gt(DATA / "labels" / a.split / (f.stem + ".txt"), w, h)
        for g in gt:
            n_gt[g[0]] += 1
        t = time.perf_counter()
        dets = det.detect_from_array(img)
        times.append((time.perf_counter() - t) * 1000)
        dets.sort(key=lambda d: -d["confidence"])
        matched = np.zeros((len(IOUS), len(gt)), bool)
        for d in dets:
            c = d["class_id"]
            tps = np.zeros(len(IOUS), bool)
            ious = [iou(d["bbox"], g[1:]) if g[0] == c else 0.0 for g in gt]
            for k, thr in enumerate(IOUS):
                best, bj = 0.0, -1
                for j, v in enumerate(ious):
                    if v >= thr and not matched[k, j] and v > best:
                        best, bj = v, j
                if bj >= 0:
                    matched[k, bj] = True
                    tps[k] = True
            records[c].append((d["confidence"], tps))
        # confusion at the alert threshold, IoU 0.5, class-agnostic matching
        used = set()
        for d in [d for d in dets if d["confidence"] >= a.alert_conf]:
            best, bj = 0.0, -1
            for j, g in enumerate(gt):
                v = iou(d["bbox"], g[1:])
                if v >= 0.5 and j not in used and v > best:
                    best, bj = v, j
            if bj >= 0:
                used.add(bj)
                confusion[d["class_id"], gt[bj][0]] += 1
            else:
                confusion[d["class_id"], -1] += 1
        for j, g in enumerate(gt):
            if j not in used:
                confusion[-1, g[0]] += 1
        if (i + 1) % 50 == 0:
            print(f"{i + 1}/{len(imgs)} images")

    per_class = []
    for c, name in enumerate(CLASSES):
        recs = records[c]
        conf = np.array([r[0] for r in recs])
        tpm = np.array([r[1] for r in recs]).reshape(-1, len(IOUS))
        aps = [ap_from(tpm[:, k].astype(float), conf, n_gt[c]) for k in range(len(IOUS))]
        sel = conf >= a.alert_conf
        tp50 = int(tpm[sel, 0].sum()) if len(recs) else 0
        npred = int(sel.sum())
        per_class.append({
            "class": name, "instances": int(n_gt[c]),
            "ap50": round(aps[0], 3), "ap50_95": round(float(np.mean(aps)), 3),
            f"precision@{a.alert_conf}": round(tp50 / npred, 3) if npred else None,
            f"recall@{a.alert_conf}": round(tp50 / n_gt[c], 3) if n_gt[c] else None,
        })
    m50 = round(float(np.mean([p["ap50"] for p in per_class])), 3)
    m5095 = round(float(np.mean([p["ap50_95"] for p in per_class])), 3)
    tp_all = sum(int(np.array([r[1][0] for r in records[c] if r[0] >= a.alert_conf]).sum()) for c in records)
    np_all = sum(sum(1 for r in records[c] if r[0] >= a.alert_conf) for c in records)
    lat = sorted(times)
    result = {
        "generated": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "model": "training/runs/detect/train3/weights/best.onnx (YOLOv8n, 5 classes, 640)",
        "runtime": "ONNX Runtime CPU, FP32 (offline reference, not the live system)",
        "split": a.split, "images": len(imgs), "instances": int(n_gt.sum()),
        "map50": m50, "map50_95": m5095,
        f"precision@{a.alert_conf}": round(tp_all / np_all, 3) if np_all else None,
        f"recall@{a.alert_conf}": round(tp_all / int(n_gt.sum()), 3),
        "cpu_latency_ms": {"p50": round(lat[len(lat) // 2], 1), "p95": round(lat[int(len(lat) * 0.95)], 1)},
        "per_class": per_class,
        "confusion_at_alert_conf": {"rows_pred": CLASSES + ["missed (background)"],
                                    "cols_gt": CLASSES + ["false positive (background)"],
                                    "matrix": confusion.tolist()},
    }
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / f"onnx_fp32_{a.split}_metrics.json").write_text(json.dumps(result, indent=2))

    pk, rk = f"precision@{a.alert_conf}", f"recall@{a.alert_conf}"
    md = [f"# Model accuracy baseline - ONNX FP32 on the {a.split} split", "",
          f"_Generated {result['generated']} by `tools/eval_model.py`. Offline reference on CPU, not the live system._", "",
          f"{len(imgs)} images, {int(n_gt.sum())} labelled animals. Alert threshold = {a.alert_conf}.", "",
          "| Class | Instances | AP50 | AP50-95 | Precision @ alert | Recall @ alert |", "|---|---|---|---|---|---|"]
    for p in per_class:
        md.append(f"| {p['class']} | {p['instances']} | {p['ap50']} | {p['ap50_95']} | {p[pk]} | {p[rk]} |")
    md.append(f"| **all** | **{int(n_gt.sum())}** | **{m50}** | **{m5095}** | **{result[pk]}** | **{result[rk]}** |")
    md += ["", f"CPU inference latency (ONNX Runtime, this laptop): p50 {result['cpu_latency_ms']['p50']} ms, "
           f"p95 {result['cpu_latency_ms']['p95']} ms per image. TensorRT numbers come from PipeGen's report.", "",
           f"## Confusion at conf >= {a.alert_conf}, IoU 0.5", "",
           "| predicted \\ actual | " + " | ".join(CLASSES) + " | background |", "|---" * (len(CLASSES) + 2) + "|"]
    for r, name in enumerate(CLASSES + ["missed"]):
        md.append(f"| {name} | " + " | ".join(str(v) for v in confusion[r]) + " |")
    sweep = [0.3, 0.4, 0.5, 0.6, 0.7]
    md += ["", "## Per-class threshold sweep (precision / recall at IoU 0.5)", "",
           "Use this to set the bridge's per-class `CONF_<CLASS>` values.", "",
           "| Class | " + " | ".join(f"conf {t}" for t in sweep) + " |", "|---" * (len(sweep) + 1) + "|"]
    result["threshold_sweep"] = {}
    for c, name in enumerate(CLASSES):
        cells = []
        for t in sweep:
            sel = [r for r in records[c] if r[0] >= t]
            tp = sum(int(r[1][0]) for r in sel)
            pr = round(tp / len(sel), 2) if sel else None
            rc = round(tp / n_gt[c], 2) if n_gt[c] else None
            result["threshold_sweep"].setdefault(name, {})[str(t)] = {"precision": pr, "recall": rc}
            cells.append(f"{pr} / {rc}")
        md.append(f"| {name} | " + " | ".join(cells) + " |")
    (OUT / f"onnx_fp32_{a.split}_metrics.json").write_text(json.dumps(result, indent=2))
    (OUT / f"onnx_fp32_{a.split}_metrics.md").write_text("\n".join(md) + "\n")
    print("\n".join(md))


if __name__ == "__main__":
    main()
