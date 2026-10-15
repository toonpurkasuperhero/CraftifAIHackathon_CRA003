# WildGuard AI — Closed-Loop Conversion Plan

**Hackathon:** Embedded SF — CraftifAI Physical AI Hackathon
**Track:** Open Innovation (Track 12) + **Closed Loop bonus** (stretch: Edge Optimization, Live Intelligence)
**Goal:** Turn WildGuard AI from "a web app that runs YOLO on a laptop" into "a Physical AI system that sees (PipeGen), decides, and acts (FirmGen) on real hardware, in real time."

**Priority legend:** `P0` = must have to qualify · `P1` = should have to win · `P2` = stretch / polish

---

## 0. TL;DR

1. **Perception moves to PipeGen.** `best.onnx` goes through all five PipeGen stages → TensorRT engine → DeepStream app on an NVIDIA GPU/Jetson, with MQTT + JSON output. The ONNX Runtime/CPU inference path is removed from the live system.
2. **Action moves to FirmGen.** A PRD is written, reviewed and **frozen**; FirmGen generates ESP-IDF v5.5 firmware for the ESP32 which senses (HC-SR04, PIR), subscribes to detection events over MQTT, runs a state machine, drives LEDs/buzzer (stepper = stretch), and **publishes an ACK** back.
3. **The loop closes in both directions.** Sensor → PipeGen → MQTT → ESP32 → physical action → ACK → dashboard (with measured end-to-end latency).
4. **The existing React/FastAPI app becomes the mission-control dashboard**, fed by MQTT instead of by its own inference endpoint and CSV file polling.
5. **Evidence is a deliverable, not an afterthought** (Pipeline IR graph, TensorRT speed report, traceability report, UART output, latency numbers).

---

## 1. Gap Analysis: Problem Statement vs. Current Project

| # | Problem-statement requirement | Current WildGuard state | Gap | Priority |
|---|---|---|---|---|
| 1 | Full PipeGen flow (Requirement → Pipeline IR → Model → Compiler → Run) | Custom Python + ONNX Runtime (CPU) | Entire perception layer must be rebuilt in PipeGen | P0 |
| 2 | TensorRT engine + PipeGen speed report | None (CPU ONNX) | Compile engine, capture report | P0 |
| 3 | Live run on camera/video/RTSP on NVIDIA GPU/Jetson | Windows laptop, `D:/` paths, CPU | Linux + NVIDIA GPU (or Jetson JetPack 6), X11 session | P0 |
| 4 | Actionable output (JSON/MQTT/RTSP/alerts) | REST API returns JSON to own frontend | MQTT/JSON feed out of PipeGen | P0 |
| 5 | PRD-driven firmware, reviewed + frozen requirements | Hand-written Arduino sketch (steppers only) | Write PRD, run FirmGen workflow | P0 |
| 6 | Firmware on real ESP32 | Sketch exists; sensor firmware is **not in the repo** | FirmGen-generated ESP-IDF firmware flashed to board | P0 |
| 7 | Acceptance evidence (UART/Monitor + physical behaviour) | None | Define acceptance criteria, capture logs/video | P0 |
| 8 | FirmGen traceability report | None | Generate and export | P0 |
| 9 | Closed Loop: perception event triggers physical action in real time | Sensor triggers camera (reverse direction), CSV file polling | Detection → MQTT → ESP32 → action → ACK | P0 |
| 10 | "Deep integration — load-bearing, not bolted on" | Hardware is a side feature | Re-architect so removing either tool breaks the product | P0 |
| 11 | Source repo with PipeGen export folder + FirmGen Git project | Single repo, no exports | Restructure repo | P0 |
| 12 | Project description, evidence, optional pitch | README only | Write submission text, screenshots, demo video | P0 |
| 13 | Edge Optimization bonus (INT8 / Jetson + trade-off report) | None | INT8 build + FP32/FP16/INT8 comparison | P2 |
| 14 | Live Intelligence bonus (telemetry from board) | None | Enable FirmGen telemetry, show during demo | P2 |

---

## 2. Review Findings — Corrections & Additions to the Original Change List

Your list is directionally right. These are the places where I'd change it or where it was incomplete.

### 2.1 Don't use the sensor to *start/stop* PipeGen — use it to *arm/confirm*
The original idea ("sensor wakes the camera") was fine for a Python webcam loop. With PipeGen/DeepStream, starting a pipeline means loading a TensorRT engine and initializing GStreamer — several seconds. That kills the "real-time" story.
**Change:** keep the PipeGen pipeline **running continuously**. The ESP32 sensors become a **second, independent signal** (sensor fusion): the ESP32 goes `ARMED` when a sensor trips, and a detection that arrives while `ARMED` is treated as *confirmed* (higher severity, full response). A detection without sensor confirmation can still trigger a lower-severity warning. This is also a better story for judges: two modalities agreeing → fewer false alarms.

### 2.2 The loop must be *measured*, not just claimed
Add an **ACK message** from the ESP32 back to the dashboard once the actuator has started. This lets you display `capture → alert → ESP32 RX → actuator ON → ACK` latency live. "Seamless, instant" becomes a number on screen.

### 2.3 The ESP32 must be more than a dumb LED relay
Judges penalise "bolted on". The ESP32 should own **real logic**: sensor reading + filtering, a state machine, per-species response profiles, debouncing/cool-down, fail-safe behaviour when Wi-Fi/MQTT drops, and status reporting (MQTT Last Will). That also gives FirmGen plenty of meaningful requirements to trace.

### 2.4 Your model is a closed-set classifier — expect false positives
YOLOv8n trained on 5 animal classes has no "person/dog/background" class. A person or a house cat may be labelled `puma` with high confidence. Mitigations (all in the plan): per-class confidence thresholds, N-consecutive-frame confirmation, track IDs, road-zone ROI, sensor confirmation, optional background/negative images in retraining, and an explicit negative-test in the test matrix.

