#!/usr/bin/env python3
"""Hardware-in-the-loop acceptance tests for the ESP32 node, traced to PRD requirement IDs.

Publishes contract-v1 test events to the broker, watches the node's ACK / sensor / status topics,
and checks the PRD acceptance criteria that can be verified over MQTT. Writes:
  docs/evidence/acceptance_results.json   (read by the backend evidence report)
  docs/evidence/acceptance_results.md     (paste into the submission)

Run against the REAL board for evidence (the simulator is only for rehearsal):
    python tools/hil_acceptance.py                 # all automatic scenarios
    python tools/hil_acceptance.py --target sim    # label the run as simulator
Keep the UART monitor open in FirmGen while it runs: the [WG] lines are the matching evidence.
Physical checks (LED/buzzer pattern, watchdog, power-cycle) are printed as a manual checklist.
"""
from __future__ import annotations

import argparse
import json
import os
import queue
import statistics
import sys
import threading
import time
import uuid
from datetime import datetime
from pathlib import Path

import paho.mqtt.client as mqtt

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "shared"))
from wg_contract import CLASS_NAMES, SPECIES, TOPICS, effective_severity  # noqa: E402

EVIDENCE = ROOT / "docs" / "evidence"

MANUAL_CHECKS = [
    ("WG-ACT-01/02", "Each species shows its own LED + buzzer pattern (film it: one clip per species)"),
    ("WG-SAF-01", "Power-cycle during an alert: all outputs OFF at boot, returns to IDLE"),
    ("WG-SAF-02", "Buzzer never sounds longer than 10 s continuously"),
    ("WG-SAF-03", "Induced hang (FirmGen breakpoint / test hook) -> task watchdog reboots the board"),
    ("WG-SAF-04", "Stop the broker: amber DEGRADED within 5 s; restart: recovers and re-subscribes"),
    ("WG-CON-01", "Power-cycle the router: node rejoins Wi-Fi and MQTT without a reset"),
    ("WG-SEN-01", "Unplug HC-SR04: error counted in telemetry, no crash"),
    ("WG-NFR-02", "30-min soak: heap_min in telemetry stays above 40 KB"),
]


class Harness:
    def __init__(self, a):
        self.a = a
        self.acks: "queue.Queue[dict]" = queue.Queue()
        self.sensor: list[tuple[float, dict]] = []
        self.status = None
        self.connected = threading.Event()
        self.prefix = f"hil{uuid.uuid4().hex[:4]}"
        self.n = 0
        c = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=f"wg-hil-{self.prefix}")
        c.on_connect = lambda cl, u, f, rc, p=None: (cl.subscribe([(TOPICS.ack, 1), (TOPICS.sensor, 0),
                                                                    (TOPICS.status, 1)]), self.connected.set())
        c.on_message = self.on_message
        self.c = c

    def on_message(self, cl, u, msg):
        try:
            p = json.loads(msg.payload)
        except ValueError:
            p = msg.payload.decode(errors="replace")
        if msg.topic == TOPICS.ack and isinstance(p, dict):
            p["_rx"] = time.time()
            self.acks.put(p)
        elif msg.topic == TOPICS.sensor and isinstance(p, dict):
            self.sensor.append((time.time(), p))
        elif msg.topic == TOPICS.status:
            self.status = p

    def start(self):
        self.c.connect(self.a.host, self.a.port, keepalive=15)
        self.c.loop_start()
        if not self.connected.wait(5):
            sys.exit(f"cannot connect to broker {self.a.host}:{self.a.port}")
        time.sleep(1.5)  # collect retained status + a sensor heartbeat

    # ------------------------------------------------------------ helpers
    def eid(self):
        self.n += 1
        return f"{self.prefix}-{self.n:03d}"

    def event(self, cls="puma", conf=0.9, **extra):
        e = {"v": 1, "event_id": self.eid(), "ts_capture": int(time.time() * 1000), "camera_id": "hil",
             "class": cls, "class_id": SPECIES[cls][0] if cls in SPECIES else 99,
             "confidence": conf, "track_id": -1, "in_road_zone": True, "sensor_confirmed": False,
             "synthetic": True}  # stored as source=synthetic, excluded from "real" latency stats
        e.update(extra)
        return e

    def send(self, payload, raw=False):
        data = payload if raw else json.dumps(payload, separators=(",", ":"))
        self.c.publish(TOPICS.detections, data, qos=1).wait_for_publish(3)
        return time.time()

    def drain(self):
        while not self.acks.empty():
            self.acks.get_nowait()

    def wait_ack(self, eid, timeout=None) -> dict | None:
        end = time.time() + (timeout or self.a.ack_timeout)
        stash = []
        found = None
        while time.time() < end and found is None:
            try:
                a = self.acks.get(timeout=max(0.01, end - time.time()))
            except queue.Empty:
                break
            if a.get("event_id") == eid:
                found = a
            else:
                stash.append(a)
        for a in stash:
            self.acks.put(a)
        return found

    def count_acks(self, eid, window):
        end = time.time() + window
        n = 0
        while time.time() < end:
            try:
                a = self.acks.get(timeout=max(0.01, end - time.time()))
            except queue.Empty:
                break
            n += a.get("event_id") == eid
        return n

    def armed_now(self) -> bool | None:
        recent = [p for t, p in self.sensor if time.time() - t < 2.5]
        return bool(recent[-1].get("armed")) if recent else None

    def set_mode(self, m):
        self.c.publish(TOPICS.mode, m, qos=1, retain=True).wait_for_publish(3)
        time.sleep(0.6)

    def wait_alert_clear(self):
        time.sleep(self.a.alert_s + 0.5)


