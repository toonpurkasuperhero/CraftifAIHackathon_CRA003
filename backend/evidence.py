"""Builds a Markdown evidence pack from live data, for the hackathon submission."""
import json
from datetime import datetime

import config
import database as db
from wg_contract import CLASS_NAMES, effective_severity


def _fmt(v, unit=""):
    return "n/a" if v is None else f"{v}{unit}"


def build_report(snapshot: dict) -> str:
    lat_all = db.get_latency_metrics(include_synthetic=True)
    lat_real = db.get_latency_metrics(include_synthetic=False)
    analytics = db.get_analytics()
    recent = db.get_detections(limit=15)
    out = []
    w = out.append

    w("# WildGuard AI - Closed-Loop Evidence Pack")
    w(f"_Generated {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} from the live system._\n")
    if snapshot.get("rehearsal"):
        sim = [n for n, on in (("PipeGen replaced by tools/pipegen_replay.py (ONNX on CPU)", snapshot["pipeline"].get("simulated")),
                               ("ESP32 replaced by tools/esp32_sim.py", snapshot["node"].get("simulated"))) if on]
        w("> **REHEARSAL DATA - NOT HARDWARE EVIDENCE.** " + "; ".join(sim) + ". "
          "This pack demonstrates the software loop only. Regenerate it on the real PipeGen pipeline and ESP32.\n")

    w("## 1. Loop health at generation time")
    node, pipe, bridge = snapshot["node"], snapshot["pipeline"], snapshot.get("bridge") or {}
    w("| Component | State | Detail |")
    w("|---|---|---|")
    w(f"| MQTT broker | {'connected' if snapshot['broker']['connected'] else 'DISCONNECTED'} | "
      f"{snapshot['broker']['host']}:{snapshot['broker']['port']} |")
    w(f"| PipeGen pipeline | {'alive' if pipe['alive'] else 'no recent messages'} | "
      f"msgs/s {_fmt(pipe.get('msgs_per_s'))}, FPS {_fmt(pipe.get('fps'))} |")
    w(f"| Bridge | {bridge.get('state', 'unknown')} | events published {_fmt(bridge.get('events_published'))} |")
    w(f"| ESP32 node `{node['id']}` | {'online' if node['reachable'] else 'OFFLINE'} | "
      f"fw {_fmt(node.get('fw'))}, RSSI {_fmt(node.get('rssi'), ' dBm')}, "
      f"uptime {_fmt((snapshot.get('telemetry') or {}).get('uptime_s', node.get('uptime_s')), ' s')} |")
    w(f"| Mode | {snapshot.get('mode') or 'unknown'} | |\n")

    w("## 2. Measured latency (capture -> ESP32 actuator ON -> ACK)")
    w("| Set | Events | ACKed | Timeouts | p50 e2e | p95 e2e | max e2e | p50 on-board RX->ACT | max on-board |")
    w("|---|---|---|---|---|---|---|---|---|")
    for name, m in (("Real PipeGen events", lat_real), ("All incl. test/replay", lat_all)):
        w(f"| {name} | {m['events']} | {m['acked']} | {m['timeouts']} | {_fmt(m['e2e_ms']['p50'], ' ms')} | "
          f"{_fmt(m['e2e_ms']['p95'], ' ms')} | {_fmt(m['e2e_ms']['max'], ' ms')} | "
          f"{_fmt(m['onboard_ms']['p50'], ' ms')} | {_fmt(m['onboard_ms']['max'], ' ms')} |")
    w("\nPRD target WG-ACT-03: on-board receive -> actuate <= 100 ms.\n")

    w("## 3. Species coverage and response profiles")
    w("| Class | Events | Confirmed severity | Unconfirmed severity |")
    w("|---|---|---|---|")
    for c in CLASS_NAMES:
        w(f"| {c} | {analytics['animal_counts'].get(c, 0)} | {effective_severity(c, True)} | {effective_severity(c, False)} |")
    w(f"\nSeverity distribution (from ESP32 ACKs): `{json.dumps(analytics['severities'])}`  ")
    w(f"Sensor confirmation: `{json.dumps(analytics['sensor_confirmation'])}`  ")
    w(f"Sources: `{json.dumps(analytics['sources'])}`\n")

    w("## 4. Most recent events")
    w("| Time | Event | Class | Conf | Source | Confirmed | Severity | ACK | e2e ms | on-board ms |")
    w("|---|---|---|---|---|---|---|---|---|---|")
    for r in recent:
        w(f"| {r['timestamp']} | {r.get('event_id') or '-'} | {r['animal']} | {r['confidence']:.2f} | {r['source']} | "
          f"{_fmt(r.get('sensor_confirmed'))} | {_fmt(r.get('severity'))} | {_fmt(r.get('ack_state'))} | "
          f"{_fmt(r.get('latency_ms'))} | {_fmt(r.get('onboard_ms'))} |")
    w("")

    w("## 5. Hardware-in-the-loop acceptance results")
    try:
        res = json.loads(config.ACCEPTANCE_RESULTS_PATH.read_text())
        w(f"Run at {res.get('started')} against node `{res.get('node')}` ({res.get('target')}). "
          f"**{res.get('passed', 0)}/{res.get('total', 0)} passed.**\n")
        w("| Scenario | Requirement(s) | Result | Detail |")
        w("|---|---|---|---|")
        for t in res.get("results", []):
            w(f"| {t['name']} | {', '.join(t.get('requirements', []))} | {'PASS' if t['passed'] else 'FAIL'} | {t.get('detail', '')} |")
    except FileNotFoundError:
        w("_Not run yet. Run `python tools/hil_acceptance.py` against the real ESP32._")
    w("")

    w("## 6. Pipeline report (from PipeGen)")
    try:
        info = json.loads(config.PIPELINE_INFO_PATH.read_text())
        w("```json")
        w(json.dumps(info, indent=2))
        w("```")
    except (FileNotFoundError, ValueError):
        w("_perception/reports/pipeline_info.json missing or invalid._")
    return "\n".join(out) + "\n"
