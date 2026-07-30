#!/usr/bin/env bash
# Agent-local regression (sandbox / CI agent). Does NOT hit production VPS.
# Usage: bash scripts/agent-selftest.sh
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
API="${PICO_API:-http://127.0.0.1:18765}"
UI="${PICO_UI:-http://127.0.0.1:8080}"
EMAIL="${DEMO_EMAIL:-teacher@example.com}"
PASS="${DEMO_PASSWORD:-pico-demo-123}"
FAIL=0

pass() { echo "  PASS  $*"; }
fail() { echo "  FAIL  $*"; FAIL=$((FAIL+1)); }

echo "=== Pico agent selftest (local) ==="
echo "API=$API UI=$UI"

h=$(curl -sS --max-time 5 "$API/health" || true)
echo "$h" | grep -q '"ok":true' && pass "api health" || fail "api health: $h"

code=$(curl -sS --max-time 90 -o /tmp/pico-st-s1.json -w '%{http_code}' \
  -H 'Authorization: Bearer pico-dev' \
  -H 'Content-Type: application/json' \
  -H 'X-Pico-Membership-Id: demo' \
  -d '{"model":"kimi-k2.6","stream":false,"messages":[{"role":"user","content":"【Pico-User:demo】只回：演示OK"}]}' \
  "$API/v1/chat/completions" || echo ERR)
if [ "$code" = "200" ] && grep -qE '演示OK|"content"' /tmp/pico-st-s1.json 2>/dev/null; then
  pass "S1 chat http=$code"
else
  fail "S1 chat http=$code body=$(head -c 160 /tmp/pico-st-s1.json 2>/dev/null)"
fi

uicode=$(curl -sS --max-time 10 -o /tmp/pico-st-login.html -w '%{http_code}' "$UI/login" || echo ERR)
if [ "$uicode" = "200" ] && grep -qiE 'root|Pico|html' /tmp/pico-st-login.html; then
  pass "UI /login http=$uicode"
else
  fail "UI /login http=$uicode"
fi

lcode=$(curl -sS --max-time 20 -o /tmp/pico-st-auth.json -w '%{http_code}' \
  -X POST "$UI/api/auth/login" \
  -H 'Content-Type: application/json' \
  -d "{\"email\":\"$EMAIL\",\"password\":\"$PASS\"}" || echo ERR)
if [ "$lcode" = "200" ] && grep -q 'token' /tmp/pico-st-auth.json; then
  pass "auth login http=$lcode"
else
  curl -sS --max-time 20 -X POST "$UI/api/auth/register" \
    -H 'Content-Type: application/json' \
    -d "{\"name\":\"Pico Teacher\",\"username\":\"teacher\",\"email\":\"$EMAIL\",\"password\":\"$PASS\",\"confirm_password\":\"$PASS\"}" >/dev/null || true
  lcode=$(curl -sS --max-time 20 -o /tmp/pico-st-auth.json -w '%{http_code}' \
    -X POST "$UI/api/auth/login" \
    -H 'Content-Type: application/json' \
    -d "{\"email\":\"$EMAIL\",\"password\":\"$PASS\"}" || echo ERR)
  if [ "$lcode" = "200" ] && grep -q 'token' /tmp/pico-st-auth.json; then
    pass "auth login after register http=$lcode"
  else
    fail "auth login http=$lcode body=$(head -c 120 /tmp/pico-st-auth.json 2>/dev/null)"
  fi
fi

# Playwright: use NODE_PATH for monorepo/template playwright
export NODE_PATH="${ROOT}/node_modules:${NODE_PATH:-}"
if node -e "require('playwright')" 2>/dev/null; then
  mkdir -p "$ROOT/screenshots"
  PICO_UI="$UI" DEMO_EMAIL="$EMAIL" DEMO_PASSWORD="$PASS" node <<'NODE' \
    && pass "playwright login screenshot" || fail "playwright"
const { chromium } = require('playwright');
(async () => {
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage({ viewport: { width: 1280, height: 800 } });
  const ui = process.env.PICO_UI || 'http://127.0.0.1:8080';
  await page.goto(ui + '/login', { waitUntil: 'domcontentloaded', timeout: 45000 });
  await page.waitForTimeout(2000);
  await page.screenshot({ path: 'screenshots/selftest-login.png', fullPage: true });
  const body = await page.locator('body').innerText().catch(() => '');
  if (!body || body.length < 3) throw new Error('empty body');
  const email = page.locator('input[type="email"], input[name="email"]').first();
  const pass = page.locator('input[type="password"]').first();
  if ((await email.count()) > 0 && (await pass.count()) > 0) {
    await email.fill(process.env.DEMO_EMAIL || 'teacher@example.com');
    await pass.fill(process.env.DEMO_PASSWORD || 'pico-demo-123');
    const btn = page.locator('button[type="submit"]').first();
    if ((await btn.count()) > 0) await btn.click({ timeout: 5000 }).catch(() => {});
    await page.waitForTimeout(3000);
    await page.screenshot({ path: 'screenshots/selftest-after-login.png', fullPage: true });
  }
  await browser.close();
})().catch((e) => { console.error(String(e)); process.exit(1); });
NODE
else
  echo "  SKIP  playwright"
fi

echo "=== summary fails=$FAIL ==="
[ "$FAIL" -eq 0 ] && echo SELFTEST_OK || { echo SELFTEST_FAIL; exit 1; }