### 2.5 Don't keep a parallel ONNX/CPU inference path in the live product
If the dashboard can still run detections via `/api/detect/image` and `/api/detect/frame` with ONNX Runtime, judges can argue PipeGen is optional. Remove those paths from the live system (keep an offline reference script under `training/` only for accuracy comparison).

### 2.6 Hardware realities missing from the original list
- **HC-SR04 ECHO is 5 V** — the ESP32 GPIO is 3.3 V. Use a voltage divider/level shifter.
- **Stepper drivers and high-power LEDs need their own supply** (not USB) with **common ground**; drive LEDs via a MOSFET/transistor.
- **Venue Wi-Fi often has client isolation** — bring a travel router or use a phone hotspot so the laptop, broker and ESP32 share a LAN.
- **TensorRT engines are not portable** between GPUs/TensorRT versions — compile on the machine you will demo on.
- PipeGen needs **x86-64 Linux + NVIDIA GPU or Jetson (JetPack 6), X11 desktop, videos under `/home`**. The project is currently Windows-pathed (`D:/…`).

### 2.7 Firmware stack mismatch
FirmGen targets **ESP-IDF v5.5** for ESP32. The existing sketch is **Arduino** (Wi-Fi web server + steppers). It can't be "ported" — the PRD must restate everything and FirmGen regenerates it. Also, the README's sensor description (CSV log from ESP32) has **no matching firmware in the repo** — that gap must be closed in the new firmware.

### 2.8 Wording & honesty fixes
- README says "5 **endangered** species". Only some are IUCN *Vulnerable/Near Threatened*; puma and jaguarundi are *Least Concern*. Use **"5 road-vulnerable Brazilian species"** or similar to avoid an easy credibility hit.
- Be explicit about **what is pre-existing** (training notebook, dashboard UI) vs **built at the hackathon** (PipeGen pipeline, FirmGen firmware, MQTT contract, bridge, integration). Keep git history clean and make the split obvious in the README.
- Real-world framing: the roadside unit primarily **warns drivers** (flashing signage) and secondarily **deters animals** (acoustic). Pitch both.
- Be honest that a 20 cm HC-SR04 range is a **bench-scale proxy** for a long-range roadside sensor (radar/LiDAR/PIR array) in a real deployment.

### 2.9 Two tracks are judged separately
Tracks A and B have **separate submission forms**. Plan to submit the same project to **both** (confirm with a mentor), each with its own evidence set and description emphasising that track's tool.

---

## 3. Target Architecture

```
                         ┌───────────────────────────── LAPTOP / JETSON (NVIDIA GPU) ─────────────────────────────┐
                         │                                                                                        │
  USB camera ───────────►│  PipeGen / DeepStream app (TensorRT FP16/INT8, YOLOv8n 5-class)                        │
  (or video file/RTSP)   │   source → preprocess → infer → tracker → ROI/line analytics → MQTT + JSON + RTSP sinks │
                         │                                   │                                                    │
                         │                       (PipeGen native MQTT/JSON)                                       │
                         │                                   ▼                                                    │
                         │                     ┌── bridge (thin Python, optional) ──┐                             │
                         │                     │ filter classes · debounce · fuse   │                             │
                         │                     │ with sensor state · normalise JSON │                             │
                         │                     └──────────────────┬─────────────────┘                             │
                         │                                        ▼                                               │
                         │                      Mosquitto MQTT broker (:1883, LAN only)                           │
                         │                          ▲        │            ▲                                      │
                         │         FastAPI backend ─┘        │            └─ React dashboard (WebSocket/SSE)     │
                         │         (MQTT subscriber, SQLite, REST, WS)                                            │
                         └────────────────────────────────────┬───────────────────────────────────────────────────┘
                                                              │ Wi-Fi (router / hotspot)
                                                              ▼
                              ┌──────────────── ESP32 (FirmGen-generated, ESP-IDF v5.5) ────────────────┐
                              │ HC-SR04 + PIR → filter → ARMED state ──► publishes sensor/status         │
                              │ MQTT RX (detections) → validate → species profile → state machine        │
                              │ ACTIONS: warning LEDs · buzzer · (stretch) stepper barrier/camera pan    │
                              │ ACK → broker  ·  LWT/heartbeat  ·  UART log  ·  (bonus) telemetry        │
                              └──────────────────────────────────────────────────────────────────────────┘
```

### Design decisions (lock these early)
| Decision | Choice | Why |
|---|---|---|
| Transport | **MQTT over Wi-Fi** (QoS 1) | Named explicitly in the problem statement; decouples components; PipeGen supports it natively |
| Broker | Mosquitto on the laptop | Zero cloud dependency; works offline at the venue |
| Who consumes PipeGen's payload? | ESP32 **directly** if PipeGen's native payload is simple; otherwise a **thin bridge** normalises it | Decide after inspecting the real PipeGen output (see §5.7). Keep the bridge < ~150 lines |
| Pipeline lifecycle | Always running | Avoid engine-load latency |
| Sensor role | Arming / confirmation | See §2.1 |
| Single vs two ESP32s | **One ESP32** for sensing + actuation (second as spare) | Fewer moving parts, tighter story |
| Dashboard feed | MQTT → backend → WebSocket | Replaces CSV polling and REST inference |

---

## 4. Hardware Plan

