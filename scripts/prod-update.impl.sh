#!/usr/bin/env bash
# Deploy impl. Entered only via prod-update.sh after checkout, so this file
# is the SHA being deployed — not the inode bash opened at invoke time.
set -euo pipefail

ROOT="${PICO_ROOT:-/opt/pico}"
COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.host.yml}"
DEPLOY_SHA="${PICO_DEPLOY_SHA:-}"

if [[ ! "$DEPLOY_SHA" =~ ^[0-9a-f]{40}$ ]]; then
  echo "[pico] BLOCKED: impl requires PICO_DEPLOY_SHA (run scripts/prod-update.sh)" >&2
  exit 2
fi

cd "$ROOT"
CURRENT_SHA="$(git rev-parse HEAD)"
if [ "$CURRENT_SHA" != "$DEPLOY_SHA" ]; then
  echo "[pico] BLOCKED: HEAD=$CURRENT_SHA is not PICO_DEPLOY_SHA=$DEPLOY_SHA; run the bootstrap" >&2
  exit 2
fi

# Preserve secrets: only stamp the public code identity into the ignored .env file.
if [ -f .env ]; then
  if grep -q '^PICO_GIT_SHA=' .env; then
    sed -i "s|^PICO_GIT_SHA=.*|PICO_GIT_SHA=${CURRENT_SHA}|" .env
  else
    echo "PICO_GIT_SHA=${CURRENT_SHA}" >>.env
  fi
fi
# Runtime identity for compose environment /health. Not a Docker build-arg.
export PICO_GIT_SHA="$CURRENT_SHA"

# One-teacher-one-disk host bind. Destroying a session must not wipe this tree.
TEACHER_DISK="${PICO_SANDBOX_DISK_HOST:-$ROOT/data/teacher-disks}"
mkdir -p "$TEACHER_DISK"
chmod 1777 "$TEACHER_DISK" 2>/dev/null || true
chown 65532:65532 "$TEACHER_DISK" 2>/dev/null || true

# Office unix socket rendezvous. Contract (not a recovery heuristic):
# - host bind, created BEFORE compose up (else dockerd makes root:755)
# - mode 1777 sticky (ops has no CAP_CHOWN; cannot chown 65532)
# - named volume pico_office_sock is forbidden
prepare_office_sock_bind() {
  local dir="$1"
  if [ -e "$dir" ] && [ ! -d "$dir" ]; then
    echo "[pico] FATAL: $dir exists and is not a directory" >&2
    exit 12
  fi
  if [ -d "$dir" ]; then
    if ! (: >"$dir/.pico-write-test") 2>/dev/null; then
      if [ -n "$(ls -A "$dir" 2>/dev/null)" ]; then
        echo "[pico] FATAL: $dir is not writable and not empty (owner $(stat -c %u:%g "$dir") mode $(stat -c %a "$dir"))" >&2
        exit 12
      fi
      rmdir "$dir" || {
        echo "[pico] FATAL: cannot replace unwritable empty $dir" >&2
        exit 12
      }
    else
      rm -f "$dir/.pico-write-test"
    fi
  fi
  mkdir -p "$dir"
  chmod 1777 "$dir" || {
    echo "[pico] FATAL: cannot chmod 1777 $dir (owner $(stat -c %u:%g "$dir") mode $(stat -c %a "$dir"))" >&2
    exit 12
  }
  rm -f "$dir/office.sock" 2>/dev/null || true
}

remove_leftover_office_named_volume() {
  local vol
  if grep -qE '^[[:space:]]+pico_office_sock:' "$COMPOSE_FILE"; then
    echo "[pico] FATAL: $COMPOSE_FILE still declares named volume pico_office_sock" >&2
    exit 12
  fi
  while IFS= read -r vol; do
    [ -z "$vol" ] && continue
    echo "[pico] removing leftover named volume $vol (office sock is host bind)"
    if ! docker volume rm "$vol"; then
      echo "[pico] FATAL: leftover office named volume $vol still in use" >&2
      exit 12
    fi
  done < <(docker volume ls -q --filter label=com.docker.compose.volume=pico_office_sock)
}

OFFICE_SOCK="${PICO_OFFICE_SOCK_HOST:-$ROOT/data/pico-office-sock}"
prepare_office_sock_bind "$OFFICE_SOCK"
remove_leftover_office_named_volume

if [ -f .env ] && grep -q '^KIMI_API_KEY=.\+' .env; then
  echo "[pico] KIMI_API_KEY=SET"
else
  echo "[pico] WARN KIMI_API_KEY empty — chat will fail"
fi

