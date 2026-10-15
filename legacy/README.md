# legacy/ - pre-hackathon, NOT part of the submitted system

| File | What it was |
|---|---|
| `sketch_mar19a/sketch_mar19a.ino` | Arduino sketch: HC-SR04 + PIR printed to serial, buzzer on near/motion. Replaced by the FirmGen ESP-IDF firmware generated from `firmware/prd/WildGuard_PRD.md`. |
| `sensor_log.csv` | Serial capture from that sketch, which the old backend polled from a file. Replaced by the MQTT sensor topic. |
| `implementation_plan.md` | Old plan for the sensor-triggered browser-webcam feature (superseded by the closed-loop architecture). |

Kept only for history and to make the "pre-existing vs built at the hackathon" split explicit.
