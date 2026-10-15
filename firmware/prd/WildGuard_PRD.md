# PRD: WildGuard Roadside Warning Node (ESP32)

**Product:** WildGuard AI roadside unit, the "act" half of a closed perception-to-action loop
**Target:** ESP32 (ESP32-WROOM-32 DevKit V1 class), ESP-IDF v5.5, FreeRTOS
**Tooling:** CraftifAI FirmGen v0.4.1 (requirements, implementation, tests, traceability)
**PRD version:** 1.0 (freeze before implementation; changes go through FirmGen review)

---

## 1. Purpose

Wildlife-vehicle collisions kill large numbers of tapirs, giant anteaters, maned wolves and wild cats on Brazilian roads every year, and also injure drivers. A camera running a CraftifAI PipeGen vision pipeline (YOLOv8n on TensorRT) detects these five species near the road. This node receives those detections over MQTT and **warns drivers physically**, with a flashing roadside sign (LEDs) and an acoustic deterrent (buzzer). It also contributes its **own sensing** (ultrasonic distance + PIR motion) so that a camera detection confirmed by a local sensor gets a stronger response.

The node owns the decision of *how* to respond. It validates each event, applies the species response profile, fuses the result with its own sensor state, enforces safety limits, and reports back what it did (ACK) so the loop's latency is measured, not claimed.

## 2. System context

```
USB camera -> PipeGen/DeepStream (TensorRT) -> bridge -> MQTT broker (laptop, LAN) -> THIS NODE -> LEDs + buzzer
                                                              ^                         |
                                                              +---- sensor / status / ACK / telemetry
```

- Broker: Mosquitto on the laptop, port 1883, same Wi-Fi LAN (travel router or hotspot).
- The node must work **without** the dashboard/backend running. Only the broker is required.

## 3. Hardware

| Function | GPIO | Direction | Notes |
|---|---|---|---|
| HC-SR04 TRIG | 25 | out | 10 us pulse |
| HC-SR04 ECHO | 34 | in | Input-only pin. **5 V echo divided to 3.3 V** (1 kOhm / 2 kOhm) |
| PIR OUT (HC-SR501) | 27 | in | PIR powered at 5 V, output is 3.3 V |
| Status LED green | 16 | out | IDLE / connected |
| Status LED amber | 17 | out | ARMED / warning / DEGRADED |
| Warning LED red (via N-MOSFET, PWM) | 26 | out (LEDC) | High-intensity strobe |
| Buzzer | 33 | out (LEDC) | Active buzzer: on/off. Passive: tone via LEDC |
| Onboard LED | 2 | out | Boot / FAULT indicator (strapping pin: keep LOW at boot) |

Power: USB 5 V for the ESP32 and sensors. High-intensity LEDs on a separate supply with **common ground**. Avoid GPIO 6-11 (flash) and do not drive strapping pins 0, 2, 12, 15 high during boot.

## 4. Connectivity

- Wi-Fi station mode. SSID/password from **menuconfig (Kconfig) or NVS**, never hard-coded in committed source.
- MQTT 3.1.1 client (ESP-IDF `esp-mqtt`), broker URI from Kconfig/NVS (default `mqtt://192.168.1.10:1883`).
- Client ID: `esp32-01` (node ID, configurable).
- Keepalive 10 s. Last Will: topic `wildguard/node/esp32-01/status`, payload `{"state":"offline"}`, QoS 1, retained.

## 5. MQTT contract (v1)

| Topic | Direction | QoS | Retained | Payload |
|---|---|---|---|---|
| `wildguard/perception/detections` | in | 1 | no | Detection event (5.1) |
| `wildguard/control/mode` | in | 1 | **yes** | `armed` or `disarmed` (plain text) |
| `wildguard/control/cmd` | in | 1 | no | `{"cmd":"selftest"}`, `{"cmd":"sim_trip","duration_s":5}`, `{"cmd":"reboot"}` |
| `wildguard/node/esp32-01/sensor` | out | 0 | no | Sensor state (5.3) |
| `wildguard/node/esp32-01/status` | out | 1 | **yes** | `{"state":"online","fw":"1.0.0","rssi":-55,"uptime_s":12}` / LWT `{"state":"offline"}` |
| `wildguard/node/esp32-01/ack` | out | 1 | no | Acknowledgement (5.2) |
| `wildguard/node/esp32-01/telemetry` | out | 0 | no | Runtime telemetry (5.4) |

