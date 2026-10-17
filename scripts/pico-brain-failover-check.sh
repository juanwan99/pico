#!/usr/bin/env bash
# pico#1336 一条命令：假上游 + 一次性栈 + 注入对账 + 拆掉（失败也拆）。
#
#   bash scripts/pico-brain-failover-check.sh git:<sha>|<src dir> [idx] [n]
#
# 只打一次性栈；假上游只在本机 127.0.0.1 监听，转发到现网 New API（只发短问题）。
set -euo pipefail
HERE="$(cd "$(dirname "$0")/.." && pwd)"
SRC="${1:?usage: pico-brain-failover-check.sh git:<sha>|<src dir> [idx] [n]}"
IDX="${2:-1}"; N="${3:-10}"; NAME="fo"
RELAY_PORT=$((18800 + IDX * 10 + 7))
WORK="$(mktemp -d "$HOME/pico-failover.XXXXXX")"
TARGET="$(docker inspect pico-pico-api-1 --format '{{range .Config.Env}}{{println .}}{{end}}' \
  | sed -n 's/^DEEPSEEK_BASE_URL=//p' | sed 's#/v1/*$##')"
echo '{"mode":"off"}' > "$WORK/fault.json"
python3 "$HERE/scripts/pico-fault-upstream.py" --listen "127.0.0.1:$RELAY_PORT" --target "$TARGET" \
  --state "$WORK/fault.json" --log "$WORK/fault.jsonl" &
RELAY_PID=$!
cleanup() {
  kill "$RELAY_PID" 2>/dev/null || true
  bash "$HERE/scripts/pico-ruler-stack.sh" down "$NAME" "$IDX" >/dev/null 2>&1 || true
}
trap cleanup EXIT
# Path keeps "127.0.0.1:3000" so Pico takes the same New API code path as live.
printf 'DEEPSEEK_BASE_URL=http://127.0.0.1:%s/127.0.0.1:3000/v1\n' "$RELAY_PORT" > "$WORK/env.extra"
PICO_RULER_API_ENV_EXTRA="$WORK/env.extra" bash "$HERE/scripts/pico-ruler-stack.sh" up "$NAME" "$SRC" "$IDX"
python3 "$HERE/scripts/pico-brain-failover-check.py" --stack "$NAME" --idx "$IDX" --relay-dir "$WORK" --n "$N" \
  | tee "$WORK/result.txt"
echo "明细：$WORK"
