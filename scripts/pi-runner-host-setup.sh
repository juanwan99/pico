#!/usr/bin/env bash
# Root-only host prerequisites for pi-runner workspace boxes (card #1093).
#
#   sudo bash scripts/pi-runner-host-setup.sh            # install / re-apply (idempotent)
#   sudo bash scripts/pi-runner-host-setup.sh --check    # print state, change nothing
#   sudo bash scripts/pi-runner-host-setup.sh --rollback # remove firewall unit + pico-ws network
#
# What it touches (nothing else):
#   1. gVisor runsc from the official apt repo; registers the "runsc" docker
#      runtime and RELOADS dockerd (SIGHUP). Never restarts dockerd — shared
#      host, edu production containers must not bounce.
#   2. docker network pico-ws 172.30.250.0/24 (icc off) — boxes only.
#   3. /var/lib/pico/workspaces (root 0711).
#   4. iptables chains PICO-WS-FWD (from DOCKER-USER) and PICO-WS-IN (from
#      INPUT), only for traffic whose source is pico-ws, persisted by the
#      systemd unit pico-ws-firewall.service.
set -euo pipefail

SUBNET="172.30.250.0/24"
GATEWAY="172.30.250.1"
PROXY_PORT="18791"
NET="pico-ws"
WS_ROOT="/var/lib/pico/workspaces"
FW_BIN="/usr/local/sbin/pico-ws-firewall.sh"
FW_UNIT="/etc/systemd/system/pico-ws-firewall.service"

mode="${1:-apply}"

if [ "$(id -u)" != "0" ]; then
  echo "run with sudo" >&2
  exit 2
fi

write_firewall() {
  cat >"$FW_BIN" <<FW
#!/usr/bin/env bash
# pico-ws box egress policy (card #1093). Source = pico-ws only.
set -euo pipefail
SUB="$SUBNET"; GW="$GATEWAY"; PORT="$PROXY_PORT"
ipt() { iptables -w "\$@"; }
remove() {
  ipt -D DOCKER-USER -s "\$SUB" -j PICO-WS-FWD 2>/dev/null || true
  ipt -D INPUT -s "\$SUB" -j PICO-WS-IN 2>/dev/null || true
  for c in PICO-WS-FWD PICO-WS-IN; do ipt -F "\$c" 2>/dev/null || true; ipt -X "\$c" 2>/dev/null || true; done
}
if [ "\${1:-apply}" = "remove" ]; then remove; exit 0; fi
# Box -> anything forwarded: public internet yes; private / Tailscale /
# metadata / loopback / multicast / SMTP no.
ipt -N PICO-WS-FWD 2>/dev/null || true
ipt -F PICO-WS-FWD
for net in 10.0.0.0/8 172.16.0.0/12 192.168.0.0/16 100.64.0.0/10 169.254.0.0/16 \\
           127.0.0.0/8 0.0.0.0/8 224.0.0.0/4 240.0.0.0/4; do
  ipt -A PICO-WS-FWD -d "\$net" -j DROP
done
ipt -A PICO-WS-FWD -p tcp --dport 25 -j DROP
ipt -A PICO-WS-FWD -j RETURN
ipt -C DOCKER-USER -s "\$SUB" -j PICO-WS-FWD 2>/dev/null || ipt -I DOCKER-USER 1 -s "\$SUB" -j PICO-WS-FWD
# Box -> this host: only the runner proxy port on the pico-ws gateway.
ipt -N PICO-WS-IN 2>/dev/null || true
ipt -F PICO-WS-IN
ipt -A PICO-WS-IN -p tcp -d "\$GW" --dport "\$PORT" -j ACCEPT
ipt -A PICO-WS-IN -j DROP
ipt -C INPUT -s "\$SUB" -j PICO-WS-IN 2>/dev/null || ipt -I INPUT 1 -s "\$SUB" -j PICO-WS-IN
FW
  chmod 0755 "$FW_BIN"
  cat >"$FW_UNIT" <<UNIT
[Unit]
Description=Pico workspace box firewall (card #1093)
After=docker.service
# Re-applied whenever docker (re)starts; never removed on stop (fail-closed).
PartOf=docker.service

[Service]
Type=oneshot
RemainAfterExit=yes
ExecStart=$FW_BIN apply

[Install]
WantedBy=multi-user.target docker.service
UNIT
}

check() {
  echo "runsc:        $(command -v runsc || echo missing) $(runsc --version 2>/dev/null | head -1 || true)"
  echo "docker rt:    $(docker info --format '{{json .Runtimes}}' | grep -o '"runsc"' || echo 'runsc not registered')"
  echo "network:      $(docker network inspect -f '{{range .IPAM.Config}}{{.Subnet}} gw {{.Gateway}}{{end}} icc={{index .Options "com.docker.network.bridge.enable_icc"}}' "$NET" 2>/dev/null || echo missing)"
  echo "ws root:      $(stat -c '%U %a' "$WS_ROOT" 2>/dev/null || echo missing)"
  echo "fw unit:      $(systemctl is-active pico-ws-firewall.service 2>/dev/null || true)"
  echo "DOCKER-USER:  $(iptables -w -S DOCKER-USER 2>/dev/null | grep -c PICO-WS-FWD || true) jump(s)"
  echo "INPUT:        $(iptables -w -S INPUT 2>/dev/null | grep -c PICO-WS-IN || true) jump(s)"
}

case "$mode" in
  --check)
    check
    exit 0
    ;;
  --rollback)
    systemctl disable --now pico-ws-firewall.service 2>/dev/null || true
    [ -x "$FW_BIN" ] && "$FW_BIN" remove || true
    rm -f "$FW_UNIT" "$FW_BIN"
    systemctl daemon-reload
    docker network rm "$NET" 2>/dev/null || true
    echo "rolled back firewall + $NET (runsc runtime and $WS_ROOT left in place; harmless)"
    check
    exit 0
    ;;
  apply) ;;
  *)
    echo "usage: $0 [--check|--rollback]" >&2
    exit 2
    ;;
