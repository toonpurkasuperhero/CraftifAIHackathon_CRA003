# Event-day runbook

Everything that does not need hardware is already built and tested. This page lists only what is left, in order. Deadline **16:00**. Feature freeze **15:00**.

## Before you leave home

- [ ] Laptop runs the rehearsal: `./scripts/start_all.sh --rehearsal`, open http://localhost:5173, then `./scripts/stop_all.sh`
- [ ] Mosquitto, Node 20+ and Python deps installed (see README Quick start, plus `pip install -r tools/requirements.txt`)
- [ ] CraftifAI account works. PipeGen v0.5.1 and FirmGen v0.4.1 installers downloaded
- [ ] `perception/export_onnx.sh` run once (needs `pip install ultralytics onnx onnxsim`). Copy `perception/export/` to a USB stick
- [ ] Calibration images: `python perception/make_calibration_list.py --n 400 --copy /home/$USER/wildguard_calib`
- [ ] Printed species cards / tablet with BRA test images, backup MP4 under /home
- [ ] Travel router or phone hotspot, data USB cables, 1 kΩ + 2 kΩ resistors (HC-SR04 echo divider), MOSFET, LEDs, buzzer
- [ ] `docs/project-description.md` read through by the whole team

## 10:00-12:00 workshops

Split the team: one person on the PipeGen lab, one on the FirmGen lab. Ask the mentors these questions early:
1. Can one closed-loop project be submitted on **both** forms?
2. Can Closed Loop be combined with Edge Optimization and Live Intelligence?
3. How do we import a **custom YOLOv8 ONNX** (output `[1, 9, 8400]`) in PipeGen's Model stage?
4. What does PipeGen's **MQTT payload** look like?
5. Is code prepared before the event acceptable if disclosed? (Our split is in the project description.)

## 12:00-13:00

**PipeGen** (follow [perception/README.md](../perception/README.md)):
- [ ] Stage 1: paste `perception/requirement.md`, take a screenshot
- [ ] Stage 2: draw the road-zone ROI. **Screenshot the Pipeline IR graph**
- [ ] Stage 3: register `export/wildguard_yolov8n_bra5.onnx` + `labels.txt`
- [ ] Stage 4: compile **FP16**. **Save the speed report**
- [ ] Stage 5: run on the USB camera with the MQTT sink set to `wildguard/pipegen/raw`
- [ ] `python bridge/bridge.py --sniff` shows parsed objects. If it shows `[]`, adapt `extract_objects()` to the captured sample

**FirmGen** (follow [firmware/README.md](../firmware/README.md)):
- [ ] Adjust PRD section 3 (pin map) to the actual kit, if it differs
- [ ] Upload the PRD, use Category-wise Manual Review, **freeze**, take a screenshot

## 13:00-14:00 firmware on the board

- [ ] Wire per [docs/hardware/README.md](hardware/README.md). **Measure ECHO ≤ 3.3 V**
- [ ] menuconfig: Wi-Fi + `mqtt://<laptop-ip>:1883` (`./scripts/check_env.sh` prints the IP)
- [ ] Build, flash, monitor. `[WG]` lines appear. Retained status `online`
- [ ] `./scripts/publish_test_alert.sh tapir`: the board strobes and the ACK appears

## 14:00-15:00 integration

- [ ] `./scripts/start_all.sh --no-pipegen` (PipeGen keeps running from its own UI)
- [ ] Dashboard shows **no** REHEARSAL banner. Loop strip all green: PipeGen, Bridge, Broker, ESP32
- [ ] Species card in front of the camera: the board reacts, and the toast shows the ACK latency
- [ ] `python tools/hil_acceptance.py --target esp32` with the FirmGen monitor open. Save the UART log to `firmware/evidence/uart_acceptance.log`
- [ ] Let at least 30 real events accumulate (cards and video) for the latency statistics

## 15:00-15:30 evidence (freeze features)

- [ ] FirmGen: generate tests, design doc, **traceability report**, then push via the Git view
- [ ] Analytics → **Evidence pack**: save as `docs/evidence/wildguard_evidence.md`
- [ ] Fill `perception/reports/pipeline_info.json` from the PipeGen report (the Analytics trade-off chart appears)
- [ ] Videos: one per species pattern, one continuous closed-loop clip, one DEGRADED recovery
- [ ] Bonus, only if all green: INT8 engine (Edge Optimization), Enable Telemetry + re-run HIL (Live Intelligence)

## 15:30-15:50 submit

- [ ] Replace every `[[...]]` in `docs/project-description.md` and the README Results table with **measured** values only
- [ ] Push the repo, then submit **both** forms (FirmGen: forms.gle/bnocK9CNLndiZLwf8 · PipeGen: forms.gle/eJyeCKCG2UH757QZ8)

## If something breaks

| Symptom | Check |
|---|---|
| ESP32 offline on the dashboard | `mosquitto_sub -t 'wildguard/node/+/status' -v`. Same LAN? Client isolation? Broker URI? |
| PipeGen "NO DATA" | `mosquitto_sub -t 'wildguard/pipegen/#' -v`. Is the MQTT sink topic right? Then `bridge --sniff` |
| Events but no board reaction | `mosquitto_sub -t 'wildguard/perception/detections' -v`, then the UART for `RX invalid` |
| Board reacts, no ACK latency | `wildguard/node/+/ack` topic and payload fields (`event_id`, `state`) |
| Not sure if it's firmware or network | Run `python tools/esp32_sim.py`. If the simulator works, the firmware or Wi-Fi is at fault |
| Camera or lighting | Switch the PipeGen source to the MP4 under /home |
