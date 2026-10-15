# Evidence pack

"A command that completes is not the same as a system that works - show the evidence."
Collect everything here (or in the folders named) before 15:30.

## Ready now (no hardware needed)
- [x] `model/` - ONNX FP32 baseline on the val split: per-class AP50/AP50-95, precision/recall at the alert threshold,
      confusion matrix, threshold sweep (`python tools/eval_model.py`) + training curves from run train3
- [x] `rehearsal/` - software-loop rehearsal (PipeGen replay + ESP32 simulator): dashboard screenshots, evidence pack,
      event CSV, simulator acceptance run. **Every file is labelled as rehearsal - not hardware evidence.**

## Track A - PipeGen
- [ ] `perception/screenshots/01_requirement.png`
- [ ] `perception/screenshots/02_pipeline_ir.png`  **(required)**
- [ ] `perception/reports/fp16_speed_report.*`  **(required)** (+ fp32 / int8 for Edge Optimization)
- [ ] `perception/screenshots/04_live_run.png` - animal boxed on the live camera
- [ ] `perception/reports/sample_pipegen_payload.json` - real MQTT message
- [ ] `perception/reports/pipeline_info.json` - filled from the reports

## Track B - FirmGen
- [ ] PRD + frozen requirements screenshot/export in `firmware/`
- [ ] `firmware/traceability_report.*`  **(required)**
- [ ] `firmware/evidence/uart_acceptance.log`  **(required)** - UART during the HIL run
- [ ] `acceptance_results.md` + `.json` here - from `python tools/hil_acceptance.py --target esp32`
- [ ] One short video per species pattern + DEGRADED recovery
- [ ] Wiring photos in `docs/hardware/`

## Closed loop
- [ ] One continuous clip: animal card → PipeGen box → event in dashboard → board strobes → toast with ACK latency
- [ ] `wildguard_evidence.md` - Analytics → **Evidence pack** button (live latency table, species coverage, HIL results)
- [ ] (Bonus) Live Intelligence screenshot with the loop running

Results produced by the simulator (`--target sim`) are for rehearsal only and must not be submitted as evidence.
