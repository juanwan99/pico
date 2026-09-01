#!/usr/bin/env bash
# 一眼看 PR 的 CI 是否可合。禁止轮询。
#
# 退出码：
#   0 绿（可合）
#   1 未出齐 / 进行中
#   2 红（失败 / 取消 / 超时 / 需人工 / 已关 / 冲突）
#   3 用法错
#
# 数据：PR_CI_READY_JSON（测试夹具）或 gh pr view --json。
set -euo pipefail

usage() {
  cat <<'EOF' >&2
用法: scripts/pr-ci-ready.sh --pr <N> [--repo owner/repo]
  --pr     必填，PR 号
  --repo   默认 juanwan99/pico
退出: 0 绿 · 1 未出齐 · 2 红 · 3 用法
禁止轮询 check-runs / sleep 等绿。未绿由本窗 subscribe-ci 再跑一眼。
EOF
}

PR=""
REPO="${PR_CI_READY_REPO:-juanwan99/pico}"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --pr)
      PR="${2:-}"
      shift 2
      ;;
    --repo)
      REPO="${2:-}"
      shift 2
      ;;
    -h|--help)
      usage
      exit 3
      ;;
    *)
      echo "未知参数: $1" >&2
      usage
      exit 3
      ;;
  esac
done

if [[ -z "$PR" || ! "$PR" =~ ^[0-9]+$ ]]; then
  echo "缺 --pr <数字>" >&2
  usage
  exit 3
fi

if [[ -n "${PR_CI_READY_JSON:-}" ]]; then
  json="$PR_CI_READY_JSON"
else
  if ! command -v gh >/dev/null 2>&1; then
    echo "本机无 gh，且未设 PR_CI_READY_JSON" >&2
    exit 3
  fi
  json="$(gh pr view "$PR" --repo "$REPO" --json statusCheckRollup,mergeStateStatus,state,files 2>/dev/null || true)"
  if [[ -z "$json" ]]; then
    echo "读不到 PR #${PR}（${REPO}）" >&2
    exit 3
  fi
fi

# heredoc 占 stdin，JSON 只走环境变量
PR_CI_READY_JSON="$json" python3 - "$PR" "$REPO" <<'PY'
import json, os, sys

pr, repo = sys.argv[1], sys.argv[2]
raw = os.environ.get("PR_CI_READY_JSON") or ""
try:
    data = json.loads(raw)
except json.JSONDecodeError as e:
    print(f"JSON 坏: {e}", file=sys.stderr)
    sys.exit(3)

state = (data.get("state") or "").upper()
if state == "CLOSED":
    print(f"PR #{pr} 已关（{repo}）", file=sys.stderr)
    sys.exit(2)
if state == "MERGED":
    print(f"PR #{pr} 已合（{repo}）", file=sys.stderr)
    sys.exit(2)

ok = {"SUCCESS", "SKIPPED", "NEUTRAL"}
bad = {
    "FAILURE",
    "ERROR",
    "CANCELLED",
    "TIMED_OUT",
    "ACTION_REQUIRED",
    "STARTUP_FAILURE",
    "STALE",
}
pending = {"IN_PROGRESS", "QUEUED", "PENDING", "WAITING", "EXPECTED", "REQUESTED"}

rollup = data.get("statusCheckRollup")
if rollup is None:
    rollup = []
if not isinstance(rollup, list):
    print("statusCheckRollup 不是数组", file=sys.stderr)
    sys.exit(3)

def conclusion_of(item):
    if not isinstance(item, dict):
        return ""
    conc = item.get("conclusion")
    if conc:
        return str(conc).upper().replace("-", "_")
    st = item.get("state")
    if st:
        return str(st).upper().replace("-", "_")
    st2 = item.get("status")
    if st2:
        return str(st2).upper().replace("-", "_")
    return ""

names = []
any_bad = False
any_pending = False
for item in rollup:
    name = "?"
    if isinstance(item, dict):
        name = item.get("name") or item.get("context") or "?"
    conc = conclusion_of(item)
    names.append(f"{name}={conc or 'EMPTY'}")
    if conc in bad:
        any_bad = True
    elif conc in ok:
        pass
    elif conc in pending or not conc:
        any_pending = True
    else:
        any_pending = True

merge_state = (data.get("mergeStateStatus") or "").upper()
if merge_state == "DIRTY":
    print(f"红 PR #{pr} 有冲突 DIRTY {' '.join(names)}", file=sys.stderr)
    sys.exit(2)
if merge_state in {"BLOCKED", "UNSTABLE"} and not any_bad:
    any_pending = True

if any_bad:
    print(f"红 PR #{pr} {' '.join(names)}", file=sys.stderr)
    sys.exit(2)

if not rollup:
    files = data.get("files") or []
    paths = []
    if isinstance(files, list):
        for item in files:
            if isinstance(item, dict) and item.get("path"):
                paths.append(str(item["path"]))
            elif isinstance(item, str):
                paths.append(item)

    def is_docs_path(p: str) -> bool:
        return p.startswith("docs/") or p.endswith(".md")

    if paths and all(is_docs_path(p) for p in paths):
        print(f"绿 PR #{pr} docs-only 无检查项（paths-ignore）")
        sys.exit(0)
    print(f"未出齐 PR #{pr} 无检查项", file=sys.stderr)
    sys.exit(1)

if any_pending:
    print(f"未出齐 PR #{pr} {' '.join(names)}", file=sys.stderr)
    sys.exit(1)

print(f"绿 PR #{pr} {' '.join(names)}")
sys.exit(0)
PY
