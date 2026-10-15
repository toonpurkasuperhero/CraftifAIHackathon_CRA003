# Model accuracy baseline - ONNX FP32 on the val split

_Generated 2026-10-15 19:51:26 by `tools/eval_model.py`. Offline reference on CPU, not the live system._

182 images, 200 labelled animals. Alert threshold = 0.5.

| Class | Instances | AP50 | AP50-95 | Precision @ alert | Recall @ alert |
|---|---|---|---|---|---|
| tapir | 41 | 0.689 | 0.486 | 0.875 | 0.512 |
| jaguarundi | 31 | 0.801 | 0.503 | 0.92 | 0.742 |
| maned_wolf | 42 | 0.725 | 0.52 | 0.929 | 0.619 |
| puma | 51 | 0.751 | 0.453 | 0.651 | 0.549 |
| giant_anteater | 35 | 0.753 | 0.555 | 0.875 | 0.6 |
| **all** | **200** | **0.744** | **0.503** | **0.826** | **0.595** |

CPU inference latency (ONNX Runtime, this laptop): p50 15.1 ms, p95 18.2 ms per image. TensorRT numbers come from PipeGen's report.

## Confusion at conf >= 0.5, IoU 0.5

| predicted \ actual | tapir | jaguarundi | maned_wolf | puma | giant_anteater | background |
|---|---|---|---|---|---|---|
| tapir | 21 | 0 | 1 | 1 | 0 | 1 |
| jaguarundi | 0 | 23 | 0 | 0 | 1 | 1 |
| maned_wolf | 0 | 0 | 26 | 0 | 0 | 2 |
| puma | 3 | 3 | 4 | 28 | 0 | 5 |
| giant_anteater | 1 | 0 | 0 | 0 | 21 | 2 |
| missed | 16 | 5 | 11 | 22 | 13 | 0 |

## Per-class threshold sweep (precision / recall at IoU 0.5)

Use this to set the bridge's per-class `CONF_<CLASS>` values.

| Class | conf 0.3 | conf 0.4 | conf 0.5 | conf 0.6 | conf 0.7 |
|---|---|---|---|---|---|
| tapir | 0.8 / 0.59 | 0.81 / 0.54 | 0.88 / 0.51 | 0.95 / 0.46 | 0.94 / 0.41 |
| jaguarundi | 0.8 / 0.77 | 0.92 / 0.74 | 0.92 / 0.74 | 0.92 / 0.71 | 0.91 / 0.65 |
| maned_wolf | 0.87 / 0.64 | 0.93 / 0.64 | 0.93 / 0.62 | 0.96 / 0.57 | 0.95 / 0.48 |
| puma | 0.56 / 0.76 | 0.62 / 0.65 | 0.65 / 0.55 | 0.78 / 0.55 | 0.84 / 0.51 |
| giant_anteater | 0.79 / 0.66 | 0.81 / 0.6 | 0.88 / 0.6 | 0.91 / 0.6 | 0.94 / 0.49 |
