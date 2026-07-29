#!/usr/bin/env bash
# Pico product: API (agent) :8000 + NextChat UI :8080
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

export PYTHONPATH="$ROOT/services/api:$ROOT/services/orchestrator${PYTHONPATH:+:$PYTHONPATH}"
if [ -f "$ROOT/.env" ]; then set -a; # shellcheck disable=SC1091
  source "$ROOT/.env"
  set +a
fi
mkdir -p "$ROOT/data"

UV="$ROOT/.venv/bin/uvicorn"
[ -x "$UV" ] || UV=uvicorn

if ! curl -sf -o /dev/null --max-time 2 http://127.0.0.1:8000/health; then
  echo "[pico] starting API :8000"
  nohup "$UV" app.main:app --app-dir "$ROOT/services/api" --host 127.0.0.1 --port 8000 \
    >>/tmp/pico-api.log 2>&1 &
  for _ in $(seq 1 40); do
    curl -sf -o /dev/null --max-time 1 http://127.0.0.1:8000/health && break
    sleep 0.25
  done
fi
echo "[pico] API ok $(curl -sf http://127.0.0.1:8000/health)"

# NextChat env
if [ ! -f "$ROOT/apps/nextchat/.env.local" ]; then
  cat > "$ROOT/apps/nextchat/.env.local" <<'ENV'
BASE_URL=http://127.0.0.1:8000
OPENAI_API_KEY=pico-dev
CUSTOM_MODELS=pico-agent=Pico 智能体（工具+账本）,moonshot-v1-8k=Kimi 月之暗面
DEFAULT_MODEL=pico-agent
HIDE_USER_API_KEY=1
ENV
fi

if ! curl -sf -o /dev/null --max-time 2 http://127.0.0.1:8080/; then
  echo "[pico] starting NextChat :8080"
  cd "$ROOT/apps/nextchat"
  [ -d node_modules ] || yarn install
  nohup npx next dev -H 0.0.0.0 -p 8080 >>/tmp/nextchat.log 2>&1 &
  for _ in $(seq 1 90); do
    curl -sf -o /dev/null --max-time 1 http://127.0.0.1:8080/ && break
    sleep 0.5
  done
fi
echo "[pico] UI http://0.0.0.0:8080  (NextChat → Pico Agent)"
echo "[pico] smoke: curl -s localhost:8000/v1/chat/completions -H 'Authorization: Bearer pico-dev' -H 'Content-Type: application/json' -d '{\"model\":\"pico-agent\",\"messages\":[{\"role\":\"user\",\"content\":\"列出我学校的班级\"}]}'"
