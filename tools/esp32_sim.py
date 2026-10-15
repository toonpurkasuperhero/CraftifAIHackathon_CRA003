#!/usr/bin/env python3
"""ESP32 node simulator - speaks MQTT contract v1 exactly like the FirmGen firmware should.

NOT a replacement for the real board (the hackathon requires real hardware). Use it to:
  * build and rehearse backend + dashboard + bridge before the firmware exists,
  * check that tools/hil_acceptance.py passes against a reference implementation,
  * isolate faults on demo day (sim works but board doesn't -> firmware/Wi-Fi problem).

Behaviour follows firmware/prd/WildGuard_PRD.md. Prints UART-style lines in the WG-LOG-01 format.
Interactive keys (type + Enter): t = trip sensor, c = clear sensor, m = PIR motion, q = quit.
"""
from __future__ import annotations

import argparse
import json
import os
import random
import sys
import threading
import time
from collections import deque
from pathlib import Path

import paho.mqtt.client as mqtt

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "shared"))
from wg_contract import SPECIES, TOPICS, effective_severity, normalise_class, validate_detection  # noqa: E402

FW_VERSION = "sim-1.0.0"
BOOT = time.monotonic()


def uptime_ms() -> int:
    return int((time.monotonic() - BOOT) * 1000)


def uart(msg: str):
    print(f"[WG] {msg}", flush=True)