esac

echo "== 1/4 gVisor runsc"
if ! command -v runsc >/dev/null; then
  for bin in curl gpg; do
    command -v "$bin" >/dev/null || { echo "missing $bin (install it first)" >&2; exit 3; }
  done
  curl -fsSL https://gvisor.dev/archive.key | gpg --dearmor --yes -o /usr/share/keyrings/gvisor-archive-keyring.gpg
  echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/gvisor-archive-keyring.gpg] https://storage.googleapis.com/gvisor/releases release main" \
    >/etc/apt/sources.list.d/gvisor.list
  # This host's root umask is 027; apt verifies as user _apt, which must read both.
  chmod 0644 /usr/share/keyrings/gvisor-archive-keyring.gpg /etc/apt/sources.list.d/gvisor.list
  # Refresh only the gVisor source: other repos on this shared host (e.g. a
  # stale third-party key) must neither block us nor be touched by us.
  apt-get update -qq \
    -o Dir::Etc::sourcelist=/etc/apt/sources.list.d/gvisor.list \
    -o Dir::Etc::sourceparts=- \
    -o APT::Get::List-Cleanup=0
  # Shared prod host: never let needrestart bounce containerd / nginx / ssh.
  NEEDRESTART_SUSPEND=1 DEBIAN_FRONTEND=noninteractive apt-get install -y -qq --no-install-recommends runsc
fi
runsc --version | head -1
if ! docker info --format '{{json .Runtimes}}' | grep -q '"runsc"'; then
  runsc install
  # Reload, not restart: runtimes are a live-reloadable daemon option.
  systemctl reload docker
  sleep 2
fi
docker info --format '{{json .Runtimes}}' | grep -q '"runsc"' || { echo "runsc runtime not registered" >&2; exit 3; }

echo "== 2/4 network $NET"
if ! docker network inspect "$NET" >/dev/null 2>&1; then
  docker network create --driver bridge \
    --subnet "$SUBNET" --gateway "$GATEWAY" \
    -o com.docker.network.bridge.name=br-pico-ws \
    -o com.docker.network.bridge.enable_icc=false \
    "$NET"
fi

echo "== 3/4 $WS_ROOT"
mkdir -p "$WS_ROOT"
chown root:root "$WS_ROOT"
chmod 0711 "$WS_ROOT"

echo "== 4/4 firewall"
write_firewall
systemctl daemon-reload
systemctl enable pico-ws-firewall.service >/dev/null
systemctl restart pico-ws-firewall.service

echo "== smoke: runsc box on $NET"
docker run --rm --runtime=runsc --network "$NET" --dns 223.5.5.5 python:3.12-slim-bookworm \
  python -c "import platform;print('box kernel', platform.release())"
check
echo "done"
