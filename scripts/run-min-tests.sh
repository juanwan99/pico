#!/usr/bin/env bash
# R8 — one-shot minimal test path for hosts without Python 3.12.
# Prefer local venv / python3.12; else docker python:3.12-slim.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

run_pytest() {
  local py="$1"
  shift
  if ! "$py" -m pip --version >/dev/null 2>&1; then
    "$py" -m ensurepip --upgrade >/dev/null 2>&1 || true
  fi
  "$py" -m pip install -q -U pip
  "$py" -m pip install -q -r requirements-dev.txt
  "$py" -m ruff check services tests scripts
  "$py" scripts/check_agent_pin.py
  "$py" -m pytest -q tests/unit "$@"
}

if command -v python3.12 >/dev/null 2>&1; then
  echo "min-tests: host python3.12"
  run_pytest python3.12 "$@"
  exit 0
fi

if [[ -x "$ROOT/.venv/bin/python" ]]; then
  ver="$("$ROOT/.venv/bin/python" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')"
  if [[ "$ver" == "3.12" || "$ver" == "3.13" || "$ver" == "3.14" ]]; then
    echo "min-tests: .venv python $ver"
    run_pytest "$ROOT/.venv/bin/python" "$@"
    exit 0
  fi
fi

if command -v docker >/dev/null 2>&1; then
  echo "min-tests: docker python:3.12-slim (host has no usable py≥3.12)"
  docker run --rm \
    -v "$ROOT:/work" -w /work \
    -e PYTHONDONTWRITEBYTECODE=1 \
    python:3.12-slim \
    bash -lc 'pip install -q -r requirements-dev.txt && ruff check services tests scripts && python scripts/check_agent_pin.py && pytest -q tests/unit'
  exit 0
fi

echo "BLOCKED: need python3.12+ or docker for min tests (requires-python>=3.12)" >&2
echo "CI path: .github/workflows/ci.yml uses actions/setup-python 3.12" >&2
exit 2
