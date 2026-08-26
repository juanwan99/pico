"""T-PPT-IMAGE-IN-DECK: ceiling stays thin adapter, no host bash."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "orchestrator"))

from pico_orchestrator.true_pi.config import ALLOWED_GATEWAY_TOOLS


def test_image_in_deck_does_not_add_host_bash() -> None:
    assert "bash" not in ALLOWED_GATEWAY_TOOLS
    assert "generate_pptx_document" in ALLOWED_GATEWAY_TOOLS
