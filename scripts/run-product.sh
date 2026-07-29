#!/usr/bin/env bash
# Product = LibreChat (apps/librechat) → Pico API 127.0.0.1:18765
# Public preview surface: 0.0.0.0:8080 only. API stays loopback.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
API_PORT=18765
export PYTHONPATH="$ROOT/services/api:$ROOT/services/orchestrator${PYTHONPATH:+:$PYTHONPATH}"
if [ -f "$ROOT/.env" ]; then set -a; # shellcheck disable=SC1091
  source "$ROOT/.env"
  set +a
fi
# PROXY=1 breaks LibreChat undici — never export it
unset PROXY || true
UV="$ROOT/.venv/bin/uvicorn"; [ -x "$UV" ] || UV=uvicorn

# Mongo (portable or existing)
if ! python3 -c "import socket;s=socket.create_connection(('127.0.0.1',27017),1);s.close()" 2>/dev/null; then
  if [ -x /tmp/mongodb/bin/mongod ]; then
    mkdir -p /tmp/mongo-data /tmp/mongo-log
    nohup /tmp/mongodb/bin/mongod --dbpath /tmp/mongo-data --bind_ip 127.0.0.1 --port 27017 \
      >>/tmp/mongo-log/stdout.log 2>&1 &
    sleep 2
  else
    echo "[pico] WARN: no MongoDB on :27017 (LibreChat will fail to start)"
  fi
fi

if ! curl -sf -o /dev/null --max-time 2 "http://127.0.0.1:${API_PORT}/health"; then
  nohup "$UV" app.main:app --app-dir "$ROOT/services/api" --host 127.0.0.1 --port "${API_PORT}" \
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
  # Always re-apply self-destroy SW after dist exists (build regenerates workbox)
  if [ -x "$ROOT/scripts/librechat-postbuild-sw.sh" ]; then
    "$ROOT/scripts/librechat-postbuild-sw.sh" || true
  fi
  if [ ! -f "$LC/.env" ]; then
    cp "$LC/.env.example" "$LC/.env"
    cat >>"$LC/.env" <<ENV

# --- Pico product overlay ---
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
MONGO_URI=mongodb://127.0.0.1:27017/LibreChat
ENV
  fi
  if ! curl -sf -o /dev/null --max-time 2 http://127.0.0.1:3080/; then
    (
      cd "$LC"
      unset PROXY HTTP_PROXY HTTPS_PROXY http_proxy https_proxy ALL_PROXY all_proxy || true
      nohup npm run backend >>/tmp/librechat-api.log 2>&1 &
    )
    for _ in $(seq 1 60); do curl -sf -o /dev/null --max-time 1 http://127.0.0.1:3080/ && break; sleep 0.5; done
  fi
fi

# Public mirror for Grok Live Preview (only HTML product surface on 0.0.0.0)
if ! curl -sf -o /dev/null --max-time 2 http://127.0.0.1:8080/; then
  nohup python3 "$ROOT/scripts/preview-mirror-8000.py" 8080 >>/tmp/pico-mirror8080.log 2>&1 &
fi
# Optional sticky-port mirror (do not pin preview here)
if ! curl -sf -o /dev/null --max-time 2 http://127.0.0.1:8000/; then
  nohup python3 "$ROOT/scripts/preview-mirror-8000.py" 8000 >>/tmp/pico-mirror8000.log 2>&1 &
fi

# Pin preview control plane → 8080
curl -sf -o /dev/null --max-time 2 -X POST http://127.0.0.1:6015/__control/target \
  -H 'Content-Type: application/json' -d '{"port":8080}' || true
if [ -x "$ROOT/scripts/pin-preview-8080.sh" ]; then
  if ! pgrep -f 'pin-preview-8080' >/dev/null 2>&1; then
    nohup "$ROOT/scripts/pin-preview-8080.sh" >>/tmp/pin-preview.log 2>&1 &
  fi
fi

echo "[pico] LibreChat :3080  public :8080  API :${API_PORT} (loopback)  pin→8080"
