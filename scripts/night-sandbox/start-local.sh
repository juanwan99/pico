#!/usr/bin/env bash
# Local teacher stack for night-sandbox P1 (no Docker).
# Mongo memory + pico-api + sandbox_worker + LibreChat API + Vite client.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
LC="$ROOT/apps/librechat"
export PYTHONPATH="$ROOT/services:$ROOT/services/api:$ROOT/services/orchestrator${PYTHONPATH:+:$PYTHONPATH}"
unset PROXY HTTP_PROXY HTTPS_PROXY http_proxy https_proxy ALL_PROXY all_proxy || true

mkdir -p /tmp/pico-night /tmp/pico-sandbox-profiles /tmp/pico-sandbox-home

if ! python3 -c "import socket;s=socket.create_connection(('127.0.0.1',27117),0.4);s.close()" 2>/dev/null; then
  echo "[night] starting mongodb-memory-server :27117"
  nohup node - <<'JS' >>/tmp/pico-night/mongo.log 2>&1 &
const { MongoMemoryServer } = require('/home/box/pico-pack/apps/librechat/node_modules/mongodb-memory-server');
(async () => {
  const mongod = await MongoMemoryServer.create({
    instance: { port: 27117, dbName: 'LibreChat' },
  });
  console.log('mongo', mongod.getUri());
  await new Promise(() => {});
})().catch((err) => {
  console.error(err);
  process.exit(1);
});
JS
  for i in $(seq 1 40); do
    python3 -c "import socket;s=socket.create_connection(('127.0.0.1',27117),0.4);s.close()" 2>/dev/null && break
    sleep 0.5
  done
fi

if [ ! -f "$ROOT/.env" ]; then
  cat >"$ROOT/.env" <<'ENV'
PICO_ENV=development
PICO_ACCEPT_TEST_ISSUER=true
PICO_JWT_SECRET=change-me-dev-only-not-for-prod-32b!
PICO_JWT_ISS=pico-test-issuer
PICO_JWT_AUD=pico-api
PICO_OPENAI_PROXY_KEY=pico-dev
PICO_API_HOST=127.0.0.1
PICO_API_PORT=18765
PICO_DATABASE_URL=sqlite+aiosqlite:///./data/pico-night.db
PICO_CORS_ORIGINS=http://127.0.0.1:3090,http://localhost:3090,http://127.0.0.1:3080,http://localhost:3080
PICO_ALLOWED_MODELS=pico-fast,pico-deep,pico-agent
PICO_MODEL_PROVIDER=deepseek
PICO_SANDBOX_URL=http://127.0.0.1:18767
PICO_GIT_SHA=local-night-sandbox
PICO_AGENT_FILE=services/orchestrator/agents/pico.yaml
PICO_DANGEROUS_TOOLS_ENABLED=false
PICO_EDU_MODE=fake
ALLOW_REGISTRATION=true
ENV
fi

if [ ! -f "$LC/.env" ]; then
  cp "$LC/.env.example" "$LC/.env"
  cat >>"$LC/.env" <<'ENV'

ENDPOINTS=openAI
OPENAI_API_KEY=pico-dev
OPENAI_REVERSE_PROXY=http://127.0.0.1:18765/v1
OPENAI_MODELS=pico-fast,pico-deep,pico-agent
PICO_OPENAI_PROXY_KEY=pico-dev
HOST=127.0.0.1
PORT=3080
DOMAIN_CLIENT=http://127.0.0.1:3090
DOMAIN_SERVER=http://127.0.0.1:3080
APP_TITLE=Pico
SEARCH=false
ALLOW_REGISTRATION=true
ALLOW_UNVERIFIED_EMAIL_LOGIN=true
MONGO_URI=mongodb://127.0.0.1:27117/LibreChat
ENV
fi

if ! curl -sf -o /dev/null --max-time 2 http://127.0.0.1:18767/health; then
  echo "[night] starting sandbox_worker :18767"
  nohup "$ROOT/.venv/bin/python" -m sandbox_worker >>/tmp/pico-night/sandbox.log 2>&1 &
fi

if ! curl -sf -o /dev/null --max-time 2 http://127.0.0.1:18765/health; then
  echo "[night] starting pico-api :18765"
  mkdir -p "$ROOT/data"
  nohup "$ROOT/.venv/bin/uvicorn" app.main:app --app-dir "$ROOT/services/api" --host 127.0.0.1 --port 18765 \
    >>/tmp/pico-night/api.log 2>&1 &
fi

if ! curl -sf -o /dev/null --max-time 2 http://127.0.0.1:3080/; then
  echo "[night] starting librechat api :3080"
  (
    cd "$LC"
    unset PROXY HTTP_PROXY HTTPS_PROXY http_proxy https_proxy ALL_PROXY all_proxy || true
    nohup npm run backend >>/tmp/pico-night/lc-api.log 2>&1 &
  )
fi

if ! curl -sf -o /dev/null --max-time 2 http://127.0.0.1:3090/; then
  echo "[night] starting vite client :3090"
  (
    cd "$LC"
    unset PROXY HTTP_PROXY HTTPS_PROXY http_proxy https_proxy ALL_PROXY all_proxy || true
    nohup npm run frontend:dev >>/tmp/pico-night/lc-vite.log 2>&1 &
  )
fi

echo "[night] waiting for ports"
for i in $(seq 1 90); do
  ok=1
  curl -sf -o /dev/null --max-time 1 http://127.0.0.1:18767/health || ok=0
  curl -sf -o /dev/null --max-time 1 http://127.0.0.1:18765/health || ok=0
  curl -sf -o /dev/null --max-time 1 http://127.0.0.1:3090/ || ok=0
  if [ "$ok" = 1 ]; then
    echo "[night] ready"
    curl -sS http://127.0.0.1:18767/health; echo
    curl -sS http://127.0.0.1:18765/health | head -c 300; echo
    exit 0
  fi
  sleep 2
done
echo "[night] TIMEOUT — see /tmp/pico-night/*.log"
tail -n 40 /tmp/pico-night/*.log || true
exit 1
