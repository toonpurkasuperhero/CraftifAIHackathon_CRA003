# Video test - model + bridge on real wildlife footage

_Generated 2026-10-15 22:51:46 by `tools/video_test.py`. Detector: PipeGen TensorRT pipeline (JSON metadata). Clips: `perception/test_videos/manifest.json` (Wikimedia Commons, see ATTRIBUTION.md)._

Detectors: our 5-species model + the stock COCO YOLOv8n as look-alike veto (person/cat/dog), exactly the two models the PipeGen pipeline runs. "Without veto" shows the same bridge with the veto off.

| Clip | Expected | Duration | Frames with expected species ≥ alert conf | Alerts without veto | Alerts with veto | First correct alert | Verdict (with veto) |
|---|---|---|---|---|---|---|---|
| tapir_trailcam | tapir | 10.0 s | — | — | tapir ×2 | 0.63 s | **PASS** |
| anteater_trailcam | giant_anteater | 10.0 s | — | — | giant_anteater ×2 | 0.63 s | **PASS** |
| jaguarundi_trailcam | jaguarundi | 15.0 s | — | — | jaguarundi ×1 | 0.63 s | **PASS** |
| puma_atlantic | puma | 10.0 s | — | — | puma ×1 | 0.63 s | **PASS** |
| maned_wolf_zoo | maned_wolf | 11.5 s | — | — | none | — | **MISSED** |
| negative_cat | none | 9.0 s | — | — | maned_wolf ×2 | — | **FALSE ALARM x2** |
| negative_dog | none | 47.3 s | — | — | maned_wolf ×1 | — | **FALSE ALARM x1** |

Annotated frame per clip (first alert, or middle frame if none): `frames/`.