All payloads are UTF-8 JSON (except `mode`), at most 256 bytes.

### 5.1 Detection event (input)

```json
{"v":1,"event_id":"wg-1405-00123","ts_capture":1760000000123,"camera_id":"cam01",
 "class":"puma","class_id":3,"confidence":0.87,"track_id":12,
 "bbox":[0.31,0.22,0.28,0.40],"in_road_zone":true,"sensor_confirmed":true}
```

Required fields: `v` (int, must be 1), `event_id` (string, 1-32 chars), `class` (string), `class_id` (int), `confidence` (number 0..1). All other fields are optional. **Unknown fields must be ignored.** `sensor_confirmed` from the camera side is informational only. The node uses **its own ARMED state** for fusion.

Class IDs: 0 `tapir`, 1 `jaguarundi`, 2 `maned_wolf`, 3 `puma`, 4 `giant_anteater`. Anything else is "unknown".

### 5.2 ACK (output), exactly one per valid, non-duplicate event

```json
{"v":1,"event_id":"wg-1405-00123","state":"ALERT","profile":"puma","severity":"HIGH",
 "confirmed":true,"t_rx_ms":4210,"t_act_ms":4216}
```

- `state`: `ALERT` (new alert started), `EXTEND` (an active alert of equal or higher severity was extended), `IGNORED` (no actuation; then `reason` is `low_conf` or `disarmed`, and `profile`/`severity` are omitted).
- `t_rx_ms` / `t_act_ms`: node uptime (ms) when the message was received and when the actuator output was switched on.
- `confirmed`: whether the node was ARMED by its own sensors when the event was evaluated.

### 5.3 Sensor state (output)

```json
{"v":1,"distance_cm":23.4,"pir":false,"armed":false,"state":"IDLE","mode":"armed","threshold_cm":20}
```

### 5.4 Telemetry (output, every 2 s)

```json
{"v":1,"uptime_s":512,"heap_free":182000,"heap_min":171500,"state":"IDLE","rssi":-55,
 "rx":34,"actions":28,"ignored":2,"malformed":3,"dupes":1,"sensor_errors":0}
```

## 6. Species response profiles

| Class | Base severity | Red LED | Amber LED | Buzzer |
|---|---|---|---|---|
| tapir | CRITICAL | strobe 8 Hz | on | 3 long beeps (400 ms), repeating |
| giant_anteater | HIGH | strobe 4 Hz | off | 2 beeps (200 ms) |
| maned_wolf | HIGH | alternate with amber, 2 Hz | alternate | 2 short beeps (100 ms) |
| puma | MEDIUM | slow pulse 1 Hz (PWM fade) | off | 1 beep (200 ms) |
| jaguarundi | LOW | off | blink 1 Hz | silent |
| unknown class (`generic`) | WARN | off | solid | silent |

**Severity fusion:** severity levels are ordered WARN < LOW < MEDIUM < HIGH < CRITICAL. If the node is ARMED when the event is evaluated, the effective severity is **one level above** the base (capped at CRITICAL). If it is not ARMED, it is **one level below** (floored at WARN). Unknown classes are always WARN. The LED/buzzer *pattern* follows the species. The effective severity is reported in the ACK and scales the buzzer: at CRITICAL the buzzer repeats for the whole alert, at HIGH it plays its pattern twice, and at MEDIUM or below once.

## 7. State machine

States: `BOOT`, `IDLE`, `ARMED`, `ALERT`, `DEGRADED`, `DISARMED`, `TEST`, `FAULT`.

- `BOOT`: all outputs OFF, onboard LED on. After Wi-Fi and MQTT connect, go to `IDLE`.
- `IDLE`: green LED on. Sensor trip goes to `ARMED`. Valid event goes to `ALERT`.
- `ARMED`: amber LED on. Distance below threshold or PIR motion. Leaves after both are clear for the hold-off (default 3 s).
- `ALERT`: species profile running for the alert duration (default 5 s), extended by re-detections. Then returns to `ARMED` or `IDLE`.
- `DEGRADED`: MQTT or Wi-Fi lost. Amber blinks while the local sensor is tripped (sensor-only warning). Reconnect with backoff. Returns to `IDLE` when reconnected.
- `DISARMED`: mode is `disarmed`. Green LED blinks slowly. Events are ACKed as IGNORED.
- `TEST`: self-test cycles each species profile for 1 s, then returns.
- `FAULT`: unrecoverable error. Outputs OFF, onboard LED blinks, watchdog reboot.

