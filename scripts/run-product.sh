#!/usr/bin/env bash
# Pico product: API :8000 + NextChat :3000 + preview gateway :8080
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
export PYTHONPATH="$ROOT/services/api:$ROOT/services/orchestrator${PYTHONPATH:+:$PYTHONPATH}"
if [ -f "$ROOT/.env" ]; then set -a; # shellcheck disable=SC1091
  source "$ROOT/.env"; set +a
fi
mkdir -p "$ROOT/data"
UV="$ROOT/.venv/bin/uvicorn"; [ -x "$UV" ] || UV=uvicorn

if ! curl -sf -o /dev/null --max-time 2 http://127.0.0.1:8000/health; then
  echo "[pico] starting API :8000"
  nohup "$UV" app.main:app --app-dir "$ROOT/services/api" --host 127.0.0.1 --port 8000 \
    >>/tmp/pico-api.log 2>&1 &
  for _ in $(seq 1 40); do curl -sf -o /dev/null --max-time 1 http://127.0.0.1:8000/health && break; sleep 0.25; done
fi

if [ ! -f "$ROOT/apps/nextchat/.env.local" ]; then
  cat > "$ROOT/apps/nextchat/.env.local" <<'ENV'
BASE_URL=http://127.0.0.1:8000
OPENAI_API_KEY=pico-dev
CUSTOM_MODELS=pico-agent=Pico 智能体（工具+账本）,moonshot-v1-8k=Kimi 月之暗面
DEFAULT_MODEL=pico-agent
HIDE_USER_API_KEY=1
DISABLE_GPT4=1
ENV
fi

if ! curl -sf -o /dev/null --max-time 2 http://127.0.0.1:3000/; then
  echo "[pico] starting NextChat :3000"
  cd "$ROOT/apps/nextchat"
  if [ ! -d node_modules ]; then yarn install || npm install; fi
  nohup npx next dev -H 127.0.0.1 -p 3000 >>/tmp/nextchat.log 2>&1 &
  for _ in $(seq 1 90); do curl -sf -o /dev/null --max-time 1 http://127.0.0.1:3000/ && break; sleep 0.5; done
  cd "$ROOT"
fi

# Prefer repo gateway script
GW="$ROOT/scripts/preview-gateway.py"
if [ ! -f "$GW" ]; then GW=/tmp/pico-gateway8080.py; fi
if ! curl -sf -o /dev/null --max-time 2 http://127.0.0.1:8080/; then
  echo "[pico] starting preview gateway :8080"
  nohup python3 "$GW" >>/tmp/pico-gateway.log 2>&1 &
  sleep 0.5
fi

echo "[pico] Preview http://0.0.0.0:8080  (NextChat)  API :8000"
echo "[pico] product_ui=nextchat — if you see JSON Not Found, hard-refresh; API root is not the UI"
if [ -x "$ROOT/scripts/assert-product-identity.sh" ]; then
  # optional soft check
  bash "$ROOT/scripts/assert-product-identity.sh" || true
fi
