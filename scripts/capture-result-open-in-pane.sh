#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUT="$ROOT/docs/evidence/pack-result-open-in-pane"
HTML="$OUT/pane.html"
SHOT="../pack-b2-real-browser/viewport-example-com.png"
CHROME="${CHROME:-google-chrome}"
mkdir -p "$OUT"

shot() {
  local name="$1" qs="$2"
  local url="file://${HTML}?${qs}"
  "$CHROME" --headless=new --disable-gpu --hide-scrollbars --no-sandbox \
    --force-device-scale-factor=1 --window-size=390,844 \
    --screenshot="$OUT/${name}.png" "$url" >/dev/null 2>&1
  python3 - <<PY
from pathlib import Path
p = Path("$OUT/${name}.png")
print(f"{p.name} {p.stat().st_size} bytes")
if p.stat().st_size < 20_000:
    raise SystemExit(f"{p} is under 20KB")
PY
}

shot "01-open-html" "mode=html"
shot "02-open-site" "mode=site&shot=${SHOT}"
shot "03-open-source" "mode=source&shot=${SHOT}"
cp -f "$OUT/02-open-site.png" "$OUT/v390.png"
echo "frames ok"
