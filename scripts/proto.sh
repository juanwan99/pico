#!/usr/bin/env bash
# Start Pico independent prototype (API + Web). Pico repo only.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if [[ ! -f .env ]]; then
  cp .env.example .env
  echo "Created .env — set KIMI_API_KEY for real model runs."
fi

if [[ ! -d .venv ]]; then
  python3.12 -m venv .venv
fi
# shellcheck disable=SC1091
source .venv/bin/activate
pip install -q -r requirements-dev.txt

if [[ ! -d apps/web/node_modules ]]; then
  (cd apps/web && npm install)
fi

mkdir -p data
export PYTHONPATH="$ROOT/services/api:$ROOT/services/orchestrator${PYTHONPATH:+:$PYTHONPATH}"

API_LOG="${TMPDIR:-/tmp}/pico-api.log"
WEB_LOG="${TMPDIR:-/tmp}/pico-web.log"

if ! curl -sf -o /dev/null --max-time 1 http://127.0.0.1:8000/health; then
  # load .env into env for uvicorn child
  set -a
  # shellcheck disable=SC1091
  source .env
  set +a
  nohup uvicorn app.main:app --app-dir services/api --host 0.0.0.0 --port 8000 \
    >"$API_LOG" 2>&1 &
  echo $! > "${TMPDIR:-/tmp}/pico-api.pid"
  echo "API starting → http://127.0.0.1:8000  (log $API_LOG)"
  for _ in $(seq 1 30); do
    curl -sf -o /dev/null --max-time 1 http://127.0.0.1:8000/health && break
    sleep 0.3
  done
else
  echo "API already up on :8000"
fi

if ! curl -sf -o /dev/null --max-time 1 http://127.0.0.1:5173/; then
  (cd apps/web && nohup npm run dev -- --host 0.0.0.0 --port 5173 >"$WEB_LOG" 2>&1 & echo $! > "${TMPDIR:-/tmp}/pico-web.pid")
  echo "Web starting → http://127.0.0.1:5173  (log $WEB_LOG)"
else
  echo "Web already up on :5173"
fi

echo ""
echo "=== Pico 独立原型 ==="
echo "  UI:  http://127.0.0.1:5173"
echo "  API: http://127.0.0.1:8000/health"
echo "  Demo script: docs/DEMO.md"
echo "  E2E: make demo"
echo "===================="
