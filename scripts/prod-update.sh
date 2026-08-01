#!/usr/bin/env bash
# Production update on the Pico host. Deploys only an explicitly selected main SHA.
# Usage: PICO_DEPLOY_SHA=<full-40-char-main-sha> bash /opt/pico/scripts/prod-update.sh
set -euo pipefail

ROOT="${PICO_ROOT:-/opt/pico}"
COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.host.yml}"
DEPLOY_SHA="${PICO_DEPLOY_SHA:-}"

if [[ ! "$DEPLOY_SHA" =~ ^[0-9a-f]{40}$ ]]; then
  echo "[pico] BLOCKED: PICO_DEPLOY_SHA must be a full 40-character commit SHA" >&2
  exit 2
fi

cd "$ROOT"
echo "[pico] update $(hostname) $(date -Is)"
echo "[pico] before: $(git rev-parse HEAD 2>/dev/null || echo none)"

# Production checkouts are immutable inputs. Never hide local edits in an automatic stash.
if [ -n "$(git status --porcelain --untracked-files=normal)" ]; then
  echo "[pico] BLOCKED: production worktree has local changes; inspect them before deploy" >&2
  git status --short >&2
  exit 2
fi

git fetch origin main
MAIN_SHA="$(git rev-parse origin/main)"
if [ "$DEPLOY_SHA" != "$MAIN_SHA" ]; then
  echo "[pico] BLOCKED: requested SHA is not the current origin/main tip" >&2
  echo "[pico] requested=$DEPLOY_SHA" >&2
  echo "[pico] origin/main=$MAIN_SHA" >&2
  exit 3
fi

# Detached checkout prevents a server-local branch from becoming a second release source.
git checkout --detach "$DEPLOY_SHA"
CURRENT_SHA="$(git rev-parse HEAD)"
if [ "$CURRENT_SHA" != "$DEPLOY_SHA" ]; then
  echo "[pico] FATAL: checkout mismatch got=$CURRENT_SHA want=$DEPLOY_SHA" >&2
  exit 3
fi
echo "[pico] deploying: $CURRENT_SHA"
git log -1 --oneline

# Preserve secrets: only stamp the public code identity into the ignored .env file.
if [ -f .env ]; then
  if grep -q '^PICO_GIT_SHA=' .env; then
    sed -i "s|^PICO_GIT_SHA=.*|PICO_GIT_SHA=${CURRENT_SHA}|" .env
  else
    echo "PICO_GIT_SHA=${CURRENT_SHA}" >>.env
  fi
fi
export PICO_GIT_SHA="$CURRENT_SHA"

if [ -f .env ] && grep -q '^KIMI_API_KEY=.\+' .env; then
  echo "[pico] KIMI_API_KEY=SET"
else
  echo "[pico] WARN KIMI_API_KEY empty — chat will fail"
fi

docker compose -f "$COMPOSE_FILE" build pico-api librechat
docker compose -f "$COMPOSE_FILE" up -d --force-recreate pico-api librechat

echo "[pico] ps:"
docker compose -f "$COMPOSE_FILE" ps

HEALTH_FILE="$(mktemp)"
trap 'rm -f "$HEALTH_FILE"' EXIT
echo "[pico] health:"
ready=0
for _ in $(seq 1 40); do
  if curl -sf --max-time 2 http://127.0.0.1:18765/health >"$HEALTH_FILE"; then
    cat "$HEALTH_FILE"
    echo
    ready=1
    break
  fi
  sleep 1
done
if [ "$ready" -ne 1 ]; then
  echo "[pico] FATAL: health endpoint did not become ready" >&2
  exit 4
fi

HEALTH_SHA="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1])).get("git_sha", ""))' "$HEALTH_FILE")"
if [ "$HEALTH_SHA" != "$CURRENT_SHA" ]; then
  echo "[pico] FATAL: health.git_sha mismatch got=$HEALTH_SHA want=$CURRENT_SHA" >&2
  exit 5
fi
echo "[pico] health.git_sha exact match: $HEALTH_SHA"

# Product UI must actually serve /login. Transport failure (set -e) and non-200 both fail closed.
UI_LOGIN_CODE="$(
  curl -sS -o /dev/null -w "%{http_code}" --max-time 5 \
    http://127.0.0.1:8080/login
)"
if [ "$UI_LOGIN_CODE" != "200" ]; then
  echo "[pico] FATAL: UI /login HTTP status not 200 got=${UI_LOGIN_CODE}" >&2
  exit 7
fi
echo "[pico] ui_login=${UI_LOGIN_CODE}"

# Security: API must not listen on all interfaces.
if command -v ss >/dev/null 2>&1; then
  if ss -lntp 2>/dev/null | grep -E '0\.0\.0\.0:18765|\*:18765' >/dev/null; then
    echo "[pico] FATAL: pico-api listening on 0.0.0.0:18765" >&2
    exit 6
  fi
  echo "[pico] listen check: 18765 not on 0.0.0.0 (ok)"
fi

echo "[pico] done — open https://pico.aivia.asia/login"
