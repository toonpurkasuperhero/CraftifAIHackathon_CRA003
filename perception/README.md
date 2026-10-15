# perception/ - PipeGen (Perception)

Live perception runs **only** in a CraftifAI PipeGen v0.5.1 pipeline: a DeepStream app with the custom YOLOv8n compiled to a TensorRT engine. There is no inference anywhere else in the live system. The old ONNX/CPU code is in `training/onnx_reference.py` for offline accuracy comparison only.

| File | What |
|---|---|
| `labels.txt` | Class names in class-ID order. This is part of the MQTT contract. |
| `export_onnx.sh` | Re-exports `best.pt` to a static 640x640 ONNX in `export/` and prints the output shape |
| `make_calibration_list.py` | Class-balanced INT8 calibration set (400 images, 80 per class) |
| `requirement.md` | The Stage 1 sentence to paste into PipeGen |
| `reports/` | PipeGen speed reports (FP32/FP16/INT8) and `pipeline_info.json` |
| `screenshots/` | Requirement stage, **Pipeline IR node graph**, Compiler report, live run |
| `pipegen_export/` | The PipeGen export folder with `run.sh` (add on the day; engines are git-ignored) |

## Environment

- x86-64 Linux with an NVIDIA GPU, or a Jetson on JetPack 6, in an **X11** desktop session. Not WSL.
- `pipegen --version` must print `0.5.1`. Sign in with the CraftifAI account first.
- Keep videos and calibration images **under /home**.
- Build TensorRT engines **on the demo machine**. Engines are not portable between GPUs or TensorRT versions.

## The five stages

1. **Requirement.** Paste `requirement.md`. Screenshot it to `screenshots/01_requirement.png`.
2. **Pipeline IR.** Expect `source (USB cam /dev/video0, or a file under /home) -> preprocess -> nvinfer (custom YOLOv8n) -> tracker -> ROI/line analytics -> sinks (display, RTSP, JSON, MQTT)`.
   - Draw the **road-zone ROI** over the lower part of the frame (the road).
   - Screenshot the node graph to `screenshots/02_pipeline_ir.png`. This is **required evidence**.
3. **Model.**
   - Run `./perception/export_onnx.sh` first. Output must be `[1, 9, 8400]`.
   - Register `export/wildguard_yolov8n_bra5.onnx` with `export/labels.txt`.
   - Start with confidence 0.35 and NMS IoU 0.45. The bridge applies the stricter alert threshold (0.50, per class if needed).
   - **Risk #1:** confirm PipeGen/DeepStream parses the YOLOv8 output layout. If not, ask a CraftifAI mentor straight away. Fallbacks are the catalog YOLOv8 route with these weights, or Deep Search.
4. **Compiler.**
   - Compile **FP16** first. Save the speed report to `reports/fp16_speed_report.*`. This is **required evidence**.
   - Edge Optimization bonus: also compile **FP32** and **INT8**. For INT8, use the calibration set:
     ```bash
     python perception/make_calibration_list.py --n 400 --copy /home/$USER/wildguard_calib
     ```
   - Copy the numbers from PipeGen's reports into `reports/pipeline_info.json`, using the template `reports/pipeline_info.example.json`. Only enter measured values. The dashboard's Analytics page charts FPS and mAP per precision from this file.
5. **Run.**
   - MQTT sink: broker `localhost:1883`, topic `wildguard/pipegen/raw`. Also enable JSON metadata and display/RTSP.
   - Check the real payload format before anything else:
     ```bash
     mosquitto_sub -h localhost -t 'wildguard/pipegen/#' -v      # raw
     python bridge/bridge.py --sniff                              # raw + how the bridge parses it
     ```
     The bridge understands DeepStream's full and minimal message schemas, generic `objects`/`detections` JSON, and JSON metadata files (`PIPEGEN_JSON_PATH`). If `--sniff` shows `[PARSED] []` for frames with animals, adapt `extract_objects()` in `bridge/bridge.py` to the captured sample and add the sample as a test in `backend/tests/test_bridge.py`.
   - Save one real payload to `reports/sample_pipegen_payload.json`.
   - Run for 15 minutes or more and note FPS and stability. Keep a video file under /home as a backup source.
   - Commit the PipeGen export folder (with `run.sh`) as `pipegen_export/`.

## Why there is a bridge

PipeGen publishes **per frame and per object**. The ESP32 should receive **one confirmed event per animal**, under 256 bytes. `bridge/bridge.py` turns the raw stream into contract-v1 events. It keeps the 5 target classes, applies per-class confidence thresholds, requires K consecutive frames per track (default 3), checks the road zone, applies a per-track cool-down, adds the ESP32's ARMED state as `sensor_confirmed`, and assigns `event_id`. It also publishes pipeline liveness and FPS for the dashboard. Every input and output is logged with timestamps in `bridge/logs/` for latency analysis.

## Optional: annotated stream in the dashboard

Re-serve PipeGen's RTSP output with [MediaMTX](https://github.com/bluenviron/mediamtx). Add a path `wildguard` whose source is PipeGen's RTSP URL, then start the dashboard with:

```bash
VITE_STREAM_URL=http://<laptop-ip>:8889/wildguard npm run dev
```

The Live Loop page embeds the WebRTC player. Without it, the page explains that boxes are on PipeGen's own display.

## Model baseline (PyTorch, before PipeGen)

From `training/runs/detect/train3/results.csv`. YOLOv8n, 10 epochs, CPU, 640 px, BRA dataset (1460 train / 182 val images):

| Metric | Value |
|---|---|
| Precision | 0.768 |
| Recall | 0.663 |
| mAP50 | 0.768 |
| mAP50-95 | 0.524 |

Compare FP32, FP16 and INT8 against this after compiling. **Known limitation:** this is a closed-set 5-class model with no person, dog or background class, so look-alikes can be labelled as a target species. Mitigations: K-frame confirmation, per-class thresholds, the road-zone ROI, sensor fusion on the ESP32, and an explicit negative test (person, dog, toy) in the demo test matrix. Retraining with background images is listed as future work.
