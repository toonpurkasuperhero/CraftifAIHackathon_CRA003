# WildGuard AI - Closed-Loop Evidence Pack
_Generated 2026-10-15 20:09:30 from the live system._

> **REHEARSAL DATA - NOT HARDWARE EVIDENCE.** PipeGen replaced by tools/pipegen_replay.py (ONNX on CPU); ESP32 replaced by tools/esp32_sim.py. This pack demonstrates the software loop only. Regenerate it on the real PipeGen pipeline and ESP32.

## 1. Loop health at generation time
| Component | State | Detail |
|---|---|---|
| MQTT broker | connected | localhost:1883 |
| PipeGen pipeline | alive | msgs/s 10.0, FPS 10.0 |
| Bridge | online | events published 61 |
| ESP32 node `esp32-01` | online | fw sim-1.0.0, RSSI -52 dBm, uptime 352 s |
| Mode | armed | |

## 2. Measured latency (capture -> ESP32 actuator ON -> ACK)
| Set | Events | ACKed | Timeouts | p50 e2e | p95 e2e | max e2e | p50 on-board RX->ACT | max on-board |
|---|---|---|---|---|---|---|---|---|
| Real PipeGen events | 0 | 0 | 0 | n/a | n/a | n/a | n/a | n/a |
| All incl. test/replay | 61 | 61 | 0 | 16.0 ms | 29.0 ms | 55.0 ms | 0.0 ms | 1.0 ms |

PRD target WG-ACT-03: on-board receive -> actuate <= 100 ms.

## 3. Species coverage and response profiles
| Class | Events | Confirmed severity | Unconfirmed severity |
|---|---|---|---|
| tapir | 12 | CRITICAL | HIGH |
| jaguarundi | 14 | MEDIUM | WARN |
| maned_wolf | 13 | CRITICAL | MEDIUM |
| puma | 14 | HIGH | LOW |
| giant_anteater | 8 | CRITICAL | MEDIUM |

Severity distribution (from ESP32 ACKs): `{"CRITICAL": 5, "HIGH": 15, "LOW": 11, "MEDIUM": 19, "WARN": 11}`  
Sensor confirmation: `{"unconfirmed": 50, "confirmed": 11}`  
Sources: `{"replay": 61}`

## 4. Most recent events
| Time | Event | Class | Conf | Source | Confirmed | Severity | ACK | e2e ms | on-board ms |
|---|---|---|---|---|---|---|---|---|---|
| 2026-10-15 20:09:27 | wg-2003-00061 | jaguarundi | 0.89 | replay | False | WARN | ALERT | 7.0 | 0.0 |
| 2026-10-15 20:09:22 | wg-2003-00060 | jaguarundi | 0.80 | replay | False | WARN | ALERT | 9.0 | 0.0 |
| 2026-10-15 20:09:17 | wg-2003-00059 | puma | 0.84 | replay | False | LOW | ALERT | 4.0 | 0.0 |
| 2026-10-15 20:09:12 | wg-2003-00058 | giant_anteater | 0.68 | replay | False | MEDIUM | EXTEND | 16.0 | 0.0 |
| 2026-10-15 20:09:07 | wg-2003-00057 | maned_wolf | 0.54 | replay | True | CRITICAL | ALERT | 16.0 | 0.0 |
| 2026-10-15 20:09:02 | wg-2003-00056 | puma | 0.81 | replay | False | LOW | ALERT | 7.0 | 0.0 |
| 2026-10-15 20:08:57 | wg-2003-00055 | tapir | 0.79 | replay | False | HIGH | ALERT | 17.0 | 1.0 |
| 2026-10-15 20:08:52 | wg-2003-00054 | puma | 0.61 | replay | False | LOW | ALERT | 29.0 | 0.0 |
| 2026-10-15 20:08:52 | wg-2003-00053 | jaguarundi | 0.69 | replay | False | WARN | ALERT | 23.0 | 0.0 |
| 2026-10-15 20:08:47 | wg-2003-00052 | giant_anteater | 0.71 | replay | False | MEDIUM | ALERT | 6.0 | 0.0 |
| 2026-10-15 20:08:42 | wg-2003-00051 | puma | 0.75 | replay | True | HIGH | ALERT | 16.0 | 0.0 |
| 2026-10-15 20:08:37 | wg-2003-00050 | jaguarundi | 0.95 | replay | False | WARN | ALERT | 20.0 | 0.0 |
| 2026-10-15 20:08:27 | wg-2003-00049 | tapir | 0.65 | replay | False | HIGH | ALERT | 5.0 | 0.0 |
| 2026-10-15 20:08:22 | wg-2003-00048 | maned_wolf | 0.86 | replay | False | MEDIUM | ALERT | 16.0 | 0.0 |
| 2026-10-15 20:08:17 | wg-2003-00047 | jaguarundi | 0.72 | replay | True | MEDIUM | ALERT | 16.0 | 0.0 |

## 5. Hardware-in-the-loop acceptance results
_Not run yet. Run `python tools/hil_acceptance.py` against the real ESP32._

## 6. Pipeline report (from PipeGen)
_perception/reports/pipeline_info.json missing or invalid._