## 8. Requirements

Each requirement has an ID and a measurable acceptance criterion. Automatic criteria are checked over MQTT by `tools/hil_acceptance.py`. Physical criteria are checked on video and on the UART log.

### Connectivity
| ID | Requirement | Acceptance criterion |
|---|---|---|
| WG-CON-01 | Join Wi-Fi in STA mode using credentials from Kconfig/NVS. Retry with exponential backoff (1 s to 30 s). | Connected within 10 s of boot. Reconnects after a router power-cycle without a reset. |
| WG-CON-02 | Connect to the MQTT broker with the Last Will in section 4. On every connect, publish retained `online` status with fw version, RSSI and uptime. | `mosquitto_sub` shows `online`. Pulling power shows `offline` within keepalive x 1.5. |
| WG-CON-03 | Subscribe to `detections`, `control/mode` and `control/cmd` on every (re)connect. | UART shows the subscription lines after each reconnect. |

### Sensing
| ID | Requirement | Acceptance criterion |
|---|---|---|
| WG-SEN-01 | Sample the HC-SR04 at 10 Hz or faster with a 3-sample median filter. Valid range 2-400 cm. Echo timeout 25 ms counts as a sensor error, not a crash. | Stable readings on UART. With the sensor unplugged, `sensor_errors` increases and the node stays up. |
| WG-SEN-02 | Read the PIR with at least 200 ms debounce. | One physical motion produces one PIR rising edge in the log. |
| WG-SEN-03 | Enter ARMED when filtered distance is below the threshold (default 20 cm, Kconfig) or PIR motion is present. Leave ARMED after both are clear for the hold-off (default 3 s). | Transitions visible on UART and on the sensor topic. |
| WG-SEN-04 | Publish sensor state (5.3) on every state change and at least every 1 s. | Dashboard shows live values. 3 or more messages in any 3.2 s window. |

### Event handling
| ID | Requirement | Acceptance criterion |
|---|---|---|
| WG-EVT-01 | Parse and validate each detection (5.1). Ignore unknown fields. Reject invalid JSON, missing fields, wrong types, `v` other than 1, or confidence outside 0..1, by logging and counting (`malformed`) without sending an ACK. | Malformed input is logged and counted. The next valid event is still ACKed. |
| WG-EVT-02 | Do not actuate for confidence below the threshold (default 0.50, Kconfig). ACK as `IGNORED` with reason `low_conf`. | A 0.20 event returns `IGNORED/low_conf` and no output changes. |
| WG-EVT-03 | Deduplicate by `event_id`, remembering the last 32 IDs. A duplicate produces no action and no second ACK. | Publishing the same event twice gives exactly one ACK. |
| WG-EVT-04 | Map `class` (or `class_id`) to the profile table in section 6. Unknown classes use profile `generic` at WARN. | Each of the 5 classes gives its own pattern and profile name in the ACK. An unknown class gives `generic/WARN`. |
| WG-EVT-05 | Compute effective severity with the fusion rule in section 6, using the node's own ARMED state at evaluation time. | Unarmed puma gives LOW. Armed puma (after `sim_trip`) gives HIGH with `confirmed:true`. |

### Actuation
| ID | Requirement | Acceptance criterion |
|---|---|---|
| WG-ACT-01 | Drive red/amber/green LEDs with the profile pattern from section 6, using a dedicated FreeRTOS task (non-blocking for the MQTT task). | Video shows each pattern. |
| WG-ACT-02 | Drive the buzzer with the profile pattern, scaled by severity as in section 6. | Audible and distinct per class. |
| WG-ACT-03 | Actuator output turns on within **100 ms** of MQTT message receipt. | `t_act_ms - t_rx_ms` at most 100 in every ACK. |
| WG-ACT-04 | Alert lasts a configurable duration (default 5 s). A new event while an alert of equal or higher severity is active extends it (ACK `EXTEND`). A higher-severity event replaces the active profile (ACK `ALERT`). | Second tapir event within 5 s returns `EXTEND`. The alert ends 5 s after the last event. |

