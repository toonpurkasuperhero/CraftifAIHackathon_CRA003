#!/usr/bin/env bash
# Start the whole WildGuard loop on the laptop: broker -> PipeGen run.sh -> bridge -> backend -> dashboard.
# The ESP32 just needs power and Wi-Fi. Logs go to logs/, PIDs to logs/pids.
#
#   ./scripts/start_all.sh            # full loop (PipeGen export must exist in perception/pipegen_export/)
#   ./scripts/start_all.sh --no-pipegen   # everything except PipeGen (e.g. while it runs from the PipeGen UI)
#   ./scripts/start_all.sh --sim          # also start the ESP32 simulator (rehearsal only, no board)
#   ./scripts/start_all.sh --rehearsal    # no hardware at all: PipeGen replay + ESP32 simulator (REHEARSAL badge)
set -uo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
LOG="$ROOT/logs"; mkdir -p "$LOG"; : > "$LOG/pids"
PY="${PYTHON:-python3}"
MQTT_HOST="${MQTT_HOST:-localhost}"; MQTT_PORT="${MQTT_PORT:-1883}"
RUN_PIPEGEN=1; RUN_SIM=0; RUN_REPLAY=0
for a in "$@"; do case "$a" in
  --no-pipegen) RUN_PIPEGEN=0;; --sim) RUN_SIM=1;;
  --rehearsal) RUN_PIPEGEN=0; RUN_SIM=1; RUN_REPLAY=1;;
esac; done

start() {  # name, workdir, command...
  local name=$1 dir=$2; shift 2
  # own process group per service, so stop_all.sh can stop grandchildren too (npm -> node vite)
  (cd "$dir" || exit 1; setsid nohup "$@" > "$LOG/$name.log" 2>&1 < /dev/null & echo "$name $!" >> "$LOG/pids")
  echo "  started $name (log: logs/$name.log)"
}
wait_port() {  # host port seconds
  for _ in $(seq 1 "$3"); do (exec 3<>"/dev/tcp/$1/$2") 2>/dev/null && return 0; sleep 1; done; return 1
}

echo "== 1/5 MQTT broker"
if wait_port "$MQTT_HOST" "$MQTT_PORT" 1; then
  echo "  broker already listening on $MQTT_HOST:$MQTT_PORT"
else
  mkdir -p /tmp/wildguard-mosquitto
  start broker "$ROOT" mosquitto -c broker/mosquitto.conf -v
  wait_port "$MQTT_HOST" "$MQTT_PORT" 10 || { echo "  !! broker did not start (sudo apt install mosquitto)"; exit 1; }
fi

if [ "$RUN_SIM" = 1 ]; then
  echo "== ESP32 simulator (rehearsal only)"
  start esp32_sim "$ROOT" "$PY" tools/esp32_sim.py --host "$MQTT_HOST" --port "$MQTT_PORT" --auto-trip-every 25
  sleep 2  # like the real board: node subscribed before perception starts
fi

echo "== 2/5 PipeGen pipeline"
if [ "$RUN_PIPEGEN" = 1 ]; then
  RUNSH="$(find "$ROOT/perception/pipegen_export" -maxdepth 3 -name run.sh 2>/dev/null | head -1)"
  if [ -n "$RUNSH" ]; then start pipegen "$(dirname "$RUNSH")" bash "$RUNSH"
  else echo "  !! no perception/pipegen_export/**/run.sh - start the pipeline from PipeGen's Run stage"; fi
elif [ "$RUN_REPLAY" = 1 ]; then
  echo "  REHEARSAL: tools/pipegen_replay.py stands in for PipeGen (ONNX on CPU, BRA test images)"
  start pipegen_replay "$ROOT" "$PY" tools/pipegen_replay.py --host "$MQTT_HOST" --port "$MQTT_PORT"
else echo "  skipped (--no-pipegen)"; fi

echo "== 3/5 Bridge"
start bridge "$ROOT" "$PY" bridge/bridge.py

echo "== 4/5 Backend API (:8001)"
start backend "$ROOT/backend" "$PY" main.py
wait_port localhost 8001 15 && echo "  API up: http://localhost:8001/api/health" || echo "  !! backend not up, see logs/backend.log"

echo "== 5/5 Dashboard (:5173)"
if [ -d "$ROOT/frontend/node_modules" ]; then start frontend "$ROOT/frontend" npm run dev -- --host
else echo "  !! run 'cd frontend && npm install' first"; fi


echo
echo "Dashboard: http://localhost:5173   Stop: ./scripts/stop_all.sh   Check: ./scripts/check_env.sh"
