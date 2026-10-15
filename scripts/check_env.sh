#!/usr/bin/env bash
# Pre-flight checks for demo day. Exit code = number of failed checks.
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
HOST="${MQTT_HOST:-localhost}"; PORT="${MQTT_PORT:-1883}"
FAIL=0
ok()   { printf "  \e[32mOK\e[0m   %s\n" "$1"; }
bad()  { printf "  \e[31mFAIL\e[0m %s\n" "$1"; FAIL=$((FAIL+1)); }
warn() { printf "  \e[33mWARN\e[0m %s\n" "$1"; }

echo "== Perception (PipeGen)"
V=$(pipegen --version 2>/dev/null); [[ "$V" == *0.5.1* ]] && ok "pipegen $V" || bad "pipegen --version should print 0.5.1 (got '${V:-not found}')"
nvidia-smi --query-gpu=name,driver_version --format=csv,noheader >/dev/null 2>&1 \
  && ok "GPU: $(nvidia-smi --query-gpu=name,driver_version --format=csv,noheader | head -1)" || bad "nvidia-smi: no NVIDIA GPU visible"
[ "${XDG_SESSION_TYPE:-}" = "x11" ] && ok "X11 session" || warn "session type is '${XDG_SESSION_TYPE:-unknown}' (PipeGen wants X11)"
ls /dev/video* >/dev/null 2>&1 && ok "camera: $(ls /dev/video* | tr '\n' ' ')" || bad "no /dev/video* camera"
[ -f "$ROOT/perception/export/wildguard_yolov8n_bra5.onnx" ] && ok "ONNX exported" || warn "run perception/export_onnx.sh"
[ -f "$ROOT/perception/reports/pipeline_info.json" ] && ok "pipeline_info.json present" || warn "perception/reports/pipeline_info.json missing (copy from the example, fill from PipeGen report)"

echo "== Broker & loop"
command -v mosquitto >/dev/null && ok "mosquitto installed" || bad "sudo apt install mosquitto mosquitto-clients"
if (exec 3<>"/dev/tcp/$HOST/$PORT") 2>/dev/null; then ok "broker listening on $HOST:$PORT"; else bad "no broker on $HOST:$PORT"; fi
if command -v mosquitto_sub >/dev/null; then
  ST=$(timeout 3 mosquitto_sub -h "$HOST" -p "$PORT" -t 'wildguard/node/+/status' -C 1 -W 3 2>/dev/null)
  [[ "$ST" == *online* ]] && ok "ESP32 status: $ST" || bad "ESP32 not online (retained status: '${ST:-none}')"
  BR=$(timeout 4 mosquitto_sub -h "$HOST" -p "$PORT" -t 'wildguard/bridge/status' -C 1 -W 4 2>/dev/null)
  [[ "$BR" == *online* ]] && ok "bridge online" || warn "bridge not running"
  RAW=$(timeout 3 mosquitto_sub -h "$HOST" -p "$PORT" -t 'wildguard/pipegen/#' -C 1 -W 3 2>/dev/null)
  [ -n "$RAW" ] && ok "PipeGen is publishing" || warn "no PipeGen message in 3 s (fine if nothing is in view)"
fi
curl -sf "http://localhost:8001/api/health" >/dev/null && ok "backend API up" || warn "backend not running"

echo "== Network"
IP=$(hostname -I 2>/dev/null | awk '{print $1}'); ok "laptop IP ${IP:-unknown}: ESP32 broker URI must be mqtt://${IP:-<ip>}:$PORT"
echo
[ $FAIL -eq 0 ] && echo "All required checks passed." || echo "$FAIL required check(s) failed."
exit $FAIL