if [ -f .env ]; then
  if grep -q '^MEILI_MASTER_KEY=.\+' .env; then
    echo "[pico] MEILI_MASTER_KEY=SET"
  else
    MEILI_GEN="$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')"
    echo "MEILI_MASTER_KEY=${MEILI_GEN}" >> .env
    echo "[pico] MEILI_MASTER_KEY generated"
  fi
  if grep -q '^PICO_HOOK_SERVICE_TOKEN=.\+' .env; then
    echo "[pico] PICO_HOOK_SERVICE_TOKEN=SET"
  else
    # Empty PICO_HOOK_SERVICE_TOKEN= would otherwise leave export 503.
    # Do not print the value.
    if grep -q '^PICO_HOOK_SERVICE_TOKEN=' .env; then
      sed -i '/^PICO_HOOK_SERVICE_TOKEN=/d' .env
    fi
    HOOK_GEN="$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')"
    echo "PICO_HOOK_SERVICE_TOKEN=${HOOK_GEN}" >> .env
    echo "[pico] PICO_HOOK_SERVICE_TOKEN generated"
  fi
  if grep -q '^PICO_SANDBOX_TOKEN=.\+' .env; then
    echo "[pico] PICO_SANDBOX_TOKEN=SET"
  else
    # Empty token = pico-sandbox / pico-office accept any local caller. The
    # office socket dir is 1777 on a shared host, so this must never stay empty.
    # Do not print the value.
    if grep -q '^PICO_SANDBOX_TOKEN=' .env; then
      sed -i '/^PICO_SANDBOX_TOKEN=/d' .env
    fi
    SANDBOX_GEN="$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')"
    echo "PICO_SANDBOX_TOKEN=${SANDBOX_GEN}" >> .env
    echo "[pico] PICO_SANDBOX_TOKEN generated"
  fi
  if ! grep -q '^PICO_MEILI_URL=' .env; then
    echo "PICO_MEILI_URL=http://127.0.0.1:7700" >> .env
  fi
fi

docker compose -f "$COMPOSE_FILE" build pico-api librechat pico-sandbox pico-office
docker compose -f "$COMPOSE_FILE" up -d --force-recreate pico-api librechat pico-sandbox pico-office meilisearch

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

# pico-office must answer over its unix socket, or the office write path is
# down (pico-api fails closed; it never runs scripts in-process). Fake-green guard.
echo "[pico] pico-office:"
office_ready=0
for _ in $(seq 1 30); do
  if docker compose -f "$COMPOSE_FILE" exec -T pico-api python3 -c '
import sys, httpx
t = httpx.HTTPTransport(uds="/run/pico-office/office.sock")
r = httpx.Client(transport=t, timeout=3).get("http://pico-office/health")
body = r.json()
sys.exit(0 if body.get("ok") and body.get("service") == "pico-office" and body.get("jail") is False else 1)
' >/dev/null 2>&1; then
    office_ready=1
    break
  fi
  sleep 1
done
if [ "$office_ready" -ne 1 ]; then
  echo "[pico] FATAL: pico-office unix socket not answering — office write path would be down" >&2
  docker compose -f "$COMPOSE_FILE" logs --no-log-prefix --tail 20 pico-office >&2 || true
  exit 11
fi
echo "[pico] pico-office socket ok"

echo "[pico] meili:"
meili_ready=0
for _ in $(seq 1 30); do
  if curl -sf --max-time 2 http://127.0.0.1:7700/health >/dev/null; then
    meili_ready=1
    break
  fi
  sleep 1
done
if [ "$meili_ready" -ne 1 ]; then
  echo "[pico] FATAL: meilisearch 127.0.0.1:7700 did not become ready" >&2
  exit 9
fi
echo "[pico] meili health ok"
REINDEX_FILE="$(mktemp)"
REINDEX_CODE="$(curl -sS -o "$REINDEX_FILE" -w "%{http_code}" --max-time 120 -X POST http://127.0.0.1:18765/v1/kb/reindex-all || echo 000)"
REINDEX_OUT="$(cat "$REINDEX_FILE" 2>/dev/null || true)"
rm -f "$REINDEX_FILE"
echo "[pico] kb reindex http=${REINDEX_CODE} body=${REINDEX_OUT:-empty}"
if [ "$REINDEX_CODE" != "200" ]; then
  echo "[pico] FATAL: kb reindex-all failed (http=${REINDEX_CODE}) — refusing fake-green deploy" >&2
  exit 10
fi
if ! python3 -c '
import json, sys
raw = sys.argv[1]
try:
    body = json.loads(raw)
except Exception as exc:
    print(f"[pico] FATAL: kb reindex body not JSON: {exc}", file=sys.stderr)
    raise SystemExit(10)
if body.get("ok") is not True:
    print("[pico] FATAL: kb reindex ok is not true", file=sys.stderr)
    raise SystemExit(10)
print(
    "[pico] kb reindex ok indexed=%s skipped=%s total=%s"
    % (body.get("indexed"), body.get("skipped"), body.get("total"))
)
' "$REINDEX_OUT"; then
  exit 10
fi
if command -v ss >/dev/null 2>&1; then
  if ss -lntp 2>/dev/null | grep -E '0\.0\.0\.0:7700|\*:7700' >/dev/null; then
    echo "[pico] FATAL: meilisearch listening on 0.0.0.0:7700" >&2
    exit 6
  fi
  echo "[pico] listen check: 7700 not on 0.0.0.0 (ok)"
fi

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
