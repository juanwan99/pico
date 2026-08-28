#!/usr/bin/env bash
# spawn-grok-ecs — thin kick to Grok Build already logged in on ECS.
# Steward only: hand the slip to /home/ops/.grok/bin/grok over ssh-ecs.
# Does not merge. Does not prod-update. Does not stay resident.
# Does not spawn Cloud Cursor. grok-bot is not the default (ACL).
# Secrets stay on the box. This script never prints auth.json values.
set -euo pipefail

REMOTE_GROK="${GROK_ECS_BIN:-/home/ops/.grok/bin/grok}"
REMOTE_CWD="${GROK_ECS_CWD:-/opt/pico}"
SSH_HOST="${GROK_ECS_SSH_HOST:-ecs}"
ISSUE=""
PROMPT_FILE=""
PROMPT_TEXT=""
PRINT_CMD=0
PROBE=0
RUN=0
NO_COMMENT=0

usage() {
  cat <<'EOF'
Usage:
  bash scripts/spawn-grok-ecs.sh --probe
  bash scripts/spawn-grok-ecs.sh --print-cmd --prompt-file slip.txt
  bash scripts/spawn-grok-ecs.sh --issue N
  bash scripts/spawn-grok-ecs.sh --prompt-file slip.txt --run

Env (names only; values never printed):
  GROK_ECS_BIN        default /home/ops/.grok/bin/grok
  GROK_ECS_CWD        default /opt/pico
  GROK_ECS_SSH_HOST   default ecs
  GROK_ECS_ALWAYS_APPROVE=1  optional; default off

Does not merge. Does not deploy. Does not start a daemon.
Cloud Cursor spawn-executor is paused (owner 2026-08-28).
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --issue) ISSUE="${2:-}"; shift 2 ;;
    --prompt-file) PROMPT_FILE="${2:-}"; shift 2 ;;
    --prompt) PROMPT_TEXT="${2:-}"; shift 2 ;;
    --print-cmd|--dry-run) PRINT_CMD=1; shift ;;
    --probe) PROBE=1; shift ;;
    --run) RUN=1; shift ;;
    --no-comment) NO_COMMENT=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *)
      echo "[spawn-grok-ecs] ERROR: unknown arg: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

if [[ "$PROBE" -eq 1 ]]; then
  if ! command -v ssh >/dev/null; then
    echo "[spawn-grok-ecs] ERROR: ssh missing" >&2
    exit 2
  fi
  out="$(
    ssh -o BatchMode=yes -o ConnectTimeout=15 "$SSH_HOST" \
      "test -x '$REMOTE_GROK' && test -s /home/ops/.grok/auth.json && echo GROK_ECS_OK"
  )"
  if [[ "$out" != *GROK_ECS_OK* ]]; then
    echo "[spawn-grok-ecs] ERROR: grok not ready on $SSH_HOST" >&2
    exit 2
  fi
  echo "GROK_ECS_OK"
  echo "host=$SSH_HOST bin=$REMOTE_GROK cwd=$REMOTE_CWD"
  exit 0
fi

if [[ -n "$PROMPT_FILE" ]]; then
  if [[ ! -f "$PROMPT_FILE" ]]; then
    echo "[spawn-grok-ecs] ERROR: prompt file missing: $PROMPT_FILE" >&2
    exit 2
  fi
  PROMPT_TEXT="$(cat "$PROMPT_FILE")"
fi

if [[ -z "$PROMPT_TEXT" && -n "$ISSUE" ]]; then
  if ! command -v gh >/dev/null; then
    echo "[spawn-grok-ecs] ERROR: gh required to read ## 派发 from issue" >&2
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
  echo "[spawn-grok-ecs] ERROR: empty prompt (need --issue, --prompt-file, or --prompt)" >&2
  exit 2
fi

slip_name="pico-grok-slip.txt"
if [[ -n "$ISSUE" ]]; then
  slip_name="pico-grok-slip-${ISSUE}.txt"
fi
remote_slip="/tmp/${slip_name}"

approve=()
if [[ "${GROK_ECS_ALWAYS_APPROVE:-}" == "1" ]]; then
  approve+=(--always-approve)
fi

remote_cmd="$REMOTE_GROK --cwd $REMOTE_CWD --prompt-file $remote_slip"
if [[ ${#approve[@]} -gt 0 ]]; then
  remote_cmd="$REMOTE_GROK --cwd $REMOTE_CWD --always-approve --prompt-file $remote_slip"
fi

if [[ "$PRINT_CMD" -eq 1 ]]; then
  echo "ssh $SSH_HOST $remote_cmd"
  echo "prompt_chars=${#PROMPT_TEXT}"
  exit 0
fi

# Default is --run (kick Grok once). Not a daemon.
if [[ "$RUN" -eq 0 && "$PRINT_CMD" -eq 0 ]]; then
  RUN=1
fi

if [[ "$RUN" -eq 1 ]]; then
  printf '%s' "$PROMPT_TEXT" | ssh -o BatchMode=yes -o ConnectTimeout=15 "$SSH_HOST" \
    "umask 077; cat > '$remote_slip' && $remote_cmd; st=\$?; rm -f '$remote_slip'; exit \$st"
  if [[ "$NO_COMMENT" -eq 0 && -n "$ISSUE" ]] && command -v gh >/dev/null; then
    gh issue comment "$ISSUE" --repo juanwan99/pico --body "## grok-ecs
已把 \`## 派发\` 交给 ECS Grok（\`ssh $SSH_HOST\` · \`$REMOTE_GROK\` · cwd=\`$REMOTE_CWD\`）。
不常驻。不合不部（总管）。写入 VERDICT_AUTHORITY: NONE。"
  fi
fi
