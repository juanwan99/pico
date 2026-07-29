#!/usr/bin/env bash
# CRITICAL for Grok live preview:
# - Do NOT listen on :8000 (preview will show FastAPI JSON)
# - Public: NextChat 0.0.0.0:8080
# - API: 127.0.0.1:18765
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
API_PORT=18765
export PYTHONPATH="$ROOT/services/api:$ROOT/services/orchestrator${PYTHONPATH:+:$PYTHONPATH}"
if [ -f "$ROOT/.env" ]; then set -a; source "$ROOT/.env"; set +a; fi
mkdir -p "$ROOT/data"
UV="$ROOT/.venv/bin/uvicorn"; [ -x "$UV" ] || UV=uvicorn

# free accidental :8000
if curl -sf -o /dev/null --max-time 1 http://127.0.0.1:8000/health 2>/dev/null; then
  echo "[pico] WARN: something on :8000 — preview will mis-attach; kill it"
fi

if ! curl -sf -o /dev/null --max-time 2 http://127.0.0.1:${API_PORT}/health; then
  echo "[pico] API 127.0.0.1:${API_PORT}"
  nohup "$UV" app.main:app --app-dir "$ROOT/services/api" --host 127.0.0.1 --port ${API_PORT} \
    >>/tmp/pico-api.log 2>&1 &
  for _ in $(seq 1 40); do curl -sf -o /dev/null --max-time 1 http://127.0.0.1:${API_PORT}/health && break; sleep 0.25; done
fi

mkdir -p "$ROOT/apps/nextchat"
cat > "$ROOT/apps/nextchat/.env.local" <<ENV
BASE_URL=http://127.0.0.1:${API_PORT}
OPENAI_API_KEY=pico-dev
CUSTOM_MODELS=pico-agent=Pico 智能体（工具+账本）,moonshot-v1-8k=Kimi 月之暗面
DEFAULT_MODEL=pico-agent
HIDE_USER_API_KEY=1
DISABLE_GPT4=1
ENV

if ! curl -sf -o /dev/null --max-time 2 http://127.0.0.1:8080/; then
  echo "[pico] NextChat 0.0.0.0:8080"
  cd "$ROOT/apps/nextchat"
  if [ ! -d node_modules ]; then yarn install || npm install; fi
  nohup npx next dev -H 0.0.0.0 -p 8080 >>/tmp/nextchat.log 2>&1 &
  for _ in $(seq 1 90); do
    t=$(curl -sf --max-time 1 http://127.0.0.1:8080/ 2>/dev/null | grep -o '<title>[^<]*' | head -1 || true)
    echo "$t" | grep -q Pico && break
    sleep 0.5
  done
fi

echo "[pico] PUBLIC: http://0.0.0.0:8080  title must be Pico"
echo "[pico] API:    127.0.0.1:${API_PORT}  (not :8000)"
# prove 8000 empty
if curl -sf --max-time 1 http://127.0.0.1:8000/ >/dev/null 2>&1; then
  echo "[pico] FAIL: :8000 still answers — preview will show API JSON"
  exit 1
fi