# ======================================================================= scenarios
def run(h: Harness):
    results = []
    rtts, onboard = [], []

    def record(name, reqs, ok, detail=""):
        results.append({"name": name, "requirements": reqs, "passed": bool(ok), "detail": detail})
        print(f"  [{'PASS' if ok else 'FAIL'}] {name}  ({', '.join(reqs)})  {detail}")

    print("\n== Connectivity & sensing")
    st = h.status if isinstance(h.status, dict) else {"state": h.status}
    record("Node reports online (retained status)", ["WG-CON-02"], st.get("state") == "online",
           f"status={st}")
    t0 = time.time()
    time.sleep(3.2)
    beats = [p for t, p in h.sensor if t >= t0]
    record("Sensor heartbeat >= 1 Hz", ["WG-SEN-04"], len(beats) >= 3, f"{len(beats)} msgs in 3.2 s")
    if beats:
        b = beats[-1]
        keys_ok = all(k in b for k in ("distance_cm", "pir", "armed", "state"))
        record("Sensor payload has distance/pir/armed/state", ["WG-SEN-04"], keys_ok, json.dumps(b)[:120])

    h.set_mode("armed")
    print("\n== Species -> response profile (one event per class)")
    for cls in CLASS_NAMES:
        h.drain()
        armed = h.armed_now()
        e = h.event(cls, 0.9)
        t_send = h.send(e)
        a = h.wait_ack(e["event_id"])
        if not a:
            record(f"{cls}: ACK received", ["WG-ACK-01", "WG-EVT-04"], False, "no ACK")
            continue
        rtts.append((a["_rx"] - t_send) * 1000)
        if isinstance(a.get("t_act_ms"), (int, float)) and isinstance(a.get("t_rx_ms"), (int, float)):
            onboard.append(a["t_act_ms"] - a["t_rx_ms"])
        conf = a.get("confirmed", armed)
        exp = effective_severity(cls, bool(conf))
        ok = a.get("state") in ("ALERT", "EXTEND") and a.get("profile") == cls and a.get("severity") == exp
        record(f"{cls}: profile + severity", ["WG-EVT-04", "WG-EVT-05", "WG-ACK-01"], ok,
               f"state={a.get('state')} profile={a.get('profile')} sev={a.get('severity')} "
               f"(expected {exp}, confirmed={conf}) rtt={rtts[-1]:.0f} ms")
        h.wait_alert_clear()

    if onboard:
        record("On-board RX -> actuate <= 100 ms", ["WG-ACT-03"], max(onboard) <= 100,
               f"max {max(onboard):.0f} ms, median {statistics.median(onboard):.0f} ms over {len(onboard)}")
    else:
        record("On-board RX -> actuate <= 100 ms", ["WG-ACT-03"], False, "ACKs carry no t_rx_ms/t_act_ms")

    print("\n== Robustness")
    h.drain()
    e = h.event("tapir", 0.20)
    h.send(e)
    a = h.wait_ack(e["event_id"])
    record("Low confidence (0.20) ignored", ["WG-EVT-02"],
           a is not None and a.get("state") == "IGNORED" and a.get("reason") == "low_conf",
           f"ack={ {k: a.get(k) for k in ('state', 'reason')} if a else None}")

    h.drain()
    e = h.event("maned_wolf", 0.9)
    h.send(e)
    h.send(e)
    n = h.count_acks(e["event_id"], 2.0)
    record("Duplicate event_id -> exactly one ACK", ["WG-EVT-03"], n == 1, f"{n} ACKs")
    h.wait_alert_clear()

    h.drain()
    h.send("{not json", raw=True)
    h.send({"v": 1, "class": "puma"})  # missing fields
    h.send({"v": 1, "event_id": "x", "class": "puma", "class_id": 3, "confidence": "high"})  # bad type
    e = h.event("puma", 0.9)
    h.send(e)
    a = h.wait_ack(e["event_id"])
    record("Malformed payloads rejected, node keeps working", ["WG-EVT-01"], a is not None,
           "valid event after 3 bad ones was ACKed" if a else "no ACK after malformed input")
    h.wait_alert_clear()

    h.drain()
    e = h.event("giant_anteater", 0.9, extra_field={"nested": [1, 2, 3]}, future="x")
    h.send(e)
    a = h.wait_ack(e["event_id"])
    record("Unknown extra fields tolerated", ["WG-EVT-01"], a is not None and a.get("state") != "IGNORED",
           f"state={a.get('state') if a else None}")
    h.wait_alert_clear()

    h.drain()
    e = h.event("capybara", 0.9)
    e["class_id"] = 42
    h.send(e)
    a = h.wait_ack(e["event_id"])
    record("Unknown class -> generic WARN profile", ["WG-EVT-04"],
           a is not None and a.get("severity") == "WARN" and a.get("profile") == "generic",
           f"profile={a.get('profile') if a else None} sev={a.get('severity') if a else None}")
    h.wait_alert_clear()

    print("\n== Alert extension")
    h.drain()
    e1, e2 = h.event("tapir", 0.9), h.event("tapir", 0.92)
    h.send(e1)
    a1 = h.wait_ack(e1["event_id"])
    time.sleep(1.0)
    h.send(e2)
    a2 = h.wait_ack(e2["event_id"])
    record("Re-detection during alert extends it", ["WG-ACT-04"],
           a1 is not None and a2 is not None and a2.get("state") == "EXTEND",
           f"first={a1.get('state') if a1 else None} second={a2.get('state') if a2 else None}")
    h.wait_alert_clear()

    print("\n== Control")
    h.set_mode("disarmed")
    h.drain()
    e = h.event("tapir", 0.95)
    h.send(e)
    a = h.wait_ack(e["event_id"])
    record("Disarmed mode suppresses actuation", ["WG-SAF-05"],
           a is not None and a.get("state") == "IGNORED" and a.get("reason") == "disarmed",
           f"ack={ {k: a.get(k) for k in ('state', 'reason')} if a else None}")
    h.set_mode("armed")

    h.c.publish(TOPICS.cmd, json.dumps({"cmd": "sim_trip", "duration_s": 4}), qos=1).wait_for_publish(3)
    t0 = time.time()
    armed_seen = False
    while time.time() - t0 < 3:
        if any(p.get("armed") for t, p in h.sensor if t >= t0):
            armed_seen = True
            break
        time.sleep(0.1)
    record("sim_trip command -> node reports ARMED", ["WG-SEN-03", "WG-TST-01"], armed_seen)
    if armed_seen:
        h.drain()
        e = h.event("puma", 0.9)
        h.send(e)
        a = h.wait_ack(e["event_id"])
        record("Sensor-confirmed detection upgrades severity", ["WG-EVT-05"],
               a is not None and a.get("confirmed") is True and a.get("severity") == effective_severity("puma", True),
               f"sev={a.get('severity') if a else None} confirmed={a.get('confirmed') if a else None}")
        h.wait_alert_clear()

    print(f"\n== Round trip over {h.a.rounds} events")
    for i in range(h.a.rounds):
        h.drain()
        e = h.event(CLASS_NAMES[i % 5], 0.9)
        t_send = h.send(e)
        a = h.wait_ack(e["event_id"])
        if a:
            rtts.append((a["_rx"] - t_send) * 1000)
        time.sleep(0.3)
    if rtts:
        s = sorted(rtts)
        p95 = s[min(len(s) - 1, int(round(0.95 * (len(s) - 1))))]
        record("Broker -> ESP32 -> ACK round trip measured", ["WG-ACK-01", "WG-ACT-03"], True,
               f"n={len(s)} p50={statistics.median(s):.0f} ms p95={p95:.0f} ms max={s[-1]:.0f} ms")
    return results, rtts, onboard


