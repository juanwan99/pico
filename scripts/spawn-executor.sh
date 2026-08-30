#!/usr/bin/env bash
# spawn-executor — thin adapter: steward SSH → ECS grok CLI (executor).
# Same GitHub contract (派发 / CANDIDATE / DEPLOYED). Not Cursor Cloud Agents.
# Steward only: launch / wake. Never merge main from this script. Never prod-update.
# Secrets stay in env / on-box grok login. This script never prints key values.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
REMOTE_HELPER="$ROOT/scripts/ecs-grok-exec.sh"
ISSUE=""
PR_URL=""
PROMPT_FILE=""
PROMPT_TEXT=""
SESSION=""
DISPLAY_NAME=""
CWD=""
REF="origin/main"
WAKE_MERGE=0
DRY_RUN=0
PRINT_PAYLOAD=0
NO_COMMENT=0
FOREGROUND=0
NO_WORKTREE=0
CONTINUE=0
MAX_TURNS="${PICO_GROK_MAX_TURNS:-80}"
SHA=""
AGENT_ID=""

CONTRACT="$(cat <<'EOF'
【执行者合同 · ECS Grok】
你是 Pico 执行者。工作流不变：1卡1PR · GitHub Issue 是唯一总线 · VERDICT_AUTHORITY: NONE。
runtime：本机 grok CLI（SSH 叫醒）。禁止改用 Cursor Cloud Agent / 评 @cursor 当执行者。
工作目录：只在本隔离 checkout。禁止把 /opt/pico 或 /opt/edu-cloud 当开发树。
部署：有差才 `PICO_DEPLOY_SHA=<40> bash /opt/pico/scripts/prod-update.sh`。
回执贴合同 Issue：## CANDIDATE / ## DEPLOYED / 五句。禁止证据进 PR。禁止 Closes 部前关卡。禁止自签 PASS。总管不合不部——合与部归你。
禁写 juanwan99/edu-cloud。
EOF
)"

usage() {
  cat <<'EOF'
Usage:
  bash scripts/spawn-executor.sh --issue N
  bash scripts/spawn-executor.sh --prompt-file slip.txt
  bash scripts/spawn-executor.sh --issue N --wake-merge --pr 683 --sha <40>
  bash scripts/spawn-executor.sh --cwd /tmp --prompt "…" --foreground --max-turns 1

Env (names only; values never printed):
  PICO_EXECUTOR_SSH_HOST   default ecs (Tailscale MagicDNS)
  PICO_EXECUTOR_SSH        optional ssh wrapper (tests)
  PICO_GROK_MAX_TURNS      default 80

Fail-closed if ssh ecs fails (except --print-payload / --dry-run).
Live tmux pico-exec-N: remote exits 2 live=true (does not kill-session).
Does not merge. Does not deploy. Does not spawn a Cursor Cloud Agent.
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
    --session) SESSION="${2:-}"; shift 2 ;;
    --agent) AGENT_ID="${2:-}"; shift 2 ;;
    --env)
      echo "[spawn-executor] WARN: --env ignored (Cursor cloud env retired; executor is ECS grok)" >&2
      shift 2
      ;;
    --name) DISPLAY_NAME="${2:-}"; shift 2 ;;
    --repo)
      echo "[spawn-executor] WARN: --repo ignored (always juanwan99/pico on ECS)" >&2
      shift 2
      ;;
    --ref) REF="${2:-}"; shift 2 ;;
    --cwd) CWD="${2:-}"; shift 2 ;;
    --sha) SHA="${2:-}"; shift 2 ;;
    --wake-merge) WAKE_MERGE=1; shift ;;
    --dry-run) DRY_RUN=1; shift ;;
    --print-payload) PRINT_PAYLOAD=1; shift ;;
    --no-comment) NO_COMMENT=1; shift ;;
    --foreground) FOREGROUND=1; shift ;;
    --no-worktree) NO_WORKTREE=1; shift ;;
    --continue) CONTINUE=1; shift ;;
    --max-turns) MAX_TURNS="${2:-}"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *)
      echo "[spawn-executor] ERROR: unknown arg: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

