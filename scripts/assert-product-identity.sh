#!/usr/bin/env bash
# Fail closed if product shell drifts (hand-rolled apps/web must not return).
set -uo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

err=0
if [ -d apps/web ]; then
  echo "FAIL: apps/web exists — hand-rolled shell must not return"
  err=1
fi
if [ ! -f apps/workbench/package.json ] && [ ! -f apps/nextchat/package.json ]; then
  echo "FAIL: no product UI (apps/workbench or apps/nextchat)"
  err=1
fi

# API meta may be loopback-only on :18765
for port in 18765 8000; do
  if curl -sf -o /dev/null --max-time 2 "http://127.0.0.1:${port}/v1/meta/version"; then
    body=$(curl -sf --max-time 2 "http://127.0.0.1:${port}/v1/meta/version" || true)
    echo "version: $body"
    if ! echo "$body" | grep -Eq '"product_ui_ok"[[:space:]]*:[[:space:]]*true'; then
      echo "FAIL: product_ui_ok is not true"
      err=1
    fi
    if ! echo "$body" | grep -Eq '"apps_web_present"[[:space:]]*:[[:space:]]*false'; then
      echo "FAIL: apps_web_present must be false"
      err=1
    fi
    break
  fi
done

if curl -sf -o /dev/null --max-time 2 http://127.0.0.1:8080/; then
  html=$(curl -sf --max-time 2 http://127.0.0.1:8080/ | head -c 1200 || true)
  if echo "$html" | grep -qi 'Claude / Codex式工作台'; then
    echo "FAIL: :8080 looks like banned apps/web shell"
    err=1
  fi
  if ! echo "$html" | grep -qiE 'Pico|workbench|root'; then
    echo "WARN: UI fingerprint weak"
  fi
  echo "UI fingerprint: ok"
fi

if [ "$err" -ne 0 ]; then
  echo "assert-product-identity: FAILED"
  exit 1
fi
echo "assert-product-identity: OK"
exit 0
