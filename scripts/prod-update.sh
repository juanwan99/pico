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

print_main_refspec_help() {
  echo "[pico] configured remote.origin.fetch:" >&2
  git config --get-all remote.origin.fetch 2>/dev/null | sed 's/^/[pico]   /' >&2 || true
  echo "[pico] fix: git config --replace-all remote.origin.fetch '+refs/heads/main:refs/remotes/origin/main'" >&2
  echo "[pico] then rerun: git fetch origin main" >&2
}

git fetch origin main
if ! FETCH_SHA="$(git rev-parse --verify 'FETCH_HEAD^{commit}' 2>/dev/null)"; then
  echo "[pico] BLOCKED: fetch completed but FETCH_HEAD is not a commit" >&2
  print_main_refspec_help
  exit 3
fi
if ! MAIN_SHA="$(git rev-parse --verify 'refs/remotes/origin/main^{commit}' 2>/dev/null)"; then
  echo "[pico] BLOCKED: origin/main is missing after fetching main" >&2
  print_main_refspec_help
  exit 3
fi
if [ "$MAIN_SHA" != "$FETCH_SHA" ]; then
  echo "[pico] BLOCKED: origin/main did not advance to the fetched main tip" >&2
  echo "[pico] FETCH_HEAD=$FETCH_SHA" >&2
  echo "[pico] origin/main=$MAIN_SHA" >&2
  print_main_refspec_help
  exit 3
fi

ORIGIN_FETCH_REFSPECS="$(git config --get-all remote.origin.fetch 2>/dev/null || true)"
FETCH_TRACKS_MAIN=0
while IFS= read -r refspec; do
  normalized_refspec="${refspec#+}"
  if [ "$normalized_refspec" = 'refs/heads/main:refs/remotes/origin/main' ] || \
    [ "$normalized_refspec" = 'refs/heads/*:refs/remotes/origin/*' ]; then
    FETCH_TRACKS_MAIN=1
    break
  fi
done <<<"$ORIGIN_FETCH_REFSPECS"
if [ "$FETCH_TRACKS_MAIN" -ne 1 ]; then
  echo "[pico] BLOCKED: remote.origin.fetch does not track main as origin/main" >&2
  print_main_refspec_help
  exit 3
fi

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

# True-Pi binary must ship with the production API image (D1 / T-OPS-TRUE-PI-HYGIENE).
# docker-compose.host.yml builds Dockerfile.pico-api.true-pi — lean rebuilds must not
# silently drop pi while DEFAULT=1 is expected.
if ! python3 -c '
import json, sys
path = sys.argv[1]
health = json.load(open(path))
ok = health.get("true_pi_binary_available") is True
pin = health.get("true_pi_package_pin") or ""
print(f"[pico] true_pi_binary_available={ok}")
print(f"[pico] true_pi_package_pin={pin}")
if not ok:
    print("[pico] FATAL: true_pi_binary_available is not true after deploy", file=sys.stderr)
    print("[pico] fix: ensure compose builds Dockerfile.pico-api.true-pi", file=sys.stderr)
    raise SystemExit(8)
' "$HEALTH_FILE"; then
  exit 8
fi

# Product UI must actually serve /login. Allow LibreChat up to about 60 seconds
# after recreate to become ready; transport failures and non-200 responses fail closed.
# Shared ECS: LibreChat loopback must be 18088 — never 8080 (edu-core-bff on same host).
# docker-compose.host.yml PORT=18088; override via LIBRECHAT_URL when needed.
LC_URL="${LIBRECHAT_URL:-http://127.0.0.1:18088}"
UI_LOGIN_CODE="000"
UI_READY_ATTEMPTS=30
echo "[pico] UI readiness: waiting for ${LC_URL}/login HTTP 200 (${UI_READY_ATTEMPTS} attempts, 1s interval)"
for attempt in $(seq 1 "$UI_READY_ATTEMPTS"); do
  if UI_LOGIN_CODE="$(
    curl -s -o /dev/null -w "%{http_code}" --max-time 1 \
      "${LC_URL}/login"
  )" && [ "$UI_LOGIN_CODE" = "200" ]; then
    echo "[pico] UI ready attempt=${attempt}/${UI_READY_ATTEMPTS}"
    break
  fi
  echo "[pico] UI not ready attempt=${attempt}/${UI_READY_ATTEMPTS} status=${UI_LOGIN_CODE:-000}" >&2
  if [ "$attempt" -lt "$UI_READY_ATTEMPTS" ]; then
    sleep 1
  fi
done
if [ "$UI_LOGIN_CODE" != "200" ]; then
  echo "[pico] FATAL: UI /login did not become ready after ${UI_READY_ATTEMPTS} attempts; last_status=${UI_LOGIN_CODE:-000}" >&2
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
