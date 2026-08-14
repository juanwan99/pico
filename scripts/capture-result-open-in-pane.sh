#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUT="$ROOT/docs/evidence/pack-result-open-in-pane"
HTML="$OUT/pane.html"
SHOT="../pack-b2-real-browser/viewport-example-com.png"
CHROME="${CHROME:-google-chrome}"
mkdir -p "$OUT"

shot() {
  local name="$1" qs="$2" w="$3" h="$4"
  local url="file://${HTML}?${qs}"
  "$CHROME" --headless=new --disable-gpu --no-sandbox --disable-dev-shm-usage \
    --force-device-scale-factor=1 --window-size="${w},${h}" \
    --screenshot="$OUT/${name}.png" "$url" >/dev/null 2>&1
  python3 - <<PY
from pathlib import Path
p = Path("$OUT/${name}.png")
print(f"{p.name} {p.stat().st_size} bytes")
if p.stat().st_size < 20_000:
    raise SystemExit(f"{p} is under 20KB")
PY
}

shot "01-open-html" "mode=wide&zoom=100%" 1280 800
shot "02-open-site" "mode=site&shot=${SHOT}" 1280 800
shot "03-open-source" "mode=source&shot=${SHOT}" 1280 800
shot "04-zoom" "mode=zoom&zoom=150%&shot=${SHOT}" 1280 800
shot "05-fullscreen" "mode=full&shot=${SHOT}" 1280 800
shot "v390" "mode=site&shot=${SHOT}" 390 844
echo "frames ok"
