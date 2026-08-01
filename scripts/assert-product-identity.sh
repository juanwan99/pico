#!/usr/bin/env bash
set -uo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
err=0
if [ -d apps/web ]; then echo "FAIL: apps/web"; err=1; fi
if [ -d apps/workbench ]; then echo "FAIL: apps/workbench should be deleted"; err=1; fi
if [ -d apps/nextchat ]; then echo "FAIL: apps/nextchat should be deleted"; err=1; fi
if [ ! -f apps/librechat/package.json ]; then echo "FAIL: apps/librechat missing"; err=1; fi
if grep -Eq 'product_ui *= *"nextchat"|StaticFiles|FileResponse|_DIST.*apps.*web' \
  services/api/app/main.py; then
  echo "FAIL: pico-api still contains a legacy product-shell fallback"
  err=1
fi
if grep -Fq 'grok/pico-preview-librechat-p0' scripts/prod-update.sh docs/DEPLOY-PUBLIC.md; then
  echo "FAIL: production deployment still points at the retired preview branch"
  err=1
fi
forbidden_demo_password='pico-demo''-123'
if grep -Rq --include='*.md' "$forbidden_demo_password" docs || \
  grep -Fq "$forbidden_demo_password" scripts/agent-selftest.sh; then
  echo "FAIL: fixed demo password is committed"
  err=1
fi
if curl -sf -o /dev/null --max-time 2 http://127.0.0.1:3080/; then
  html=$(curl -sf --max-time 2 http://127.0.0.1:3080/ | head -c 800 || true)
  if echo "$html" | grep -qi 'LibreChat\|Pico\|root'; then echo "UI: LibreChat up"; else echo "WARN: unexpected UI"; fi
fi
if [ "$err" -ne 0 ]; then echo FAILED; exit 1; fi
echo "assert-product-identity: OK"
