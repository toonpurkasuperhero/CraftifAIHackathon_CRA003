# HIL acceptance results (sim)

> **REHEARSAL against tools/esp32_sim.py - not hardware evidence.** It shows the test suite and the contract work end to end; re-run with `--target esp32` on the real board.

Started 2026-10-15 20:10:00 - node `esp32-01` - broker `localhost:1883` - **19/19 passed**

| Scenario | Requirement(s) | Result | Detail |
|---|---|---|---|
| Node reports online (retained status) | WG-CON-02 | PASS | status={'state': 'online', 'fw': 'sim-1.0.0', 'rssi': -52, 'uptime_s': 0} |
| Sensor heartbeat >= 1 Hz | WG-SEN-04 | PASS | 3 msgs in 3.2 s |
| Sensor payload has distance/pir/armed/state | WG-SEN-04 | PASS | {"v": 1, "distance_cm": 206.7, "pir": false, "armed": false, "state": "IDLE", "mode": "armed", "threshold_cm": 20.0} |
| tapir: profile + severity | WG-EVT-04, WG-EVT-05, WG-ACK-01 | PASS | state=ALERT profile=tapir sev=HIGH (expected HIGH, confirmed=False) rtt=1 ms |
| jaguarundi: profile + severity | WG-EVT-04, WG-EVT-05, WG-ACK-01 | PASS | state=ALERT profile=jaguarundi sev=WARN (expected WARN, confirmed=False) rtt=1 ms |
| maned_wolf: profile + severity | WG-EVT-04, WG-EVT-05, WG-ACK-01 | PASS | state=ALERT profile=maned_wolf sev=MEDIUM (expected MEDIUM, confirmed=False) rtt=1 ms |
| puma: profile + severity | WG-EVT-04, WG-EVT-05, WG-ACK-01 | PASS | state=ALERT profile=puma sev=HIGH (expected HIGH, confirmed=True) rtt=1 ms |
| giant_anteater: profile + severity | WG-EVT-04, WG-EVT-05, WG-ACK-01 | PASS | state=ALERT profile=giant_anteater sev=MEDIUM (expected MEDIUM, confirmed=False) rtt=1 ms |
| On-board RX -> actuate <= 100 ms | WG-ACT-03 | PASS | max 1 ms, median 0 ms over 5 |
| Low confidence (0.20) ignored | WG-EVT-02 | PASS | ack={'state': 'IGNORED', 'reason': 'low_conf'} |
| Duplicate event_id -> exactly one ACK | WG-EVT-03 | PASS | 1 ACKs |
| Malformed payloads rejected, node keeps working | WG-EVT-01 | PASS | valid event after 3 bad ones was ACKed |
| Unknown extra fields tolerated | WG-EVT-01 | PASS | state=ALERT |
| Unknown class -> generic WARN profile | WG-EVT-04 | PASS | profile=generic sev=WARN |
| Re-detection during alert extends it | WG-ACT-04 | PASS | first=ALERT second=EXTEND |
| Disarmed mode suppresses actuation | WG-SAF-05 | PASS | ack={'state': 'IGNORED', 'reason': 'disarmed'} |
| sim_trip command -> node reports ARMED | WG-SEN-03, WG-TST-01 | PASS |  |
| Sensor-confirmed detection upgrades severity | WG-EVT-05 | PASS | sev=HIGH confirmed=True |
| Broker -> ESP32 -> ACK round trip measured | WG-ACK-01, WG-ACT-03 | PASS | n=35 p50=40 ms p95=41 ms max=41 ms |

## Manual / physical checks (tick on the day, attach video)

- [ ] **WG-ACT-01/02**: Each species shows its own LED + buzzer pattern (film it: one clip per species)
- [ ] **WG-SAF-01**: Power-cycle during an alert: all outputs OFF at boot, returns to IDLE
- [ ] **WG-SAF-02**: Buzzer never sounds longer than 10 s continuously
- [ ] **WG-SAF-03**: Induced hang (FirmGen breakpoint / test hook) -> task watchdog reboots the board
- [ ] **WG-SAF-04**: Stop the broker: amber DEGRADED within 5 s; restart: recovers and re-subscribes
- [ ] **WG-CON-01**: Power-cycle the router: node rejoins Wi-Fi and MQTT without a reset
- [ ] **WG-SEN-01**: Unplug HC-SR04: error counted in telemetry, no crash
- [ ] **WG-NFR-02**: 30-min soak: heap_min in telemetry stays above 40 KB
