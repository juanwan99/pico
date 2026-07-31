#!/usr/bin/env bash
# Compatibility wrapper. Production demo seeding is always explicit.
set -euo pipefail

ROOT="${PICO_ROOT:-/opt/pico}"
if [ "${PICO_DEMO_SEED:-0}" != "1" ]; then
  echo "[pico] BLOCKED: set PICO_DEMO_SEED=1 explicitly" >&2
  exit 2
fi

exec "${ROOT}/scripts/vps-seed-demo-user.sh"
