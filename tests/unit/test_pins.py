from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "orchestrator"))

from pico_orchestrator.pins import AGENT_PINS, assert_pins, installed_versions


def test_pins_match_installed() -> None:
    assert AGENT_PINS["default_runtime"] == "pi-agent"
    assert AGENT_PINS["kimi-agent-sdk"] == "0.0.5"
    assert AGENT_PINS["kimi-cli"] == "1.12.0"
    # Legacy packages optional on Pi-only deploys; assert_pins only fails on mismatch.
    assert_pins()
    versions = installed_versions()
    assert versions["default_runtime"] == "pi-agent"