### 4.1 Bill of materials (and spares)
- [ ] NVIDIA GPU laptop/desktop (x86-64 Linux) **or** Jetson on JetPack 6 `P0` — confirm which you have (see §18)
- [ ] USB camera (+ tripod/stand, fixed position) `P0`
- [ ] ESP32 dev board (+ **a spare**) `P0` — ESP32 required (Wi-Fi); STM32 kit boards lack BLE and aren't needed here
- [ ] HC-SR04 ultrasonic sensor `P0`
- [ ] PIR sensor (HC-SR501 or similar) `P0`
- [ ] Warning LEDs: red / amber / green (+ resistors) and **one high-intensity LED or LED strip via MOSFET** `P0`
- [ ] Buzzer (active for simple beeps, or passive for tone patterns) `P0`
- [ ] Voltage divider (e.g., 1 kΩ / 2 kΩ) or level shifter for HC-SR04 ECHO `P0`
- [ ] Stepper motor + driver (A4988/DRV8825) + external 9–12 V supply `P2`
- [ ] Wi-Fi router or phone hotspot (shared LAN with the laptop) `P0`
- [ ] Breadboard, jumper wires, USB cables (data-capable), power strip, spare power bank `P0`
- [ ] Printed animal cards / tablet with test images + backup MP4 clips `P0`
- [ ] Small road-scene mock-up (cardboard road, toy car, roadside "sign" with LEDs) `P1` — makes the demo legible to judges

### 4.2 Proposed pin map (state it as a PRD requirement; verify against your exact board)
| Function | GPIO | Notes |
|---|---|---|
| HC-SR04 TRIG | 25 | 3.3 V output is fine |
| HC-SR04 ECHO | 34 | **Input-only pin; use 5 V → 3.3 V divider** |
| PIR OUT | 27 | PIR powered from 5 V, output is typically 3.3 V |
| Status LED – green | 16 | Idle / connected |
| Status LED – amber | 17 | Armed / warning |
| Warning LED – red (via MOSFET, PWM) | 26 | High-intensity strobe |
| Buzzer | 33 | Active: GPIO on/off · Passive: LEDC PWM |
| Onboard LED | 2 | Boot/FAULT indicator |
| Stepper STEP / DIR (stretch) | 19 / 18 | Reuse existing wiring |
| Stepper 2 STEP / DIR (stretch) | 21 / 22 | Optional |

Avoid GPIO 6–11 (flash), and be careful with strapping pins (0, 2, 12, 15) on boot.

### 4.3 Electrical safety checklist
- [ ] ECHO line divided to ≤ 3.3 V
- [ ] Motors/high-power LEDs on a **separate supply**, **common GND** with ESP32
- [ ] Flyback/protection where relevant; MOSFET gate resistor
- [ ] All actuators default **OFF** at boot (also a PRD requirement)
- [ ] Wiring photographed and a schematic saved to `docs/hardware/`

---

## 5. Workstream A — PipeGen (Perception)  `P0`

### 5.1 Environment
- [ ] Linux x86-64 with NVIDIA GPU **or** Jetson (JetPack 6); X11 desktop session
- [ ] Sign up at the CraftifAI developer portal and **sign in** before the event
- [ ] Install **PipeGen v0.5.1**; verify `pipegen --version` → `0.5.1`
- [ ] Keep all videos/test clips under `/home`
- [ ] Install and test Mosquitto: `sudo apt install mosquitto mosquitto-clients`
- [ ] Do a dry run of the PipeGen lab doc end-to-end with a catalog model before touching your own

### 5.2 Prepare the model
- [ ] Keep `best.pt` (not just `best.onnx`) from `runs/detect/train3/weights/`
- [ ] Re-export cleanly (confirm settings with the PipeGen lab doc): `yolo export model=best.pt format=onnx imgsz=640 opset=12 simplify=True dynamic=False`
- [ ] Create `labels.txt` in class-ID order: `tapir, jaguarundi, maned_wolf, puma, giant_anteater`
- [ ] **Verify PipeGen can import a custom YOLOv8 ONNX** and that DeepStream parses the YOLOv8 output layout (`[1, 9, 8400]` for 5 classes). **Do this first** — it's the #1 technical risk. If not supported, ask a CraftifAI mentor immediately; fallbacks: a catalog YOLOv8 + fine-tuned weights through the supported route, or Deep Search.
- [ ] Record model accuracy from the notebook (mAP50, mAP50-95, per-class P/R, confusion matrix) — you'll compare against FP16/INT8 later

### 5.3 Stage 1 — Requirement
- [ ] Write the requirement sentence, e.g.:
  > *"Detect tapir, jaguarundi, maned wolf, puma and giant anteater in a live USB camera stream using my custom YOLOv8n model. Track each animal, flag when it is inside the road zone, publish a JSON event over MQTT for each confirmed animal, and output an annotated RTSP stream and JSON metadata."*
- [ ] Screenshot the Requirement stage

### 5.4 Stage 2 — Pipeline IR
- [ ] Node graph: **source (USB cam / file / RTSP) → preprocess → detector (custom YOLOv8n) → tracker → analytics (ROI zone and/or line-crossing) → sinks (display, RTSP, JSON, MQTT)**
- [ ] Draw the **road-edge ROI / line** so only animals *near or on the road* raise alerts `P1`
- [ ] Screenshot the node graph (**required evidence**)

### 5.5 Stage 3 — Model
- [ ] Register the custom model + labels
- [ ] Set NMS/confidence: start at **conf 0.35 / IoU 0.45** (current values), then tune per class to cut false positives; target alert-level threshold ≥ 0.50 `P1`

### 5.6 Stage 4 — Compiler
- [ ] Compile to **TensorRT FP16** first (safe default) `P0`
- [ ] Save the **PipeGen speed report** (**required evidence**)
- [ ] Compile **INT8** with a calibration set (~300–500 representative images from `images/train`, varied lighting) and **FP32** baseline `P2` (Edge Optimization bonus)
- [ ] Build engines **on the demo machine**

