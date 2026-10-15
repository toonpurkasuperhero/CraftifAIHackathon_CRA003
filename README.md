# WildGuard AI: roadside wildlife-collision warning, a closed Physical AI loop

**Embedded SF: CraftifAI Physical AI Hackathon** · Open Innovation track · **Closed Loop** bonus (stretch: Edge Optimization, Live Intelligence)

A camera running a **CraftifAI PipeGen** pipeline (custom YOLOv8n on TensorRT/DeepStream) spots one of five road-vulnerable Brazilian species near the road. An **ESP32 running FirmGen-generated firmware** fuses that event with its own ultrasonic and PIR sensors, decides how hard to respond, flashes a roadside warning sign and sounds a deterrent within 100 ms, then reports back what it did. The dashboard shows every alert with its **measured** end-to-end latency.

```
USB camera → PipeGen (YOLOv8n · TensorRT · tracker · road-zone ROI) → MQTT → bridge (confirm · dedupe · cool-down)
          → MQTT → ESP32 / FirmGen (sensor fusion · species profile · LEDs + buzzer) → ACK → mission-control dashboard
```

Details: [docs/project-description.md](docs/project-description.md) (submission text) · [docs/event-day-runbook.md](docs/event-day-runbook.md) · [docs/architecture.md](docs/architecture.md) · [docs/mqtt-contract.md](docs/mqtt-contract.md) · [firmware/prd/WildGuard_PRD.md](firmware/prd/WildGuard_PRD.md)

## Why it matters

Collisions with wildlife on Brazilian highways kill large numbers of tapirs and giant anteaters (both IUCN Vulnerable) and maned wolves (Near Threatened), and also injure drivers. Warning signs are static and get ignored. WildGuard turns the sign on **only when an animal is actually at the road**, so drivers learn to trust it.

Species: tapir, jaguarundi, maned wolf, puma, giant anteater ([BRA dataset](training/archive/README.md): Ferrante et al., SIBGRAPI 2022, DOI 10.1109/SIBGRAPI55357.2022.9991774).

## How each CraftifAI tool is load-bearing

| Tool | What it owns | Evidence |
|---|---|---|
| **PipeGen** | All perception: the five stages from Requirement to Run, TensorRT engine, tracker, ROI, MQTT/JSON/RTSP output. There is no other inference path in the live system. | Pipeline IR graph, TensorRT speed report, live run, sample payload in [perception/](perception/README.md) |
| **FirmGen** | All action: the PRD with 30 requirements is frozen, then FirmGen generates ESP-IDF v5.5 firmware for validation, sensor fusion, species profiles, actuation, ACK, fail-safe and telemetry. | Frozen requirements, traceability report, UART log, HIL results in [firmware/](firmware/README.md) |
| **Closed loop** | A PipeGen detection triggers a physical action on the board in real time. The ACK closes the loop back. | Live Loop page, evidence pack, demo clip |

## Repository layout

| Folder | Contents | When |
|---|---|---|
| [perception/](perception/README.md) | PipeGen export, labels, ONNX export, INT8 calibration list, reports, screenshots | Inputs prepared before the event. Pipeline and engines built **at the event** |
| [firmware/](firmware/README.md) | FirmGen PRD, frozen requirements, traceability report, UART evidence (code lives in the FirmGen Git repo) | PRD prepared before. Freeze, firmware and evidence **at the event** |
| [bridge/](bridge/bridge.py) | PipeGen output → contract-v1 events (K-frames, cool-down, road zone, sensor flag) | Prepared before the event |
| [backend/](backend/main.py) | FastAPI MQTT observer: SQLite, WebSocket, control/test endpoints, latency metrics, evidence pack | Prepared before the event (rewrite) |
| [frontend/](frontend/README.md) | React mission-control dashboard | Prepared before the event (rework of an earlier UI) |
| [shared/](shared/wg_contract.py) | MQTT contract v1 for all Python components | Prepared before the event |
| [tools/](tools/) | `hil_acceptance.py` (19 PRD-traced checks on the real board), `eval_model.py` (accuracy baseline), rehearsal stand-ins `pipegen_replay.py` and `esp32_sim.py` | Prepared before the event |
| [broker/](broker/mosquitto.conf), [scripts/](scripts/) | Mosquitto config, `start_all.sh`, `stop_all.sh`, `check_env.sh`, `publish_test_alert.sh` | Prepared before the event |
| [docs/](docs/) | Project description, event-day runbook, architecture, contract, hardware, demo script, evidence (model + rehearsal) | Prepared before; hardware evidence **at the event** |
| [training/](training/) | YOLOv8n training notebook, dataset config, runs, offline ONNX reference | **Pre-existing** |
| [legacy/](legacy/README.md) | Old Arduino sketch, serial CSV, old plan | **Pre-existing**, not used |

