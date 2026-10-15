# Software-loop rehearsal (no hardware) - NOT hardware evidence

Recorded 2026-10-15 before the event, with `./scripts/start_all.sh --rehearsal`:

| Stand-in | Replaces | What is real |
|---|---|---|
| `tools/pipegen_replay.py` | PipeGen pipeline | The trained YOLOv8n (ONNX, CPU) on BRA test images, 10 FPS, DeepStream-style JSON |
| `tools/esp32_sim.py` | ESP32 firmware | Implements the PRD contract; sensor auto-trip every 25 s |
| — | — | Broker, bridge, backend, dashboard, database and all measurements are the real software |

## What it shows

| Check | Result |
|---|---|
| Events through the full software loop | 61 / 61 ACKed, 0 timeouts |
| Capture → ACK (software path only) | p50 16 ms · p95 29 ms · max 55 ms |
| Species coverage | all 5 species; all 5 severity levels reached; sensor-confirmed and camera-only both exercised |
| Contract acceptance suite vs simulator | 19 / 19 ([acceptance_results.md](acceptance_results.md)) |
| Dashboard | [screenshots/](screenshots/) - every page shows the REHEARSAL banner and SIM badges |

The latency excludes camera capture and GPU inference (the replay runs the model once per image) and the
Wi-Fi hop to a real board. The real figure comes from the event hardware.

Files: `evidence_pack_rehearsal.md` (dashboard Evidence pack export), `events_rehearsal.csv` (all events with
ACK state and latency), `acceptance_results.*`, `screenshots/`.
