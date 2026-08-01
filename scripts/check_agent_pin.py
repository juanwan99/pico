#!/usr/bin/env python3
"""Verify installed kimi-agent-sdk / kimi-cli versions match freeze pins.

Not a proof that open-source Kimi Agent runtime executes multi-step runs.
"""
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
    print("OK: package pins match freeze (not runtime-integration proof)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
