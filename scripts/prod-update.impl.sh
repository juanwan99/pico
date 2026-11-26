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

# Preserve secrets: change only the deployment setting passed to this function.
stamp_env() {
  local key="$1" value="$2"
  if [ -f .env ]; then
    if grep -q "^$key=" .env; then
      sed -i "s|^$key=.*|$key=$value|" .env
    else
      echo "$key=$value" >>.env
    fi
  fi
}
stamp_env PICO_GIT_SHA "$CURRENT_SHA"
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

# edu → Pico bridge socket (#995). Same host-bind contract as the office sock.
EDU_GW_SOCK="${PICO_EDU_GW_SOCK_HOST:-$ROOT/data/pico-edu-gw-sock}"
mkdir -p "$EDU_GW_SOCK"
chmod 1777 "$EDU_GW_SOCK" 2>/dev/null || true

# 2026-09-15 the bridge was hand-run (`docker run`) to restore edu after the
# dockerd restart. Compose owns it from this SHA on: a same-named container
# without our compose label would make `up` fail with a name conflict, so
# remove it first. edu loses the gateway for the second compose needs to
# recreate it — acceptable, and far better than a /tmp orphan.
adopt_hand_run_edu_gw() {
  local name project
  for name in edu-pico-gw pico-edu-gw-host; do
    project="$(docker inspect -f '{{index .Config.Labels "com.docker.compose.project"}}' "$name" 2>/dev/null || true)"
    if docker inspect "$name" >/dev/null 2>&1 && [ "$project" != "pico" ]; then
      echo "[pico] adopting hand-run $name into compose (removing the manual container)"
      docker rm -f "$name" >/dev/null 2>&1 || true
    fi
  done
}
adopt_hand_run_edu_gw

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
  # #1003: one-shot host env bump. Compose interpolates this; Python default
  # alone would leave live at 2 because /opt/pico/.env already pins it.
  if grep -q '^PICO_CHAT_MAX_CONCURRENT=2$' .env; then
    sed -i 's/^PICO_CHAT_MAX_CONCURRENT=2$/PICO_CHAT_MAX_CONCURRENT=4/' .env
    echo "[pico] PICO_CHAT_MAX_CONCURRENT 2→4 (#1003)"
  fi
fi

# Base images must be resolvable before we spend minutes building. Live
# 2026-09-13: dockerd sat behind a dead host proxy and the first mirror had
# started demanding login; build died at FROM after 10 min of output. Fail
# here, in one line, and name the machine-side cause.
precheck_base_images() {
  local df img seen="" missing=""
  while IFS= read -r df; do
    [ -n "$df" ] && [ -f "$df" ] || continue
    while IFS= read -r img; do
      [ -z "$img" ] && continue
      case " $seen " in *" $img "*) continue ;; esac
      seen="$seen $img"
      if docker image inspect "$img" >/dev/null 2>&1; then
        continue
      fi
      echo "[pico] base image $img not local — pulling"
      if ! docker pull "$img" >/dev/null 2>&1; then
        missing="$missing $img"
      fi
    done < <(grep -E '^FROM[[:space:]]' "$df" | awk '{for(i=2;i<=NF;i++){if($i !~ /^--/){print $i;break}}}' | grep -E '[:@]')
  done < <(grep -E '^[[:space:]]+dockerfile:' "$COMPOSE_FILE" | awk '{print $2}' | sort -u)
  # Pulled images (no build:) — e.g. the socat bridge. Skip our own pico-* builds.
  while IFS= read -r img; do
    [ -z "$img" ] && continue
    case "$img" in pico-*) continue ;; esac
    case " $seen " in *" $img "*) continue ;; esac
    seen="$seen $img"
    if docker image inspect "$img" >/dev/null 2>&1; then
      continue
    fi
    echo "[pico] image $img not local — pulling"
    if ! docker pull "$img" >/dev/null 2>&1; then
      missing="$missing $img"
    fi
  done < <(grep -E '^[[:space:]]+image:' "$COMPOSE_FILE" | awk '{print $2}' | grep -E '[:@]' | sort -u)
  if [ -n "$missing" ]; then
    echo "[pico] FATAL: base image(s) not local and not pullable:$missing" >&2
    echo "[pico] 机器层问题，不是代码：dockerd 代理 / 镜像站（见 #985 root 清单、#994 阶段 0）。未碰任何容器。" >&2
    exit 13
  fi
}
precheck_base_images

docker compose -f "$COMPOSE_FILE" build pico-api librechat pico-sandbox pico-office

