#!/usr/bin/env bash
# Publish one synthetic contract-v1 detection straight to the broker (no camera, no backend needed).
#   ./scripts/publish_test_alert.sh tapir [confidence]
# Watch the ACK with:  mosquitto_sub -h localhost -t 'wildguard/node/+/ack' -v
set -euo pipefail
SPECIES="${1:-tapir}"; CONF="${2:-0.9}"
HOST="${MQTT_HOST:-localhost}"; PORT="${MQTT_PORT:-1883}"
case "$SPECIES" in
  tapir) ID=0;; jaguarundi) ID=1;; maned_wolf) ID=2;; puma) ID=3;; giant_anteater) ID=4;;
  *) echo "species: tapir|jaguarundi|maned_wolf|puma|giant_anteater"; exit 1;;
esac
TS=$(date +%s%3N)
EID="cli-$(date +%H%M%S)-$RANDOM"
PAYLOAD="{\"v\":1,\"event_id\":\"$EID\",\"ts_capture\":$TS,\"camera_id\":\"cli\",\"class\":\"$SPECIES\",\"class_id\":$ID,\"confidence\":$CONF,\"track_id\":-1,\"in_road_zone\":true,\"synthetic\":true}"
mosquitto_pub -h "$HOST" -p "$PORT" -q 1 -t wildguard/perception/detections -m "$PAYLOAD"
echo "published $EID ($SPECIES, conf $CONF)"