class SimNode:
    def __init__(self, a):
        self.a = a
        self.mode = "armed"
        self.state = "BOOT"
        self.distance = 250.0
        self.pir = False
        self.trip_until = 0.0
        self.armed_hold_until = 0.0
        self.alert = None  # dict(profile, severity, until)
        self.seen_ids: deque = deque(maxlen=32)
        self.counters = {"rx": 0, "malformed": 0, "ignored": 0, "actions": 0, "dupes": 0}
        self.lock = threading.Lock()
        self.connected = False
        c = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=f"{TOPICS.node}-sim")
        c.will_set(TOPICS.status, json.dumps({"state": "offline"}), qos=1, retain=True)
        c.on_connect = self.on_connect
        c.on_disconnect = self.on_disconnect
        c.on_message = self.on_message
        c.reconnect_delay_set(1, 8)
        self.c = c

    # ------------------------------------------------------------ connectivity
    def on_connect(self, client, userdata, flags, rc, props=None):
        if rc.is_failure:
            return
        self.connected = True
        client.subscribe([(TOPICS.detections, 1), (TOPICS.mode, 1), (TOPICS.cmd, 1)])
        client.publish(TOPICS.status, json.dumps({"state": "online", "fw": FW_VERSION, "rssi": -52,
                                                   "uptime_s": uptime_ms() // 1000}), qos=1, retain=True)
        uart("MQTT connected, subscribed detections/mode/cmd")
        if self.state in ("BOOT", "DEGRADED"):
            self.set_state("IDLE")

    def on_disconnect(self, client, userdata, flags, rc, props=None):
        self.connected = False
        uart(f"MQTT lost rc={rc} -> DEGRADED (sensor-only amber warning)")
        self.set_state("DEGRADED")

    def set_state(self, s):
        if s != self.state:
            uart(f"STATE {self.state} -> {s}")
            self.state = s

    # -------------------------------------------------------------- messages
    def on_message(self, client, userdata, msg):
        t_rx = uptime_ms()
        if msg.topic == TOPICS.mode:
            m = msg.payload.decode(errors="replace").strip().strip('"').lower()
            if m in ("armed", "disarmed"):
                self.mode = m
                uart(f"MODE {m}")
            return
        if msg.topic == TOPICS.cmd:
            try:
                p = json.loads(msg.payload)
            except ValueError:
                return
            self.on_cmd(p)
            return
        # detection
        self.counters["rx"] += 1
        try:
            p = json.loads(msg.payload)
        except ValueError:
            self.counters["malformed"] += 1
            uart(f"RX malformed JSON ({len(msg.payload)} B) dropped, count={self.counters['malformed']}")
            return
        errs = validate_detection(p)
        if errs:
            self.counters["malformed"] += 1
            uart(f"RX invalid event dropped: {'; '.join(errs)}")
            return
        eid = p["event_id"]
        with self.lock:
            if eid in self.seen_ids:
                self.counters["dupes"] += 1
                uart(f"RX duplicate id={eid} ignored")
                return
            self.seen_ids.append(eid)
        cls = normalise_class(p["class"])
        uart(f"RX id={eid} class={p['class']} conf={p['confidence']:.2f}")
        if self.a.onboard_delay_ms:
            time.sleep(self.a.onboard_delay_ms / 1000)
        if self.mode == "disarmed":
            return self.ack(eid, "IGNORED", None, None, t_rx, reason="disarmed")
        if p["confidence"] < self.a.min_conf:
            return self.ack(eid, "IGNORED", None, None, t_rx, reason="low_conf")
        confirmed = self.is_armed()
        sev = effective_severity(cls, confirmed)
        profile = cls if cls in SPECIES else "generic"
        with self.lock:
            extend = self.alert is not None and self.alert["until"] > time.monotonic() and \
                SEV_RANK[self.alert["severity"]] >= SEV_RANK[sev]
            until = time.monotonic() + self.a.alert_s
            if extend:
                self.alert["until"] = until
            else:
                self.alert = {"profile": profile, "severity": sev, "until": until}
            self.counters["actions"] += 1
        self.set_state("ALERT")
        t_act = uptime_ms()
        uart(f"ACT {'extend' if extend else 'start'} profile={profile} sev={sev} confirmed={confirmed} dt={t_act - t_rx}ms")
        self.ack(eid, "EXTEND" if extend else "ALERT", profile, sev, t_rx, confirmed=confirmed, t_act=t_act)

    def ack(self, eid, state, profile, sev, t_rx, reason=None, confirmed=None, t_act=None):
        if self.a.drop_acks:
            uart(f"ACK suppressed (--drop-acks) id={eid}")
            return
        a = {"v": 1, "event_id": eid, "state": state, "t_rx_ms": t_rx, "t_act_ms": t_act or uptime_ms()}
        if profile:
            a.update(profile=profile, severity=sev, confirmed=confirmed)
        if reason:
            a["reason"] = reason
            self.counters["ignored"] += 1
            uart(f"IGNORED id={eid} reason={reason}")
        self.c.publish(TOPICS.ack, json.dumps(a, separators=(",", ":")), qos=1)
        uart(f"ACK sent id={eid} state={state}")

    def on_cmd(self, p):
        cmd = p.get("cmd")
        uart(f"CMD {cmd}")
        if cmd == "sim_trip":
            self.trip_until = time.monotonic() + float(p.get("duration_s", 5))
        elif cmd == "selftest":
            threading.Thread(target=self.selftest, daemon=True).start()
        elif cmd == "reboot":
            uart("reboot requested (simulated: outputs OFF, back to IDLE)")
            self.alert = None
            self.set_state("IDLE")

    def selftest(self):
        self.set_state("TEST")
        for cls in SPECIES:
            uart(f"TEST profile={cls}")
            time.sleep(1.0)
        uart("TEST done")
        self.set_state("IDLE")

    # --------------------------------------------------------------- sensing
    def is_armed(self) -> bool:
        return time.monotonic() < self.armed_hold_until

    def sense_loop(self):
        last_pub = 0.0
        last_tel = 0.0
        last_key = None
        next_auto = time.monotonic() + self.a.auto_trip_every if self.a.auto_trip_every else None
        while True:
            now = time.monotonic()
            if next_auto and now >= next_auto:
                self.trip_until = now + 4
                next_auto = now + self.a.auto_trip_every
                uart("SENSOR auto-trip (rehearsal, 4 s)")
            tripped = now < self.trip_until
            self.distance = random.uniform(8, 15) if tripped else random.uniform(180, 320)
            near = self.distance < self.a.threshold_cm
            if near or self.pir:
                self.armed_hold_until = now + self.a.hold_s
            armed = self.is_armed()
            if self.alert and self.alert["until"] <= now:
                uart(f"ACT end profile={self.alert['profile']}")
                self.alert = None
            if self.state not in ("DEGRADED", "TEST", "BOOT"):
                if self.mode == "disarmed":
                    self.set_state("DISARMED")
                elif self.alert:
                    self.set_state("ALERT")
                else:
                    self.set_state("ARMED" if armed else "IDLE")
            key = (armed, self.pir, self.state)
            if self.connected and (key != last_key or now - last_pub >= 1.0):
                last_key, last_pub = key, now
                self.c.publish(TOPICS.sensor, json.dumps({
                    "v": 1, "distance_cm": round(self.distance, 1), "pir": self.pir, "armed": armed,
                    "state": self.state, "mode": self.mode, "threshold_cm": self.a.threshold_cm,
                }, separators=(",", ":")), qos=0)
            if self.connected and now - last_tel >= 2.0:
                last_tel = now
                self.c.publish(TOPICS.telemetry, json.dumps({
                    "v": 1, "uptime_s": uptime_ms() // 1000, "heap_free": 182_000 - random.randint(0, 3000),
                    "heap_min": 171_500, "state": self.state, "rssi": -52 + random.randint(-3, 3),
                    **self.counters,
                }, separators=(",", ":")), qos=0)
            time.sleep(0.1)

    def keys(self):
        for line in sys.stdin:
            k = line.strip().lower()
            if k == "t":
                self.trip_until = time.monotonic() + 5
                uart("SENSOR trip (5 s)")
            elif k == "c":
                self.trip_until = 0
                self.pir = False
            elif k == "m":
                self.pir = not self.pir
                uart(f"PIR {'motion' if self.pir else 'clear'}")
            elif k == "q":
                os._exit(0)

    def run(self):
        uart(f"boot fw={FW_VERSION} node={TOPICS.node} outputs OFF")
        self.c.connect_async(self.a.host, self.a.port, keepalive=10)
        self.c.loop_start()
        threading.Thread(target=self.keys, daemon=True).start()
        self.sense_loop()


SEV_RANK = {"WARN": 0, "LOW": 1, "MEDIUM": 2, "HIGH": 3, "CRITICAL": 4}

if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--host", default=os.getenv("MQTT_HOST", "localhost"))
    ap.add_argument("--port", type=int, default=int(os.getenv("MQTT_PORT", "1883")))
    ap.add_argument("--min-conf", type=float, default=0.50)
    ap.add_argument("--threshold-cm", type=float, default=20.0)
    ap.add_argument("--hold-s", type=float, default=3.0, help="ARMED hold-off after sensor clears")
    ap.add_argument("--alert-s", type=float, default=5.0)
    ap.add_argument("--onboard-delay-ms", type=float, default=0, help="inject RX->ACT delay (test the 100 ms check)")
    ap.add_argument("--drop-acks", action="store_true", help="never ACK (test dashboard timeouts)")
    ap.add_argument("--auto-trip-every", type=float, default=0, help="rehearsal: simulate a 4 s sensor trip every N s")
    SimNode(ap.parse_args()).run()
