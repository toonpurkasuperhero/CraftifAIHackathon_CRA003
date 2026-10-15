# MQTT contract v1

This is the bridge between PipeGen and FirmGen. The same contract appears in three places, and they must agree:

- `firmware/prd/WildGuard_PRD.md` section 5. The ESP32 firmware is generated from it.
- `shared/wg_contract.py`. Used by the bridge, backend, simulator and acceptance tests.
- This document, for humans.

Broker: Mosquitto on the laptop, `mqtt://<laptop-ip>:1883`, LAN only.

## Topics

| Topic | Producer to consumer | QoS | Retained | Purpose |
|---|---|---|---|---|
| `wildguard/pipegen/raw` | PipeGen MQTT sink to bridge | 0 | no | Raw per-frame / per-object DeepStream messages |
| `wildguard/perception/detections` | bridge (or test tools) to ESP32 and backend | 1 | no | Confirmed animal events |
| `wildguard/node/esp32-01/sensor` | ESP32 to bridge and backend | 0 | no | Distance, PIR, ARMED, state. On change and at least 1 Hz |
| `wildguard/node/esp32-01/status` | ESP32 to backend | 1 | **yes** | `online` with fw/RSSI/uptime. Last Will is `offline` |
| `wildguard/node/esp32-01/ack` | ESP32 to backend | 1 | no | What the node did for each `event_id` |
| `wildguard/node/esp32-01/telemetry` | ESP32 to backend | 0 | no | Heap, uptime, counters, every 2 s |
| `wildguard/control/mode` | dashboard to ESP32 | 1 | **yes** | `armed` or `disarmed` |
| `wildguard/control/cmd` | dashboard to ESP32 | 1 | no | `selftest`, `sim_trip`, `reboot` |
| `wildguard/bridge/status` | bridge to backend | 1/0 | online/offline retained, stats not | Bridge liveness, PipeGen message rate, FPS, drop counters |

**Change from the original plan:** "test" is a one-shot command, not a retained mode. A retained `test` mode would re-run the self-test after every ESP32 reboot.

## Detection event (bridge to ESP32), 256 bytes or less

```json
{"v":1,"event_id":"wg-1405-00123","ts_capture":1760000000123,"camera_id":"cam01",
 "class":"puma","class_id":3,"confidence":0.87,"track_id":12,
 "bbox":[0.31,0.22,0.28,0.40],"in_road_zone":true,"sensor_confirmed":true}
```

- Required: `v`, `event_id`, `class`, `class_id`, `confidence`. Consumers ignore unknown fields.
- `ts_capture` is laptop epoch ms (the DeepStream frame timestamp when available). End-to-end latency is computed on the laptop as ACK arrival minus `ts_capture`, so the ESP32 needs no clock sync.
- `bbox` is normalised `[x, y, w, h]`. The bridge drops it if the payload would exceed 256 bytes.
- Test tools add `"synthetic": true`. The backend stores those separately from real PipeGen events.

## ACK (ESP32 to backend), exactly one per valid, non-duplicate event

```json
{"v":1,"event_id":"wg-1405-00123","state":"ALERT","profile":"puma","severity":"HIGH",
 "confirmed":true,"t_rx_ms":4210,"t_act_ms":4216}
```

| `state` | Meaning |
|---|---|
| `ALERT` | New alert started |
| `EXTEND` | Active alert of equal or higher severity extended |
| `IGNORED` | No actuation. `reason` is `low_conf` or `disarmed` |

`t_act_ms - t_rx_ms` is the on-board receive-to-actuate time. The PRD target is 100 ms or less.

## Severity and sensor fusion

| Class | Base | ESP32 ARMED (confirmed) | Not armed |
|---|---|---|---|
| tapir | CRITICAL | CRITICAL | HIGH |
| giant_anteater | HIGH | CRITICAL | MEDIUM |
| maned_wolf | HIGH | CRITICAL | MEDIUM |
| puma | MEDIUM | HIGH | LOW |
| jaguarundi | LOW | MEDIUM | WARN |
| unknown | WARN | WARN | WARN |

The ESP32 decides `confirmed` from **its own** sensor state, so the fusion logic lives in the FirmGen firmware. The bridge's `sensor_confirmed` field is informational only.

## Reliability rules and where they live

| Rule | Where |
|---|---|
| Keep 5 target classes, per-class confidence threshold | bridge (and ESP32 re-checks the threshold) |
| K consecutive frames per track (default 3) | bridge |
| Road-zone check (bottom-centre of box in ROI) | PipeGen ROI analytics if available, else bridge |
| Cool-down per track (default 5 s) | bridge |
| Dedupe by `event_id` (last 32) | ESP32 |
| Alert extension, max buzzer 10 s | ESP32 |
| DEGRADED fail-safe on Wi-Fi/MQTT loss | ESP32 |
| Last Will offline, dashboard "node offline" banner | ESP32 and backend |
| ACK timeout (3 s) marked in history | backend |

## Quick manual test

```bash
mosquitto_sub -h localhost -t 'wildguard/#' -v &
./scripts/publish_test_alert.sh tapir 0.9
```
