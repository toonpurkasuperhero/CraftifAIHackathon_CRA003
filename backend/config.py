"""Backend configuration. Values come from environment variables or backend/.env."""
import os
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent
REPO_ROOT = BACKEND_DIR.parent
sys.path.insert(0, str(REPO_ROOT / "shared"))


def _load_dotenv(path: Path) -> None:
    """Tiny .env loader so we do not need python-dotenv. Real env vars win."""
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


_load_dotenv(BACKEND_DIR / ".env")

MQTT_HOST = os.getenv("MQTT_HOST", "localhost")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))
MQTT_USERNAME = os.getenv("MQTT_USERNAME") or None
MQTT_PASSWORD = os.getenv("MQTT_PASSWORD") or None

API_HOST = os.getenv("API_HOST", "0.0.0.0")
API_PORT = int(os.getenv("API_PORT", "8001"))
CORS_ORIGINS = [o.strip() for o in os.getenv("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(",") if o.strip()]

DB_PATH = Path(os.getenv("WG_DB_PATH", str(BACKEND_DIR / "detections.db")))

# Node is considered offline if no sensor heartbeat for this long (in addition to the LWT)
NODE_STALE_S = float(os.getenv("NODE_STALE_S", "5"))
# Pipeline is considered down if the bridge has not seen a PipeGen message for this long
PIPELINE_STALE_S = float(os.getenv("PIPELINE_STALE_S", "10"))
# An alert with no ACK after this long is marked as a timeout
ACK_TIMEOUT_S = float(os.getenv("ACK_TIMEOUT_S", "3"))

PIPELINE_INFO_PATH = REPO_ROOT / "perception" / "reports" / "pipeline_info.json"
ACCEPTANCE_RESULTS_PATH = REPO_ROOT / "docs" / "evidence" / "acceptance_results.json"
