#!/usr/bin/env bash
# Cloud Agent bootstrap: Tailscale client + materialize start helpers (idempotent).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." 2>/dev/null && pwd || true)"
BIN="${HOME}/.local/bin"
mkdir -p "${BIN}" "${HOME}/.ssh" /var/lib/tailscale /var/run/tailscale 2>/dev/null || true
chmod 700 "${HOME}/.ssh" || true
mkdir -p "${BIN}"

if ! command -v tailscale >/dev/null 2>&1 || ! command -v tailscaled >/dev/null 2>&1; then
  curl -fsSL https://tailscale.com/install.sh | sh
fi

# Prefer workspace scripts when present (feature branch / main after merge);
# otherwise keep whatever already lives under ~/.local/bin (snapshot base).
for name in cloud-agent-install.sh cloud-agent-start.sh; do
  src=""
  if [[ -n "${ROOT}" && -f "${ROOT}/scripts/${name}" ]]; then
    src="${ROOT}/scripts/${name}"
  elif [[ -f "/workspace/scripts/${name}" ]]; then
    src="/workspace/scripts/${name}"
  fi
  if [[ -n "${src}" ]]; then
    cp -f "${src}" "${BIN}/${name}"
    chmod 755 "${BIN}/${name}"
  fi
done

echo "[pico] cloud-agent-install: tailscale=$(tailscale version 2>/dev/null | head -1 || echo missing) bin=${BIN}"
