#!/usr/bin/env python3
"""Verify installed Kimi Agent pins match D1 freeze."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "services" / "orchestrator"))

from pico_orchestrator.pins import AGENT_PINS, assert_pins, installed_versions


def main() -> int:
    print("Pinned:", AGENT_PINS)
    print("Installed:", installed_versions())
    try:
        assert_pins()
    except RuntimeError as e:
        print("FAIL:", e)
        return 1
    print("OK: agent pins match freeze")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
