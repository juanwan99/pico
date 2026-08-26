"""T-VISION-SANDBOX: remembered pixels stay on one conversation."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "orchestrator"))

from pico_orchestrator.vision import (
    clear_conversation_images,
    conversation_images,
    remember_conversation_png,
)

ONE_PNG = (
    b"\x89PNG\r\n\x1a\n"
    b"\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde"
    b"\x00\x00\x00\x0cIDATx\x9cc``\x00\x00\x00\x04\x00\x01\xa3\x0a\x0d\xe4"
    b"\x00\x00\x00\x00IEND\xaeB`\x82"
)


def test_remembered_png_does_not_leak_across_conversations() -> None:
    clear_conversation_images()
    assert remember_conversation_png(ONE_PNG, conversation_id="convo-a")
    assert conversation_images("convo-a")
    assert conversation_images("convo-b") == []
    clear_conversation_images()
