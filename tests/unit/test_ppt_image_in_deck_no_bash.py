"""T-PPT-IMAGE-IN-DECK: ceiling stays thin adapter, no host bash."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "orchestrator"))

from pico_orchestrator.true_pi.config import ALLOWED_GATEWAY_TOOLS


def test_image_in_deck_does_not_add_host_bash() -> None:
    assert "bash" not in ALLOWED_GATEWAY_TOOLS
    assert "generate_pptx_document" not in ALLOWED_GATEWAY_TOOLS
    assert "sandbox_office_lib" in ALLOWED_GATEWAY_TOOLS
    assert "generate_image" in ALLOWED_GATEWAY_TOOLS
    # parse-only fake exec retired with the office computer v2 (#959)
    assert "sandbox_workspace_exec" not in ALLOWED_GATEWAY_TOOLS
    assert "exec" not in ALLOWED_GATEWAY_TOOLS
    assert "run_python" not in ALLOWED_GATEWAY_TOOLS
