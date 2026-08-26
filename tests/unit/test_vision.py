"""T-UNMASK-PI: chat images stay visible; no self-built vision kernel."""

from __future__ import annotations

import base64
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "orchestrator"))

from pico_orchestrator.provider import DEFAULT_DEEPSEEK_VISION, is_deepseek_model
from pico_orchestrator.run_types import RunCaps
from pico_orchestrator.true_pi.client import (
    FakeTransport,
    TruePiRpcClient,
    true_pi_models_document,
)
from pico_orchestrator.vision import (
    apply_images_to_caps,
    extract_images_from_content,
    hosted_user_content,
    last_user_images,
    pi_rpc_images,
)


class _Msg:
    def __init__(self, role: str, content: object) -> None:
        self.role = role
        self.content = content


PNG_B64 = base64.b64encode(
    b"\x89PNG\r\n\x1a\n" + b"\x00" * 32
).decode("ascii")


def test_extracts_data_url_and_drops_text_only() -> None:
    parts = [
        {"type": "text", "text": "这是什么"},
        {
            "type": "image_url",
            "image_url": {"url": f"data:image/png;base64,{PNG_B64}"},
        },
    ]
    images = extract_images_from_content(parts)
    assert len(images) == 1
    assert images[0]["mimeType"] == "image/png"
    assert images[0]["data"] == PNG_B64
    rpc = pi_rpc_images(images)
    assert rpc[0]["type"] == "image"
    hosted = hosted_user_content("这是什么", images)
    assert isinstance(hosted, list)
    assert hosted[0]["type"] == "text"
    assert hosted[1]["type"] == "image_url"


def test_last_user_images_only_current_turn() -> None:
    prior = _Msg(
        "user",
        [
            {
                "type": "image_url",
                "image_url": {"url": f"data:image/png;base64,{PNG_B64}"},
            }
        ],
    )
    current = _Msg("user", "只问字")
    assert last_user_images([prior, current]) == []
    assert last_user_images([current, prior])


def test_apply_images_switches_to_vision_model() -> None:
    caps = apply_images_to_caps(
        RunCaps(backend_model="deepseek-v4-flash"),
        [{"type": "image", "data": PNG_B64, "mimeType": "image/png"}],
    )
    assert caps.backend_model == DEFAULT_DEEPSEEK_VISION
    assert caps.images
    assert is_deepseek_model(DEFAULT_DEEPSEEK_VISION)


def test_models_json_text_only_unless_vision() -> None:
    flash = true_pi_models_document(
        provider="deepseek",
        model="deepseek-v4-flash",
        max_context=128000,
        max_tokens=8000,
    )
    assert flash["providers"]["deepseek"]["models"][0]["input"] == ["text"]
    vision = true_pi_models_document(
        provider="deepseek",
        model=DEFAULT_DEEPSEEK_VISION,
        max_context=128000,
        max_tokens=8000,
    )
    assert vision["providers"]["deepseek"]["models"][0]["input"] == ["text", "image"]


@pytest.mark.asyncio
async def test_true_pi_prompt_forwards_images() -> None:
    transport = FakeTransport()
    await transport.start()
    client = TruePiRpcClient(transport)
    await client.prompt(
        "这是什么",
        images=[{"type": "image", "data": PNG_B64, "mimeType": "image/png"}],
    )
    sent = transport.sent[0]
    assert sent["type"] == "prompt"
    assert sent["message"] == "这是什么"
    assert sent["images"][0]["data"] == PNG_B64
    await transport.close()
