#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TESTS=(
  tests/unit/test_api_health.py
  tests/unit/test_kimi_runtime.py
  tests/integration/test_ledger_and_flow.py
  tests/integration/test_task_conversation_run_artifacts.py
)

if command -v python3.12 >/dev/null 2>&1; then
  cd "$ROOT"
  exec python3.12 -m pytest -q "${TESTS[@]}"
fi

if command -v docker >/dev/null 2>&1; then
  exec docker run --rm -v "$ROOT:/workspace" -w /workspace python:3.12-slim \
    bash -lc 'python -m pip install -q -r requirements-dev.txt && python -m pytest -q tests/unit/test_api_health.py tests/unit/test_kimi_runtime.py tests/integration/test_ledger_and_flow.py tests/integration/test_task_conversation_run_artifacts.py'
fi

echo "[pico] Python 3.12 or Docker is required; CI uses Python 3.12." >&2
exit 2
