#!/usr/bin/env bash
# Load demo credentials + Node path for visual-gate.mjs.
# Usage:  set -a; source scripts/visual-gate-env.sh; set +a
# Does not print secrets. Safe to source from agent startup.

set -euo pipefail

_VG_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# Prefer restricted host secret file (never commit).
for f in \
  "${PICO_VISUAL_SECRET_FILE:-}" \
  "${HOME}/.secrets/pico-r4r6-evidence.env" \
  "${HOME}/.secrets/pico-e2e.env"
do
  if [[ -n "$f" && -f "$f" ]]; then
    # shellcheck disable=SC1090
    set -a
    # shellcheck disable=SC1091
    . "$f"
    set +a
    break
  fi
done

export PICO_E2E_EMAIL="${PICO_E2E_EMAIL:-${DEMO_EMAIL:-}}"
export PICO_E2E_PASSWORD="${PICO_E2E_PASSWORD:-${DEMO_PASSWORD:-}}"
export PICO_PUBLIC_BASE="${PICO_PUBLIC_BASE:-https://pico.aivia.asia}"

# Playwright resolution for node scripts without repo-local node_modules.
if [[ -d "${HOME}/.npm-global/lib/node_modules" ]]; then
  export NODE_PATH="${HOME}/.npm-global/lib/node_modules${NODE_PATH:+:$NODE_PATH}"
fi
if [[ -d "${_VG_ROOT}/apps/librechat/node_modules" ]]; then
  export NODE_PATH="${_VG_ROOT}/apps/librechat/node_modules${NODE_PATH:+:$NODE_PATH}"
fi

if [[ -z "${PICO_E2E_EMAIL:-}" || "${#PICO_E2E_PASSWORD}" -lt 12 ]]; then
  echo "[visual-gate-env] BLOCKED: DEMO_EMAIL/DEMO_PASSWORD (or PICO_E2E_*) not loaded" >&2
  return 2 2>/dev/null || exit 2
fi

echo "[visual-gate-env] OK email=${PICO_E2E_EMAIL:0:2}*** base=${PICO_PUBLIC_BASE}"
