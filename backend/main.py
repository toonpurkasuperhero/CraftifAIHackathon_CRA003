"""WildGuard mission-control backend.

Perception runs in the PipeGen/DeepStream pipeline (TensorRT) and action runs on the
FirmGen-generated ESP32 firmware. This service only observes and controls the loop over MQTT:
  - subscribes to detections, sensor, status, ACK, telemetry and bridge topics
  - stores events + measured end-to-end latency in SQLite
  - pushes everything live to the dashboard over a WebSocket
  - lets the operator arm/disarm the node and fire synthetic test alerts

There is intentionally NO inference endpoint here (the old ONNX/CPU path lives in
training/onnx_reference.py for offline accuracy comparison only).
"""
import asyncio
import csv
import io
import json
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Literal, Optional

from fastapi import FastAPI, HTTPException, Query, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse, StreamingResponse
from pydantic import BaseModel, Field

import config  # noqa: F401  (sets up sys.path for wg_contract)
import database as db
import evidence
from mqtt_hub import hub
from wg_contract import CLASS_NAMES, SPECIES, TOPICS, effective_severity


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.init_db()
    hub.start(asyncio.get_running_loop())
    print(f"[Startup] DB ready, MQTT -> {config.MQTT_HOST}:{config.MQTT_PORT}")
    yield
    hub.stop()


