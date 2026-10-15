"""
WildGuard MQTT contract (v1) - single source of truth for the Python side.

Used by: backend/, bridge/, tools/esp32_sim.py, tools/hil_acceptance.py.
The ESP32 firmware implements the same contract from firmware/prd/WildGuard_PRD.md
(FirmGen generates it; it does NOT import this file). docs/mqtt-contract.md is the
human-readable version. If you change anything here, change both documents too.
"""
from __future__ import annotations

import os
from dataclasses import dataclass

CONTRACT_VERSION = 1

# --------------------------------------------------------------------------- topics
TOPIC_PREFIX = os.getenv("WG_TOPIC_PREFIX", "wildguard")
NODE_ID = os.getenv("WG_NODE_ID", "esp32-01")


@dataclass(frozen=True)
class Topics:
    prefix: str = TOPIC_PREFIX
    node: str = NODE_ID

    # perception -> ESP32 / backend (QoS 1, not retained)
    @property
    def detections(self) -> str:
        return f"{self.prefix}/perception/detections"

    # ESP32 -> backend (QoS 0): distance, PIR, armed
    @property
    def sensor(self) -> str:
        return f"{self.prefix}/node/{self.node}/sensor"

    # ESP32 -> backend (QoS 1, retained, also the MQTT Last Will)
    @property
    def status(self) -> str:
        return f"{self.prefix}/node/{self.node}/status"

    # ESP32 -> backend (QoS 1): action started for event_id
    @property
    def ack(self) -> str:
        return f"{self.prefix}/node/{self.node}/ack"

    # ESP32 -> backend (QoS 0): bonus runtime telemetry
    @property
    def telemetry(self) -> str:
        return f"{self.prefix}/node/{self.node}/telemetry"

    # dashboard -> ESP32 (QoS 1, retained): "armed" | "disarmed"
    @property
    def mode(self) -> str:
        return f"{self.prefix}/control/mode"

    # dashboard -> ESP32 (QoS 1, NOT retained): one-shot test commands
    @property
    def cmd(self) -> str:
        return f"{self.prefix}/control/cmd"

    # bridge -> backend (QoS 1, retained + LWT): bridge liveness and pipeline stats
    @property
    def bridge_status(self) -> str:
        return f"{self.prefix}/bridge/status"

    # wildcard for the backend
    @property
    def all(self) -> str:
        return f"{self.prefix}/#"


TOPICS = Topics()

# ----------------------------------------------------------------------- species
# class_id order MUST match training/bra_dataset.yaml and perception/labels.txt
SEVERITIES = ["WARN", "LOW", "MEDIUM", "HIGH", "CRITICAL"]

SPECIES = {
    # name:          (class_id, IUCN status,         base severity, LED pattern,                buzzer)
    "tapir":          (0, "Vulnerable",         "CRITICAL", "fast red strobe 8 Hz + amber", "3 long beeps, repeating"),
    "jaguarundi":     (1, "Least Concern",      "LOW",      "amber blink 1 Hz",             "silent"),
    "maned_wolf":     (2, "Near Threatened",    "HIGH",     "red/amber alternate 2 Hz",     "2 short beeps"),
    "puma":           (3, "Least Concern",      "MEDIUM",   "slow red pulse 1 Hz",          "1 beep"),
    "giant_anteater": (4, "Vulnerable",         "HIGH",     "red strobe 4 Hz",              "2 beeps"),
}
CLASS_NAMES = sorted(SPECIES, key=lambda k: SPECIES[k][0])  # index == class_id

# DeepStream / PipeGen labels may use spaces or capitals ("Maned Wolf")
_ALIASES = {n.replace("_", " "): n for n in SPECIES} | {n.replace("_", ""): n for n in SPECIES}


def normalise_class(label) -> str | None:
    """Map a raw detector label or class id to a contract class name (None if not one of ours)."""
    if label is None:
        return None
    if isinstance(label, (int, float)) or (isinstance(label, str) and label.strip().isdigit()):
        idx = int(label)
        return CLASS_NAMES[idx] if 0 <= idx < len(CLASS_NAMES) else None
    key = str(label).strip().lower()
    if key in SPECIES:
        return key
    return _ALIASES.get(key) or _ALIASES.get(key.replace("-", " "))


def base_severity(cls: str | None) -> str:
    return SPECIES[cls][2] if cls in SPECIES else "WARN"


def effective_severity(cls: str | None, sensor_confirmed: bool) -> str:
    """Sensor-fusion rule (PRD WG-EVT-05).

    Confirmed by the ESP32's own ARMED state -> one level up (max CRITICAL).
    Not confirmed -> one level down (min WARN). Unknown classes are always WARN.
    """
    if cls not in SPECIES:
        return "WARN"
    i = SEVERITIES.index(base_severity(cls))
    i = min(i + 1, len(SEVERITIES) - 1) if sensor_confirmed else max(i - 1, 0)
    return SEVERITIES[i]


# --------------------------------------------------------------------- validation
REQUIRED_DETECTION_FIELDS = {"v": int, "event_id": str, "class": str, "class_id": int, "confidence": (int, float)}
MAX_PAYLOAD_BYTES = 256


def validate_detection(p) -> list[str]:
    """Return a list of problems (empty = valid). Mirrors PRD WG-EVT-01."""
    if not isinstance(p, dict):
        return ["payload is not a JSON object"]
    errs = []
    for k, t in REQUIRED_DETECTION_FIELDS.items():
        if k not in p:
            errs.append(f"missing '{k}'")
        elif not isinstance(p[k], t) or isinstance(p[k], bool):
            errs.append(f"'{k}' has wrong type")
    if not errs:
        if p["v"] != CONTRACT_VERSION:
            errs.append(f"unsupported version {p['v']}")
        if not 0.0 <= float(p["confidence"]) <= 1.0:
            errs.append("confidence out of range")
        if not 0 < len(p["event_id"]) <= 32:
            errs.append("event_id length must be 1..32")
    return errs


MODES = ("armed", "disarmed")
COMMANDS = ("selftest", "sim_trip", "reboot")
