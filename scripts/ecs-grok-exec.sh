#!/usr/bin/env bash
# ecs-grok-exec — runs ON ECS. Thin wrap of upstream grok CLI.
# Steward uploads this per wake. Never uses /opt/pico as a development tree.
# GitHub remains the durable bus. This script is not a mailbox / second ledger.
set -euo pipefail

SESSION=""
PROMPT_FILE=""
CWD=""
CLONE="${PICO_EXECUTOR_CLONE:-/home/ops/pico-exec}"
WT_ROOT="${PICO_EXECUTOR_WT_ROOT:-/home/ops/pico-wt}"
ISSUE=""
PR=""
REF="origin/main"
FOREGROUND=0
NO_WORKTREE=0
MAX_TURNS="${PICO_GROK_MAX_TURNS:-80}"
CONTINUE=0

usage() {
  cat <<'EOF'
Usage: bash ecs-grok-exec.sh --session NAME --prompt FILE [options]
  --session NAME     tmux session (pico-exec-<issue>)
  --prompt FILE      prompt already on this machine
  --cwd DIR          working directory (forbidden: /opt/pico, /opt/edu-cloud)
  --clone DIR        git clone used as worktree source (default /home/ops/pico-exec)
  --issue N          create/reuse worktree /home/ops/pico-wt/issue-N
  --pr N|URL         checkout that PR in the worktree
  --ref REF          base ref for new worktree (default origin/main)
  --foreground       run grok -p in this SSH session (no tmux)
  --no-worktree      do not create a git worktree
  --max-turns N
  --continue         grok --continue in --cwd
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --session) SESSION="${2:-}"; shift 2 ;;
    --prompt) PROMPT_FILE="${2:-}"; shift 2 ;;
    --cwd) CWD="${2:-}"; shift 2 ;;
    --clone) CLONE="${2:-}"; shift 2 ;;
    --issue) ISSUE="${2:-}"; shift 2 ;;
    --pr) PR="${2:-}"; shift 2 ;;
    --ref) REF="${2:-}"; shift 2 ;;
    --foreground) FOREGROUND=1; shift ;;
    --no-worktree) NO_WORKTREE=1; shift ;;
    --max-turns) MAX_TURNS="${2:-}"; shift 2 ;;
    --continue) CONTINUE=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *)
      echo "[ecs-grok-exec] ERROR: unknown arg: $1" >&2
      exit 2
      ;;
  esac
done

if [[ -z "$SESSION" || -z "$PROMPT_FILE" ]]; then
  echo "[ecs-grok-exec] ERROR: --session and --prompt required" >&2
  exit 2
fi
if [[ ! -f "$PROMPT_FILE" ]]; then
  echo "[ecs-grok-exec] ERROR: prompt missing: $PROMPT_FILE" >&2
  exit 2
fi
if [[ ! "$SESSION" =~ ^[A-Za-z0-9_-]+$ ]]; then
  echo "[ecs-grok-exec] ERROR: bad session name" >&2
  exit 2
fi

# Login-equivalent PATH + proxy. Non-interactive SSH does not source ~/.bashrc.
if [[ -f /home/ops/.grok/env.sh ]]; then
  # shellcheck disable=SC1091
  . /home/ops/.grok/env.sh
fi
export PATH="/home/ops/.local/bin:/home/ops/.grok/bin:${PATH}"

if ! command -v grok >/dev/null 2>&1; then
  echo "[ecs-grok-exec] ERROR: grok not on PATH after sourcing ~/.grok/env.sh" >&2
  exit 2
fi

