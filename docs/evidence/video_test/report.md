# Video test - model + bridge on real wildlife footage

_Generated 2026-10-15 21:24:11 by `tools/video_test.py`. Detector: ONNX FP32 reference on CPU (same weights PipeGen compiles to TensorRT). Clips: `perception/test_videos/manifest.json` (Wikimedia Commons, see ATTRIBUTION.md)._

Detectors: our 5-species model + the stock COCO YOLOv8n as look-alike veto (person/cat/dog), exactly the two models the PipeGen pipeline runs. "Without veto" shows the same bridge with the veto off.

| Clip | Expected | Duration | Frames with expected species ≥ alert conf | Alerts without veto | Alerts with veto | First correct alert | Verdict (with veto) |
|---|---|---|---|---|---|---|---|
| tapir_trailcam | tapir | 10.0 s | 100% | tapir ×2 | tapir ×2 | 0.53 s | **PASS** |
| anteater_trailcam | giant_anteater | 10.0 s | 63% | giant_anteater ×2 | giant_anteater ×2 | 0.53 s | **PASS** |
| jaguarundi_trailcam | jaguarundi | 15.0 s | 20% | jaguarundi ×1 | jaguarundi ×1 | 0.53 s | **PASS** |
| puma_atlantic | puma | 10.0 s | 49% | puma ×1 | puma ×1 | 1.9 s | **PASS** |
| maned_wolf_zoo | maned_wolf | 11.5 s | 10% | maned_wolf ×2, puma ×2 | maned_wolf ×2, puma ×2 | 1.73 s | **PASS, with wrong-class alerts** |
| negative_cat | none | 9.0 s | — | maned_wolf ×2 | none | — | **PASS (no alert)** |
| negative_dog | none | 47.3 s | — | maned_wolf ×4 | none | — | **PASS (no alert)** |

Annotated frame per clip (first alert, or middle frame if none): `frames/`.

