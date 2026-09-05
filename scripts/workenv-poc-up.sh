#!/usr/bin/env bash
# Start the PoC overlay network + container on a NON-production host.
# FORBIDDEN: install nft on live pico.aivia.asia ECS.
# FORBIDDEN: this file is not read by scripts/prod-update.sh.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
COMPOSE=(docker compose -f docker-compose.workenv-poc.yml)

if [[ "${PICO_WORKENV_ALLOW_LIVE_HOST:-}" != "1" ]]; then
  host="$(hostname -f 2>/dev/null || hostname)"
  if [[ "$host" == *aivia* ]] || [[ -f /opt/pico/docker-compose.host.yml ]]; then
    echo "[workenv-poc] BLOCKED: looks like the live Pico host ($host)." >&2
    echo "[workenv-poc] nft / overlay must not run here. Use an independent compose host." >&2
    echo "[workenv-poc] override only with PICO_WORKENV_ALLOW_LIVE_HOST=1 (still no nft)." >&2
    exit 4
  fi
fi

"${COMPOSE[@]}" up --no-start
HOST_GW="$(docker network inspect pico-workenv -f '{{(index .IPAM.Config 0).Gateway}}')"
if [[ ! "$HOST_GW" =~ ^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
  echo "[workenv-poc] BLOCKED: pico-workenv Gateway is not an IPv4: $HOST_GW" >&2
  exit 3
fi
export HOST_GW
echo "[workenv-poc] HOST_GW=$HOST_GW (inspect pico-workenv; not docker0 magic)"
"${COMPOSE[@]}" up -d
echo "[workenv-poc] listening intent 127.0.0.1:18768 — do not bind 0.0.0.0"
echo "[workenv-poc] nft publisher is NOT installed by this script."
