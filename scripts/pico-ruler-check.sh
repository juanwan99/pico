#!/usr/bin/env bash
# One command for the pico#1323 acceptance: throwaway stack up, the ruler twice,
# card items reconciled, pass-1 vs pass-2 table, stack down (also on failure).
#
#   bash scripts/pico-ruler-check.sh git:<sha>|<src dir> [name] [idx]
#
# Output: ~/pico-ruler-out/<name>-<stamp>/{pass1,pass2}.{json,md,log} + reconcile.txt
set -euo pipefail
HERE="$(cd "$(dirname "$0")/.." && pwd)"
SRC="${1:?usage: pico-ruler-check.sh git:<sha>|<src dir> [name] [idx]}"
NAME="${2:-check}"
IDX="${3:-0}"
OUT="$HOME/pico-ruler-out/$NAME-$(date +%m%d-%H%M)"
mkdir -p "$OUT"
trap 'bash "$HERE/scripts/pico-ruler-stack.sh" down "$NAME" "$IDX" >/dev/null 2>&1 || true' EXIT
bash "$HERE/scripts/pico-ruler-stack.sh" up "$NAME" "$SRC" "$IDX"
for n in 1 2; do
  python3 "$HERE/scripts/pico-ruler.py" --stack "$NAME" --idx "$IDX" --label "$SRC · 第 $n 遍" \
    --json "$OUT/pass$n.json" --md "$OUT/pass$n.md" > "$OUT/pass$n.log" 2>&1
done
python3 "$HERE/scripts/pico-ruler.py" --compare "$OUT/pass1.json" "$OUT/pass2.json" > "$OUT/compare.md"
set +e
python3 "$HERE/scripts/pico-ruler.py" --reconcile "$OUT/pass1.json" "$OUT/pass2.json" | tee "$OUT/reconcile.txt"
rc=${PIPESTATUS[0]}
echo "out: $OUT"
exit "$rc"