# Card #1093 workspace boxes: only when .env arms the runner. Host prerequisites
# (runsc runtime, pico-ws network) are root work in scripts/pi-runner-host-setup.sh;
# without them fail here, before any container is touched.
RUNNER_ON=0
if [ -f .env ] && grep -Eq '^PICO_RUNNER_TOKEN=.{24,}' .env; then
  RUNNER_ON=1
  if ! docker info --format '{{json .Runtimes}}' | grep -q '"runsc"'; then
    echo "[pico] FATAL: PICO_RUNNER_TOKEN set but dockerd has no runsc runtime — run: sudo bash scripts/pi-runner-host-setup.sh" >&2
    exit 15
  fi
  if ! docker network inspect pico-ws >/dev/null 2>&1; then
    echo "[pico] FATAL: PICO_RUNNER_TOKEN set but docker network pico-ws missing — run: sudo bash scripts/pi-runner-host-setup.sh" >&2
    exit 15
  fi
  docker compose -f "$COMPOSE_FILE" build pi-runner pi-workspace
fi

# Teacher runs are owned by the pico-api process. Wait first: poll the live
# /health inflight_runs (old image without the field, or API down, counts as 0).
# #1104 T4: long office tasks run 5–10 min (LT6 570s); the wait covers a whole
# one so a deploy lands between tasks, not inside one. Tunable via .env.
# Past the budget we warn and recreate: workspace runs carry on in the same Pi
# session after restart (#1133 run_resume.py); the rest fail in teacher words.
inflight_runs_now() {
  local body
  body="$(curl -sf --max-time 2 http://127.0.0.1:18765/health 2>/dev/null || true)"
  [ -z "$body" ] && { echo 0; return; }
  python3 -c '
import json, sys
try:
    n = json.loads(sys.argv[1]).get("inflight_runs", 0)
    print(int(n) if isinstance(n, int) and n > 0 else 0)
except Exception:
    print(0)
' "$body"
}

if [ -z "${PICO_DEPLOY_DRAIN_WAIT_S:-}" ] && [ -f .env ]; then
  PICO_DEPLOY_DRAIN_WAIT_S="$(grep -E '^PICO_DEPLOY_DRAIN_WAIT_S=[0-9]+$' .env | tail -1 | cut -d= -f2 || true)"
fi
DRAIN_WAIT_S="${PICO_DEPLOY_DRAIN_WAIT_S:-900}"
# edu-core acceptance on this host talks to Pico: queue for its lock first,
# then drain (its runs are done by then) and recreate (edu-core#4735).
. "$ROOT/scripts/edu-accept-lock.sh"
edu_accept_lock_take || exit $?
DRAIN_POLL_S=5
inflight="$(inflight_runs_now)"
if [ "$inflight" -gt 0 ]; then
  echo "[pico] inflight_runs=${inflight} — waiting up to ${DRAIN_WAIT_S}s before recreate"
  waited=0
  while [ "$inflight" -gt 0 ] && [ "$waited" -lt "$DRAIN_WAIT_S" ]; do
    sleep "$DRAIN_POLL_S"
    waited=$((waited + DRAIN_POLL_S))
    inflight="$(inflight_runs_now)"
  done
  if [ "$inflight" -gt 0 ]; then
    echo "[pico] WARN recreating with inflight_runs=${inflight} after ${waited}s (owner allows interrupt)" >&2
  else
    echo "[pico] inflight_runs=0 after ${waited}s — recreating"
  fi
fi

health_identity() {
  local port="$1"
  shift
  "$@" curl -fsS --max-time 2 "http://127.0.0.1:$port/health" >"$HEALTH_FILE" || return
  python3 -c '
import json, sys
body = json.load(sys.stdin)
if body.get("ok") is not True or not body.get("git_sha"):
    sys.exit(5)
print("{}:{}".format(body["git_sha"], body.get("backend_port", "")))
' <"$HEALTH_FILE"
}

health_at() {
  local port="$1" expected="$2" identity status=4
  shift 2
  for _ in $(seq 1 40); do
    if identity="$(health_identity "$port" "$@")"; then
      if [ "$identity" = "$expected" ]; then
        cat "$HEALTH_FILE"
        echo
        echo "[pico] health.git_sha exact match: ${identity%%:*} (port $port, backend ${identity#*:})"
        return 0
      fi
      status=5
      # HUP is asynchronous. Only the shared listener can still serve the old SHA.
      if [ "$#" -ne 0 ]; then break; fi
    fi
    sleep 1
  done
  if [ "$status" -eq 5 ]; then
    echo "[pico] FATAL: port $port health identity mismatch got=$identity want=$expected" >&2
  else
    echo "[pico] FATAL: port $port /health did not become ready" >&2
  fi
  return "$status"
}