if [[ -n "$AGENT_ID" ]]; then
  if [[ "$AGENT_ID" == bc-* ]]; then
    echo "[spawn-executor] ERROR: Cursor agent id retired. Executor is ECS grok. Use --session pico-exec-<issue>." >&2
    exit 2
  fi
  SESSION="$AGENT_ID"
fi

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
    "黄审已过则：squash 合该候选 SHA → 读 origin/main 的 40 位 → 一次 PICO_DEPLOY_SHA=<main> prod-update → tip=origin/main → 五句 DONE 贴合同 Issue。",
    "禁止：新开第二张 PR/卡 · 合了未部报 DONE · Closes 部前关卡 · 自签 PASS · 直推 main · 部 PR 头 SHA · 活窗再 spawn · 改生产账号哈希拍过门图",
]
print("\n".join(lines))
PY
  )"
fi

FULL_PROMPT="${CONTRACT}

${PROMPT_TEXT}"

if [[ -z "$SESSION" ]]; then
  if [[ -n "$DISPLAY_NAME" ]]; then
    SESSION="$(printf '%s' "$DISPLAY_NAME" | tr -c 'A-Za-z0-9_-' '-' | cut -c1-40)"
  elif [[ -n "$ISSUE" ]]; then
    SESSION="pico-exec-${ISSUE}"
  else
    SESSION="pico-exec-adhoc"
  fi
fi
if [[ ! "$SESSION" =~ ^[A-Za-z0-9_-]+$ ]]; then
  echo "[spawn-executor] ERROR: bad session name: $SESSION" >&2
  exit 2
fi

if [[ -n "$CWD" ]]; then
  NO_WORKTREE=1
fi
if [[ -z "$CWD" && -z "$ISSUE" && "$NO_WORKTREE" -eq 1 ]]; then
  echo "[spawn-executor] ERROR: --cwd required when --no-worktree without --issue" >&2
  exit 2
fi
if [[ -z "$CWD" && -z "$ISSUE" ]]; then
  echo "[spawn-executor] ERROR: need --issue or --cwd" >&2
  exit 2
fi

REMOTE_CWD="$CWD"
if [[ -z "$REMOTE_CWD" && -n "$ISSUE" ]]; then
  REMOTE_CWD="/home/ops/pico-wt/issue-${ISSUE}"
fi

PR_N=""
if [[ "$PR_URL" =~ /pull/([0-9]+) ]]; then
  PR_N="${BASH_REMATCH[1]}"
fi

PAYLOAD="$(
  FULL_PROMPT="$FULL_PROMPT" \
  SESSION="$SESSION" \
  REMOTE_CWD="$REMOTE_CWD" \
  ISSUE="$ISSUE" \
  PR_N="$PR_N" \
  REF="$REF" \
  FOREGROUND="$FOREGROUND" \
  NO_WORKTREE="$NO_WORKTREE" \
  CONTINUE="$CONTINUE" \
  MAX_TURNS="$MAX_TURNS" \
  WAKE_MERGE="$WAKE_MERGE" \
  PICO_EXECUTOR_SSH_HOST="${PICO_EXECUTOR_SSH_HOST:-}" \
  python3 - <<'PY'
import json, os
print(json.dumps({
    "runtime": "ecs-grok",
    "ssh_host": os.environ.get("PICO_EXECUTOR_SSH_HOST") or "ecs",
    "session": os.environ["SESSION"],
    "cwd": os.environ.get("REMOTE_CWD") or "",
    "issue": os.environ.get("ISSUE") or "",
    "pr": os.environ.get("PR_N") or "",
    "ref": os.environ.get("REF") or "origin/main",
    "foreground": os.environ.get("FOREGROUND") == "1",
    "no_worktree": os.environ.get("NO_WORKTREE") == "1",
    "continue": os.environ.get("CONTINUE") == "1",
    "max_turns": int(os.environ.get("MAX_TURNS") or "80"),
    "wake_merge": os.environ.get("WAKE_MERGE") == "1",
    "prompt": os.environ["FULL_PROMPT"],
}, ensure_ascii=False))
PY
)"

