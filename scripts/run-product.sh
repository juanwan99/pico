#!/usr/bin/env bash
# Cloud preview: user never opens localhost. Preview may attach to :8000 or :8080.
# Both must serve NextChat HTML. API only on 127.0.0.1:18765.
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

cat > "$ROOT/apps/nextchat/.env.local" <<ENV
BASE_URL=http://127.0.0.1:${API_PORT}
OPENAI_API_KEY=pico-dev
CUSTOM_MODELS=pico-agent=Pico 智能体（工具+账本）,moonshot-v1-8k=Kimi 月之暗面
DEFAULT_MODEL=pico-agent
HIDE_USER_API_KEY=1
DISABLE_GPT4=1
ENV

if ! curl -sf -o /dev/null --max-time 2 http://127.0.0.1:8080/; then
  cd "$ROOT/apps/nextchat"
  if [ ! -d node_modules ]; then yarn install || npm install; fi
  nohup npx next dev -H 0.0.0.0 -p 8080 >>/tmp/nextchat.log 2>&1 &
  for _ in $(seq 1 90); do curl -sf -o /dev/null --max-time 1 http://127.0.0.1:8080/ && break; sleep 0.5; done
  cd "$ROOT"
fi

if ! curl -sf -o /dev/null --max-time 2 http://127.0.0.1:8000/; then
  nohup python3 "$ROOT/scripts/preview-mirror-8000.py" >>/tmp/pico-mirror8000.log 2>&1 &
  sleep 0.5
fi

echo "[pico] :8000 and :8080 both → NextChat UI (for cloud preview)"
echo "[pico] API 127.0.0.1:${API_PORT}"