### 5.7 Stage 5 — Run
- [ ] Run live from the **USB camera** (`/dev/video0`); also keep a **video-file source** as backup `P0`
- [ ] Enable **MQTT sink** → `localhost:1883`, plus **JSON metadata** and **RTSP/display** `P0`
- [ ] Subscribe with `mosquitto_sub -h localhost -t '#' -v` and **capture a real sample payload** → this fixes the contract in §6
- [ ] Decide: ESP32 parses PipeGen's payload directly **or** a bridge (§8) normalises it
- [ ] Run for ≥ 15 minutes continuously to check stability/thermals; record FPS
- [ ] Keep the generated `run.sh`; commit the **PipeGen export folder**

### 5.8 Evidence to save (Track A)
- [ ] Requirement stage screenshot
- [ ] **Pipeline IR node graph screenshot**
- [ ] **TensorRT speed report** (per precision)
- [ ] Screenshot/video of live annotated stream with animal detected
- [ ] Sample MQTT/JSON payloads
- [ ] Accuracy comparison table (FP32/FP16/INT8) if done

---

## 6. Workstream B — Message Contract (MQTT)  `P0`

Write this into the FirmGen PRD **and** `docs/mqtt-contract.md`. Keep payloads small (< 256 bytes) for the ESP32.

### 6.1 Topics
| Topic | Direction | QoS | Retained | Purpose |
|---|---|---|---|---|
| `wildguard/perception/detections` | PipeGen/bridge → ESP32, backend | 1 | no | Confirmed animal events |
| `wildguard/node/esp32-01/sensor` | ESP32 → backend/bridge | 0 | no | Distance + PIR + armed state (on change, ≥ 1 Hz heartbeat) |
| `wildguard/node/esp32-01/status` | ESP32 → backend | 1 | **yes** | `online` / `offline` (LWT), firmware version, RSSI, uptime |
| `wildguard/node/esp32-01/ack` | ESP32 → backend | 1 | no | Action started for `event_id` |
| `wildguard/node/esp32-01/telemetry` | ESP32 → backend | 0 | no | Bonus: heap, tasks, state |
| `wildguard/control/mode` | dashboard → ESP32 | 1 | yes | `armed` / `disarmed` / `test` |

### 6.2 Detection event (v1)
```json
{
  "v": 1,
  "event_id": "wg-000123",
  "ts_capture": 1760000000123,
  "camera_id": "cam01",
  "class": "puma",
  "class_id": 3,
  "confidence": 0.87,
  "track_id": 12,
  "bbox": [0.31, 0.22, 0.28, 0.40],
  "in_road_zone": true,
  "sensor_confirmed": true
}
```
- `ts_capture` uses the **laptop clock**. Latency is computed on the laptop (ACK round-trip) so the ESP32 doesn't need clock sync.
- ESP32 must tolerate unknown extra fields and reject malformed JSON safely.

### 6.3 ACK
```json
{ "v": 1, "event_id": "wg-000123", "state": "ALERT", "profile": "puma", "t_rx_ms": 4210, "t_act_ms": 4216 }
```
(`t_*` are ESP32 uptime ms: gives on-board receive→actuate time.)

### 6.4 Species → response profiles (proposed — tune to taste)
| Class | Conservation status | Severity | LED behaviour | Buzzer | Stretch action |
|---|---|---|---|---|---|
| `tapir` | Vulnerable (very large, high crash risk) | **CRITICAL** | Fast red strobe (≈ 8 Hz) + amber | 3 long beeps, repeating | Stepper → "barrier down" |
| `giant_anteater` | Vulnerable | HIGH | Red strobe (≈ 4 Hz) | 2 beeps | Stepper → partial |
| `maned_wolf` | Near Threatened | HIGH | Red/amber alternate | 2 short beeps | — |
| `puma` | Least Concern | MEDIUM | Slow red pulse | 1 beep | Camera pan to track |
| `jaguarundi` | Least Concern | LOW | Amber blink | silent | — |
| *unknown / low conf* | — | WARN | Amber solid | silent | — |

Sensor confirmation upgrades severity by one level (e.g., MEDIUM → HIGH); an unconfirmed detection is capped at one level lower.

### 6.5 Reliability rules
- [ ] **Cool-down:** ignore repeat events for the same `track_id`/class for *N* s (default 5); re-detections extend the alert
- [ ] **Dedupe** on `event_id`
- [ ] **Confirmation:** require ≥ *K* consecutive frames (e.g., 3) before an event is published
- [ ] **Max buzzer duration** (e.g., 10 s) to avoid endless noise
- [ ] **Fail-safe:** if Wi-Fi/MQTT is lost, the ESP32 keeps local sensor-only warning (amber) and reconnects with backoff
- [ ] **LWT** marks node offline; dashboard shows it immediately

---

## 7. Workstream C — FirmGen (Action)  `P0`

### 7.1 Environment
- [ ] Install **FirmGen v0.4.1** + prerequisites from the developer portal; confirm **ESP-IDF v5.5**
- [ ] Do the FirmGen Hands-On Lab once with the sample ESP32 BLE PRD
- [ ] Confirm board detection, flashing and UART monitor work (data-capable USB cable!)

### 7.2 Write the PRD (what you give FirmGen)
Use "Help me write one" or upload your own. Sections: purpose, hardware & pin map (§4.2), connectivity, MQTT contract (§6), species profiles (§6.4), state machine, timing, safety, logging, non-functional requirements, acceptance criteria. **Explicitly include the closed-loop requirement:**
> *"The ESP32 shall subscribe to perception events over MQTT, map the animal class to a response profile, and execute physical countermeasures (LEDs, buzzer) within 100 ms of message receipt, then publish an acknowledgement."*

### 7.3 Draft requirement set (to be reviewed, tagged Explicit/Inferred, then **frozen**)

