#!/usr/bin/env bash
set -euo pipefail
export PLAYWRIGHT_BROWSERS_PATH="${PLAYWRIGHT_BROWSERS_PATH:-/opt/pw-browsers}"
export BROWSER_ALLOW_EXTERNAL_HOST=1
export PICO_E2E_BASE="${PICO_E2E_BASE:-https://pico.aivia.asia}"
export PICO_E2E_OUT="${PICO_E2E_OUT:-/workspace/screenshots/e2e}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
if [[ -z "${PICO_E2E_EMAIL:-${PICO_DEMO_EMAIL:-}}" || -z "${PICO_E2E_PASSWORD:-${PICO_DEMO_PASSWORD:-}}" ]]; then
  echo "BLOCKED: set PICO_E2E_EMAIL and PICO_E2E_PASSWORD (12+ chars)" >&2
  exit 2
fi
exec node scripts/e2e-public-complex.mjs