def write(results, rtts, onboard, a, started):
    out = EVIDENCE if a.target == "esp32" else EVIDENCE / "rehearsal"
    out.mkdir(parents=True, exist_ok=True)
    passed = sum(r["passed"] for r in results)
    doc = {"started": started, "target": a.target, "node": TOPICS.node, "broker": f"{a.host}:{a.port}",
           "passed": passed, "total": len(results), "results": results,
           "rtt_ms": [round(x, 1) for x in rtts], "onboard_ms": onboard,
           "manual_checks": [{"requirements": r, "check": c} for r, c in MANUAL_CHECKS]}
    (out / "acceptance_results.json").write_text(json.dumps(doc, indent=2))
    md = [f"# HIL acceptance results ({a.target})", "",
          *(["> **REHEARSAL against tools/esp32_sim.py - not hardware evidence.** It shows the test suite and the "
             "contract work end to end; re-run with `--target esp32` on the real board.", ""] if a.target != "esp32" else []),
          f"Started {started} - node `{TOPICS.node}` - broker `{a.host}:{a.port}` - **{passed}/{len(results)} passed**", "",
          "| Scenario | Requirement(s) | Result | Detail |", "|---|---|---|---|"]
    md += [f"| {r['name']} | {', '.join(r['requirements'])} | {'PASS' if r['passed'] else 'FAIL'} | {r['detail']} |"
           for r in results]
    md += ["", "## Manual / physical checks (tick on the day, attach video)", ""]
    md += [f"- [ ] **{r}**: {c}" for r, c in MANUAL_CHECKS]
    (out / "acceptance_results.md").write_text("\n".join(md) + "\n")
    print(f"\n{passed}/{len(results)} passed -> {out / 'acceptance_results.md'}")
    return passed == len(results)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--host", default=os.getenv("MQTT_HOST", "localhost"))
    ap.add_argument("--port", type=int, default=int(os.getenv("MQTT_PORT", "1883")))
    ap.add_argument("--target", default="esp32", choices=["esp32", "sim"])
    ap.add_argument("--ack-timeout", type=float, default=2.0)
    ap.add_argument("--alert-s", type=float, default=5.0, help="node alert duration (PRD default 5 s)")
    ap.add_argument("--rounds", type=int, default=30)
    a = ap.parse_args()
    started = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    h = Harness(a)
    h.start()
    print(f"HIL acceptance against {a.target} via {a.host}:{a.port}")
    results, rtts, onboard = run(h)
    ok = write(results, rtts, onboard, a, started)
    print("\nManual checks still required:")
    for r, c in MANUAL_CHECKS:
        print(f"  - {r}: {c}")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