| ID | Requirement | Acceptance criterion (measurable) |
|---|---|---|
| **Connectivity** | | |
| WG-CON-01 | Join Wi-Fi (STA) using credentials from NVS/Kconfig; retry with exponential backoff | Connects ≤ 10 s after boot; reconnects after router power-cycle |
| WG-CON-02 | Connect to MQTT broker; set Last Will (`offline`, retained); publish `online` retained on connect | `mosquitto_sub` shows `online`; pull power → `offline` appears |
| WG-CON-03 | Subscribe to `wildguard/perception/detections` (QoS 1) and `wildguard/control/mode` | UART shows subscription OK |
| **Sensing** | | |
| WG-SEN-01 | Sample HC-SR04 at ≥ 10 Hz with 3-sample median filter; valid range 2–400 cm; handle timeouts | UART shows stable readings; unplugged sensor → error counted, no crash |
| WG-SEN-02 | Read PIR with debounce (≥ 200 ms) | One physical motion = one event |
| WG-SEN-03 | Enter `ARMED` when distance < threshold (default 20 cm, configurable) **or** PIR motion; exit after clear + hold-off | State transitions visible in UART |
| WG-SEN-04 | Publish sensor state on change and every 1 s | Dashboard shows live values |
| **Event handling** | | |
| WG-EVT-01 | Parse and validate detection JSON (`v`, `event_id`, `class`, `class_id`, `confidence`); ignore unknown fields; reject malformed | Malformed payload logged + counted, device stays up |
| WG-EVT-02 | Ignore events with `confidence` below configurable threshold (default 0.50) | Low-conf test → no action |
| WG-EVT-03 | Deduplicate by `event_id`; apply per-class cool-down | Duplicate publish → one action |
| WG-EVT-04 | Map `class`/`class_id` to a response profile (table in §6.4); unknown → generic WARN | Each of 5 classes → distinct pattern |
| **Actuation** | | |
| WG-ACT-01 | Drive red/amber/green LEDs with profile-specific patterns | Visual + logic-analyzer/video check |
| WG-ACT-02 | Drive buzzer with profile-specific patterns | Audible, distinct per class |
| WG-ACT-03 | Actuation begins ≤ **100 ms** after MQTT message receipt | Timestamps in ACK/UART |
| WG-ACT-04 | Alert lasts configurable duration (default 5 s), extended by re-detection, then returns to IDLE | Observed |
| WG-ACT-05 | *(Stretch)* Move stepper to preset position for CRITICAL/HIGH and return afterward | Observed; no missed steps |
| **Acknowledgement** | | |
| WG-ACK-01 | Publish ACK with `event_id`, state, profile, timestamps after actuation starts | Dashboard computes latency |
| **State machine & safety** | | |
| WG-SAF-01 | All outputs OFF at boot and on fault | Verified at power-up |
| WG-SAF-02 | Max continuous buzzer ≤ 10 s | Verified |
| WG-SAF-03 | Task watchdog enabled; reboot on hang | Induced hang → reboot |
| WG-SAF-04 | On MQTT loss, enter DEGRADED mode (sensor-only amber warning), keep trying to reconnect | Kill broker → amber; restart broker → recovers |
| WG-SAF-05 | `disarmed` mode suppresses actuation; `test` mode runs each profile | Dashboard control works |
| **Logging** | | |
| WG-LOG-01 | UART 115200 8N1, structured lines, e.g. `[WG] RX id=wg-000123 class=puma conf=0.87 sev=MEDIUM` / `[WG] ACT start profile=puma dt=6ms` / `[WG] ACK sent` | Lines appear for every event (**this is your acceptance evidence**) |
| **Non-functional** | | |
| WG-NFR-01 | Boot to ready ≤ 5 s (excluding Wi-Fi join) | Measured |
| WG-NFR-02 | Free heap never below a defined floor (e.g., 40 KB) during a 30-min soak | Logged |
| WG-NFR-03 | Secrets (Wi-Fi/MQTT) not hard-coded in committed source | Code review |
| **Bonus** | | |
| WG-TEL-01 | Telemetry enabled via FirmGen Live Intelligence: state, heap, task stats, last event | Live panel during demo |

### 7.4 FirmGen workflow checklist
- [ ] Upload PRD (or "Help me write one") → generate requirements, tasks, acceptance criteria
- [ ] Choose a path: **Category-wise Manual Review** is best for a judged project (shows you reviewed/froze requirements); Auto Mode for speed if time is short
- [ ] **Review every requirement** (Explicit vs Inferred); fix wrong inferences; **freeze** the set — snapshot a screenshot
- [ ] Implement → build → flash → monitor
- [ ] Generate requirement-linked **unit tests**, **design document**, **traceability report**
- [ ] Push via FirmGen's **Git view** to its own repo (e.g., `wildguard-firmware`)
- [ ] Re-run build after any hand edit so the traceability report stays consistent
- [ ] **Do not hand-patch around FirmGen** — prefer fixing the PRD and regenerating, so the tool stays load-bearing

### 7.5 Evidence to save (Track B)
- [ ] The PRD file and **frozen requirement list**
- [ ] **Traceability report** (requirement → code → tests)
- [ ] **UART/Monitor capture** showing RX of a real PipeGen detection + action + ACK
- [ ] Short video of the physical behaviour (LED/buzzer) per species
- [ ] Photo of the final wiring

---

## 8. Workstream D — Bridge / Gateway Service  `P1` (only if needed)

Purpose: thin glue so PipeGen's native output meets the contract in §6.2 without making the ESP32 parse a complex payload.

- [ ] Subscribe to PipeGen's MQTT output (or tail its JSON metadata)
- [ ] Filter to the 5 target classes; drop low-confidence
- [ ] Require K consecutive frames; assign `event_id`; apply cool-down per `track_id`
- [ ] Merge latest ESP32 sensor state → set `sensor_confirmed`
- [ ] Publish normalised event to `wildguard/perception/detections` (QoS 1)
- [ ] Log every in/out message with timestamps (used for latency analysis)
- [ ] Run as a `systemd`/script-managed process started by `scripts/start_all.sh`

