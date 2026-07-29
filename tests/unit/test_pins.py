from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "orchestrator"))

from pico_orchestrator.pins import AGENT_PINS, assert_pins


def test_pins_match_installed() -> None:
    assert AGENT_PINS["kimi-agent-sdk"] == "0.0.5"
    assert AGENT_PINS["kimi-cli"] == "1.12.0"
    assert_pins()
