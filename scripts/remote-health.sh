#!/usr/bin/env bash
# Read production health. Prefer local loopback when this host is the ECS origin
# (ssh-ecs). Fall back to SSH jump. Does not deploy or print secrets.
set -euo pipefail

ssh_host="${1:-}"

if ! command -v python3 >/dev/null 2>&1; then
  echo "[pico] ERROR: python3 is required to parse health JSON" >&2
  exit 2
fi

health_json=""
if [[ -z "$ssh_host" ]] && curl -sf --max-time 3 http://127.0.0.1:18765/health >/dev/null 2>&1; then
  health_json="$(curl -sf --max-time 5 http://127.0.0.1:18765/health)"
else
  ssh_host="${ssh_host:-pico-prod}"
  if ! command -v ssh >/dev/null 2>&1; then
    echo "[pico] ERROR: ssh client missing" >&2
    exit 2
  fi
  if [[ "$ssh_host" == -* || ! "$ssh_host" =~ ^[A-Za-z0-9._@:-]+$ ]]; then
    echo "[pico] ERROR: invalid SSH host: $ssh_host" >&2
    exit 2
  fi
  if ! health_json="$(
    ssh -o BatchMode=yes -o ConnectTimeout=8 "$ssh_host" \
      'curl -sf --max-time 5 http://127.0.0.1:18765/health'
  )"; then
    echo "[pico] ERROR: failed to read production health via SSH host $ssh_host" >&2
    exit 2
  fi
fi

if ! python3 -c '
import json
import re
import sys

try:
    health = json.load(sys.stdin)
except (json.JSONDecodeError, UnicodeDecodeError) as exc:
    print(f"[pico] ERROR: invalid health JSON: {exc}", file=sys.stderr)
    raise SystemExit(2)

if health.get("ok") is not True:
    print("[pico] ERROR: health ok is not true", file=sys.stderr)
    raise SystemExit(2)

git_sha = health.get("git_sha")
if not isinstance(git_sha, str) or re.fullmatch(r"[0-9a-fA-F]{40}", git_sha) is None:
    print("[pico] ERROR: health git_sha is not a full commit SHA", file=sys.stderr)
    raise SystemExit(2)

print("ok=true")
print(f"git_sha={git_sha}")
' <<<"$health_json"; then
  exit 2
fi
