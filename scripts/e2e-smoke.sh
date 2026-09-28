#!/usr/bin/env bash
# Pico E2E smoke — one command, read-only, exit 0 only when every check passes.
#
# Registered in AGENTS.md as E2E-SMOKE (agent-policy TASK-POLICY.md §1).
# scripts/prod-update.impl.sh runs `--prod` as its last gate: a failed smoke is
# a failed deploy.
#
# Modes
#   bash scripts/e2e-smoke.sh            local: API 127.0.0.1:18765, UI 127.0.0.1:8080, key pico-dev
#   bash scripts/e2e-smoke.sh --public   anonymous read-only against https://pico.aivia.asia
#                                        (authenticated checks only when PICO_SMOKE_KEY is set)
#   bash scripts/e2e-smoke.sh --prod     on the production host: loopback API/UI + public tip,
#                                        key read from $PICO_ROOT/.env (never printed)
#   --no-ui                              drop the LibreChat checks (API-only dev box)
#
# Env overrides: PICO_SMOKE_API, PICO_SMOKE_UI, PICO_SMOKE_PUBLIC, PICO_SMOKE_KEY,
#   PICO_SMOKE_TENANT (default smoke-school:smoke-e2e), PICO_SMOKE_EXPECT_SHA,
#   PICO_SMOKE_TIMEOUT (seconds per request, default 10).
#
# Read-only by design: GET only, a dedicated smoke tenant, no chat, no kb/search
# (that records a usage event), no writes to real teacher data.
# Last line is always `smoke <pass>/<total> PASS` or `smoke <pass>/<total> FAIL`.
set -uo pipefail

MODE="local"
WITH_UI=1
for arg in "$@"; do
  case "$arg" in
    --public) MODE="public" ;;
    --prod) MODE="prod" ;;
    --no-ui) WITH_UI=0 ;;
    -h|--help)
      sed -n '2,24p' "$0" | sed 's/^# \{0,1\}//'
      exit 0
      ;;
    *)
      echo "smoke: unknown argument: $arg" >&2
      exit 2
      ;;
  esac
done

PUBLIC="${PICO_SMOKE_PUBLIC:-https://pico.aivia.asia}"
TIMEOUT="${PICO_SMOKE_TIMEOUT:-10}"
TENANT="${PICO_SMOKE_TENANT:-smoke-school:smoke-e2e}"
KEY="${PICO_SMOKE_KEY:-}"

case "$MODE" in
  local)
    API="${PICO_SMOKE_API:-http://127.0.0.1:18765}"
    UI="${PICO_SMOKE_UI:-http://127.0.0.1:8080}"
    TIP_URL="$API/v1/meta/tip"
    HEALTH_URL="$API/health"
    HEALTH_JSON=1
    KEY="${KEY:-pico-dev}"
    ;;
  public)
    API="${PICO_SMOKE_API:-$PUBLIC/api/pico}"
    UI="${PICO_SMOKE_UI:-$PUBLIC}"
    TIP_URL="$UI/api/pico/tip"
    # Public /health is the edge's plain "OK"; the JSON health stays on loopback.
    HEALTH_URL="$UI/health"
    HEALTH_JSON=0
    ;;
  prod)
    API="${PICO_SMOKE_API:-http://127.0.0.1:18765}"
    # Shared ECS: LibreChat loopback is 18088 — never 8080 (edu-core-bff).
    UI="${PICO_SMOKE_UI:-${LIBRECHAT_URL:-http://127.0.0.1:18088}}"
    TIP_URL="$PUBLIC/api/pico/tip"
    HEALTH_URL="$API/health"
    HEALTH_JSON=1
    if [ -z "$KEY" ]; then
      ENV_FILE="${PICO_ROOT:-/opt/pico}/.env"
      if [ -f "$ENV_FILE" ]; then
        KEY="$(grep -E '^PICO_OPENAI_PROXY_KEY=' "$ENV_FILE" | head -1 | cut -d= -f2- | tr -d '"'"'" || true)"
      fi
    fi
    ;;
esac
[ "$WITH_UI" -eq 1 ] && [ -z "$UI" ] && WITH_UI=0

WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT
BODY="$WORK/body"
PASS=0
TOTAL=0
FAILED=""
TIP_SHA=""

# http <method> <url> [curl args…] → prints status code, body lands in $BODY.
http() {
  local method="$1" url="$2"
  shift 2
  : >"$BODY"
  local code
  code="$(curl -sS -X "$method" -o "$BODY" -w '%{http_code}' --max-time "$TIMEOUT" "$@" "$url" 2>/dev/null)" || true
  printf '%s' "${code:-000}"
}

