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
    clear_conversation_images,
    conversation_images,
    extract_images_from_content,
    hosted_user_content,
    last_user_images,
    merge_images,
    pi_rpc_images,
    png_bytes_to_image,
    remember_conversation_png,
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


def test_last_user_images_reads_librechat_sibling_image_urls() -> None:
    """LC AgentClient may keep pixels on message.image_urls while content is text."""
    msg = _Msg("user", "这是什么")
    msg.image_urls = [
        {
            "type": "image_url",
            "image_url": {"url": f"data:image/png;base64,{PNG_B64}"},
        }
    ]
    images = last_user_images([msg])
    assert len(images) == 1
    assert images[0]["data"] == PNG_B64
    assert pi_rpc_images(images)[0]["data"] == PNG_B64


def test_last_user_images_drops_relative_librechat_path() -> None:
    """`/images/user/file.png` is not fetched (SSRF / cross-container FS)."""
    parts = [
        {"type": "text", "text": "这是什么"},
        {"type": "image_url", "image_url": {"url": "/images/u1/shot.png"}},
    ]
    assert extract_images_from_content(parts) == []
    assert last_user_images([_Msg("user", parts)]) == []
    assert pi_rpc_images([{"type": "image_url", "url": "/images/u1/shot.png"}]) == []


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


def test_gpt55_keeps_model_when_images_attached() -> None:
    caps = apply_images_to_caps(
        RunCaps(backend_model="gpt-5.5"),
        [{"type": "image", "data": PNG_B64, "mimeType": "image/png"}],
    )
    assert caps.backend_model == "gpt-5.5"
    gpt = true_pi_models_document(
        provider="openai",
        model="gpt-5.5",
        max_context=128000,
        max_tokens=8000,
        base_url="https://superaichao.xin/openai",
        api="openai-responses",
    )
    assert gpt["providers"]["openai"]["models"][0]["input"] == ["text", "image"]


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


def test_png_bytes_and_merge_and_conversation_remember() -> None:
    raw = base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
    )
    item = png_bytes_to_image(raw)
    assert item and item["mimeType"] == "image/png"
    assert png_bytes_to_image(b"not-png") is None
    merged = merge_images(
        [{"type": "image", "data": "aaa", "mimeType": "image/png"}],
        [{"type": "image", "data": "aaa", "mimeType": "image/png"}, item],
    )
    assert len(merged) == 2
    clear_conversation_images()
    assert remember_conversation_png(raw, conversation_id="c-vis-1")
    assert not remember_conversation_png(raw, conversation_id="")
    pending = conversation_images("c-vis-1")
    assert pending and pending[0]["data"] == item["data"]
    assert conversation_images("other") == []
    clear_conversation_images("c-vis-1")
    assert conversation_images("c-vis-1") == []


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
