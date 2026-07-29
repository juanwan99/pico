#!/usr/bin/env bash
# Fail closed if product shell drifts (the failure mode that shipped orange 三栏).
set -uo pipefail
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

if curl -sf -o /dev/null --max-time 2 http://127.0.0.1:8000/v1/meta/version; then
  body=$(curl -sf --max-time 2 http://127.0.0.1:8000/v1/meta/version || true)
  echo "version: $body"
  if ! echo "$body" | grep -Eq '"product_ui_ok"[[:space:]]*:[[:space:]]*true'; then
    echo "FAIL: product_ui_ok is not true"
    err=1
  fi
  if ! echo "$body" | grep -Eq '"apps_web_present"[[:space:]]*:[[:space:]]*false'; then
    echo "FAIL: apps_web_present must be false"
    err=1
  fi
fi

if curl -sf -o /dev/null --max-time 2 http://127.0.0.1:8080/; then
  html=$(curl -sf --max-time 2 http://127.0.0.1:8080/ | head -c 800 || true)
  if echo "$html" | grep -qi 'vite/client'; then
    echo "FAIL: :8080 looks like Vite apps/web, not NextChat"
    err=1
  fi
  echo "UI fingerprint: ok-ish (not vite client)"
fi

if [ "$err" -ne 0 ]; then
  echo "assert-product-identity: FAILED"
  exit 1
fi
echo "assert-product-identity: OK"
exit 0
