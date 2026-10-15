#!/usr/bin/env bash
# Stop everything started by start_all.sh
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
[ -f "$ROOT/logs/pids" ] || { echo "nothing to stop"; exit 0; }
while read -r name pid; do
  if kill -TERM -- "-$pid" 2>/dev/null || kill "$pid" 2>/dev/null; then echo "stopped $name ($pid)"; fi
done < "$ROOT/logs/pids"
: > "$ROOT/logs/pids"