forbid_prod_tree() {
  local abs
  abs="$(readlink -f "$1")"
  case "$abs" in
    /opt/pico|/opt/pico/*|/opt/edu-cloud|/opt/edu-cloud/*)
      echo "[ecs-grok-exec] ERROR: forbidden cwd $abs (production tree)" >&2
      exit 2
      ;;
  esac
}

ensure_clone() {
  if [[ -d "$CLONE/.git" || -f "$CLONE/.git" ]]; then
    git -C "$CLONE" fetch origin --prune >/dev/null 2>&1 || \
      git -C "$CLONE" fetch origin --prune
    return 0
  fi
  mkdir -p "$(dirname "$CLONE")"
  git clone git@github.com:juanwan99/pico.git "$CLONE"
}

if [[ "$NO_WORKTREE" -eq 0 && -z "$CWD" ]]; then
  if [[ -z "$ISSUE" ]]; then
    echo "[ecs-grok-exec] ERROR: need --issue or --cwd or --no-worktree" >&2
    exit 2
  fi
  ensure_clone
  mkdir -p "$WT_ROOT"
  CWD="${WT_ROOT}/issue-${ISSUE}"
  if [[ ! -d "$CWD" ]]; then
    git -C "$CLONE" worktree add -B "exec/issue-${ISSUE}" "$CWD" "$REF"
  fi
elif [[ -z "$CWD" ]]; then
  echo "[ecs-grok-exec] ERROR: --cwd required with --no-worktree" >&2
  exit 2
fi

mkdir -p "$CWD"
forbid_prod_tree "$CWD"

if [[ -n "$PR" ]]; then
  if ! command -v gh >/dev/null 2>&1; then
    echo "[ecs-grok-exec] ERROR: gh required to checkout PR" >&2
    exit 2
  fi
  pr_n="$PR"
  if [[ "$PR" =~ /pull/([0-9]+) ]]; then
    pr_n="${BASH_REMATCH[1]}"
  fi
  git -C "$CWD" fetch origin --prune >/dev/null 2>&1 || true
  (cd "$CWD" && gh pr checkout "$pr_n")
fi

JOBDIR="$(dirname "$PROMPT_FILE")"
LOG="${JOBDIR}/grok.log"
RUN="${JOBDIR}/run.sh"
abs_cwd="$(readlink -f "$CWD")"
abs_prompt="$(readlink -f "$PROMPT_FILE")"
cont_flag=""
if [[ "$CONTINUE" -eq 1 ]]; then
  cont_flag=" --continue"
fi
cat > "$RUN" <<EOF
#!/usr/bin/env bash
set -euo pipefail
if [[ -f /home/ops/.grok/env.sh ]]; then . /home/ops/.grok/env.sh; fi
export PATH="/home/ops/.local/bin:/home/ops/.grok/bin:\${PATH}"
exec grok -p "\$(cat $(printf '%q' "$abs_prompt"))" \\
  --cwd $(printf '%q' "$abs_cwd") \\
  --max-turns $(printf '%q' "$MAX_TURNS") \\
  --always-approve --permission-mode bypassPermissions \\
  --no-alt-screen --output-format plain${cont_flag}
EOF
chmod +x "$RUN"

echo "ok=true"
echo "runtime=ecs-grok"
echo "session=${SESSION}"
echo "cwd=${abs_cwd}"
echo "log=${LOG}"
echo "detached=$([[ "$FOREGROUND" -eq 1 ]] && echo false || echo true)"
echo "grok=$(command -v grok)"
echo "max_turns=${MAX_TURNS}"

if [[ "$FOREGROUND" -eq 1 ]]; then
  bash "$RUN" 2>&1 | tee "$LOG"
  exit "${PIPESTATUS[0]}"
fi

if ! command -v tmux >/dev/null 2>&1; then
  echo "[ecs-grok-exec] ERROR: tmux required for detached wake" >&2
  exit 2
fi

# Only kill this named executor session. Never kill other grok processes (interactive pts stays).
if tmux has-session -t "$SESSION" 2>/dev/null; then
  tmux kill-session -t "$SESSION"
fi
tmux new-session -d -s "$SESSION" "bash $(printf '%q' "$RUN") > $(printf '%q' "$LOG") 2>&1"
echo "tmux=${SESSION}"
