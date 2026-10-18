#!/usr/bin/env bash
# Throwaway Pico stack for the ruler (pico#1323). Same images as prod, source
# mounted from <src>, own sqlite, own pi-runner + gVisor boxes. Touches no live
# container, no host firewall rule, no live meili.
#
#   bash scripts/pico-ruler-stack.sh up   <name> <src> [idx]   # src: dir or git:<ref> (archived from /opt/pico)
#   Boxes run pico-workspace:v1 with <src>'s true_pi_bridge laid on top (tag pico-workspace:ruler-<name>).
#   bash scripts/pico-ruler-stack.sh down <name> [idx]
#   bash scripts/pico-ruler-stack.sh info <name> [idx]          # ports + paths for scripts/pico-ruler.py
#
# idx (0-4) picks ports 188<idx>0..188<idx>6 and box subnet 172.30.(253+idx).0/24,
# so two stacks (before / after) can run side by side.
#
# Why it looks like this (pico#1323 card comments):
# - Boxes cannot use pico-ws: the host firewall lets only pico-ws reach the live
#   runner, and we do not touch host rules. Boxes get an --internal network (no
#   route out); the runner proxy reaches them through two socat relays over a
#   unix socket (the edu-pico-gw pattern). The relay shares the box bridge, so
#   that bridge has ICC on; at most two test boxes ever sit on it.
# - The stock runner reaps every `pico.ws=1` container it does not own, and the
#   live runner would reap ours. The stack mounts a copy of <src>/services/pi_runner
#   with that label renamed to `pico.ws=ruler-<name>` (exactly two places).
# - Meili is off: uploads and outputs would otherwise be projected into the live
#   index. The kb tool reports "not configured"; both sides of a compare match.
# - Limits: api 2g/1cpu, sandbox 1g/1cpu, office 1g/1cpu, runner 1.5g/1cpu,
#   2 boxes x 1536m/1.5cpu (not in pico-ws.slice), relays/page 64-128m. The
#   runner starts no box under 8 GB MemAvailable; `up` refuses under 8 GB too.
set -euo pipefail

HERE="$(cd "$(dirname "$0")/.." && pwd)"
ROOT_DIR="${PICO_RULER_ROOT:-$HOME/pico-ruler}"
LIVE_API="${PICO_RULER_LIVE_API:-pico-pico-api-1}"
LIVE_REPO="${PICO_RULER_LIVE_REPO:-/opt/pico}"
PAGE_HOST="login.pico-ruler.cn"
MIN_AVAIL_MB=8192

cmd="${1:-}"; name="${2:-}"
[[ "$name" =~ ^[a-z0-9-]{1,20}$ ]] || { echo "usage: $0 up|down|info <name> ..." >&2; exit 2; }
if [[ "$cmd" == up ]]; then src="${3:-}"; idx="${4:-0}"; else idx="${3:-0}"; fi
[[ "$idx" =~ ^[0-4]$ ]] || { echo "idx must be 0-4" >&2; exit 2; }

D="$ROOT_DIR/$name"
P=$((18800 + idx * 10))
API=$P SB=$((P + 1)) CTL=$((P + 2)) PX=$((P + 3)) PAGE=$((P + 4))
SUB=$((253 + idx))
NET="ruler-ws-$name"
RELAY_IP="172.30.$SUB.2"
LABEL="ruler-$name"

avail_mb() { awk '/MemAvailable/ {print int($2 / 1024)}' /proc/meminfo; }

info() {
  cat <<EOF
{"name":"$name","dir":"$D","base":"http://127.0.0.1:$API","db":"$D/data/pico.db","env":"$D/api.env",
 "page":"http://$PAGE_HOST:$PAGE/","box_label":"pico.ws=$LABEL","net":"$NET"}
EOF
}

