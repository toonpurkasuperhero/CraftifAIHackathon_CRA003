#!/usr/bin/env bash
# Export both models PipeGen's Model stage needs, as static 640x640 ONNX in perception/export/:
#   wildguard_yolov8n_bra5.onnx  - our 5-species detector (primary)          output [1, 9, 8400]
#   coco_yolov8n.onnx            - stock YOLOv8n COCO, "veto" detector       output [1, 84, 8400]
#                                  (person / cat / dog / livestock -> suppress look-alike alerts)
# Training artifacts are never modified: we export from copies.
# Confirm opset/dynamic settings against the PipeGen v0.5.1 lab doc before the event.
set -euo pipefail
cd "$(dirname "$0")"
PY="${PYTHON:-python3}"
OUT=export
mkdir -p "$OUT"
"$PY" -c "import ultralytics, onnx" 2>/dev/null || { echo "pip install ultralytics onnx onnxslim"; exit 1; }

cp ../training/runs/detect/train3/weights/best.pt "$OUT/wildguard_yolov8n_bra5.pt"
cp ../training/yolov8n.pt "$OUT/coco_yolov8n.pt"

"$PY" - <<'PY'
from pathlib import Path
import onnx
from ultralytics import YOLO

out = Path("export")
for name, n_cls in (("wildguard_yolov8n_bra5", 5), ("coco_yolov8n", 80)):
    m = YOLO(str(out / f"{name}.pt"))
    f = Path(m.export(format="onnx", imgsz=640, opset=12, simplify=True, dynamic=False))
    target = out / f"{name}.onnx"
    if f.resolve() != target.resolve():
        f.replace(target)
    g = onnx.load(str(target)).graph
    dims = [d.dim_value for d in g.output[0].type.tensor_type.shape.dim]
    want = [1, 4 + n_cls, 8400]
    assert dims == want, f"{name}: output {dims}, expected {want}"
    print(f"OK  {target}  input {[d.dim_value for d in g.input[0].type.tensor_type.shape.dim]}  output {dims}")
    names = m.names
    (out / f"{name}_labels.txt").write_text("\n".join(names[i] for i in range(len(names))) + "\n")
PY
cp labels.txt "$OUT/labels.txt"
rm -f "$OUT"/*.pt
cmp -s "$OUT/labels.txt" "$OUT/wildguard_yolov8n_bra5_labels.txt" || { echo "labels.txt does not match the model's class order"; exit 1; }
echo "Done -> perception/$OUT/"
