#!/usr/bin/env bash
# Fail-fast: is the production deploy channel usable from this host?
# Does NOT deploy. Does NOT print secrets.
set -euo pipefail

echo "[pico] check-deploy-channel on $(hostname) $(date -Is)"

if ! command -v ssh >/dev/null 2>&1; then
  echo "[pico] BLOCKED: ssh client missing" >&2
  exit 2
fi

if ! ssh -o BatchMode=yes -o ConnectTimeout=8 pico-prod 'test -d /opt/pico && echo HAS_PICO' 2>/tmp/pico-ssh-err; then
  echo "[pico] BLOCKED: cannot ssh Host pico-prod (alias, not public DNS)" >&2
  echo "[pico] ssh stderr:" >&2
  cat /tmp/pico-ssh-err >&2 || true
  echo >&2
  echo "[pico] fix: on the jump host, configure ~/.ssh/config Host pico-prod" >&2
  echo "[pico]   HostName <prod-ip>  # docs default 139.196.147.40" >&2
  echo "[pico]   User <deploy-user> IdentityFile ~/.ssh/pico_prod_deploy" >&2
  echo "[pico] see docs/DEPLOY-TWO-HOST.md §0 / §3" >&2
  echo "[pico] or run prod-update.sh ON the production host directly" >&2
  exit 2
fi

echo "[pico] ssh pico-prod: OK"
ssh -o BatchMode=yes -o ConnectTimeout=8 pico-prod   'hostname; curl -sf --max-time 3 http://127.0.0.1:18765/health | head -c 400; echo'
echo "[pico] channel READY (still need PICO_DEPLOY_SHA=main tip for prod-update.sh)"
