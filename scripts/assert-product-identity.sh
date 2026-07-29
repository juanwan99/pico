#!/usr/bin/env bash
# Fail closed if product shell drifts (the failure mode that shipped orange 三栏).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

err=0
if [ -d apps/web ]; then
  echo "FAIL: apps/web exists — hand-rolled shell must not return"
  err=1
fi
if [ ! -f apps/nextchat/package.json ]; then
  echo "FAIL: apps/nextchat missing — no product UI"
  err=1
fi
if [ -f apps/web/src/App.vue ] 2>/dev/null; then
  echo "FAIL: apps/web/src/App.vue present"
  err=1
fi

# Optional live check when API is up
if curl -sf -o /dev/null --max-time 2 http://127.0.0.1:8000/v1/meta/version; then
  body=$(curl -sf --max-time 2 http://127.0.0.1:8000/v1/meta/version)
  echo "version: $body"
  echo "$body" | grep -q '"product_ui_ok": true' || echo "$body" | grep -q '"product_ui_ok":true' || {
    echo "FAIL: product_ui_ok is not true"
    err=1
  }
  echo "$body" | grep -q '"apps_web_present": false' || echo "$body" | grep -q '"apps_web_present":false' || {
    echo "FAIL: apps_web_present must be false"
    err=1
  }
fi

# Optional UI fingerprint (NextChat, not Vite vue shell)
if curl -sf -o /dev/null --max-time 2 http://127.0.0.1:8080/; then
  html=$(curl -sf --max-time 2 http://127.0.0.1:8080/ | head -c 400)
  if echo "$html" | grep -qi 'vite/client'; then
    echo "FAIL: :8080 looks like Vite apps/web, not NextChat"
    err=1
  fi
  if echo "$html" | grep -qi '新对话' && echo "$html" | grep -qi 'Tools sandbox'; then
    echo "FAIL: :8080 fingerprint matches removed 三栏 shell"
    err=1
  fi
  echo "UI fingerprint: ok-ish (not vite client)"
fi

if [ "$err" -ne 0 ]; then
  echo "assert-product-identity: FAILED"
  exit 1
fi
echo "assert-product-identity: OK"
