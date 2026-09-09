"""T-PPT-SANDBOX-LIB: isolated python-pptx, never host bash."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "orchestrator"))

from pico_orchestrator.office.sandbox_lib import run_pptx_lib_source
from pico_orchestrator.true_pi.config import ALLOWED_GATEWAY_TOOLS


def test_sandbox_pptx_lib_allowlist_has_no_bash() -> None:
    assert "sandbox_pptx_lib" not in ALLOWED_GATEWAY_TOOLS
    assert "sandbox_office_lib" in ALLOWED_GATEWAY_TOOLS
    assert "read_office_skill" in ALLOWED_GATEWAY_TOOLS
    assert "bash" not in ALLOWED_GATEWAY_TOOLS
    client = (ROOT / "services/orchestrator/pico_orchestrator/office/sandbox_lib.py").read_text(
        encoding="utf-8"
    )
    # pico-api is a client now; the interpreter lives in the pico-office container
    assert "subprocess" not in client
    runner = (ROOT / "services/sandbox_worker/office_runner.py").read_text(encoding="utf-8")
    assert "sys.executable" in runner
    assert "shell=True" not in runner
    assert run_pptx_lib_source is not None
