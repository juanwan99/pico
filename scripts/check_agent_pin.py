#!/usr/bin/env python3
"""Verify installed kimi-agent-sdk / kimi-cli versions match freeze pins.

Also prints the exact ruff pin (E1) so CI logs show the lint tool version.

Not a proof that open-source Kimi Agent runtime executes multi-step runs.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "services" / "orchestrator"))

from pico_orchestrator.pins import AGENT_PINS, assert_pins, installed_versions


def _ruff_pin_and_installed() -> tuple[str | None, str | None]:
    req = (ROOT / "requirements-dev.txt").read_text(encoding="utf-8")
    m = re.search(r"^ruff==(0\.\d+\.\d+)\s*$", req, re.MULTILINE)
    pin = m.group(1) if m else None
    installed: str | None = None
    try:
        import importlib.metadata as md

        installed = md.version("ruff")
    except Exception:  # noqa: BLE001
        installed = None
    return pin, installed


def main() -> int:
    print("Pinned:", AGENT_PINS)
    print("Installed:", installed_versions())
    ruff_pin, ruff_installed = _ruff_pin_and_installed()
    print(f"ruff pin: {ruff_pin}  installed: {ruff_installed}")
    if not ruff_pin:
        print("FAIL: ruff must be exact-pinned in requirements-dev.txt (ruff==X.Y.Z)")
        return 1
    if ruff_installed is not None and ruff_installed != ruff_pin:
        print(f"FAIL: installed ruff {ruff_installed} != pin {ruff_pin}")
        return 1
    try:
        assert_pins()
    except RuntimeError as e:
        print("FAIL:", e)
        return 1
    print("OK: package pins match freeze (not runtime-integration proof)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