> If PipeGen's payload is already simple enough, skip the bridge and implement the filtering in the ESP32 requirements instead (stronger "FirmGen is load-bearing" story).

---

## 9. Workstream E — Backend Changes (FastAPI)  `P0/P1`

| File | Change | Priority |
|---|---|---|
| `backend/model.py` | **Remove from runtime.** Move to `training/onnx_reference.py` (offline accuracy comparison only) | P0 |
| `backend/main.py` | Remove `POST /api/detect/image` and `POST /api/detect/frame` from the live app (or relabel as "offline analysis — not part of the closed loop") | P0 |
| `backend/main.py` | Add **MQTT subscriber** (paho-mqtt) on startup: detections, sensor, status, ack | P0 |
| `backend/main.py` | Add **WebSocket/SSE** `/api/events` that pushes live events to the dashboard | P0 |
| `backend/main.py` | Replace CSV-based `GET /api/sensor/latest` with MQTT-cached state | P0 |
| `backend/main.py` | Extend `GET /api/health`: backend, broker connection, node online/offline, last-seen, pipeline alive | P1 |
| `backend/main.py` | New `POST /api/control/mode` (armed/disarmed/test) → publishes to MQTT | P1 |
| `backend/main.py` | New `POST /api/test/alert` (publish a synthetic detection for a chosen species) — lets you demo the actuator even if the camera misbehaves | P1 |
| `backend/main.py` | New `GET /api/metrics/latency` (p50/p95 capture→ACK) | P1 |
| `backend/main.py` | New `GET /api/pipeline/info` (precision, FPS, engine, model) from a static JSON exported from PipeGen's report | P1 |
| `backend/database.py` | Migrate schema: `source='pipegen'`, add `event_id`, `track_id`, `severity`, `sensor_confirmed`, `action_profile`, `ack_ts`, `latency_ms`; new `sensor_events` and `node_status` tables; enable WAL; add indexes on `timestamp`, `animal` | P0 |
| `backend/database.py` | Thumbnails: drop for now, or capture a snapshot from the RTSP stream | P2 |
| `backend/requirements.txt` | Remove `onnxruntime` (and `opencv`/`pillow` if unused); add `paho-mqtt`; pin versions | P0 |
| `backend/.env` / config | `MQTT_HOST`, `MQTT_PORT`, topic prefix, thresholds, CORS origins; `.env.example` committed, real `.env` ignored | P0 |

---

## 10. Workstream F — Frontend Changes (React)  `P1`

| Page / component | Change |
|---|---|
| **Dashboard** | Add a **closed-loop status strip**: Pipeline (FPS, precision) · Broker · ESP32 node (online, RSSI, last seen) · Last alert → ACK latency · Armed/disarmed |
| **LiveDetection** | Replace browser-webcam + frame-POST with PipeGen's **annotated RTSP stream** (via MediaMTX → WebRTC/HLS/MJPEG) `P2`; otherwise show the live **event feed**. Keep the live sensor panel (distance, PIR, ARMED) fed by WebSocket |
| **ImageDetection** | Remove from nav (or relabel "Offline analysis (not part of loop)") |
| **History** | Add columns: severity, track ID, sensor-confirmed, action profile, ACK latency; filters for severity/profile; CSV export includes new fields |
| **Analytics** | Add: latency histogram, alerts per species/profile, hourly trend; **FP32 vs FP16 vs INT8** FPS/accuracy chart (from PipeGen reports) |
| **New: Control & Test page** | Arm/disarm, per-species "simulate alert" buttons, simulate sensor trip, last-10 ACKs, kill switch |
| **AlertBanner** | Real-time toast on new alert with species, severity, and "Actuator responded in X ms" |
| **AnimalTag** | Add severity colours aligned with §6.4 |
| **services/api.js** | Base URL via env var; WebSocket client with auto-reconnect; error states |
| **UX details** | Empty/loading/offline states; "Node offline" banner; responsive layout for a projector; large-font "demo mode" |

---

## 11. Workstream G — Repository, Docs & Housekeeping  `P0/P1`

### 11.1 Proposed layout
```
wildguard-ai/
├── perception/          # PipeGen export folder, labels.txt, run.sh, calibration list,
│                        # reports/ (speed report), screenshots/ (IR graph)
├── firmware/            # FirmGen project (PRD, frozen requirements, design doc,
│                        # traceability report, src, tests)  → also pushed from FirmGen Git view
├── bridge/              # optional thin gateway
├── backend/             # FastAPI + MQTT subscriber + SQLite
├── frontend/            # React dashboard
├── broker/              # mosquitto.conf
├── training/            # notebook, bra_dataset.yaml (relative paths), onnx_reference.py
├── docs/
│   ├── architecture.md
│   ├── mqtt-contract.md
│   ├── hardware/        # schematic, wiring photos, BOM
│   ├── evidence/        # screenshots, UART logs, videos
│   └── demo-script.md
├── scripts/             # start_all.sh, publish_test_alert.sh, check_env.sh
├── legacy/              # old Arduino sketch (clearly marked pre-hackathon)
├── .gitignore           # .env, *.db, engines/, node_modules, sdkconfig secrets
└── README.md
```
> Submission asks for the **PipeGen export folder** and/or the **FirmGen project pushed via FirmGen's Git view**. Keep the FirmGen project in its own repo too (link/submodule it) so its Git history is genuine.

### 11.2 Fix existing issues
- [ ] `bra_dataset.yaml`: replace `D:/animal_detection/...` with relative paths
- [ ] README: replace `your-username` clone URL, fix "endangered" wording, replace the generic `universe.roboflow.com` link with the **exact dataset source, licence and citation**
- [ ] Fix the README's sensor/firmware description to match reality
- [ ] Add model metrics (mAP, per-class table, confusion matrix) to the README
- [ ] Remove `detections.db`, `sensor_log.csv`, weights/engines from git (or use releases/LFS)
- [ ] Don't commit Wi-Fi passwords, MQTT credentials, `sdkconfig` with secrets

