#!/usr/bin/env bash
# Agent-local regression. Does NOT hit production VPS.
# Usage:
#   bash scripts/agent-selftest.sh
#   PICO_SELFTEST_API_ONLY=1 bash scripts/agent-selftest.sh   # skip LibreChat UI
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
API="${PICO_API:-http://127.0.0.1:18765}"
UI="${PICO_UI:-http://127.0.0.1:8080}"
EMAIL="${DEMO_EMAIL:-teacher@example.com}"
PASS="${DEMO_PASSWORD:-pico-demo-123}"
API_ONLY="${PICO_SELFTEST_API_ONLY:-0}"
FAIL=0

pass() { echo "  PASS  $*"; }
fail() { echo "  FAIL  $*"; FAIL=$((FAIL + 1)); }
skip() { echo "  SKIP  $*"; }

echo "=== Pico agent selftest (local) ==="
echo "API=$API UI=$UI API_ONLY=$API_ONLY"

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

if [ "$API_ONLY" = "1" ]; then
  skip "UI / auth / playwright"
else
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

  export NODE_PATH="${ROOT}/node_modules:${NODE_PATH:-}"
  if node -e "require('playwright')" 2>/dev/null; then
    mkdir -p "$ROOT/screenshots"
    if PICO_UI="$UI" DEMO_EMAIL="$EMAIL" DEMO_PASSWORD="$PASS" node <<'NODE'
const { chromium } = require('playwright');
(async () => {
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage({ viewport: { width: 1280, height: 800 } });
  const ui = process.env.PICO_UI || 'http://127.0.0.1:8080';
  await page.goto(ui + '/login', { waitUntil: 'domcontentloaded', timeout: 45000 });
  await page.waitForTimeout(1500);
  await page.screenshot({ path: 'screenshots/selftest-login.png', fullPage: true });
  await browser.close();
})().catch((e) => { console.error(String(e)); process.exit(1); });
NODE
    then
      pass "playwright login screenshot"
    else
      fail "playwright"
    fi
  else
    skip "playwright"
  fi
fi


# S2 pico-agent explicit multi-step path (smoke, not full tool matrix)
python3 - <<'PYS2' && pass "S2 pico-agent reply" || fail "S2 pico-agent"
import json, urllib.request, urllib.error, os, sys
API=os.environ.get("PICO_API","http://127.0.0.1:18765")
H={"Authorization":"Bearer pico-dev","Content-Type":"application/json","X-Pico-Membership-Id":"selftest-s2"}
body={"model":"pico-agent","stream":False,"messages":[{"role":"user","content":"【Pico-User:s2】用一句话说明你是谁，不要调工具"}]}
req=urllib.request.Request(API+"/v1/chat/completions", data=json.dumps(body).encode(), method="POST", headers=H)
try:
    with urllib.request.urlopen(req, timeout=120) as r:
        d=json.loads(r.read().decode())
except urllib.error.HTTPError as e:
    print(e.code, e.read()[:200]); sys.exit(1)
msg=((d.get("choices") or [{}])[0].get("message") or {}).get("content") or ""
assert len(msg.strip())>0, d
print("s2", msg[:120].replace("\n"," "))
PYS2

# S7 membership isolation
python3 - <<'PYISO' && pass "S7 membership isolation" || fail "S7 isolation"
import json, urllib.request, urllib.error, os, sys
API=os.environ.get("PICO_API","http://127.0.0.1:18765")

def req(mid, method, path, body=None):
    data=None if body is None else json.dumps(body).encode()
    h={"Authorization":"Bearer pico-dev","Content-Type":"application/json","X-Pico-Membership-Id":mid}
    r=urllib.request.Request(API+path, data=data, method=method, headers=h)
    with urllib.request.urlopen(r, timeout=30) as resp:
        return json.loads(resp.read().decode() or "{}")

a=req("iso-a","POST","/v1/changes",{"title":"iso-a","summary":"only a","payload":{}})
cid=a["change"]["id"]
list_b=req("iso-b","GET","/v1/changes")
ids=[c.get("id") for c in (list_b.get("changes") or [])]
assert cid not in ids, ("leak", ids)
list_a=req("iso-a","GET","/v1/changes")
ids_a=[c.get("id") for c in (list_a.get("changes") or [])]
assert cid in ids_a, ids_a
print("iso ok", cid)
PYISO

python3 - <<'PYS7' && pass "S7 create/confirm/reject" || fail "S7 API"
import json, urllib.request, urllib.error, os, sys
API = os.environ.get("PICO_API", "http://127.0.0.1:18765")

def req(method, path, body=None):
    data = None if body is None else json.dumps(body).encode()
    h = {
        "Authorization": "Bearer pico-dev",
        "Content-Type": "application/json",
        "X-Pico-Membership-Id": "selftest-s7",
    }
    r = urllib.request.Request(API + path, data=data, method=method, headers=h)
    try:
        with urllib.request.urlopen(r, timeout=30) as resp:
            return resp.status, json.loads(resp.read().decode() or "{}")
    except urllib.error.HTTPError as e:
        print("http", e.code, e.read()[:200])
        sys.exit(1)

st, d = req("POST", "/v1/changes", {"title": "selftest", "summary": "s7", "payload": {"t": 1}})
assert st == 200 and d.get("change", {}).get("id"), d
cid = d["change"]["id"]
st, c = req("POST", f"/v1/changes/{cid}/confirm", {})
assert st == 200 and c.get("change", {}).get("status") == "confirmed", c
print("ok", cid)
PYS7

python3 - <<'PYART' && pass "hello.txt artifact ledger" || fail "artifact path"
import json, urllib.request, urllib.error, os, sys
API = os.environ.get("PICO_API", "http://127.0.0.1:18765")
H = {
    "Authorization": "Bearer pico-dev",
    "Content-Type": "application/json",
    "X-Pico-Membership-Id": "selftest-art",
}

def req(method, path, body=None, timeout=120):
    data = None if body is None else json.dumps(body).encode()
    r = urllib.request.Request(API + path, data=data, method=method, headers=H)
    try:
        with urllib.request.urlopen(r, timeout=timeout) as resp:
            return resp.status, json.loads(resp.read().decode() or "{}")
    except urllib.error.HTTPError as e:
        print(e.code, e.read()[:200])
        sys.exit(1)

st, d = req(
    "POST",
    "/v1/chat/completions",
    {
        "model": "kimi-k2.6",
        "stream": False,
        "messages": [{"role": "user", "content": "【Pico-User:selftest-art】创建 hello.txt，内容为 hi"}],
    },
)
assert st == 200, d
st, t = req("GET", "/v1/tasks")
tasks = (t.get("tasks") or []) if isinstance(t, dict) else []
assert tasks, t
tid = tasks[0]["id"]
st, detail = req("GET", f"/v1/tasks/{tid}")
arts = (detail.get("artifacts") or []) if isinstance(detail, dict) else []
titles = [a.get("title") for a in arts]
assert "hello.txt" in titles or any(a.get("kind") == "file" for a in arts), titles
print("artifacts", titles)
PYART

echo "=== summary fails=$FAIL ==="
if [ "$FAIL" -eq 0 ]; then
  echo SELFTEST_OK
  exit 0
fi
echo SELFTEST_FAIL
exit 1
