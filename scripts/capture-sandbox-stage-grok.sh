#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUT="$ROOT/docs/evidence/pack-sandbox-stage-grok"
HTML="$OUT/stage.html"
SHOT="../pack-b2-real-browser/viewport-example-com.png"
WORD="${WORD_SHOT:-$OUT/writer-raw.png}"
CHROME="${CHROME:-google-chrome}"
mkdir -p "$OUT"

shot() {
  local name="$1" qs="$2" w="$3" h="$4"
  "$CHROME" --headless=new --disable-gpu --no-sandbox --disable-dev-shm-usage \
    --force-device-scale-factor=1 --window-size="${w},${h}" \
    --screenshot="$OUT/${name}.png" "file://${HTML}?${qs}" >/dev/null 2>&1
  python3 - <<PY
from pathlib import Path
p = Path("$OUT/${name}.png")
print(f"{p.name} {p.stat().st_size} bytes")
if p.stat().st_size < 20_000:
    raise SystemExit(f"{p} is under 20KB")
PY
}

shot "01-f1-site" "mode=site&shot=${SHOT}" 1280 800
if [ -f "$WORD" ]; then
  shot "02-f2-word" "mode=word&word=$(basename "$WORD")" 1280 800
else
  echo "WARN: no Writer raw shot yet"
fi
shot "03-f3-chat-clean" "mode=clean" 1280 800
shot "04-f4-390" "mode=v390" 390 844
echo "frames ok"
