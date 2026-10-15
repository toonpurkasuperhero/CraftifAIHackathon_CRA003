# Sensor-Triggered Camera Feature

The [sensor_log.csv](file:///d:/animal_detection/sensor_log.csv) contains real sensor readings in the format:
```
Distance: 156.79 cm | PIR: No Motion
Distance: 15.20 cm | PIR: Motion Detected
```

## Goal
- **Auto-trigger**: Camera auto-activates only when **distance < 20 cm** is detected from the sensor feed.
- **Manual override**: A "Turn On Camera" button lets the user start the camera at any time regardless of sensor data.
- The Live Detection page will display a live **Sensor Monitor** panel showing the latest distance & PIR readings, and a status badge ("🔴 Animal Nearby!" vs "🟢 Clear").

---

## Proposed Changes

### Backend — New Sensor Endpoint

#### [MODIFY] [main.py](file:///d:/animal_detection/backend/main.py)
- Add `GET /api/sensor/latest` endpoint that reads [sensor_log.csv](file:///d:/animal_detection/sensor_log.csv) (from [d:/animal_detection/sensor_log.csv](file:///d:/animal_detection/sensor_log.csv)), parses the **last valid** `Distance: X cm | PIR: Y` line, and returns:
  ```json
  { "distance_cm": 15.2, "pir": "Motion Detected", "triggered": true }
  ```
  `triggered = true` when `distance_cm < 20`.

---

### Frontend — API Service

#### [MODIFY] [api.js](file:///d:/animal_detection/frontend/src/services/api.js)
- Add `getSensorLatest()` → `GET /api/sensor/latest`

---

### Frontend — Live Detection Page (main changes)

#### [MODIFY] [LiveDetection.jsx](file:///d:/animal_detection/frontend/src/pages/LiveDetection.jsx)
- Add a **Sensor Monitor** panel (top-right sidebar card) showing:
  - Current distance (cm) with color-coded badge  
  - PIR status  
  - "🔴 ANIMAL NEARBY — Camera Auto-Started!" alert when triggered
- **Auto-start logic**: Poll `/api/sensor/latest` every **2 seconds**. When `triggered = true` and camera is not running → auto-call [startDetection()](file:///d:/animal_detection/frontend/src/pages/LiveDetection.jsx#41-56). When distance goes back to ≥ 20 cm AND camera was auto-started (not manually started) → auto-stop.
- **Manual toggle button**: Always visible "📷 Start Camera Manually" button that sets a `manualMode` flag, preventing auto-stop even when sensor data clears.
- Track `autoStarted` vs `manualStarted` separately so manual sessions are never stopped by sensor polling.

---

## Verification Plan

### Backend test (manual)
1. With the backend running (`python main.py` in `d:/animal_detection/backend`), open browser and navigate to:  
   `http://localhost:8001/api/sensor/latest`
2. You should see a JSON response with `distance_cm`, `pir`, and `triggered` fields.
3. Verify: since all readings in the current CSV are > 20 cm, `triggered` should be `false`.

### Frontend test (manual, browser)
1. Run frontend with `cmd /c "npm run dev"` in `d:/animal_detection/frontend`.
2. Open `http://localhost:5173` → go to **Live Detection** page.
3. Confirm you see the **Sensor Monitor** card on the right panel with live distance/PIR readings updating every 2 seconds.
4. Confirm the **"📷 Start Camera Manually"** button is visible and starts the camera when clicked.
5. To test auto-trigger: temporarily add a line `Distance: 10.00 cm | PIR: Motion Detected` to [sensor_log.csv](file:///d:/animal_detection/sensor_log.csv) — the camera should auto-start within ~2 seconds. Then remove that line — the camera should auto-stop (if it was auto-started).
