#!/usr/bin/env bash
# spawn-executor — thin adapter to the official Cursor Cloud Agents API.
# Steward only: launch / wake an executor. Never merge main. Never prod-update.
# Upstream: https://cursor.com/docs/cloud-agent/api/endpoints  POST /v1/agents
# Secrets stay in env. This script never prints key values.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
API_BASE="${CURSOR_API_BASE:-https://api.cursor.com}"
REPO_URL="${CURSOR_REPO_URL:-https://github.com/juanwan99/pico}"
STARTING_REF="${CURSOR_STARTING_REF:-main}"
EXEC_ENV="${CURSOR_EXECUTOR_ENV:-}"
ISSUE=""
PR_URL=""
PROMPT_FILE=""
PROMPT_TEXT=""
AGENT_ID=""
DISPLAY_NAME=""
WAKE_MERGE=0
DRY_RUN=0
PRINT_PAYLOAD=0
NO_COMMENT=0
SHA=""

usage() {
  cat <<'EOF'
Usage:
  bash scripts/spawn-executor.sh --issue N
  bash scripts/spawn-executor.sh --prompt-file slip.txt [--env NAME]
  bash scripts/spawn-executor.sh --agent bc-… --prompt-file wake.txt
  bash scripts/spawn-executor.sh --issue N --wake-merge --pr 683 --sha <40>

Env (names only; values never printed):
  CURSOR_API_KEY          required except --print-payload / --dry-run
  CURSOR_EXECUTOR_ENV     named cloud env with TS/SSH (exclusive with repos)
  CURSOR_API_BASE         default https://api.cursor.com
  CURSOR_REPO_URL         default https://github.com/juanwan99/pico

Does not merge. Does not deploy. Fail-closed if the key is missing.
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --issue) ISSUE="${2:-}"; shift 2 ;;
    --pr)
      raw="${2:-}"
      if [[ "$raw" =~ ^[0-9]+$ ]]; then
        PR_URL="https://github.com/juanwan99/pico/pull/${raw}"
      else
        PR_URL="$raw"
      fi
      shift 2
      ;;
    --prompt-file) PROMPT_FILE="${2:-}"; shift 2 ;;
    --prompt) PROMPT_TEXT="${2:-}"; shift 2 ;;
    --agent) AGENT_ID="${2:-}"; shift 2 ;;
    --env) EXEC_ENV="${2:-}"; shift 2 ;;
    --name) DISPLAY_NAME="${2:-}"; shift 2 ;;
    --repo) REPO_URL="${2:-}"; shift 2 ;;
    --ref) STARTING_REF="${2:-}"; shift 2 ;;
    --sha) SHA="${2:-}"; shift 2 ;;
    --wake-merge) WAKE_MERGE=1; shift ;;
    --dry-run) DRY_RUN=1; shift ;;
    --print-payload) PRINT_PAYLOAD=1; shift ;;
    --no-comment) NO_COMMENT=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *)
      echo "[spawn-executor] ERROR: unknown arg: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

if [[ -n "$PROMPT_FILE" ]]; then
  if [[ ! -f "$PROMPT_FILE" ]]; then
    echo "[spawn-executor] ERROR: prompt file missing: $PROMPT_FILE" >&2
    exit 2
  fi
  PROMPT_TEXT="$(cat "$PROMPT_FILE")"
fi

if [[ -z "$PROMPT_TEXT" && -n "$ISSUE" ]]; then
  if ! command -v gh >/dev/null; then
    echo "[spawn-executor] ERROR: gh required to read ## 派发 from issue" >&2
    exit 2
  fi
  PROMPT_TEXT="$(
    ISSUE="$ISSUE" python3 - <<'PY'
import json, os, subprocess, sys
n = os.environ["ISSUE"]
raw = subprocess.check_output(
    ["gh", "api", f"repos/juanwan99/pico/issues/{n}/comments", "--paginate"],
    text=True,
)
comments = json.loads(raw)
chosen = ""
for c in comments:
    body = (c.get("body") or "").strip()
    if body.startswith("## 派发") or body.startswith("## 续派"):
        chosen = body
if not chosen:
    print("ERROR no ## 派发 / ## 续派 comment", file=sys.stderr)
    raise SystemExit(2)
print(chosen)
PY
  )"
fi

if [[ -z "${PROMPT_TEXT// }" ]]; then
  echo "[spawn-executor] ERROR: empty prompt (need --issue, --prompt-file, or --prompt)" >&2
  exit 2
fi

if [[ "$WAKE_MERGE" -eq 1 ]]; then
  PROMPT_TEXT="$(
    PROMPT_TEXT="$PROMPT_TEXT" PR_URL="$PR_URL" SHA="$SHA" ISSUE="$ISSUE" python3 - <<'PY'
import os
base = os.environ["PROMPT_TEXT"].rstrip()
pr = os.environ.get("PR_URL") or ""
sha = os.environ.get("SHA") or ""
issue = os.environ.get("ISSUE") or ""
lines = [
    base,
    "",
    "【续派 · 合部】",
]
if issue:
    lines.append(f"合同：https://github.com/juanwan99/pico/issues/{issue}")
if pr:
    lines.append(f"PR：{pr}")
if sha:
    lines.append(f"exact SHA：{sha}")
lines += [
    "黄审已过则：squash 合该 SHA → 一次 prod-update → tip=origin/main → 五句 DONE 贴合同 Issue。",
    "禁止：新开第二张 PR/卡 · 合了未部报 DONE · Closes 部前关卡 · 自签 PASS · 直推 main",
]
print("\n".join(lines))
PY
  )"
fi

