from fastapi.testclient import TestClient

import database as db
import main
from mqtt_hub import hub


def client():
    return TestClient(main.app)


def test_no_inference_endpoints_in_live_app():
    paths = {r.path for r in main.app.routes}
    assert "/api/detect/image" not in paths and "/api/detect/frame" not in paths


def test_health_and_state_without_broker():
    with client() as c:
        h = c.get("/api/health").json()
        assert h["status"] == "ok" and h["broker_connected"] is False
        s = c.get("/api/state").json()
        assert {"broker", "node", "sensor", "pipeline", "mode"} <= s.keys()


def test_control_returns_503_without_broker():
    with client() as c:
        assert c.post("/api/control/mode", json={"mode": "armed"}).status_code == 503
        assert c.post("/api/control/mode", json={"mode": "test"}).status_code == 422
        assert c.post("/api/test/alert", json={"species": "puma"}).status_code == 503


def test_detection_ack_flow_records_latency():
    with client() as c:
        hub._dispatch("wildguard/perception/detections",
                      {"v": 1, "event_id": "t-1", "class": "puma", "class_id": 3, "confidence": 0.9,
                       "ts_capture": None})
        hub._dispatch("wildguard/perception/detections",  # QoS1 redelivery: ignored
                      {"v": 1, "event_id": "t-1", "class": "puma", "class_id": 3, "confidence": 0.9})
        hub._dispatch("wildguard/node/esp32-01/ack",
                      {"v": 1, "event_id": "t-1", "state": "ALERT", "profile": "puma", "severity": "LOW",
                       "confirmed": False, "t_rx_ms": 100, "t_act_ms": 104})
        rows = [r for r in c.get("/api/history").json()["records"] if r["event_id"] == "t-1"]
        assert len(rows) == 1
        r = rows[0]
        assert r["ack_state"] == "ALERT" and r["severity"] == "LOW" and r["onboard_ms"] == 4
        assert r["latency_ms"] is not None and r["latency_ms"] >= 0
        m = c.get("/api/metrics/latency").json()
        assert m["acked"] >= 1
        assert "Closed-Loop Evidence Pack" in c.get("/api/evidence/report").text
        csv = c.get("/api/export/csv").text
        assert "latency_ms" in csv.splitlines()[0]


def test_ignored_ack_has_no_latency():
    with client():
        hub._dispatch("wildguard/perception/detections",
                      {"v": 1, "event_id": "t-2", "class": "tapir", "class_id": 0, "confidence": 0.3})
        hub._dispatch("wildguard/node/esp32-01/ack",
                      {"v": 1, "event_id": "t-2", "state": "IGNORED", "reason": "low_conf", "t_rx_ms": 1, "t_act_ms": 1})
        r = [r for r in db.get_detections() if r["event_id"] == "t-2"][0]
        assert r["ack_state"] == "IGNORED" and r["latency_ms"] is None


def test_lwt_marks_node_offline():
    with client() as c:
        hub._dispatch("wildguard/node/esp32-01/status", {"state": "online", "fw": "1.0.0", "rssi": -60})
        assert c.get("/api/state").json()["node"]["reachable"] is True
        hub._dispatch("wildguard/node/esp32-01/status", {"state": "offline"})
        assert c.get("/api/state").json()["node"]["reachable"] is False


def test_species_table():
    with client() as c:
        t = {r["class"]: r for r in c.get("/api/species").json()}
        assert t["puma"]["confirmed_severity"] == "HIGH" and t["puma"]["unconfirmed_severity"] == "LOW"


def test_replay_events_are_not_real_pipegen():
    with client() as c:
        hub._dispatch("wildguard/perception/detections",
                      {"v": 1, "event_id": "r-1", "class": "puma", "class_id": 3, "confidence": 0.9, "replay": True})
        r = [r for r in db.get_detections() if r["event_id"] == "r-1"][0]
        assert r["source"] == "replay"
        real = c.get("/api/metrics/latency", params={"include_synthetic": False}).json()
        assert real["events"] == len([x for x in db.get_detections(limit=10000) if x["source"] == "pipegen"])