## Quick start

Prerequisites: x86-64 Linux with an NVIDIA GPU (or a Jetson on JetPack 6) in an X11 session, PipeGen v0.5.1, FirmGen v0.4.1 with ESP-IDF v5.5, Mosquitto, Python 3.10+ and Node 20+.

```bash
sudo apt install mosquitto mosquitto-clients
pip install -r backend/requirements.txt -r bridge/requirements.txt
(cd frontend && npm install)
cp backend/.env.example backend/.env && cp bridge/.env.example bridge/.env

./scripts/check_env.sh          # pre-flight: pipegen 0.5.1, GPU, camera, broker, ESP32 online
./scripts/start_all.sh          # broker → PipeGen run.sh → bridge → backend → dashboard
open http://localhost:5173
```

Then:
1. **Perception:** follow [perception/README.md](perception/README.md). Export ONNX, run the five PipeGen stages, and set the MQTT sink to `wildguard/pipegen/raw`.
2. **Action:** follow [firmware/README.md](firmware/README.md). Upload the PRD to FirmGen, review and freeze, generate, flash.
3. **Acceptance:** run `python tools/hil_acceptance.py --target esp32` with the board online.
4. **Without hardware** (rehearsal only): `./scripts/start_all.sh --rehearsal` (needs `pip install -r tools/requirements.txt`).
   A replay of the trained model on BRA test images stands in for PipeGen and a contract simulator stands in for the ESP32.
   The dashboard then shows a yellow REHEARSAL banner and SIM badges, and stores those events as `replay`, never as PipeGen evidence.

Tests (no broker needed):

```bash
cd backend && python -m pytest -q
```

## Species → response (decided on the ESP32)

| Species | IUCN | Camera only | Camera + board sensor | Sign / buzzer |
|---|---|---|---|---|
| Tapir | Vulnerable | HIGH | CRITICAL | Fast red strobe + amber / 3 long beeps |
| Giant anteater | Vulnerable | MEDIUM | CRITICAL | Red strobe 4 Hz / 2 beeps |
| Maned wolf | Near Threatened | MEDIUM | CRITICAL | Red/amber alternate / 2 short beeps |
| Puma | Least Concern | LOW | HIGH | Slow red pulse / 1 beep |
| Jaguarundi | Least Concern | WARN | MEDIUM | Amber blink / silent |

## Results

Fill these from measurements only (see [docs/evidence/README.md](docs/evidence/README.md)).

| Metric | Value |
|---|---|
| YOLOv8n (Ultralytics val, 10 epochs) mAP50 / mAP50-95 | 0.768 / 0.524 |
| ONNX FP32 baseline on val (`tools/eval_model.py`) mAP50 / mAP50-95 · precision / recall @ 0.5 | 0.744 / 0.503 · 0.826 / 0.595 ([per class](docs/evidence/model/onnx_fp32_val_metrics.md)) |
| TensorRT engine and FPS (PipeGen report) | _TBD_ |
| FP32 / FP16 / INT8 FPS and mAP | _TBD_ |
| Capture → ACK latency p50 / p95 | _TBD_ |
| On-board receive → actuate (max) | _TBD_ (target 100 ms or less) |
| HIL acceptance on the real ESP32 | _TBD_ / 19 |

## Limitations and future work

- **Closed-set model:** 5 classes, no person, dog or background class, so look-alikes can be misclassified. Mitigated by K-frame confirmation, per-class thresholds, the road-zone ROI, on-board sensor fusion and a negative test. Next step: retrain with background images.
- **Bench-scale sensing:** the HC-SR04 (about 4 m range) stands in for radar, LiDAR or a PIR array on a real road.
- **Deployment:** solar power, LoRa for roads without Wi-Fi, multi-camera coverage, TLS and authentication on the broker.
