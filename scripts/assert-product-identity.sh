#!/usr/bin/env bash
set -uo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
err=0
if [ -d apps/web ]; then echo "FAIL: apps/web"; err=1; fi
if [ -d apps/workbench ]; then echo "FAIL: apps/workbench should be deleted"; err=1; fi
if [ ! -f apps/librechat/package.json ]; then echo "FAIL: apps/librechat missing"; err=1; fi
if [ -d apps/nextchat ]; then echo "WARN: apps/nextchat still present (legacy)"; fi
if curl -sf -o /dev/null --max-time 2 http://127.0.0.1:3080/; then
  html=$(curl -sf --max-time 2 http://127.0.0.1:3080/ | head -c 800 || true)
  if echo "$html" | grep -qi 'LibreChat\|Pico\|root'; then echo "UI: LibreChat up"; else echo "WARN: unexpected UI"; fi
fi
if [ "$err" -ne 0 ]; then echo FAILED; exit 1; fi
echo "assert-product-identity: OK"
