#!/usr/bin/env bash
# Cloud Agent bootstrap: Tailscale client + materialize start helpers (idempotent).
# Must succeed as non-root: never fail on /var/* (start creates those with sudo).
set -euo pipefail

BIN="${HOME}/.local/bin"
mkdir -p "${BIN}" "${HOME}/.ssh"
chmod 700 "${HOME}/.ssh" || true

if ! command -v tailscale >/dev/null 2>&1 || ! command -v tailscaled >/dev/null 2>&1; then
  curl -fsSL https://tailscale.com/install.sh | sh
fi

# Prefer workspace scripts when present (feature branch / main after merge).
for name in cloud-agent-install.sh cloud-agent-start.sh; do
  src=""
  if [[ -f "/workspace/scripts/${name}" ]]; then
    src="/workspace/scripts/${name}"
  fi
  if [[ -n "${src}" ]]; then
    cp -f "${src}" "${BIN}/${name}"
    chmod 755 "${BIN}/${name}"
  fi
done

echo "[pico] cloud-agent-install: tailscale=$(tailscale version 2>/dev/null | head -1 || echo missing) bin=${BIN}"
