"""T-UNMASK-PI: actual /v1/chat/completions path, not just vision.py units.

LibreChat AgentClient → OpenAI reverse proxy posts the user turn as either
``content: [{type:text}, {type:image_url, data-URL}]`` or a text content plus
sibling ``image_urls``. Both must reach ``_run_and_collect(..., images=)``.
"""

from __future__ import annotations

import base64
import sys
from pathlib import Path

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "api"))
sys.path.insert(0, str(ROOT / "services" / "orchestrator"))

from app.main import app
from app.openai_compat import ChatCompletionRequest, ChatMessage
from app.settings import Settings, get_settings
from pico_orchestrator.vision import last_user_images, pi_rpc_images

# Real 1×1 PNG pixels (not random bytes).
PNG_B64 = (
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
)
assert base64.b64decode(PNG_B64)[:8] == b"\x89PNG\r\n\x1a\n"


def _client() -> TestClient:
    settings = Settings(
        _env_file=None,
        pico_env="test",
        pico_openai_proxy_key="pico-dev",
        pico_allowed_models="pico-fast,pico-deep,pico-agent",
        pico_accept_test_issuer=True,
    )
    app.dependency_overrides[get_settings] = lambda: settings
    return TestClient(app)


def _lc_content_payload() -> dict:
    return {
        "model": "pico-fast",
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "这是什么"},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/png;base64,{PNG_B64}"},
                    },
                ],
            }
        ],
        "stream": False,
    }


def _lc_sibling_payload() -> dict:
    return {
        "model": "pico-fast",
        "messages": [
            {
                "role": "user",
                "content": "这是什么",
                "image_urls": [
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/png;base64,{PNG_B64}"},
                    }
                ],
            }
        ],
        "stream": False,
    }


def test_request_model_keeps_librechat_content_and_sibling() -> None:
    body = ChatCompletionRequest.model_validate(_lc_content_payload())
    images = last_user_images(body.messages)
    assert images and images[0]["data"] == PNG_B64
    assert pi_rpc_images(images)[0]["mimeType"] == "image/png"

    sibling = ChatCompletionRequest.model_validate(_lc_sibling_payload())
    assert sibling.messages[0].image_urls
    images = last_user_images(sibling.messages)
    assert images and images[0]["data"] == PNG_B64


def test_http_content_data_url_reaches_run_caps(monkeypatch) -> None:
    captured: list[dict] = []

    async def fake_ledger(**kwargs):  # type: ignore[no-untyped-def]
        del kwargs
        return "task-vision-1", "run-vision-1"

    async def fake_run_and_collect(*_a, **kwargs):  # type: ignore[no-untyped-def]
        captured.append(kwargs)
        class R:
            status = "succeeded"
            final_text = "红点"
            error = None

        return R()

    async def fake_finalize(*_a, **_k):  # type: ignore[no-untyped-def]
        return None

    monkeypatch.setattr("app.openai_compat._ledger_task_run", fake_ledger)
    monkeypatch.setattr("app.openai_compat._run_and_collect", fake_run_and_collect)
    monkeypatch.setattr("app.openai_compat._finalize_run", fake_finalize)

    client = _client()
    try:
        r = client.post(
            "/v1/chat/completions",
            headers={
                "Authorization": "Bearer pico-dev",
                "X-Pico-Membership-Id": "test-member",
            },
            json=_lc_content_payload(),
        )
        assert r.status_code == 200, r.text
        assert captured, "run path was not entered"
        images = captured[0].get("images") or []
        assert images, "LibreChat content[] image_url never reached the run"
        assert images[0]["data"] == PNG_B64
        assert "红点" in r.json()["choices"][0]["message"]["content"]
    finally:
        app.dependency_overrides.pop(get_settings, None)


def test_http_sibling_image_urls_reach_run_caps(monkeypatch) -> None:
    captured: list[dict] = []

    async def fake_ledger(**kwargs):  # type: ignore[no-untyped-def]
        del kwargs
        return "task-vision-2", "run-vision-2"

    async def fake_run_and_collect(*_a, **kwargs):  # type: ignore[no-untyped-def]
        captured.append(kwargs)
        class R:
            status = "succeeded"
            final_text = "看见了"
            error = None

        return R()

    async def fake_finalize(*_a, **_k):  # type: ignore[no-untyped-def]
        return None

    monkeypatch.setattr("app.openai_compat._ledger_task_run", fake_ledger)
    monkeypatch.setattr("app.openai_compat._run_and_collect", fake_run_and_collect)
    monkeypatch.setattr("app.openai_compat._finalize_run", fake_finalize)

    client = _client()
    try:
        r = client.post(
            "/v1/chat/completions",
            headers={
                "Authorization": "Bearer pico-dev",
                "X-Pico-Membership-Id": "test-member",
            },
            json=_lc_sibling_payload(),
        )
        assert r.status_code == 200, r.text
        images = (captured[0].get("images") or []) if captured else []
        assert images and images[0]["data"] == PNG_B64
    finally:
        app.dependency_overrides.pop(get_settings, None)


def test_http_relative_images_path_does_not_invent_pixels(monkeypatch) -> None:
    captured: list[dict] = []

    async def fake_ledger(**kwargs):  # type: ignore[no-untyped-def]
        del kwargs
        return "task-vision-3", "run-vision-3"

    async def fake_run_and_collect(*_a, **kwargs):  # type: ignore[no-untyped-def]
        captured.append(kwargs)
        class R:
            status = "succeeded"
            final_text = "没有图"
            error = None

        return R()

    async def fake_finalize(*_a, **_k):  # type: ignore[no-untyped-def]
        return None

    monkeypatch.setattr("app.openai_compat._ledger_task_run", fake_ledger)
    monkeypatch.setattr("app.openai_compat._run_and_collect", fake_run_and_collect)
    monkeypatch.setattr("app.openai_compat._finalize_run", fake_finalize)

    client = _client()
    try:
        r = client.post(
            "/v1/chat/completions",
            headers={
                "Authorization": "Bearer pico-dev",
                "X-Pico-Membership-Id": "test-member",
            },
            json={
                "model": "pico-fast",
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": "这是什么"},
                            {
                                "type": "image_url",
                                "image_url": {"url": "/images/u1/shot.png"},
                            },
                        ],
                    }
                ],
            },
        )
        assert r.status_code == 200, r.text
        images = (captured[0].get("images") or []) if captured else []
        assert images == []
    finally:
        app.dependency_overrides.pop(get_settings, None)


def test_chat_message_no_longer_drops_image_urls() -> None:
    msg = ChatMessage.model_validate(
        {
            "role": "user",
            "content": "这是什么",
            "image_urls": [
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:image/png;base64,{PNG_B64}"},
                }
            ],
        }
    )
    assert msg.image_urls
    assert last_user_images([msg])


def test_chat_message_keeps_native_file_parts() -> None:
    from app.openai_compat import _content_text, _last_user_prompt

    msg = ChatMessage.model_validate(
        {
            "role": "user",
            "content": [
                {"type": "text", "text": "这份是什么"},
                {
                    "type": "file",
                    "file": {
                        "filename": "地理答案.pdf",
                        "file_data": "data:application/pdf;base64,JVBERi0=",
                    },
                },
            ],
            "files": [{"filename": "补充说明.docx", "file_data": "AAA="}],
        }
    )
    assert msg.files
    assert "地理答案.pdf" in _content_text(msg.content)
    prompt = _last_user_prompt([msg])
    assert "地理答案.pdf" in prompt
    assert "补充说明.docx" in prompt
