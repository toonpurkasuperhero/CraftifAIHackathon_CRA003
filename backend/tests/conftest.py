import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
os.environ.setdefault("WG_DB_PATH", str(Path(tempfile.mkdtemp()) / "test.db"))
os.environ.setdefault("MQTT_HOST", "127.0.0.1")
os.environ.setdefault("MQTT_PORT", "1")  # nothing listens: tests must not need a broker
for p in (ROOT / "backend", ROOT / "shared", ROOT / "bridge"):
    sys.path.insert(0, str(p))
