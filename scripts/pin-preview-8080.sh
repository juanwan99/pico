#!/bin/sh
# DEPRECATED-FOR-OWNER-PATH: Grok Live Preview pin helper — not production owner path (use pico.aivia.asia).
# Keep Grok preview control plane pointed at LibreChat public UI.
set -eu
CONTROL="${PICO_PREVIEW_CONTROL:-http://127.0.0.1:6015/__control/target}"
PORT="${PICO_PREVIEW_PORT:-8080}"
INTERVAL="${PICO_PREVIEW_PIN_INTERVAL:-3}"
while true; do
  curl -sf -o /dev/null --max-time 2 -X POST "$CONTROL" \
    -H 'Content-Type: application/json' \
    -d "{\"port\":${PORT}}" || true
  sleep "$INTERVAL"
done
