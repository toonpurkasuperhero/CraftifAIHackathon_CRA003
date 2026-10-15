"""SQLite persistence for the closed loop.

detections    one row per perception event (from PipeGen via the bridge), updated when the ESP32 ACKs
sensor_events ESP32 sensor state changes (ARMED transitions, PIR edges)
node_status   ESP32 online/offline history (from the retained status topic / LWT)

Rows written before the hackathon (source = 'image' / 'webcam', ONNX on CPU) are kept and shown as legacy.
"""
import json
import sqlite3
import statistics
import threading
from datetime import datetime

from config import DB_PATH

_lock = threading.Lock()

DETECTION_COLUMNS = {
    # column: type  (added to old databases by migrate())
    "event_id": "TEXT",
    "track_id": "INTEGER",
    "camera_id": "TEXT",
    "severity": "TEXT",
    "sensor_confirmed": "INTEGER",
    "in_road_zone": "INTEGER",
    "action_profile": "TEXT",
    "ack_state": "TEXT",
    "ts_capture_ms": "INTEGER",
    "ack_ts_ms": "INTEGER",
    "latency_ms": "REAL",
    "onboard_ms": "REAL",
}


def get_connection():
    conn = sqlite3.connect(DB_PATH, timeout=10, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def _now_str():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def init_db():
    with _lock:
        conn = get_connection()
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("""
            CREATE TABLE IF NOT EXISTS detections (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                animal TEXT NOT NULL,
                confidence REAL NOT NULL,
                source TEXT NOT NULL,
                thumbnail TEXT,
                bbox TEXT,
                session_id TEXT
            )
        """)
        existing = {r["name"] for r in conn.execute("PRAGMA table_info(detections)")}
        for col, typ in DETECTION_COLUMNS.items():
            if col not in existing:
                conn.execute(f"ALTER TABLE detections ADD COLUMN {col} {typ}")
        conn.execute("""
            CREATE TABLE IF NOT EXISTS sensor_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                distance_cm REAL,
                pir INTEGER,
                armed INTEGER,
                state TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS node_status (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                node_id TEXT NOT NULL,
                status TEXT NOT NULL,
                fw_version TEXT,
                rssi INTEGER
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_det_ts ON detections(timestamp)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_det_animal ON detections(animal)")
        conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_det_event ON detections(event_id) WHERE event_id IS NOT NULL")
        conn.commit()
        conn.close()


# ------------------------------------------------------------------ detections
def insert_event(evt: dict, source: str = "pipegen") -> int | None:
    """Insert a perception event. Duplicate event_ids are ignored (returns None)."""
    with _lock:
        conn = get_connection()
        try:
            cur = conn.execute(
                """INSERT OR IGNORE INTO detections
                   (timestamp, animal, confidence, source, bbox, event_id, track_id, camera_id,
                    sensor_confirmed, in_road_zone, ts_capture_ms)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    _now_str(),
                    evt.get("class", "unknown"),
                    float(evt.get("confidence", 0)),
                    source,
                    json.dumps(evt.get("bbox")) if evt.get("bbox") is not None else None,
                    evt.get("event_id"),
                    evt.get("track_id"),
                    evt.get("camera_id"),
                    int(bool(evt.get("sensor_confirmed"))) if "sensor_confirmed" in evt else None,
                    int(bool(evt.get("in_road_zone"))) if "in_road_zone" in evt else None,
                    evt.get("ts_capture"),
                ),
            )
            conn.commit()
            return cur.lastrowid if cur.rowcount else None
        finally:
            conn.close()


