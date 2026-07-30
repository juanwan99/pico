#!/usr/bin/env bash
# Production hot-update on Aliyun VPS. Run ON the server:
#   bash /opt/pico/scripts/prod-update.sh
set -euo pipefail
ROOT="${PICO_ROOT:-/opt/pico}"
BRANCH="${PICO_BRANCH:-grok/pico-preview-librechat-p0}"
COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.host.yml}"
cd "$ROOT"

echo "[pico] update $(hostname) $(date -Is)"
git fetch origin
git checkout "$BRANCH"
git pull --ff-only origin "$BRANCH"
echo "[pico] SHA=$(git rev-parse HEAD)"
git log -1 --oneline

# never print secrets
if [ -f .env ]; then
  if grep -q '^KIMI_API_KEY=.\+' .env; then
    echo "[pico] KIMI_API_KEY=SET"
  else
    echo "[pico] WARN KIMI_API_KEY empty — chat will fail"
  fi
else
  echo "[pico] WARN no .env"
fi

docker compose -f "$COMPOSE_FILE" up -d
# pick up mounted source / env changes for shell
docker compose -f "$COMPOSE_FILE" up -d --force-recreate librechat 2>/dev/null || true

echo "[pico] ps:"
docker compose -f "$COMPOSE_FILE" ps

echo "[pico] health:"
for i in $(seq 1 30); do
  if curl -sf --max-time 2 http://127.0.0.1:18765/health >/tmp/pico-health.json; then
    cat /tmp/pico-health.json; echo
    break
  fi
  sleep 1
done
curl -sS -o /dev/null -w "ui_login=%{http_code}\n" --max-time 5 http://127.0.0.1:8080/login || true
echo "[pico] done — open https://pico.aivia.asia/login"
echo "[pico] optional: bash scripts/vps-fix-login.sh   # if login broken"
echo "[pico] optional: bash scripts/agent-selftest.sh    # only if stack is local-style ports"