write_listener_config() {
  local file
  file="$(mktemp "$LISTENER_DIR/nginx.XXXXXX")" || return
  cat >"$file" <<EOF || return
error_log /dev/stderr notice;
worker_shutdown_timeout 60s;
events {}
stream {
    server {
        listen 127.0.0.1:18765;
        proxy_pass 127.0.0.1:$1;
        proxy_half_close on;
        proxy_timeout 6h;
    }
}
EOF
  mv "$file" "$LISTENER_DIR/$2"
}

reload_api_listener() {
  mv "$LISTENER_DIR/nginx.next.conf" "$LISTENER_DIR/nginx.conf" || return
  docker kill --signal HUP "$1"
}

switch_api_listener() {
  local listener="$1" port="$2" identity="$3" workers
  if [ -z "$listener" ]; then
    write_listener_config "$port" nginx.conf || return
    docker compose -f "$COMPOSE_FILE" up -d --no-deps pico-api-listener || return
  else
    workers="$(docker exec "$listener" cat /proc/1/task/1/children)" || return
    reload_api_listener "$listener" || return
  fi
  health_at 18765 "$identity" || return
  if [ -n "$listener" ]; then
    # The old workers still own already accepted TCP connections after HUP.
    # Wait for those sessions to drain before stopping their upstream.
    timeout 65 docker exec "$listener" sh -c '
      for pid do
        while kill -0 "$pid" 2>/dev/null; do sleep 0.2; done
      done
    ' sh $workers
  fi
}

record_backend_port() {
  if [ -f .env ] && ! grep -qx "PICO_API_BACKEND_PORT=$1" .env; then
    PICO_OPS_ENV="$ROOT/.env" python3 "$ROOT/scripts/pico_ops_watch.py" env-set \
      "PICO_API_BACKEND_PORT=$1" --card 'pico#1474' --why "API handoff for $CURRENT_SHA"
  fi
}

api_port() {
  docker inspect --format '{{index .Config.Labels "pico.api.port"}}' "$1"
}

recover_api_handoff() {
  local listener="$1" id port identity active_identity active_port inactive="" inactive_name
  shift
  old_api=""
  if [ -n "$listener" ]; then
    active_identity="$(health_identity 18765)"
  fi
  for id do
    port="$(api_port "$id")"
    if { [ -z "$listener" ] && [ -z "$port" ]; } ||
       { [ -n "$listener" ] && [ -n "$port" ] &&
         identity="$(health_identity "$port" docker exec "$id")" &&
         [ "$identity" = "$active_identity" ]; }; then
      if [ -n "$old_api" ]; then
        echo "[pico] FATAL: ambiguous live API in interrupted handoff" >&2
        return 4
      fi
      old_api="$id"
      active_port="$port"
    else
      inactive="$id"
    fi
  done
  if [ -z "$old_api" ] || [ -z "$inactive" ]; then
    echo "[pico] FATAL: cannot identify the live API in interrupted handoff" >&2
    return 4
  fi
  inactive_name="$(docker inspect --format '{{.Name}}' "$inactive")"
  if [ -n "$listener" ]; then
    # Confirm the live target again and drain any workers from the interrupted reload.
    write_listener_config "$active_port" nginx.next.conf
    switch_api_listener "$listener" "$active_port" "$active_identity"
    docker stop "$inactive"
  else
    docker stop "$inactive"
    docker start "$old_api"
  fi
  docker rm "$inactive"
  if [[ "$inactive_name" == *-1 ]]; then
    docker rename "$old_api" "${inactive_name#/}"
  fi
  if [ -n "$active_port" ]; then
    record_backend_port "$active_port"
  fi
}