def apply_ack(event_id: str, ack: dict, ack_ts_ms: int, latency_ms: float | None) -> bool:
    onboard = None
    acted = ack.get("state") in ("ALERT", "EXTEND")
    if acted and isinstance(ack.get("t_rx_ms"), (int, float)) and isinstance(ack.get("t_act_ms"), (int, float)):
        onboard = float(ack["t_act_ms"]) - float(ack["t_rx_ms"])
    with _lock:
        conn = get_connection()
        try:
            cur = conn.execute(
                """UPDATE detections SET ack_state=?, action_profile=?, severity=?, ack_ts_ms=?, latency_ms=?,
                       onboard_ms=?, sensor_confirmed=COALESCE(?, sensor_confirmed)
                   WHERE event_id=?""",
                (
                    ack.get("state"),
                    ack.get("profile"),
                    ack.get("severity"),
                    ack_ts_ms,
                    latency_ms,
                    onboard,
                    int(bool(ack["confirmed"])) if "confirmed" in ack else None,
                    event_id,
                ),
            )
            conn.commit()
            return cur.rowcount > 0
        finally:
            conn.close()


def get_ts_capture(event_id: str):
    conn = get_connection()
    row = conn.execute("SELECT ts_capture_ms FROM detections WHERE event_id=?", (event_id,)).fetchone()
    conn.close()
    return row["ts_capture_ms"] if row else None


def mark_ack_timeout(event_id: str) -> None:
    with _lock:
        conn = get_connection()
        conn.execute("UPDATE detections SET ack_state='TIMEOUT' WHERE event_id=? AND ack_state IS NULL", (event_id,))
        conn.commit()
        conn.close()


def get_detections(animal=None, date_from=None, date_to=None, min_confidence=None, limit=200,
                   severity=None, source=None):
    conn = get_connection()
    query = "SELECT * FROM detections WHERE 1=1"
    params = []
    if animal:
        query += " AND animal = ?"
        params.append(animal)
    if date_from:
        query += " AND timestamp >= ?"
        params.append(date_from)
    if date_to:
        query += " AND timestamp <= ?"
        params.append(date_to + " 23:59:59")
    if min_confidence is not None:
        query += " AND confidence >= ?"
        params.append(min_confidence)
    if severity:
        query += " AND severity = ?"
        params.append(severity)
    if source:
        query += " AND source = ?"
        params.append(source)
    query += " ORDER BY id DESC LIMIT ?"
    params.append(limit)
    rows = conn.execute(query, params).fetchall()
    conn.close()
    result = []
    for r in rows:
        d = dict(r)
        d.pop("thumbnail", None)  # legacy column, no longer produced
        if d.get("bbox"):
            try:
                d["bbox"] = json.loads(d["bbox"])
            except ValueError:
                pass
        for b in ("sensor_confirmed", "in_road_zone"):
            if d.get(b) is not None:
                d[b] = bool(d[b])
        result.append(d)
    return result


def delete_detection(record_id: int) -> bool:
    with _lock:
        conn = get_connection()
        cur = conn.execute("DELETE FROM detections WHERE id = ?", (record_id,))
        conn.commit()
        conn.close()
        return cur.rowcount > 0


# --------------------------------------------------------------- sensor / node
def insert_sensor_event(distance_cm, pir, armed, state):
    with _lock:
        conn = get_connection()
        conn.execute(
            "INSERT INTO sensor_events (timestamp, distance_cm, pir, armed, state) VALUES (?,?,?,?,?)",
            (_now_str(), distance_cm, None if pir is None else int(bool(pir)),
             None if armed is None else int(bool(armed)), state),
        )
        conn.commit()
        conn.close()


def insert_node_status(node_id, status, fw_version=None, rssi=None):
    with _lock:
        conn = get_connection()
        conn.execute(
            "INSERT INTO node_status (timestamp, node_id, status, fw_version, rssi) VALUES (?,?,?,?,?)",
            (_now_str(), node_id, status, fw_version, rssi),
        )
        conn.commit()
        conn.close()


def get_node_status_history(limit=50):
    conn = get_connection()
    rows = [dict(r) for r in conn.execute("SELECT * FROM node_status ORDER BY id DESC LIMIT ?", (limit,))]
    conn.close()
    return rows


# ------------------------------------------------------------------- analytics
def _percentile(values, p):
    if not values:
        return None
    s = sorted(values)
    k = (len(s) - 1) * p / 100
    f = int(k)
    c = min(f + 1, len(s) - 1)
    return round(s[f] + (s[c] - s[f]) * (k - f), 1)


