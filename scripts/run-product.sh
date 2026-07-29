#!/usr/bin/env bash
# ONLY public: NextChat :8080. API loopback :8000 (preview must not attach to API).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
export PYTHONPATH="$ROOT/services/api:$ROOT/services/orchestrator${PYTHONPATH:+:$PYTHONPATH}"
if [ -f "$ROOT/.env" ]; then set -a; source "$ROOT/.env"; set +a; fi
mkdir -p "$ROOT/data"
UV="$ROOT/.venv/bin/uvicorn"; [ -x "$UV" ] || UV=uvicorn

if ! curl -sf -o /dev/null --max-time 2 http://127.0.0.1:8000/health; then
  echo "[pico] API 127.0.0.1:8000"
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

# Kill any leftover gateway so it cannot steal :8080
pkill -f preview-gateway.py 2>/dev/null || true

if ! curl -sf -o /dev/null --max-time 2 http://127.0.0.1:8080/; then
  echo "[pico] NextChat product UI 0.0.0.0:8080"
  cd "$ROOT/apps/nextchat"
  if [ ! -d node_modules ]; then yarn install || npm install; fi
  nohup npx next dev -H 0.0.0.0 -p 8080 >>/tmp/nextchat.log 2>&1 &
  for _ in $(seq 1 90); do
    body=$(curl -sf --max-time 1 http://127.0.0.1:8080/ 2>/dev/null | head -c 40 || true)
    echo "$body" | grep -qi html && break
    sleep 0.5
  done
fi

echo "[pico] PUBLIC UI http://0.0.0.0:8080 (must be HTML/NextChat, never API JSON)"
echo "[pico] API loopback only 127.0.0.1:8000"
