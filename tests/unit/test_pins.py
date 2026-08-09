from __future__ import annotations

import re
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


def test_ruff_exact_pin_in_dev_deps() -> None:
    """E1: ruff must be exact-pinned (not a floating range) for reproducible CI."""
    req = (ROOT / "requirements-dev.txt").read_text(encoding="utf-8")
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    m = re.search(r"^ruff==(0\.\d+\.\d+)\s*$", req, re.MULTILINE)
    assert m, "requirements-dev.txt must pin ruff==X.Y.Z"
    pin = m.group(1)
    assert f'ruff=={pin}' in pyproject or f'"ruff=={pin}"' in pyproject
    # When ruff is installed (CI/local), version must match pin.
    try:
        import importlib.metadata as md

        installed = md.version("ruff")
    except Exception:  # noqa: BLE001
        return
    assert installed == pin, f"installed ruff {installed} != pin {pin}"