if [[ "$PRINT_PAYLOAD" -eq 1 || "$DRY_RUN" -eq 1 ]]; then
  printf '%s\n' "$PAYLOAD"
  if [[ "$DRY_RUN" -eq 1 ]]; then
    echo "ok=dry-run"
    echo "runtime=ecs-grok"
    echo "session=${SESSION}"
    echo "cwd=${REMOTE_CWD}"
  fi
  exit 0
fi

if [[ ! -f "$REMOTE_HELPER" ]]; then
  echo "[spawn-executor] ERROR: missing $REMOTE_HELPER" >&2
  exit 2
fi

executor_ssh() {
  if [[ -n "${PICO_EXECUTOR_SSH:-}" ]]; then
    # Test/override wrapper. Receives the remote command as remaining args.
    # shellcheck disable=SC2086
    ${PICO_EXECUTOR_SSH} "$@"
    return
  fi
  ssh -o BatchMode=yes -o ConnectTimeout=20 "${PICO_EXECUTOR_SSH_HOST:-ecs}" "$@"
}

if ! executor_ssh "true"; then
  echo "[spawn-executor] ERROR: ssh ecs failed (need ssh-ecs / Tailscale). Fail-closed." >&2
  exit 2
fi

JOBDIR="/home/ops/.pico-exec/jobs/${SESSION}"
executor_ssh "mkdir -p $(printf '%q' "$JOBDIR") && chmod 700 /home/ops/.pico-exec /home/ops/.pico-exec/jobs $(printf '%q' "$JOBDIR")"
printf '%s' "$FULL_PROMPT" | executor_ssh "cat > $(printf '%q' "$JOBDIR/prompt.md")"
executor_ssh "cat > $(printf '%q' "$JOBDIR/ecs-grok-exec.sh") && chmod +x $(printf '%q' "$JOBDIR/ecs-grok-exec.sh")" < "$REMOTE_HELPER"

REMOTE_ARGS=(
  bash "$(printf '%q' "$JOBDIR/ecs-grok-exec.sh")"
  --session "$(printf '%q' "$SESSION")"
  --prompt "$(printf '%q' "$JOBDIR/prompt.md")"
  --max-turns "$(printf '%q' "$MAX_TURNS")"
  --ref "$(printf '%q' "$REF")"
)
if [[ -n "$ISSUE" ]]; then
  REMOTE_ARGS+=(--issue "$(printf '%q' "$ISSUE")")
fi
if [[ -n "$CWD" ]]; then
  REMOTE_ARGS+=(--cwd "$(printf '%q' "$CWD")")
fi
if [[ "$NO_WORKTREE" -eq 1 ]]; then
  REMOTE_ARGS+=(--no-worktree)
fi
if [[ "$FOREGROUND" -eq 1 ]]; then
  REMOTE_ARGS+=(--foreground)
fi
if [[ "$CONTINUE" -eq 1 ]]; then
  REMOTE_ARGS+=(--continue)
fi
if [[ -n "$PR_N" ]]; then
  REMOTE_ARGS+=(--pr "$(printf '%q' "$PR_N")")
fi

# Join already-quoted tokens into one remote command.
REMOTE_CMD="${REMOTE_ARGS[*]}"
PARSED="$(executor_ssh "$REMOTE_CMD")"
printf '%s\n' "$PARSED"

if [[ -n "$ISSUE" && "$NO_COMMENT" -eq 0 ]] && command -v gh >/dev/null; then
  LOG_PATH="$(printf '%s\n' "$PARSED" | awk -F= '/^log=/{print $2; exit}')"
  CWD_OUT="$(printf '%s\n' "$PARSED" | awk -F= '/^cwd=/{print $2; exit}')"
  gh issue comment "$ISSUE" --repo juanwan99/pico --body "$(cat <<EOF
## 起窗

- runtime: ecs-grok（SSH \`ecs\` → 机上 grok CLI）
- session: \`${SESSION}\`
- cwd: \`${CWD_OUT:-$REMOTE_CWD}\`
- log: \`${LOG_PATH:-$JOBDIR/grok.log}\`
- 首条 = 本卡 \`## 派发\` / \`## 续派\`
- 总管不合不部
- 禁止 Cursor Cloud Agent / \`@cursor\` 当执行者

CLAIM-WB-DEGREE-WEB: NO
EOF
)" >/dev/null
fi
