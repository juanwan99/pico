#!/usr/bin/env bash
# Patch production/local .env with tiered run budgets (P-COMPLEX-DONE package A).
# Only rewrites known PICO_RUN_* keys; never prints secrets from other lines.
#
# Usage (on the host that owns the .env):
#   bash scripts/apply-tiered-run-caps.sh /opt/pico/.env
# Or via SSH from ops:
#   bash scripts/apply-tiered-run-caps.sh --remote pico-prod
set -euo pipefail

DELIVERY_SECONDS="${PICO_RUN_MAX_SECONDS:-900}"
DELIVERY_TOKENS="${PICO_RUN_MAX_TOKENS:-32000}"
DELIVERY_STEPS="${PICO_RUN_MAX_STEPS:-24}"
DELIVERY_RETRIES="${PICO_RUN_MAX_RETRIES:-2}"
SHORT_SECONDS="${PICO_RUN_SHORT_MAX_SECONDS:-120}"
SHORT_TOKENS="${PICO_RUN_SHORT_MAX_TOKENS:-8000}"
DURABLE_SECONDS="${PICO_RUN_DURABLE_MAX_SECONDS:-3600}"
DETACH="${PICO_RUN_DETACH_ON_DISCONNECT:-1}"

patch_env_file() {
  local env_file="$1"
  if [[ ! -f "$env_file" ]]; then
    echo "[pico] ERROR: env file not found: $env_file" >&2
    return 2
  fi
  # Backup once per run
  local bak="${env_file}.bak-tiered-caps-$(date +%Y%m%d%H%M%S)"
  cp -a "$env_file" "$bak"
  python3 - "$env_file" <<'PY'
import re
import sys
from pathlib import Path

path = Path(sys.argv[1])
text = path.read_text(encoding="utf-8")
updates = {
    "PICO_RUN_MAX_SECONDS": "900",
    "PICO_RUN_MAX_TOKENS": "32000",
    "PICO_RUN_MAX_STEPS": "24",
    "PICO_RUN_MAX_RETRIES": "2",
    "PICO_RUN_SHORT_MAX_SECONDS": "120",
    "PICO_RUN_SHORT_MAX_TOKENS": "8000",
    "PICO_RUN_DURABLE_MAX_SECONDS": "3600",
    "PICO_RUN_DETACH_ON_DISCONNECT": "1",
}
# Allow env overrides when script is invoked with exports
import os
for key in list(updates):
    if os.environ.get(key):
        updates[key] = os.environ[key]

lines = text.splitlines(keepends=True)
seen: set[str] = set()
out: list[str] = []
for line in lines:
    m = re.match(r"^([A-Z0-9_]+)=(.*)$", line.rstrip("\n"))
    if m and m.group(1) in updates:
        key = m.group(1)
        out.append(f"{key}={updates[key]}\n")
        seen.add(key)
    else:
        out.append(line if line.endswith("\n") else line + "\n")
missing = [k for k in updates if k not in seen]
if missing:
    if out and not out[-1].endswith("\n"):
        out[-1] = out[-1] + "\n"
    out.append("\n# Tiered run budgets (P-COMPLEX-DONE)\n")
    for key in missing:
        out.append(f"{key}={updates[key]}\n")
path.write_text("".join(out), encoding="utf-8")
print(f"[pico] patched {path}")
for key, value in updates.items():
    print(f"[pico]   {key}={value}")
PY
}

if [[ "${1:-}" == "--remote" ]]; then
  host="${2:-pico-prod}"
  if [[ "$host" == -* || ! "$host" =~ ^[A-Za-z0-9._@:-]+$ ]]; then
    echo "[pico] ERROR: invalid SSH host: $host" >&2
    exit 2
  fi
  # Stream this script body to remote and run against /opt/pico/.env
  ssh -o BatchMode=yes -o ConnectTimeout=12 "$host" \
    "PICO_RUN_MAX_SECONDS=${DELIVERY_SECONDS} \
     PICO_RUN_MAX_TOKENS=${DELIVERY_TOKENS} \
     PICO_RUN_MAX_STEPS=${DELIVERY_STEPS} \
     PICO_RUN_MAX_RETRIES=${DELIVERY_RETRIES} \
     PICO_RUN_SHORT_MAX_SECONDS=${SHORT_SECONDS} \
     PICO_RUN_SHORT_MAX_TOKENS=${SHORT_TOKENS} \
     PICO_RUN_DURABLE_MAX_SECONDS=${DURABLE_SECONDS} \
     PICO_RUN_DETACH_ON_DISCONNECT=${DETACH} \
     bash -s" <<'REMOTE'
set -euo pipefail
ENV_FILE="${PICO_ENV_FILE:-/opt/pico/.env}"
if [[ ! -f "$ENV_FILE" ]]; then
  echo "[pico] ERROR: missing $ENV_FILE" >&2
  exit 2
fi
bak="${ENV_FILE}.bak-tiered-caps-$(date +%Y%m%d%H%M%S)"
cp -a "$ENV_FILE" "$bak"
python3 - "$ENV_FILE" <<'PY'
import os, re
from pathlib import Path
path = Path(__import__("sys").argv[1])
text = path.read_text(encoding="utf-8")
updates = {
    "PICO_RUN_MAX_SECONDS": os.environ.get("PICO_RUN_MAX_SECONDS", "900"),
    "PICO_RUN_MAX_TOKENS": os.environ.get("PICO_RUN_MAX_TOKENS", "32000"),
    "PICO_RUN_MAX_STEPS": os.environ.get("PICO_RUN_MAX_STEPS", "24"),
    "PICO_RUN_MAX_RETRIES": os.environ.get("PICO_RUN_MAX_RETRIES", "2"),
    "PICO_RUN_SHORT_MAX_SECONDS": os.environ.get("PICO_RUN_SHORT_MAX_SECONDS", "120"),
    "PICO_RUN_SHORT_MAX_TOKENS": os.environ.get("PICO_RUN_SHORT_MAX_TOKENS", "8000"),
    "PICO_RUN_DURABLE_MAX_SECONDS": os.environ.get("PICO_RUN_DURABLE_MAX_SECONDS", "3600"),
    "PICO_RUN_DETACH_ON_DISCONNECT": os.environ.get("PICO_RUN_DETACH_ON_DISCONNECT", "1"),
}
lines = text.splitlines(keepends=True)
seen = set()
out = []
for line in lines:
    m = re.match(r"^([A-Z0-9_]+)=(.*)$", line.rstrip("\n"))
    if m and m.group(1) in updates:
        key = m.group(1)
        out.append(f"{key}={updates[key]}\n")
        seen.add(key)
    else:
        out.append(line if line.endswith("\n") else line + "\n")
missing = [k for k in updates if k not in seen]
if missing:
    if out and not out[-1].endswith("\n"):
        out[-1] += "\n"
    out.append("\n# Tiered run budgets (P-COMPLEX-DONE)\n")
    for key in missing:
        out.append(f"{key}={updates[key]}\n")
path.write_text("".join(out), encoding="utf-8")
print(f"[pico] patched {path}")
for key, value in updates.items():
    print(f"[pico]   {key}={value}")
PY
REMOTE
  exit 0
fi

env_file="${1:-.env}"
patch_env_file "$env_file"