### Acknowledgement
| ID | Requirement | Acceptance criterion |
|---|---|---|
| WG-ACK-01 | Publish exactly one ACK (5.2) per valid, non-duplicate event, after the actuator has started (or the decision to ignore was made). | Dashboard shows ACK latency for every event. No timeouts in a 30-event run. |

### Control and test
| ID | Requirement | Acceptance criterion |
|---|---|---|
| WG-SAF-05 | `control/mode = disarmed` suppresses all actuation (events ACKed `IGNORED/disarmed`). `armed` re-enables it. The retained value is applied after a reconnect. | The dashboard kill switch works and survives a node reset. |
| WG-TST-01 | `cmd: sim_trip` forces ARMED for `duration_s` (default 5 s). `cmd: selftest` runs the TEST state. `cmd: reboot` performs a clean restart. | Each command observed on UART and on the sensor topic. |

### Safety and robustness
| ID | Requirement | Acceptance criterion |
|---|---|---|
| WG-SAF-01 | All outputs OFF at boot, on reboot, and in FAULT. | Power-cycle during an alert: outputs OFF at boot. |
| WG-SAF-02 | The buzzer never sounds longer than 10 s continuously, whatever events arrive. | Repeated tapir events for 30 s: buzzer pauses at 10 s. |
| WG-SAF-03 | Task watchdog enabled for the sensing, actuation and MQTT tasks. A hang reboots the board. | Induced hang leads to watchdog reset, then outputs OFF and recovery. |
| WG-SAF-04 | On Wi-Fi or MQTT loss, enter DEGRADED: sensor-only amber warning, reconnect with backoff, resubscribe, republish status. | Stop the broker: DEGRADED within 5 s. Restart it: back to IDLE. |

### Logging
| ID | Requirement | Acceptance criterion |
|---|---|---|
| WG-LOG-01 | UART 115200 8N1, one structured line per event, prefixed `[WG]`. Example lines: `[WG] RX id=wg-1405-00123 class=puma conf=0.87`, `[WG] ACT start profile=puma sev=HIGH confirmed=1 dt=6ms`, `[WG] ACK sent id=wg-1405-00123 state=ALERT`, `[WG] STATE IDLE -> ARMED`. | Lines appear for every event. This is the acceptance evidence. |

### Telemetry
| ID | Requirement | Acceptance criterion |
|---|---|---|
| WG-TEL-01 | Publish telemetry (5.4) every 2 s: uptime, free heap, minimum free heap, state, RSSI and event counters. | Dashboard "Board internals" panel updates live. |
| WG-TEL-02 | *(Bonus)* Compatible with FirmGen Live Intelligence: Enable Telemetry must not break the requirements above. | Live Intelligence RTOS monitor shown during the demo with the loop running. |

### Non-functional
| ID | Requirement | Acceptance criterion |
|---|---|---|
| WG-NFR-01 | Boot to ready in 5 s or less, excluding Wi-Fi join time. | Measured from the UART timestamp. |
| WG-NFR-02 | Free heap never below 40 KB during a 30-minute soak with periodic events. | `heap_min` in telemetry stays above 40 KB. |
| WG-NFR-03 | No secrets (Wi-Fi password, MQTT credentials) in committed source. `sdkconfig` with secrets is git-ignored. | Code review of the FirmGen repository. |
| WG-NFR-04 | Configuration (thresholds, durations, broker URI, node ID) via Kconfig with the defaults in this PRD. | `idf.py menuconfig` shows a "WildGuard" menu. |

## 9. Out of scope (stretch, only after the set above is frozen and passing)

- WG-ACT-05: stepper "barrier" (STEP/DIR on GPIO 19/18) moved for CRITICAL/HIGH, returned afterwards.
- TLS to the broker, OTA updates, BLE provisioning.

## 10. Test hooks for FirmGen unit tests

Pure functions that FirmGen should implement and unit-test on the host or target:
- `wg_parse_event(json, &event)`: validation rules of WG-EVT-01.
- `wg_effective_severity(class, armed)`: fusion table of WG-EVT-05 (all 5 classes x 2 states + unknown).
- `wg_dedupe_seen(event_id)`: ring buffer of 32 IDs (WG-EVT-03).
- `wg_median3(a, b, c)` and the distance validity check (WG-SEN-01).
- `wg_profile_for(class)`: profile table of section 6 (WG-EVT-04).