down() {
  docker rm -f "ruler-$name-api" "ruler-$name-runner" "ruler-$name-sb" "ruler-$name-office" \
    "ruler-$name-page" "ruler-$name-relay-host" "ruler-$name-relay-ws" >/dev/null 2>&1 || true
  local boxes
  boxes=$(docker ps -aq --filter "label=pico.ws=$LABEL")
  [[ -n "$boxes" ]] && docker rm -f $boxes >/dev/null
  docker network rm "$NET" >/dev/null 2>&1 || true
  docker rmi "pico-workspace:$LABEL" >/dev/null 2>&1 || true
  if [[ -d "$D" ]]; then
    # Box and runner files are root/65532-owned; remove them with a container.
    docker run --rm --network none -v "$ROOT_DIR:/r" --entrypoint rm alpine/socat -rf "/r/$name"
  fi
  echo "down $name: containers, boxes, network, $D removed"
}

fetch_src() {
  mkdir -p "$D/src"
  if [[ "$src" == git:* ]]; then
    local ref="${src#git:}"
    git -C "$LIVE_REPO" cat-file -e "$ref^{commit}" 2>/dev/null \
      || { echo "ref $ref not in $LIVE_REPO (fetch it first)" >&2; exit 2; }
    git -C "$LIVE_REPO" archive "$ref" services testdata | tar -x -C "$D/src"
    git -C "$LIVE_REPO" rev-parse "$ref" > "$D/src/REVISION"
  else
    [[ -d "$src/services" ]] || { echo "$src has no services/" >&2; exit 2; }
    cp -a "$src/services" "$D/src/"
    git -C "$src" rev-parse HEAD > "$D/src/REVISION" 2>/dev/null || echo "dir:$src" > "$D/src/REVISION"
  fi
}

patch_runner() {
  cp -a "$D/src/services/pi_runner" "$D/pi_runner"
  local hits
  hits=$(grep -o 'pico\.ws=1' "$D/pi_runner/app.py" "$D/pi_runner/policy.py" | wc -l)
  [[ "$hits" == 2 ]] || { echo "runner label sites changed ($hits != 2); update this script" >&2; exit 3; }
  sed -i "s/pico\.ws=1/pico.ws=$LABEL/" "$D/pi_runner/app.py" "$D/pi_runner/policy.py"
}

api_env() {
  # Live pico-api env minus everything the stack owns. Secrets stay in this
  # 600 file on the host; `down` deletes it.
  ( umask 077
    docker inspect "$LIVE_API" --format '{{range .Config.Env}}{{println .}}{{end}}' \
      | grep -vE '^(PICO_DATABASE_URL|PICO_SANDBOX_URL|PICO_OFFICE_URL|PICO_RUNNER_URL|PICO_RUNNER_TOKEN|PICO_RUNNER_PROXY_URL|PICO_HOOK_SERVICE_TOKEN|PICO_EDU_BASE_URL|PICO_EDU_SERVICE_TOKEN|PICO_EDU_HANDOFF_ENABLED|PICO_API_PORT|PICO_SANDBOX_DISK|PICO_GIT_SHA|PICO_MEILI_URL|MEILI_MASTER_KEY|PICO_SANDBOX_URL)=' \
      | grep -v '^$' > "$D/api.env"
    printf 'PICO_RUNNER_TOKEN=%s\n' "$(head -c 32 /dev/urandom | od -An -tx1 | tr -d ' \n')" >> "$D/api.env"
    # pico#1336: KEY=VALUE lines that replace the live value (e.g. point
    # DEEPSEEK_BASE_URL at scripts/pico-fault-upstream.py).
    if [[ -n "${PICO_RULER_API_ENV_EXTRA:-}" ]]; then
      local k
      while IFS= read -r line; do
        [[ "$line" == *=* ]] || continue
        k="${line%%=*}"
        grep -v "^$k=" "$D/api.env" > "$D/api.env.tmp" || true
        mv "$D/api.env.tmp" "$D/api.env"
        printf '%s\n' "$line" >> "$D/api.env"
      done < "$PICO_RULER_API_ENV_EXTRA"
    fi
  )
}

# The box runs the bridge baked into pico-workspace:v1 (prod rebuilds it each
# deploy). Lay <src>'s bridge on top, or a branch that changes the bridge is
# measured with the live one (pico#1342).
ws_image() {
  docker build -q -t "pico-workspace:$LABEL" -f - "$D/src/services" >/dev/null <<'EOF'
FROM pico-workspace:v1
COPY true_pi_bridge /opt/pico/true_pi_bridge
EOF
}