# jq-free JSON assertions (python3 is on every Pico host and in CI).
json() {
  python3 - "$BODY" "$@" <<'PY'
import json, re, sys
path, expr = sys.argv[1], sys.argv[2]
args = sys.argv[3:]
try:
    body = json.load(open(path, encoding="utf-8"))
except Exception as exc:  # noqa: BLE001
    print(f"not-json: {exc}")
    raise SystemExit(1)
def fail(msg):
    print(msg)
    raise SystemExit(1)
if expr == "tip":
    sha = body.get("git_sha") or ""
    if body.get("ok") is not True or not re.fullmatch(r"[0-9a-f]{40}", sha):
        fail(f"ok={body.get('ok')} git_sha={sha!r}")
    if args and args[0] and sha != args[0]:
        fail(f"git_sha={sha} expected={args[0]}")
    print(sha)
elif expr == "health":
    sha = body.get("git_sha") or ""
    if body.get("ok") is not True or body.get("service") != "pico-api":
        fail(f"ok={body.get('ok')} service={body.get('service')!r}")
    if args and args[0] and sha != args[0]:
        fail(f"health.git_sha={sha} tip={args[0]} (split brain)")
    print(f"sha={sha[:12]} runtime={body.get('default_runtime')}")
elif expr == "me":
    school, member = args[0], args[1]
    if body.get("school_id") != school or body.get("membership_id") != member:
        fail(f"school_id={body.get('school_id')!r} membership_id={body.get('membership_id')!r}")
    scopes = body.get("scopes") or []
    if "ai:read" not in scopes:
        fail(f"scopes={scopes}")
    print(f"{school}:{member} scopes={len(scopes)}")
elif expr == "models":
    ids = [m.get("id") for m in (body.get("data") or []) if isinstance(m, dict)]
    if not ids:
        fail(f"no models: {json.dumps(body)[:120]}")
    print(",".join(str(i) for i in ids[:4]))
elif expr == "skills":
    skills = body.get("skills")
    if not isinstance(skills, list) or not skills:
        fail(f"no skills: {json.dumps(body)[:120]}")
    print(f"skills={len(skills)}")
elif expr == "tools":
    tools = body.get("tools")
    if not isinstance(tools, list):
        fail(f"no tools list: {json.dumps(body)[:120]}")
    print(f"tools={len(tools)}")
elif expr == "tasks":
    if not isinstance(body.get("tasks"), list):
        fail(f"no tasks list: {json.dumps(body)[:120]}")
    print(f"tasks={len(body['tasks'])}")
elif expr == "usage":
    if body.get("schema") != "pico.usage.v1" or body.get("billing") is not False:
        fail(f"schema={body.get('schema')!r} billing={body.get('billing')!r}")
    print(f"schema={body['schema']} days={len(body.get('days') or [])}")
elif expr == "folders":
    if not isinstance(body.get("folders"), list):
        fail(f"no folders list: {json.dumps(body)[:120]}")
    print(f"folders={len(body['folders'])}")
elif expr == "config":
    if not isinstance(body, dict) or "appTitle" not in body:
        fail(f"not a LibreChat config: {json.dumps(body)[:120]}")
    print(f"appTitle={body.get('appTitle')!r}")
else:
    fail(f"unknown assertion {expr}")
PY
}

report() {
  local ok="$1" name="$2" detail="$3"
  TOTAL=$((TOTAL + 1))
  if [ "$ok" -eq 0 ]; then
    PASS=$((PASS + 1))
    printf 'ok   %-12s %s\n' "$name" "$detail"
  else
    FAILED="$FAILED $name"
    printf 'FAIL %-12s %s\n' "$name" "$detail"
  fi
}

# check <name> <expected-code> <json-expr|-> <method> <url> [curl args…]
check() {
  local name="$1" want="$2" expr="$3" method="$4" url="$5"
  shift 5
  local code detail rc=0
  code="$(http "$method" "$url" "$@")"
  if [ "$code" != "$want" ]; then
    report 1 "$name" "http=$code want=$want $url"
    return 1
  fi
  if [ "$expr" = "-" ]; then
    report 0 "$name" "http=$code"
    return 0
  fi
  detail="$(json "$expr" ${JSON_ARGS[@]+"${JSON_ARGS[@]}"})" || rc=1
  report "$rc" "$name" "$detail"
  return "$rc"
}

JSON_ARGS=("${PICO_SMOKE_EXPECT_SHA:-}")
if check tip 200 tip GET "$TIP_URL"; then
  TIP_SHA="$(json tip "${PICO_SMOKE_EXPECT_SHA:-}")"
fi

if [ "$HEALTH_JSON" -eq 1 ]; then
  JSON_ARGS=("$TIP_SHA")
  check health 200 health GET "$HEALTH_URL"
else
  check health 200 - GET "$HEALTH_URL"
fi

if [ "$WITH_UI" -eq 1 ]; then
  check ui-login 200 - GET "$UI/login"
  JSON_ARGS=()
  check ui-config 200 config GET "$UI/api/config"
fi

# Fail-closed auth: the tenant-scoped API must reject anonymous callers.
check auth-401 401 - GET "$API/v1/me"

if [ -n "$KEY" ]; then
  AUTH=(-H "Authorization: Bearer $KEY" -H "X-Pico-Membership-Id: $TENANT")
  SCHOOL="${TENANT%%:*}"
  MEMBER="${TENANT#*:}"
  JSON_ARGS=("$SCHOOL" "$MEMBER")
  check me 200 me GET "$API/v1/me" "${AUTH[@]}"
  JSON_ARGS=()
  check models 200 models GET "$API/v1/models" "${AUTH[@]}"
  check skills 200 skills GET "$API/v1/skills/catalog" "${AUTH[@]}"
  check tools 200 tools GET "$API/v1/tools" "${AUTH[@]}"
  check tasks 200 tasks GET "$API/v1/tasks" "${AUTH[@]}"
  check usage 200 usage GET "$API/v1/usage/summary" "${AUTH[@]}"
  check my-folders 200 folders GET "$API/v1/my/folders" "${AUTH[@]}"
elif [ "$MODE" = "prod" ]; then
  # Production must be able to exercise the authenticated read paths.
  report 1 key "PICO_OPENAI_PROXY_KEY missing (env PICO_SMOKE_KEY or \$PICO_ROOT/.env)"
else
  echo "note anonymous only — set PICO_SMOKE_KEY for the authenticated checks"
fi

if [ "$PASS" -eq "$TOTAL" ] && [ "$TOTAL" -gt 0 ]; then
  echo "smoke $PASS/$TOTAL PASS ($MODE)"
  exit 0
fi
echo "smoke $PASS/$TOTAL FAIL ($MODE) failed:${FAILED:- none}"
exit 1
