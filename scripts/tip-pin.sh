#!/usr/bin/env bash
# Pin public tip (40-char git_sha). BINDING companion to visual-gate (#384 / TIP-PROBE).
# Usage: bash scripts/tip-pin.sh [base_url]
set -euo pipefail

BASE="${1:-${PICO_PUBLIC_BASE:-https://pico.aivia.asia}}"
BASE="${BASE%/}"
URL="${BASE}/api/pico/tip"

if ! command -v python3 >/dev/null; then
  echo "[tip-pin] ERROR: python3 required" >&2
  exit 2
fi

# Prefer python urllib (curl may be restricted in some agent sandboxes)
TIP_JSON="$(python3 - "$URL" <<'PY'
import json, sys, urllib.request
url = sys.argv[1]
with urllib.request.urlopen(url, timeout=15) as r:
    raw = r.read().decode()
print(raw)
PY
)"

TIP_URL="$URL" TIP_JSON="$TIP_JSON" python3 <<'PY'
import json, os, re, sys
raw = os.environ["TIP_JSON"]
url = os.environ["TIP_URL"]
try:
    data = json.loads(raw)
except Exception as e:
    print(f"[tip-pin] ERROR: invalid JSON: {e}", file=sys.stderr)
    raise SystemExit(2)
sha = data.get("git_sha") or ""
if not data.get("ok") or not re.fullmatch(r"[0-9a-f]{40}", sha or ""):
    print(f"[tip-pin] ERROR: bad tip payload: {raw[:200]}", file=sys.stderr)
    raise SystemExit(2)
print(f"tip_url={url}")
print(f"git_sha={sha}")
print(f"service={data.get('service', '')}")
print("ok=true")
PY
