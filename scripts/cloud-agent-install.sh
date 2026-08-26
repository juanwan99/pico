#!/usr/bin/env bash
# Cloud Agent bootstrap: Tailscale client (idempotent). Used by environment install.
set -euo pipefail
if ! command -v tailscale >/dev/null 2>&1 || ! command -v tailscaled >/dev/null 2>&1; then
  curl -fsSL https://tailscale.com/install.sh | sh
fi
mkdir -p "${HOME}/.ssh" /var/lib/tailscale /var/run/tailscale
chmod 700 "${HOME}/.ssh" || true
echo "[pico] cloud-agent-install: tailscale=$(tailscale version | head -1)"