def get_latency_metrics(include_synthetic=True):
    conn = get_connection()
    q = "SELECT latency_ms, onboard_ms, source, ack_state FROM detections WHERE event_id IS NOT NULL"
    rows = [dict(r) for r in conn.execute(q)]
    conn.close()
    if not include_synthetic:  # "real" = live PipeGen events only
        rows = [r for r in rows if r["source"] == "pipegen"]
    lat = [r["latency_ms"] for r in rows if r["latency_ms"] is not None]
    onb = [r["onboard_ms"] for r in rows if r["onboard_ms"] is not None]
    timeouts = sum(1 for r in rows if r["ack_state"] == "TIMEOUT")
    bins = [25, 50, 100, 200, 400, 800, 1600]
    hist = []
    lo = 0
    for hi in bins + [None]:
        n = sum(1 for v in lat if v >= lo and (hi is None or v < hi))
        hist.append({"bucket": f"{lo}-{hi}" if hi else f"{lo}+", "count": n})
        lo = hi or lo
    return {
        "events": len(rows),
        "acked": len(lat),
        "timeouts": timeouts,
        "ack_rate": round(len(lat) / len(rows), 3) if rows else None,
        "e2e_ms": {
            "p50": _percentile(lat, 50), "p95": _percentile(lat, 95),
            "mean": round(statistics.fmean(lat), 1) if lat else None,
            "min": round(min(lat), 1) if lat else None, "max": round(max(lat), 1) if lat else None,
        },
        "onboard_ms": {
            "p50": _percentile(onb, 50), "p95": _percentile(onb, 95),
            "max": round(max(onb), 1) if onb else None,
        },
        "histogram": hist,
    }


def get_analytics():
    conn = get_connection()
    animal_counts = {r["animal"]: r["cnt"] for r in conn.execute(
        "SELECT animal, COUNT(*) as cnt FROM detections GROUP BY animal")}
    today = datetime.now().strftime("%Y-%m-%d")
    today_count = conn.execute(
        "SELECT COUNT(*) as cnt FROM detections WHERE timestamp LIKE ?", (today + "%",)).fetchone()["cnt"]
    total = conn.execute("SELECT COUNT(*) as cnt FROM detections").fetchone()["cnt"]
    most_frequent = max(animal_counts, key=animal_counts.get) if animal_counts else None

    hourly = {str(i): 0 for i in range(24)}
    for row in conn.execute("SELECT SUBSTR(timestamp, 12, 2) as hour, COUNT(*) as cnt FROM detections GROUP BY hour"):
        h = (row["hour"] or "0").lstrip("0") or "0"
        hourly[h] = row["cnt"]

    daily = {r["day"]: r["cnt"] for r in conn.execute(
        "SELECT SUBSTR(timestamp, 1, 10) as day, COUNT(*) as cnt FROM detections GROUP BY day ORDER BY day DESC LIMIT 14")}
    sources = {r["source"]: r["cnt"] for r in conn.execute(
        "SELECT source, COUNT(*) as cnt FROM detections GROUP BY source")}
    severities = {r["severity"]: r["cnt"] for r in conn.execute(
        "SELECT severity, COUNT(*) as cnt FROM detections WHERE severity IS NOT NULL GROUP BY severity")}
    profiles = {r["action_profile"]: r["cnt"] for r in conn.execute(
        "SELECT action_profile, COUNT(*) as cnt FROM detections WHERE action_profile IS NOT NULL GROUP BY action_profile")}
    confirmed = {("confirmed" if r["sc"] else "unconfirmed"): r["cnt"] for r in conn.execute(
        "SELECT sensor_confirmed as sc, COUNT(*) as cnt FROM detections WHERE sensor_confirmed IS NOT NULL GROUP BY sc")}
    conn.close()
    return {
        "total": total,
        "today": today_count,
        "most_frequent": most_frequent,
        "animal_counts": animal_counts,
        "hourly": hourly,
        "daily": dict(reversed(list(daily.items()))),
        "sources": sources,
        "severities": severities,
        "profiles": profiles,
        "sensor_confirmation": confirmed,
    }
