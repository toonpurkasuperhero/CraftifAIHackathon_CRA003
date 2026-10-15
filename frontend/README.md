# frontend/ - WildGuard mission-control dashboard (React + Vite)

Live view and control of the closed loop. It does **no inference**: everything arrives from the backend WebSocket (`/api/ws`), which mirrors MQTT.

```bash
npm install
npm run dev -- --host          # http://localhost:5173
```

Pages: **Dashboard** (loop status strip, KPIs), **Live Loop** (PipeGen stream embed, event → ACK feed with latency waterfall, ESP32 sensor and telemetry), **Control & Test** (arm/disarm kill switch, sensor-trip and self-test commands, synthetic species alerts, last 10 ACKs, species profile table), **Event History** (severity, sensor confirmation, ACK state, latency, CSV export), **Analytics** (latency histogram, severity, FP32/FP16/INT8 trade-off, evidence pack).

Configuration (`.env.local`, see `.env.example`): `VITE_API_BASE` if the API is not on `<this host>:8001`, and `VITE_STREAM_URL` for the MediaMTX WebRTC page of PipeGen's RTSP output. "Demo mode" in the top bar enlarges everything for a projector.