app = FastAPI(title="WildGuard Mission Control API", version="2.0.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.CORS_ORIGINS,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --------------------------------------------------------------------------- models
class ModeRequest(BaseModel):
    mode: Literal["armed", "disarmed"]


class TestAlertRequest(BaseModel):
    species: str
    confidence: float = Field(0.9, ge=0, le=1)
    in_road_zone: bool = True


class CommandRequest(BaseModel):
    cmd: Literal["selftest", "sim_trip", "reboot"]
    duration_s: Optional[int] = Field(None, ge=1, le=60)


# ------------------------------------------------------------------------ live state
@app.get("/api/health")
def health():
    s = hub.snapshot()
    return {
        "status": "ok",
        "timestamp": datetime.now().isoformat(),
        "broker_connected": s["broker"]["connected"],
        "node_online": s["node"]["reachable"],
        "node_last_seen_ms": s["node"]["last_seen_ms"],
        "pipeline_alive": s["pipeline"]["alive"],
        "bridge_online": (s["bridge"] or {}).get("state") == "online",
    }


@app.get("/api/state")
def state():
    """Full live snapshot of the loop (broker, pipeline, node, sensor, mode, last alert/ACK)."""
    return hub.snapshot()


@app.websocket("/api/ws")
async def ws_events(ws: WebSocket):
    await ws.accept()
    q = hub.subscribe()
    loop = asyncio.get_running_loop()
    try:
        await ws.send_json({"type": "snapshot", "data": hub.snapshot()})
        next_snap = loop.time() + 5
        while True:
            try:
                msg = await asyncio.wait_for(q.get(), timeout=max(0.1, next_snap - loop.time()))
                await ws.send_json(msg)
            except asyncio.TimeoutError:
                pass
            if loop.time() >= next_snap:  # periodic full resync, even when the stream is busy
                await ws.send_json({"type": "snapshot", "data": hub.snapshot()})
                next_snap = loop.time() + 5
    except (WebSocketDisconnect, RuntimeError):
        pass
    finally:
        hub.unsubscribe(q)


@app.get("/api/sensor/latest")
def sensor_latest():
    """Latest ESP32 sensor state from MQTT (replaces the old sensor_log.csv polling)."""
    s = hub.snapshot()
    sensor = s["sensor"] or {}
    return {
        "distance_cm": sensor.get("distance_cm"),
        "pir": sensor.get("pir"),
        "armed": sensor.get("armed", False),
        "state": sensor.get("state"),
        "threshold_cm": sensor.get("threshold_cm"),
        "node_online": s["node"]["reachable"],
        "received_ms": sensor.get("received_ms"),
    }


# ---------------------------------------------------------------------- control
@app.post("/api/control/mode")
def set_mode(req: ModeRequest):
    if not hub.publish(TOPICS.mode, req.mode, qos=1, retain=True):
        raise HTTPException(503, "MQTT broker not connected")
    return {"status": "published", "mode": req.mode}


@app.post("/api/control/cmd")
def send_cmd(req: CommandRequest):
    payload = {"cmd": req.cmd}
    if req.duration_s:
        payload["duration_s"] = req.duration_s
    if not hub.publish(TOPICS.cmd, payload, qos=1, retain=False):
        raise HTTPException(503, "MQTT broker not connected")
    return {"status": "published", **payload}


@app.post("/api/test/alert")
def test_alert(req: TestAlertRequest):
    """Publish a synthetic detection (marked synthetic=true) to exercise the actuator path without a camera."""
    evt = hub.publish_synthetic(req.species, req.confidence, req.in_road_zone)
    if not evt:
        raise HTTPException(503, "MQTT broker not connected")
    return {"status": "published", "event": evt}


# ---------------------------------------------------------------------- metrics
@app.get("/api/metrics/latency")
def latency(include_synthetic: bool = Query(True)):
    return db.get_latency_metrics(include_synthetic)


@app.get("/api/pipeline/info")
def pipeline_info():
    """PipeGen report summary (engine, precision, FPS, accuracy per precision), exported by hand
    from PipeGen's Compiler-stage report into perception/reports/pipeline_info.json."""
    try:
        return json.loads(config.PIPELINE_INFO_PATH.read_text())
    except FileNotFoundError:
        raise HTTPException(404, f"{config.PIPELINE_INFO_PATH.name} not found - fill it from the PipeGen speed report")
    except ValueError as e:
        raise HTTPException(500, f"pipeline_info.json is not valid JSON: {e}")


@app.get("/api/species")
def species():
    """Species -> response profile table (same table as the FirmGen PRD)."""
    return [
        {"class": n, "class_id": SPECIES[n][0], "iucn": SPECIES[n][1], "base_severity": SPECIES[n][2],
         "confirmed_severity": effective_severity(n, True), "unconfirmed_severity": effective_severity(n, False),
         "led": SPECIES[n][3], "buzzer": SPECIES[n][4]}
        for n in CLASS_NAMES
    ]


# ---------------------------------------------------------------------- history
@app.get("/api/history")
def history(
    animal: Optional[str] = Query(None),
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    min_confidence: Optional[float] = Query(None),
    severity: Optional[str] = Query(None),
    source: Optional[str] = Query(None),
    limit: int = Query(200, le=10000),
):
    records = db.get_detections(animal, date_from, date_to, min_confidence, limit, severity, source)
    return {"records": records, "count": len(records)}


@app.delete("/api/history/{record_id}")
def delete_record(record_id: int):
    if not db.delete_detection(record_id):
        raise HTTPException(status_code=404, detail="Record not found")
    return {"status": "deleted"}


@app.get("/api/analytics")
def analytics():
    return db.get_analytics()


@app.get("/api/node/history")
def node_history(limit: int = Query(50, le=500)):
    return {"records": db.get_node_status_history(limit)}


EXPORT_FIELDS = ["id", "timestamp", "event_id", "animal", "confidence", "source", "camera_id", "track_id",
                 "in_road_zone", "sensor_confirmed", "severity", "action_profile", "ack_state",
                 "latency_ms", "onboard_ms"]


@app.get("/api/export/csv")
def export_csv(
    animal: Optional[str] = Query(None),
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    min_confidence: Optional[float] = Query(None),
    severity: Optional[str] = Query(None),
    source: Optional[str] = Query(None),
):
    records = db.get_detections(animal, date_from, date_to, min_confidence, 10000, severity, source)
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=EXPORT_FIELDS, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(records)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=wildguard_events.csv"},
    )


@app.get("/api/evidence/report", response_class=PlainTextResponse)
def evidence_report():
    """Markdown evidence pack for the submission: loop health, latency, species coverage, acceptance results."""
    md = evidence.build_report(hub.snapshot())
    return PlainTextResponse(md, headers={"Content-Disposition": "attachment; filename=wildguard_evidence.md"})


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host=config.API_HOST, port=config.API_PORT, reload=False)