deploy_pico_api() {
  local old_api old_port="" old_name listener new_port=18769 replicas=1 legacy=0
  local api_ids id candidate_status=0 image config current old_identity
  local -a containers
  mkdir -p "$LISTENER_DIR"
  listener="$(docker compose -f "$COMPOSE_FILE" ps --quiet pico-api-listener)"
  api_ids="$(docker compose -f "$COMPOSE_FILE" ps --all --quiet pico-api)"
  read -r -a containers <<< "${api_ids//$'\n'/ }"
  case "${#containers[@]}" in
    0) old_api="" ;;
    1) old_api="${containers[0]}" ;;
    2) recover_api_handoff "$listener" "${containers[@]}" ;;
    *) echo "[pico] FATAL: more than two pico-api containers before handoff" >&2; exit 4 ;;
  esac
  if [ -n "$old_api" ]; then
    old_port="$(api_port "$old_api")"
    old_name="$(docker inspect --format '{{.Name}}' "$old_api")"
    replicas=2
    case "$old_port" in
      18769) new_port=18770 ;;
      "") legacy=1 ;;
    esac
  else
    docker compose -f "$COMPOSE_FILE" up -d mongo meilisearch pico-office
  fi
  if [ -n "$listener" ] && [ -n "$old_port" ]; then
    # A no-op build/config keeps the running process, as under Compose's normal up.
    image="$(docker compose -f "$COMPOSE_FILE" config --format json pico-api | python3 -c '
import json, sys
print(json.load(sys.stdin)["services"]["pico-api"]["image"])
')"
    image="$(docker image inspect --format '{{.Id}}' "$image")"
    config="$(PICO_API_BACKEND_PORT="$old_port" docker compose -f "$COMPOSE_FILE" config --hash pico-api)"
    current="$(docker inspect --format '{{.State.Running}} {{.Image}} {{index .Config.Labels "com.docker.compose.config-hash"}}' "$old_api")"
    if [ "$current" = "true $image ${config#* }" ]; then
      new_api="$old_api"
      health_at 18765 "$CURRENT_SHA:$old_port"
      # An interrupted deploy can leave just the promoted container to rename.
      if [[ "$old_name" =~ -pico-api-[0-9]+$ && "$old_name" != *-1 ]]; then
        old_name="${old_name#/}"
        docker rename "$old_api" "${old_name%-*}-1"
      fi
      record_backend_port "$old_port"
      return
    fi
  fi

  if [ -n "$listener" ]; then
    write_listener_config "$new_port" nginx.next.conf
    docker exec "$listener" nginx -t -c /etc/pico-api/nginx.next.conf
  fi
  PICO_API_BACKEND_PORT="$new_port" docker compose -f "$COMPOSE_FILE" up --no-start --no-deps \
    --no-recreate --scale "pico-api=$replicas" pico-api
  api_ids="$(docker compose -f "$COMPOSE_FILE" ps --all --quiet pico-api)"
  new_api=""
  for id in $api_ids; do
    if [ "$id" != "$old_api" ]; then new_api="$id"; fi
  done
  if [ -z "$new_api" ]; then
    echo "[pico] FATAL: Compose did not create a pico-api candidate" >&2
    exit 4
  fi
  # The old release binds 18765 directly and has no background lock.
  if [ "$legacy" = "1" ]; then
    echo "[pico] first listener migration: stopping the legacy 18765 bind"
    docker stop "$old_api"
  fi
  docker start "$new_api" &&
    health_at "$new_port" "$CURRENT_SHA:$new_port" docker exec "$new_api" || candidate_status=$?
  if [ "$candidate_status" -ne 0 ]; then
    docker logs --tail 30 "$new_api" || true
    if [ "$legacy" = "1" ]; then
      docker stop "$new_api"
      docker start "$old_api"
      if ! docker rm "$new_api"; then
        echo "[pico] FATAL: could not remove stopped candidate $new_api" >&2
      fi
    else
      docker rm -f "$new_api"
    fi
    exit "$candidate_status"
  fi

  candidate_status=0
  switch_api_listener "$listener" "$new_port" "$CURRENT_SHA:$new_port" || candidate_status=$?
  if [ "$candidate_status" -ne 0 ]; then
    echo "[pico] FATAL: 18765 did not switch to the candidate" >&2
    if [ -n "$listener" ]; then
      write_listener_config "$old_port" nginx.next.conf
      reload_api_listener "$listener"
      old_identity="$(health_identity "$old_port" docker exec "$old_api")"
      health_at 18765 "$old_identity"
    else
      docker compose -f "$COMPOSE_FILE" stop pico-api-listener
    fi
    docker stop "$new_api"
    if [ "$legacy" = "1" ]; then docker start "$old_api"; fi
    docker rm "$new_api"
    exit "$candidate_status"
  fi
  record_backend_port "$new_port"
  if [ -n "$old_api" ]; then
    if [ "$legacy" = "0" ]; then docker stop "$old_api"; fi
    docker rm "$old_api"
    # Existing operations scripts address the original Compose container name.
    docker rename "$new_api" "${old_name#/}"
  fi
}