envval() { grep "^$1=" "$D/api.env" | head -1 | cut -d= -f2-; }

up() {
  [[ -n "$src" ]] || { echo "up needs <src>" >&2; exit 2; }
  docker ps -aq --filter "name=^ruler-$name-" | grep -q . && { echo "stack $name exists; down it first" >&2; exit 2; }
  local avail; avail=$(avail_mb)
  (( avail >= MIN_AVAIL_MB )) || { echo "MemAvailable ${avail}MB < ${MIN_AVAIL_MB}MB, not starting" >&2; exit 4; }
  mkdir -p "$D"/{data,disks,office-sock,ws,relay,www}
  chmod 777 "$D/data" "$D/disks" "$D/office-sock" "$D/relay"
  fetch_src
  patch_runner
  api_env
  # The test page ships with this script (the stack's <src> may predate it).
  cp "$HERE/testdata/pico-ruler/www/"* "$D/www/"
  # Containers run as uid 65532; this host's umask (027) would hide the source.
  chmod -R a+rX "$D/src" "$D/pi_runner" "$D/www"
  ws_image
  local sbtok rtok s="$D/src/services"
  sbtok=$(envval PICO_SANDBOX_TOKEN); rtok=$(envval PICO_RUNNER_TOKEN)

  docker network create --internal --subnet "172.30.$SUB.0/24" --gateway "172.30.$SUB.1" \
    --label "pico.ruler=$name" "$NET" >/dev/null

  docker run -d --name "ruler-$name-office" --network none -u 65532:65532 --read-only \
    --memory 1g --cpus 1 --tmpfs /tmp:size=512m -v "$D/office-sock:/run/pico-office" \
    -e PICO_OFFICE_TMP=/tmp -e PICO_OFFICE_CONCURRENCY=2 -e HOME=/tmp -e LANG=C.UTF-8 -e LC_ALL=C.UTF-8 \
    -e PICO_SANDBOX_TOKEN="$sbtok" -v "$s/sandbox_worker:/app/services/sandbox_worker:ro" \
    pico-sandbox:v13 python -m sandbox_worker.office_runner --uds /run/pico-office/office.sock >/dev/null

  docker run -d --name "ruler-$name-page" --network host -u 65532:65532 --read-only --memory 128m --cpus 0.25 \
    -v "$D/www:/www:ro" pico-sandbox:v13 python -m http.server "$PAGE" --bind 127.0.0.1 --directory /www >/dev/null

  # The test page has a public-looking name; the browser resolves it to the page server.
  docker run -d --name "ruler-$name-sb" --network host -u 65532:65532 --read-only \
    --memory 1g --cpus 1 --tmpfs /tmp --tmpfs /dev/shm:size=64m --add-host "$PAGE_HOST:127.0.0.1" \
    -e PICO_SANDBOX_HOST=127.0.0.1 -e PICO_SANDBOX_PORT="$SB" -e HOME=/tmp/h -e XDG_CONFIG_HOME=/tmp/h/.config \
    -e XDG_CACHE_HOME=/tmp/h/.cache -e PLAYWRIGHT_BROWSERS_PATH=/opt/ms-playwright -e PICO_SANDBOX_PROFILE_ROOT=/tmp/prof \
    -e PICO_SANDBOX_DISK=/var/lib/pico/teacher-disks -e PICO_SANDBOX_TOKEN="$sbtok" \
    -v "$D/disks:/var/lib/pico/teacher-disks" \
    -v "$s/sandbox_worker:/app/services/sandbox_worker:ro" -v "$s/orchestrator:/app/services/orchestrator:ro" \
    pico-sandbox:v13 >/dev/null

  docker run -d --name "ruler-$name-relay-host" --network host --memory 64m --cpus 0.25 -v "$D/relay:/s" \
    alpine/socat "UNIX-LISTEN:/s/proxy.sock,fork,mode=777,unlink-early" "TCP:127.0.0.1:$PX" >/dev/null
  docker run -d --name "ruler-$name-relay-ws" --network "$NET" --ip "$RELAY_IP" --memory 64m --cpus 0.25 \
    -v "$D/relay:/s" alpine/socat "TCP-LISTEN:$PX,fork,reuseaddr" "UNIX-CONNECT:/s/proxy.sock" >/dev/null

  docker run -d --name "ruler-$name-runner" --network host --memory 1536m --cpus 1 --read-only --tmpfs /tmp:size=64m \
    -v /var/run/docker.sock:/var/run/docker.sock -v "$D/ws:$D/ws" -v "$D/pi_runner:/app/services/pi_runner:ro" \
    -e PICO_RUNNER_TOKEN="$rtok" -e PICO_RUNNER_UPSTREAM="http://127.0.0.1:$API" -e PICO_RUNNER_WS_ROOT="$D/ws" \
    -e PICO_RUNNER_IMAGE="pico-workspace:$LABEL" -e PICO_RUNNER_NETWORK="$NET" -e PICO_RUNNER_RUNTIME=runsc \
    -e PICO_RUNNER_CONTROL_PORT="$CTL" -e PICO_RUNNER_PROXY_HOST=127.0.0.1 -e PICO_RUNNER_PROXY_PORT="$PX" \
    -e PICO_RUNNER_MAX_SESSIONS=2 -e PICO_RUNNER_MAX_PER_SCHOOL=2 -e PICO_RUNNER_CGROUP_PARENT= \
    -e PICO_RUNNER_MEM=1536m -e PICO_RUNNER_CPUS=1.5 -e PICO_RUNNER_MIN_AVAIL_MB="$MIN_AVAIL_MB" \
    -e PICO_RUNNER_MIN_FREE_MB=3072 pico-pi-runner:v1 >/dev/null

  docker run -d --name "ruler-$name-api" --network host --memory 2g --cpus 1 --env-file "$D/api.env" \
    -e PICO_DATABASE_URL=sqlite+aiosqlite:///./data/pico.db -e PICO_SANDBOX_URL="http://127.0.0.1:$SB" \
    -e PICO_OFFICE_URL=unix:///run/pico-office/office.sock -e PICO_RUNNER_URL="http://127.0.0.1:$CTL" \
    -e PICO_RUNNER_PROXY_URL="http://$RELAY_IP:$PX" -e PICO_HOOK_SERVICE_TOKEN= -e PICO_EDU_BASE_URL= \
    -e PICO_EDU_SERVICE_TOKEN= -e PICO_EDU_HANDOFF_ENABLED=0 -e PICO_API_PORT="$API" -e PICO_MEILI_URL= \
    -e MEILI_MASTER_KEY= -e PICO_SANDBOX_DISK=/var/lib/pico/teacher-disks -e PICO_GIT_SHA="ruler-$name" \
    -v "$D/data:/app/data" -v "$D/disks:/var/lib/pico/teacher-disks" -v "$D/office-sock:/run/pico-office" \
    -v "$s/api:/app/services/api:ro" -v "$s/orchestrator:/app/services/orchestrator:ro" \
    -v "$s/true_pi_bridge:/app/services/true_pi_bridge:ro" \
    pico-api:v13 uvicorn app.main:app --app-dir services/api --host 127.0.0.1 --port "$API" >/dev/null

  for _ in $(seq 1 60); do
    curl -fsS "http://127.0.0.1:$API/health" >/dev/null 2>&1 && break
    sleep 2
  done
  curl -fsS "http://127.0.0.1:$API/health" | python3 -c 'import json,sys; h=json.load(sys.stdin); print("health", h.get("revision"), h.get("default_runtime"), "meili", h.get("meili_configured"))'
  echo "src $(cat "$D/src/REVISION") · avail $(avail_mb)MB"
  info
}

case "$cmd" in
  up) up ;;
  down) down ;;
  info) info ;;
  *) echo "usage: $0 up|down|info <name> ..." >&2; exit 2 ;;
esac
