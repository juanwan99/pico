#!/usr/bin/env bash
# Public workbench check for login page, release tip and first-screen bundles.
set -euo pipefail

cd "$(dirname "$0")/../.."
. scripts/pico-first-screen-assets.sh
base="${PICO_PUBLIC_BASE:-https://pico.aivia.asia}"
base="${base%/}"
work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT

get_public_page "$base" /login "$work/login.html"
get_public_page "$base" /api/pico/tip "$work/tip.json"

python3 - "$work/tip.json" <<'PY'
import json
import re
import sys

with open(sys.argv[1], encoding="utf-8") as file:
    tip = json.load(file)
sha = tip.get("git_sha", "")
if tip.get("ok") is not True or not re.fullmatch(r"[0-9a-f]{40}", sha):
    raise SystemExit("FAIL /api/pico/tip did not return a release SHA")
print(f"PASS tip {sha}")
PY

# Check the cache as a visitor finds it, without filling it first.
fetch_first_screen_bundles "$base" "$work/login.html" check
