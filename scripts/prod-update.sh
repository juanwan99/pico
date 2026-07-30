#!/usr/bin/env bash
# Production hot-update on Aliyun VPS. Run ON the server:
#   bash /opt/pico/scripts/prod-update.sh
# Hard: always align to origin tip (stash local compose/env-layout noise first).
set -euo pipefail
ROOT="${PICO_ROOT:-/opt/pico}"
BRANCH="${PICO_BRANCH:-grok/pico-preview-librechat-p0}"
COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.host.yml}"
cd "$ROOT"

echo "[pico] update $(hostname) $(date -Is)"
echo "[pico] before: $(git rev-parse --short HEAD 2>/dev/null || echo none)"

git fetch origin
# preserve secrets: never touch .env content beyond PICO_GIT_SHA stamp later
# local compose tweaks often block pull — stash untracked-safe:
if ! git diff --quiet || ! git diff --cached --quiet; then
  echo "[pico] stashing local tracked edits (compose etc.)"
  git stash push -u -m "pico-prod-update-auto $(date -Is)" --     docker-compose.host.yml docker-compose.yml ||   git stash push -m "pico-prod-update-auto $(date -Is)" || true
fi

git checkout "$BRANCH"
# prefer hard align to origin so "origin SHA == local" always true after update
git reset --hard "origin/${BRANCH}"
echo "[pico] after:  $(git rev-parse HEAD)"
echo "[pico] origin: $(git rev-parse "origin/${BRANCH}")"
git log -1 --oneline

SHA=$(git rev-parse HEAD)
if [ -f .env ]; then
  if grep -q '^PICO_GIT_SHA=' .env; then
    sed -i "s|^PICO_GIT_SHA=.*|PICO_GIT_SHA=${SHA}|" .env
  else
    echo "PICO_GIT_SHA=${SHA}" >>.env
  fi
fi
export PICO_GIT_SHA="$SHA"

if [ -f .env ]; then
  if grep -q '^KIMI_API_KEY=.\+' .env; then
    echo "[pico] KIMI_API_KEY=SET"
  else
    echo "[pico] WARN KIMI_API_KEY empty — chat will fail"
  fi
else
  echo "[pico] WARN no .env"
fi

# ensure host compose still binds localhost only (idempotent safety)
if [ -f "$COMPOSE_FILE" ]; then
  # no rewrite of secrets; compose from git already uses 127.0.0.1
  true
fi

docker compose -f "$COMPOSE_FILE" up -d
docker compose -f "$COMPOSE_FILE" up -d --force-recreate pico-api
docker compose -f "$COMPOSE_FILE" up -d --force-recreate librechat 2>/dev/null || true

echo "[pico] ps:"
docker compose -f "$COMPOSE_FILE" ps

echo "[pico] health:"
for i in $(seq 1 40); do
  if curl -sf --max-time 2 http://127.0.0.1:18765/health >/tmp/pico-health.json; then
    cat /tmp/pico-health.json; echo
    break
  fi
  sleep 1
done
curl -sS -o /dev/null -w "ui_login=%{http_code}\n" --max-time 5 http://127.0.0.1:8080/login || true

# fail loud if still old tip when EXPECTED set
if [ -n "${EXPECT_SHA_PREFIX:-}" ]; then
  cur=$(git rev-parse --short HEAD)
  case "$cur" in
    ${EXPECT_SHA_PREFIX}*) echo "[pico] EXPECT_SHA ok $cur" ;;
    *) echo "[pico] EXPECT_SHA mismatch got=$cur want_prefix=$EXPECT_SHA_PREFIX" >&2; exit 3 ;;
  esac
fi

echo "[pico] done — open https://pico.aivia.asia/login"
echo "[pico] optional: bash scripts/vps-fix-login.sh"
