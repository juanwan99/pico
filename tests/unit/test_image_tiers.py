"""generate_image tiers: one verb, 档 is a parameter. No second image kernel."""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "orchestrator"))

from pico_orchestrator.gateway import ToolError
from pico_orchestrator.image_generate import (
    CHEAP_MODEL,
    HIGH_MODEL,
    NO_TEXT_SUFFIX,
    TIER_MESSAGE,
    generate_image_bytes,
    image_model_for,
    normalize_image_tier,
)
from pico_orchestrator.user_errors import user_message_for_error

ONE_PNG = (
    b"\x89PNG\r\n\x1a\n"
    b"\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde"
    b"\x00\x00\x00\x0cIDATx\x9cc``\x00\x00\x00\x04\x00\x01\xa3\x0a\x0d\xe4"
    b"\x00\x00\x00\x00IEND\xaeB`\x82"
)


def test_tier_aliases_and_unknown_fail_closed() -> None:
    assert normalize_image_tier(None) == "cheap"
    assert normalize_image_tier("") == "cheap"
    assert normalize_image_tier("fast") == "cheap"
    assert normalize_image_tier("quality") == "high"
    with pytest.raises(ToolError) as caught:
        normalize_image_tier("flux")
    assert caught.value.code == "image.unsupported_tier"
    assert caught.value.message == TIER_MESSAGE
    assert "密钥" not in user_message_for_error(TIER_MESSAGE, code="image.unsupported_tier")


def test_models_are_env_pins_not_a_kernel() -> None:
    assert image_model_for("cheap") == CHEAP_MODEL
    assert image_model_for("high") == HIGH_MODEL
    assert CHEAP_MODEL.startswith("black-forest-labs/")
    assert HIGH_MODEL.startswith("Kwai-Kolors/")


@pytest.mark.asyncio
async def test_cheap_default_is_unlettered_schnell(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SILICONFLOW_API_KEY", "test-key-not-a-secret")
    captured: dict = {}

    async def fake_post(payload, *, api_key, timeout):
        captured.update(payload)
        import base64

        return SimpleNamespace(
            status_code=200,
            json=lambda: {
                "images": [{"b64_json": base64.b64encode(ONE_PNG).decode("ascii")}]
            },
        )

    monkeypatch.setattr("pico_orchestrator.image_generate._post_images", fake_post)
    raw, ext, meta = await generate_image_bytes("豌豆花解剖示意图")
    assert ext == "png"
    assert raw.startswith(b"\x89PNG")
    assert meta["tier"] == "cheap"
    assert meta["unlettered"] is True
    assert captured["model"] == CHEAP_MODEL
    assert NO_TEXT_SUFFIX.strip() in captured["prompt"]
    assert "num_inference_steps" not in captured


@pytest.mark.asyncio
async def test_high_keeps_kolors_and_does_not_force_no_text(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SILICONFLOW_API_KEY", "test-key-not-a-secret")
    captured: dict = {}

    async def fake_post(payload, *, api_key, timeout):
        captured.update(payload)
        import base64

        return SimpleNamespace(
            status_code=200,
            json=lambda: {
                "images": [{"b64_json": base64.b64encode(ONE_PNG).decode("ascii")}]
            },
        )

    monkeypatch.setattr("pico_orchestrator.image_generate._post_images", fake_post)
    _raw, _ext, meta = await generate_image_bytes("一朵豌豆花", tier="high")
    assert meta["tier"] == "high"
    assert captured["model"] == HIGH_MODEL
    assert captured["num_inference_steps"] == 20
    assert NO_TEXT_SUFFIX not in captured["prompt"]
