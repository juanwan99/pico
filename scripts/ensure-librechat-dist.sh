#!/usr/bin/env bash
# Ensure client dist index.html points at an existing JS bundle; rebuild if broken.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
LC="$ROOT/apps/librechat"
DIST="$LC/client/dist"
if [ ! -f "$DIST/index.html" ]; then
  echo "[pico] no dist — building client"
  (cd "$LC" && npm run build:client)
  [ -x "$ROOT/scripts/librechat-postbuild-sw.sh" ] && "$ROOT/scripts/librechat-postbuild-sw.sh" || true
  exit 0
fi
ASSET=$(grep -oE 'assets/index\.[A-Za-z0-9_-]+\.js' "$DIST/index.html" | head -1 || true)
if [ -z "$ASSET" ] || [ ! -f "$DIST/$ASSET" ]; then
  echo "[pico] dist asset missing ($ASSET) — rebuilding client"
  (cd "$LC" && npm run build:client)
  [ -x "$ROOT/scripts/librechat-postbuild-sw.sh" ] && "$ROOT/scripts/librechat-postbuild-sw.sh" || true
fi
# If backend is up but serves a different index (stale memory), leave restart to caller