HEALTH_FILE="$(mktemp)"
trap 'rm -f "$HEALTH_FILE"' EXIT
LISTENER_DIR="$ROOT/data/pico-api-listener"
deploy_pico_api

# Dependencies that name pico-api must not trigger a second Compose convergence.
docker compose -f "$COMPOSE_FILE" up -d --no-deps mongo librechat pico-sandbox pico-office meilisearch pico-edu-gw-host edu-pico-gw
if [ "$RUNNER_ON" = "1" ]; then
  # Recreates only when runner code/config changed; boxes of a restarted
  # runner are reaped and those turns fail in teacher words.
  docker compose -f "$COMPOSE_FILE" up -d pi-runner
  RUNNER_OK=0
  for _ in $(seq 1 20); do
    if curl -sf --max-time 2 http://127.0.0.1:18790/health >/dev/null; then RUNNER_OK=1; break; fi
    sleep 1
  done
  if [ "$RUNNER_OK" != "1" ]; then
    echo "[pico] FATAL: pi-runner 127.0.0.1:18790/health not answering" >&2
    docker compose -f "$COMPOSE_FILE" logs --no-log-prefix --tail 20 pi-runner >&2 || true
    exit 15
  fi
  echo "[pico] pi-runner ok"
fi

echo "[pico] ps:"
docker compose -f "$COMPOSE_FILE" ps

# pico-office must answer over its unix socket, or the office write path is
# down (pico-api fails closed; it never runs scripts in-process). Fake-green guard.
echo "[pico] pico-office:"
office_ready=0
for _ in $(seq 1 30); do
  if docker exec "$new_api" python3 -c '
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

# edu → Pico bridge must answer from inside edu's network, or edu's sidebar/SSO
# is silently dead while everything on loopback looks green (2026-09-15).
echo "[pico] edu-pico-gw:"
# busybox wget from the same pinned socat image (socat's own STDIO client
# half-closes on stdin EOF before the reply lands — verified 2026-09-15).
EDU_GW_IMAGE="$( { grep -oE 'alpine/socat@sha256:[0-9a-f]+' "$COMPOSE_FILE" || true; } | head -1)"
EDU_GW_IMAGE="${EDU_GW_IMAGE:-alpine/socat@sha256:3d9e7966201dd3a065df591020a09fd3c70845de7e7086e3531ea69db774406b}"
edu_gw_ready=0
edu_gw_body=""
for _ in $(seq 1 20); do
  edu_gw_body="$(docker run --rm --network edu-core_default --entrypoint wget "$EDU_GW_IMAGE" \
    -qO- -T 5 http://edu-pico-gw:18765/health 2>/dev/null || true)"
  if python3 -c '
import json, sys
body = json.loads(sys.argv[1])
sys.exit(0 if body.get("ok") is True and body.get("git_sha") == sys.argv[2] else 1)
' "$edu_gw_body" "$CURRENT_SHA" 2>/dev/null; then
    edu_gw_ready=1
    break
  fi
  sleep 1
done
if [ "$edu_gw_ready" -ne 1 ]; then
  echo "[pico] FATAL: edu-pico-gw:18765 does not answer /health with this SHA from edu-core_default — edu → Pico would be down" >&2
  echo "[pico] last body: ${edu_gw_body:-empty}" >&2
  docker compose -f "$COMPOSE_FILE" logs --no-log-prefix --tail 10 edu-pico-gw pico-edu-gw-host >&2 || true
  exit 14
fi
echo "[pico] edu-pico-gw ok (sha matches)"

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
# pico-api owns the background rebuild. Check acceptance and the existing index.
REINDEX_URL="http://127.0.0.1:18765/v1/kb/reindex-all"
if [ "${PICO_KB_REINDEX_FORCE:-0}" = "1" ]; then
  REINDEX_URL+="?force=1"
fi
REINDEX_FILE="$(mktemp)"
REINDEX_CODE="$(curl -sS -o "$REINDEX_FILE" -w "%{http_code}" --max-time 8 -X POST "$REINDEX_URL")" || REINDEX_CODE=000
REINDEX_OUT="$(cat "$REINDEX_FILE")"
rm -f "$REINDEX_FILE"
echo "[pico] kb reindex http=${REINDEX_CODE} body=${REINDEX_OUT:-empty}"
if [ "$REINDEX_CODE" != "202" ]; then
  echo "[pico] FATAL: kb reindex-all failed (http=${REINDEX_CODE})" >&2
  exit 10
