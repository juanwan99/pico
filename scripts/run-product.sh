#!/usr/bin/env bash
# Product = apps/workbench (WorkBuddy-class task shell). API loopback :18765.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
API_PORT=18765
export PYTHONPATH="$ROOT/services/api:$ROOT/services/orchestrator${PYTHONPATH:+:$PYTHONPATH}"
if [ -f "$ROOT/.env" ]; then set -a; source "$ROOT/.env"; set +a; fi
mkdir -p "$ROOT/data"
UV="$ROOT/.venv/bin/uvicorn"; [ -x "$UV" ] || UV=uvicorn

if ! curl -sf -o /dev/null --max-time 2 http://127.0.0.1:${API_PORT}/health; then
  nohup "$UV" app.main:app --app-dir "$ROOT/services/api" --host 127.0.0.1 --port ${API_PORT} \
    >>/tmp/pico-api.log 2>&1 &
  for _ in $(seq 1 40); do curl -sf -o /dev/null --max-time 1 http://127.0.0.1:${API_PORT}/health && break; sleep 0.25; done
fi

if ! curl -sf -o /dev/null --max-time 2 http://127.0.0.1:8080/; then
  cd "$ROOT/apps/workbench"
  if [ ! -d node_modules ]; then npm install; fi
  nohup npx vite --host 0.0.0.0 --port 8080 >>/tmp/pico-workbench.log 2>&1 &
  for _ in $(seq 1 60); do curl -sf -o /dev/null --max-time 1 http://127.0.0.1:8080/ && break; sleep 0.5; done
  cd "$ROOT"
fi

if ! curl -sf -o /dev/null --max-time 2 http://127.0.0.1:8000/; then
  nohup python3 "$ROOT/scripts/preview-mirror-8000.py" >>/tmp/pico-mirror8000.log 2>&1 &
fi

echo "[pico] workbench :8080 (+ :8000 mirror)  API :${API_PORT}"