### 11.3 New/updated README sections
- [ ] Problem & impact (road mortality; driver safety) — one strong paragraph
- [ ] **Closed-loop diagram** and 30-second explanation
- [ ] How PipeGen is used (5 stages, TensorRT, precision, FPS) and how FirmGen is used (PRD → traceability)
- [ ] **"Built at the hackathon vs pre-existing"** table
- [ ] One-command start (`scripts/start_all.sh`) and manual steps
- [ ] MQTT contract summary and species→action table
- [ ] Hardware wiring + photos
- [ ] Results: latency, FPS, accuracy
- [ ] Limitations & future work (radar/LiDAR range, solar power, LoRa for remote roads, multi-camera, retraining with negatives)

### 11.4 Scripts
- [ ] `scripts/start_all.sh` — broker → PipeGen `run.sh` → bridge → backend → frontend, with health checks
- [ ] `scripts/publish_test_alert.sh <species>` — `mosquitto_pub` a synthetic event (works with no camera)
- [ ] `scripts/check_env.sh` — verifies `pipegen --version`, GPU, broker, camera, ESP32 online

---

## 12. Bonus Stack

### 12.1 Edge Optimization (Track A) `P2`
- [ ] Build FP32, FP16, INT8 engines; record latency/FPS/power (if available) from PipeGen reports
- [ ] Measure accuracy per precision on the validation set; table of **speed ↔ power ↔ accuracy** trade-off
- [ ] If a Jetson is available: deploy there as the "pole-mounted unit" story
- [ ] Choose which engine is used in the live demo and justify it

### 12.2 Live Intelligence (Track B) `P2` — do **after** everything else works and is frozen
- [ ] Enable Telemetry in FirmGen (it rebuilds and reflashes) and verify the closed loop still passes all tests
- [ ] Show the RTOS/System Monitor and/or a breakpoint while a detection arrives
- [ ] Confirm that you're allowed to claim multiple bonuses (ask a mentor); list all claimed bonuses in the submission text

---

## 13. Test & Validation Plan  `P0`

### 13.1 Scenario matrix
| # | Scenario | Expected result |
|---|---|---|
| 1 | Show each of the 5 species to the camera, sensor armed | Correct distinct LED/buzzer profile; ACK; dashboard row |
| 2 | Species detected, sensor **not** armed | Lower-severity response (per §6.4 rule) |
| 3 | Sensor armed, **no** animal | ESP32 → ARMED (amber) only; no species alert |
| 4 | Person/dog/other object in frame | No alert (thresholds/K-frame/ROI hold) — **log false-positive rate** |
| 5 | Low-confidence detection | Ignored |
| 6 | Same animal stays in frame 30 s | One alert, extended — not a spam of alerts |
| 7 | Duplicate `event_id` published twice | One action |
| 8 | Malformed JSON published | Logged, ignored, device stable |
| 9 | Broker stopped mid-demo | ESP32 → DEGRADED; auto-recovers when broker returns |
| 10 | Wi-Fi router power-cycled | ESP32 reconnects, re-subscribes |
| 11 | ESP32 reset during alert | Boots with outputs OFF, returns to IDLE |
| 12 | PipeGen restarted | Dashboard shows pipeline down/up; no crash elsewhere |
| 13 | Camera unplugged | Pipeline falls back/reports error; dashboard indicator |
| 14 | 30-min soak with periodic events | No memory leak (heap floor), stable FPS |
| 15 | Video-file source instead of camera | Same behaviour (demo fallback) |

### 13.2 Metrics to record (put them in the README and the pitch)
- [ ] Pipeline FPS per precision (PipeGen report)
- [ ] **End-to-end latency**: frame capture → ESP32 actuator ON (p50 / p95 over ≥ 30 events)
- [ ] ESP32 receive→actuate time (from ACK timestamps)
- [ ] Detection accuracy on val set (per class) + false-positive observations on negatives
- [ ] Uptime during soak test

---

## 14. Submission Checklist (mapped to the problem statement)

**Both tracks**
- [ ] Working prototype demo on hardware at the venue
- [ ] Source repository link(s) (PipeGen export folder + FirmGen project pushed via Git view)
- [ ] Project description: problem, track (Open Innovation), **how PipeGen and FirmGen connect**, bonuses claimed (**Closed Loop**, plus Edge Optimization / Live Intelligence if done)
- [ ] Optional pitch deck/video (recommended: 60–90 s demo video as backup)
- [ ] Submit to **both** forms (FirmGen form and PipeGen form) before **4:00 pm** — confirm with a mentor how closed-loop projects should file

**Track A evidence (PipeGen)**
- [ ] Pipeline IR node-graph screenshot
- [ ] TensorRT speed report
- [ ] Live run proof (camera/video) + MQTT/JSON output proof
- [ ] Pipeline description: inputs, tasks, models, precision, outputs

**Track B evidence (FirmGen)**
- [ ] PRD + frozen requirements
- [ ] Traceability report
- [ ] UART/Monitor output showing received detection payload and action
- [ ] Physical behaviour proof (video/photos)

**Closed Loop evidence**
- [ ] The Bridge requirement written in the PRD (MQTT contract)
- [ ] One continuous clip: camera → detection → MQTT → ESP32 reacts → ACK on dashboard (with latency)

---

## 15. Demo Plan