fi
if ! python3 -c '
import json, sys
try:
    body = json.loads(sys.argv[1])
except json.JSONDecodeError as exc:
    print(f"[pico] FATAL: kb reindex body not JSON: {exc}", file=sys.stderr)
    raise SystemExit(10)
if not isinstance(body, dict) or body.get("ok") is not True or body.get("queued") is not True:
    print("[pico] FATAL: kb reindex was not queued", file=sys.stderr)
    raise SystemExit(10)
print("[pico] kb reindex queued mode=%s" % body.get("mode"))
' "$REINDEX_OUT"; then
  exit 10
fi
# A2 live miss: HTTP 200 + indexed>0 while Meili tasks all failed → 0 docs.
MEILI_KEY=""
if [ -f .env ]; then
  MEILI_KEY="$(grep '^MEILI_MASTER_KEY=' .env | head -1 | cut -d= -f2- || true)"
fi
STATS_FILE="$(mktemp)"
STATS_CODE="$(curl -sS -o "$STATS_FILE" -w "%{http_code}" --max-time 8 \
  ${MEILI_KEY:+-H "Authorization: Bearer ${MEILI_KEY}"} \
  http://127.0.0.1:7700/indexes/pico_materials/stats)" || STATS_CODE=000
STATS_OUT="$(cat "$STATS_FILE")"
rm -f "$STATS_FILE"
if ! python3 -c '
import json, sys
stats_raw, stats_code = sys.argv[1:]
if stats_code != "200":
    print(f"[pico] FATAL: meili stats http={stats_code}", file=sys.stderr)
    raise SystemExit(10)
try:
    stats = json.loads(stats_raw)
except json.JSONDecodeError as exc:
    print(f"[pico] FATAL: meili stats not JSON: {exc}", file=sys.stderr)
    raise SystemExit(10)
docs = int(stats.get("numberOfDocuments") or 0)
print(f"[pico] meili docs={docs}")
if docs < 1:
    print("[pico] FATAL: Meili has 0 documents", file=sys.stderr)
    raise SystemExit(10)
' "$STATS_OUT" "$STATS_CODE"; then
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

# E2E smoke gate (#1095, agent-policy §1): the read-only key flows must pass
# against the tree just deployed, or this deploy is a failure. Same command
# AGENTS.md registers as E2E-SMOKE. Rollback = redeploy the previous main SHA.
SMOKE="$ROOT/scripts/e2e-smoke.sh"
PREV_SHA="${PICO_PREV_SHA:-}"
if [ -z "$PREV_SHA" ]; then
  PREV_SHA="$(git rev-parse --verify -q 'HEAD@{1}' 2>/dev/null || true)"
fi
echo "[pico] e2e smoke:"
if [ ! -f "$SMOKE" ]; then
  echo "[pico] FATAL: $SMOKE missing — this SHA is not a valid deploy tree" >&2
  exit 16
fi
if ! PICO_SMOKE_EXPECT_SHA="$CURRENT_SHA" bash "$SMOKE" --prod; then
  echo "[pico] FATAL: e2e smoke failed — deploy of $CURRENT_SHA is NOT good" >&2
  echo "[pico] rollback: PICO_DEPLOY_SHA=${PREV_SHA:-<previous-main-sha>} bash /opt/pico/scripts/prod-update.sh (pre-migration SHA: see docs/OPS-PICO-API-HANDOFF.md)" >&2
  exit 16
fi
echo "[pico] e2e smoke ok"

echo "[pico] edge cache warmup:"
(
  . "$ROOT/scripts/pico-first-screen-assets.sh"
  public_login="$(mktemp)"
  trap 'rm -f "$public_login"' EXIT
  public_base=https://pico.aivia.asia
  proxy_args=(--proxy http://127.0.0.1:7893)
  get_public_page "$public_base" /login "$public_login" 10 "${proxy_args[@]}"
  fetch_first_screen_bundles "$public_base" "$public_login" warm "${proxy_args[@]}"
)

# Long-run continuity (edu-core#5337 · long-haul E1 resume / E3 stop): the last
# 7 days of the ledger. Report only — never fails the deploy.
echo "[pico] run continuity (7d):"
docker exec -i "$new_api" python - --days 7 <"$ROOT/scripts/run-continuity-report.py" \
  || echo "[pico] WARN run continuity report did not run" >&2

echo "[pico] done — open https://pico.aivia.asia/login"
