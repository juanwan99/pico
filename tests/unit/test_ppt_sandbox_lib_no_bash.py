"""T-PPT-SANDBOX-LIB: isolated python-pptx, never host bash."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "orchestrator"))

from pico_orchestrator.office.sandbox_lib import run_pptx_lib_source
from pico_orchestrator.true_pi.config import ALLOWED_GATEWAY_TOOLS


def test_sandbox_pptx_lib_allowlist_has_no_bash() -> None:
    assert "sandbox_pptx_lib" in ALLOWED_GATEWAY_TOOLS
    assert "bash" not in ALLOWED_GATEWAY_TOOLS
    src = (ROOT / "services/orchestrator/pico_orchestrator/office/sandbox_lib.py").read_text(
        encoding="utf-8"
    )
    assert "sys.executable" in src
    assert "shell=True" not in src
    assert run_pptx_lib_source is not None