### 15.1 90-second script
1. **Problem (10 s):** wildlife–vehicle collisions on Brazilian roads; drivers get no warning.
2. **Show the rig (10 s):** camera + roadside unit (ESP32, LEDs, buzzer) + dashboard.
3. **Idle (10 s):** green LED, node online, pipeline FPS visible.
4. **Sensor trip (10 s):** wave toy/object near HC-SR04 → amber ARMED.
5. **Tapir card in front of camera (20 s):** PipeGen box + label → MQTT message appears → red strobe + beeps → dashboard shows alert + "ACK in X ms".
6. **Swap to jaguarundi (10 s):** different (milder) response — proves species mapping.
7. **Evidence (15 s):** Pipeline IR graph, TensorRT report, traceability report, UART log.
8. **Resilience (optional 5 s):** stop broker → amber DEGRADED → recovers.

### 15.2 Backup plans
- [ ] Pre-recorded video clip as the PipeGen source if camera/lighting fails
- [ ] `publish_test_alert.sh` to prove the actuator path independently
- [ ] Spare ESP32 flashed with the same firmware
- [ ] Phone hotspot as secondary network
- [ ] Offline copies of all evidence (PDF/screenshots) and a recorded demo video

### 15.3 Day-of kit
Laptop + charger, router/hotspot, power strip, spare cables, printed cards, tablet, tripod, ESP32 (+ spare), full breadboard rig pre-wired, multimeter, tape, USB hub.

---

## 16. Timeline

### Before the event `P0`
- [ ] Linux + GPU environment ready; PipeGen v0.5.1 and FirmGen v0.4.1 installed; developer portal login working
- [ ] Re-export `best.pt` → ONNX; prepare `labels.txt`, calibration image list
- [ ] Mosquitto installed and tested; dashboard cleaned of the ONNX path
- [ ] Hardware pre-wired on a breadboard and verified with a throw-away test (not submitted)
- [ ] PRD v0 drafted from §6 and §7.3; contract doc written
- [ ] Complete both labs on sample material

### Event day (assuming 10:00 start, 16:00 deadline)
| Time | Activity |
|---|---|
| 10:00–12:00 | Workshops (PipeGen + FirmGen run in parallel — split roles, or prioritise the one you're least sure about) |
| 12:00–13:00 | PipeGen: import model, build IR, compile FP16, **first live run + MQTT message captured**. FirmGen: PRD review + **freeze** |
| 13:00–14:00 | FirmGen: generate, build, flash, verify UART; contract finalised |
| 14:00–15:00 | **Integration:** end-to-end loop, bridge (if needed), dashboard wiring, latency measurement |
| 15:00–15:30 | Evidence capture, scenario tests, record backup video |
| 15:30–15:50 | README/description, push repos, bonus (INT8/telemetry) only if all green |
| 15:50–16:00 | **Submit** (buffer!) |

> Rule: **freeze features at 15:00.** Anything not working by then is cut.

---

## 17. Risk Register

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| PipeGen can't import custom YOLOv8 ONNX / output parser mismatch | Med | **Critical** | Test first thing; ask CraftifAI mentor; keep export recipe + labels ready |
| No NVIDIA GPU/Jetson available or wrong OS | Low–Med | Critical | Confirm now; borrow hardware from organisers |
| Venue Wi-Fi isolates clients | Med | High | Bring router/hotspot; test at arrival |
| PipeGen MQTT payload format unexpected | Med | Med | Capture sample early; bridge as adapter |
| FirmGen build/flash issues (ESP-IDF, drivers, cable) | Med | High | Pre-install; data cable; spare board; practice run |
| HC-SR04 5 V damaging ESP32 pin | Low | High | Voltage divider (checklist §4.3) |
| False positives (closed-set classes) | High | Med | Thresholds, K-frames, ROI, sensor fusion, negative tests |
| Poor lighting / printed cards under-detect | Med | Med | Use tablet/screen images; fixed lighting; video backup |
| Running out of time | High | High | P0/P1/P2 discipline; feature freeze at 15:00 |
| "Bolted-on" perception of integration | Med | High | Remove ONNX path; ESP32 owns real logic; show ACK + latency |
| TensorRT engine incompatibility | Low | Med | Build on demo machine; keep run.sh |
| Secrets leaked in repo | Low | Med | `.gitignore`, `.env.example`, scan before push |

---

## 18. Open Questions to Settle First

1. **Compute:** laptop with NVIDIA GPU, desktop, or Jetson? Which JetPack/driver/TensorRT versions?
2. **OS:** is Linux (native, not WSL) available? PipeGen needs an X11 desktop session.
3. **Which ESP32 board** exactly, and which sensors/actuators are in your kit vs. your own?
4. **Single or dual submission:** can one closed-loop project be filed on both forms? (Ask at the hardware desk.)
5. **Multiple bonuses:** can Closed Loop be combined with Edge Optimization and Live Intelligence?
6. **PipeGen's custom-model import path** and MQTT payload format — confirm with the lab doc/mentor.
7. **Rules on pre-existing code** — confirm what's acceptable and disclose accordingly.

---

## 19. Definition of Done

**Qualifies (P0):**
- [ ] YOLOv8 model compiled via PipeGen to TensorRT; speed report saved; IR graph screenshot saved
- [ ] PipeGen runs **live** on camera/video and publishes MQTT/JSON on detection
- [ ] PRD → frozen requirements → FirmGen firmware flashed to a real ESP32
- [ ] ESP32 receives the PipeGen detection and triggers a species-specific LED/buzzer response; ACK returned
- [ ] Traceability report + UART output captured
- [ ] Dashboard shows live events from MQTT; ONNX CPU path removed from the live system
- [ ] Repo(s) pushed; README/description written; both forms submitted before 4:00 pm

**Wins (P1):** sensor fusion, road-zone ROI, per-species profiles, measured latency, DEGRADED fail-safe, Control & Test page, strong evidence pack, clean demo script.

**Stands out (P2):** INT8 vs FP16 trade-off report, Jetson deployment, Live Intelligence telemetry, stepper barrier action, RTSP stream embedded in the dashboard, mock road scene.
