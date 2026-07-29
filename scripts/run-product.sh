#!/usr/bin/env bash
# Product = LibreChat (apps/librechat) → Pico API 127.0.0.1:18765
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
API_PORT=18765
export PYTHONPATH="$ROOT/services/api:$ROOT/services/orchestrator${PYTHONPATH:+:$PYTHONPATH}"
if [ -f "$ROOT/.env" ]; then set -a; source "$ROOT/.env"; set +a; fi
UV="$ROOT/.venv/bin/uvicorn"; [ -x "$UV" ] || UV=uvicorn

# Mongo (portable or existing)
if ! python3 -c "import socket;s=socket.create_connection(('127.0.0.1',27017),1);s.close()" 2>/dev/null; then
  if [ -x /tmp/mongodb/bin/mongod ]; then
    mkdir -p /tmp/mongo-data /tmp/mongo-log
    nohup /tmp/mongodb/bin/mongod --dbpath /tmp/mongo-data --bind_ip 127.0.0.1 --port 27017 \
      >>/tmp/mongo-log/stdout.log 2>&1 &
    sleep 2
  else
    echo "[pico] WARN: no MongoDB on :27017"
  fi
fi

if ! curl -sf -o /dev/null --max-time 2 http://127.0.0.1:${API_PORT}/health; then
  nohup "$UV" app.main:app --app-dir "$ROOT/services/api" --host 127.0.0.1 --port ${API_PORT} \
    >>/tmp/pico-api.log 2>&1 &
  sleep 1
fi

LC="$ROOT/apps/librechat"
if [ -f "$LC/package.json" ]; then
  if [ ! -d "$LC/node_modules" ]; then
    (cd "$LC" && npm install)
  fi
  if [ ! -d "$LC/client/dist" ]; then
    (cd "$LC" && npm run build:packages && npm run build:client)
  fi
  if [ ! -f "$LC/.env" ]; then
    cp "$LC/.env.example" "$LC/.env"
    # minimal pico overlay
    cat >> "$LC/.env" <<ENV

ENDPOINTS=openAI
OPENAI_API_KEY=pico-dev
OPENAI_REVERSE_PROXY=http://127.0.0.1:${API_PORT}/v1
OPENAI_MODELS=moonshot-v1-8k,pico-agent
HOST=0.0.0.0
PORT=3080
DOMAIN_CLIENT=http://127.0.0.1:8080
DOMAIN_SERVER=http://127.0.0.1:3080
APP_TITLE=Pico
SEARCH=false
ALLOW_REGISTRATION=true
ENV
  fi
  if ! curl -sf -o /dev/null --max-time 2 http://127.0.0.1:3080/; then
    (cd "$LC" && nohup npm run backend >>/tmp/librechat-api.log 2>&1 &)
    for _ in $(seq 1 40); do curl -sf -o /dev/null --max-time 1 http://127.0.0.1:3080/ && break; sleep 0.5; done
  fi
fi

# Public mirrors for Grok preview
if ! curl -sf -o /dev/null --max-time 2 http://127.0.0.1:8080/; then
  nohup python3 "$ROOT/scripts/preview-mirror-8000.py" 8080 >>/tmp/pico-mirror8080.log 2>&1 &
fi
if ! curl -sf -o /dev/null --max-time 2 http://127.0.0.1:8000/; then
  nohup python3 "$ROOT/scripts/preview-mirror-8000.py" 8000 >>/tmp/pico-mirror8000.log 2>&1 &
fi
echo "[pico] LibreChat :3080  public :8080/:8000  API :${API_PORT}"