if [[ -z "${CURSOR_API_KEY:-}" && "$PRINT_PAYLOAD" -eq 0 && "$DRY_RUN" -eq 0 ]]; then
  echo "[spawn-executor] ERROR: CURSOR_API_KEY unset (Dashboard → API Keys). Fail-closed." >&2
  exit 2
fi

PAYLOAD="$(
  PROMPT_TEXT="$PROMPT_TEXT" \
  REPO_URL="$REPO_URL" \
  STARTING_REF="$STARTING_REF" \
  EXEC_ENV="$EXEC_ENV" \
  PR_URL="$PR_URL" \
  AGENT_ID="$AGENT_ID" \
  DISPLAY_NAME="$DISPLAY_NAME" \
  python3 - <<'PY'
import json, os
prompt = os.environ["PROMPT_TEXT"]
agent_id = os.environ.get("AGENT_ID") or ""
if agent_id:
    body = {"prompt": {"text": prompt}}
    print(json.dumps(body, ensure_ascii=False))
    raise SystemExit(0)

body = {
    "prompt": {"text": prompt},
    "autoCreatePR": False,
    "skipReviewerRequest": True,
}
name = os.environ.get("DISPLAY_NAME") or ""
if name:
    body["name"] = name[:100]
env_name = os.environ.get("EXEC_ENV") or ""
pr_url = os.environ.get("PR_URL") or ""
if env_name:
    # Named cloud env is mutually exclusive with explicit repos.
    body["env"] = {"type": "cloud", "name": env_name}
    if pr_url:
        body["prompt"]["text"] = (
            prompt.rstrip()
            + "\n\n工作对象 PR（环境已含仓，按此 PR 的 head 继续，勿新开第二张）："
            + pr_url
        )
else:
    repo = {"url": os.environ["REPO_URL"], "startingRef": os.environ["STARTING_REF"]}
    if pr_url:
        repo["prUrl"] = pr_url
        body["workOnCurrentBranch"] = True
    body["repos"] = [repo]
print(json.dumps(body, ensure_ascii=False))
PY
)"

if [[ "$PRINT_PAYLOAD" -eq 1 || "$DRY_RUN" -eq 1 ]]; then
  printf '%s\n' "$PAYLOAD"
  if [[ "$DRY_RUN" -eq 1 ]]; then
    echo "ok=dry-run"
    echo "agent_id="
    echo "agent_url="
  fi
  exit 0
fi

if [[ -n "$AGENT_ID" ]]; then
  URL="${API_BASE%/}/v1/agents/${AGENT_ID}/runs"
else
  URL="${API_BASE%/}/v1/agents"
fi

RESP="$(
  URL="$URL" PAYLOAD="$PAYLOAD" python3 - <<'PY'
import json, os, sys, urllib.error, urllib.request
url = os.environ["URL"]
payload = os.environ["PAYLOAD"].encode()
key = os.environ.get("CURSOR_API_KEY") or ""
req = urllib.request.Request(
    url,
    data=payload,
    method="POST",
    headers={
        "Content-Type": "application/json",
        "Authorization": f"Bearer {key}",
    },
)
try:
    with urllib.request.urlopen(req, timeout=30) as r:
        raw = r.read().decode()
        code = r.status
except urllib.error.HTTPError as e:
    raw = e.read().decode() if e.fp else str(e)
    print(f"[spawn-executor] ERROR: HTTP {e.code}: {raw[:400]}", file=sys.stderr)
    raise SystemExit(2)
except Exception as e:
    print(f"[spawn-executor] ERROR: request failed: {e}", file=sys.stderr)
    raise SystemExit(2)
print(raw)
PY
)"

PARSED="$(
  RESP="$RESP" AGENT_ID="$AGENT_ID" python3 - <<'PY'
import json, os, sys
data = json.loads(os.environ["RESP"])
follow = bool(os.environ.get("AGENT_ID"))
if follow:
    run = data.get("run") or data
    agent_id = run.get("agentId") or os.environ.get("AGENT_ID") or ""
    run_id = run.get("id") or ""
    status = run.get("status") or ""
    url = f"https://cursor.com/agents/{agent_id}" if agent_id else ""
else:
    agent = data.get("agent") or data
    run = data.get("run") or {}
    agent_id = agent.get("id") or ""
    run_id = run.get("id") or agent.get("latestRunId") or ""
    status = run.get("status") or agent.get("status") or ""
    url = agent.get("url") or (f"https://cursor.com/agents/{agent_id}" if agent_id else "")
if not agent_id:
    print("[spawn-executor] ERROR: no agent id in response", file=sys.stderr)
    raise SystemExit(2)
print(f"ok=true")
print(f"agent_id={agent_id}")
print(f"agent_url={url}")
print(f"run_id={run_id}")
print(f"run_status={status}")
PY
)"
printf '%s\n' "$PARSED"

if [[ -n "$ISSUE" && "$NO_COMMENT" -eq 0 ]] && command -v gh >/dev/null; then
  AGENT_URL="$(printf '%s\n' "$PARSED" | awk -F= '/^agent_url=/{print $2}')"
  AGENT_ID_OUT="$(printf '%s\n' "$PARSED" | awk -F= '/^agent_id=/{print $2}')"
  gh issue comment "$ISSUE" --repo juanwan99/pico --body "$(cat <<EOF
## 起窗

- agent: ${AGENT_URL}
- id: \`${AGENT_ID_OUT}\`
- 首条 = 本卡 \`## 派发\` / \`## 续派\`
- 总管不合不部

CLAIM-WB-DEGREE-WEB: NO
EOF
)" >/dev/null
fi
