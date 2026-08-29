#!/usr/bin/env bash
# Cloud Agent per-boot: Tailscale join + ssh ecs/pico-prod → aliyun-hy (ops).
# Requires env secrets: TS_AUTHKEY, PICO_PROD_SSH_PRIVATE_KEY
# Optional: PICO_PROD_SSH_USER (default ops), PICO_PROD_SSH_HOST (default aliyun-hy)
set -euo pipefail

SOCK="${TS_SOCKET:-/var/run/tailscale/tailscaled.sock}"
STATE="${TS_STATE:-/var/lib/tailscale/tailscaled.state}"
USER_NAME="${PICO_PROD_SSH_USER:-ops}"
HOST_NAME="${PICO_PROD_SSH_HOST:-aliyun-hy}"
case "${HOST_NAME}" in
  47.*|139.*|100.*) HOST_NAME="aliyun-hy" ;;
esac
if [[ "${USER_NAME}" == "ps" ]]; then
  USER_NAME="ops"
fi

SUDO=""
if [[ "$(id -u)" -ne 0 ]]; then
  SUDO="sudo"
fi

mkdir -p "${HOME}/.ssh"
chmod 700 "${HOME}/.ssh"
# /var/* needs root; never mkdir those as the unprivileged agent user.
$SUDO mkdir -p "$(dirname "$SOCK")" "$(dirname "$STATE")"

if ! command -v tailscale >/dev/null 2>&1; then
  curl -fsSL https://tailscale.com/install.sh | sh
fi

ts() { $SUDO tailscale --socket="$SOCK" "$@"; }

if ! ts status >/dev/null 2>&1; then
  $SUDO pkill tailscaled 2>/dev/null || true
  # /tmp/tailscaled.log is often ubuntu-owned; sudo nohup cannot truncate it.
  $SUDO bash -c "nohup tailscaled --state='$STATE' --socket='$SOCK' --port=41641 >/var/tmp/tailscaled.log 2>&1 &"
  for _ in $(seq 1 30); do
    ts status >/dev/null 2>&1 && break
    sleep 0.5
  done
fi

# Prefer operator so later non-sudo works; ignore failure.
$SUDO tailscale --socket="$SOCK" set --operator="${USER:-ubuntu}" >/dev/null 2>&1 || true

BACKEND="$(ts status --json 2>/dev/null | python3 -c 'import sys,json; print(json.load(sys.stdin).get("BackendState",""))' 2>/dev/null || true)"
if [[ -z "${TS_AUTHKEY:-}" ]]; then
  if [[ "$BACKEND" != "Running" ]]; then
    echo "[pico] BLOCKED: TS_AUTHKEY missing (BackendState=${BACKEND:-unknown})" >&2
    exit 2
  fi
else
  HN="cursor-pico-${HOSTNAME:-agent}"
  # Cloud Agent pods are IPv4-only. MagicDNS AAAA for controlplane kills
  # map long-poll after sleep; connmark/nfmask is missing in this kernel.
  ts up --reset --authkey="$TS_AUTHKEY" --hostname="$HN" \
    --accept-routes --accept-dns=false --netfilter-mode=off
fi

if [[ -z "${PICO_PROD_SSH_PRIVATE_KEY:-}" ]]; then
  echo "[pico] BLOCKED: PICO_PROD_SSH_PRIVATE_KEY missing" >&2
  exit 2
fi

KEY="${PICO_PROD_SSH_PRIVATE_KEY}"
if [[ "$KEY" == *'\\n'* ]]; then
  KEY="${KEY//\\n/$'\n'}"
fi
if [[ "$KEY" != *"BEGIN"* ]]; then
  KEY="-----BEGIN OPENSSH PRIVATE KEY-----
${KEY}
-----END OPENSSH PRIVATE KEY-----"
fi
printf '%s\n' "$KEY" > "${HOME}/.ssh/pico_prod_deploy"
chmod 600 "${HOME}/.ssh/pico_prod_deploy"

# Without MagicDNS, HostName must be the peer's 100.x (env 100.* is still rejected).
SSH_HOST="$HOST_NAME"
PEER_IP="$(
  TS_PEER_HOST="$HOST_NAME" ts status --json 2>/dev/null | python3 -c '
import json, os, sys
want = os.environ.get("TS_PEER_HOST") or "aliyun-hy"
try:
    data = json.load(sys.stdin)
except Exception:
    raise SystemExit(0)
for peer in (data.get("Peer") or {}).values():
    if peer.get("HostName") != want:
        continue
    ips = [ip for ip in (peer.get("TailscaleIPs") or []) if ":" not in ip]
    if ips:
        print(ips[0])
    break
' || true
)"
if [[ -n "${PEER_IP}" ]]; then
  SSH_HOST="$PEER_IP"
  if grep -qE '[[:space:]]aliyun-hy$' /etc/hosts 2>/dev/null; then
    $SUDO sed -i "s/^.*[[:space:]]aliyun-hy$/${PEER_IP} aliyun-hy/" /etc/hosts
  else
    echo "${PEER_IP} aliyun-hy" | $SUDO tee -a /etc/hosts >/dev/null
  fi
fi

cat > "${HOME}/.ssh/config" <<EOF
Host *
  StrictHostKeyChecking accept-new
  IdentitiesOnly yes
  IdentityFile ~/.ssh/pico_prod_deploy
  ConnectTimeout 12

Host ecs pico-prod aliyun-hy
  HostName ${SSH_HOST}
  User ${USER_NAME}
EOF
chmod 600 "${HOME}/.ssh/config"

echo "[pico] cloud-agent-start: $(ts status 2>/dev/null | head -1 || true)"
if ssh -o BatchMode=yes -o ConnectTimeout=20 ecs 'test -d /opt/pico && echo ECS_OK'; then
  echo "[pico] ssh ecs: OK"
else
  echo "[pico] WARN: ssh ecs not ready yet" >&2
fi
