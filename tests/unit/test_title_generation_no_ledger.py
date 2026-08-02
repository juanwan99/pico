"""Auto-title / auxiliary requests must not create durable Task/Run (stage #260 P0)."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import AsyncMock

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "api"))
sys.path.insert(0, str(ROOT / "services" / "orchestrator"))

from app.main import app  # noqa: E402
from app.openai_compat import (  # noqa: E402
    ChatMessage,
    _is_title_generation_request,
    _synthetic_title_from_messages,
)
from app.settings import Settings, get_settings  # noqa: E402


TITLE_PROMPTS = [
    (
        "Analyze this conversation and provide:\n"
        "1. The detected language of the conversation\n"
        "2. A concise title in the detected language (5 words or less, no punctuation or quotation)\n\n"
        "User: 请创建 stage260-cancelled.txt 内容为 cancelled\n"
    ),
    (
        "Provide a concise, 5-word-or-less title for the conversation, "
        "using title case conventions. Only return the title itself.\n\n"
        "Conversation:\n请用计算器算 1+1\n"
    ),
    (
        "Please generate a concise title (max 40 characters) for a conversation that starts with:\n"
        "User: 写一个文件 hello.txt\n"
        "Assistant: 好的\n\n"
        "Title:"
    ),
]


def test_detector_matches_librechat_title_shapes() -> None:
    for prompt in TITLE_PROMPTS:
        assert _is_title_generation_request(prompt, [ChatMessage(role="user", content=prompt)])
    assert not _is_title_generation_request(
        "请用计算器计算 1+1，并把结果写入 notes.txt",
        [ChatMessage(role="user", content="请用计算器计算 1+1，并把结果写入 notes.txt")],
    )


def test_synthetic_title_prefers_user_turn() -> None:
    title = _synthetic_title_from_messages(
        [ChatMessage(role="user", content=TITLE_PROMPTS[0])],
        TITLE_PROMPTS[0],
    )
    assert title
    assert "stage260" in title or "创建" in title
    assert len(title) <= 40


def _client() -> TestClient:
    settings = Settings(
        _env_file=None,
        pico_env="test",
        pico_openai_proxy_key="pico-dev",
        pico_allowed_models="kimi-k2.6,pico-agent",
        pico_accept_test_issuer=True,
    )
    app.dependency_overrides[get_settings] = lambda: settings
    return TestClient(app)


def test_title_generation_does_not_touch_ledger(monkeypatch) -> None:
    ledger = AsyncMock(side_effect=AssertionError("ledger must not be called for title requests"))
    monkeypatch.setattr("app.openai_compat._ledger_task_run", ledger)
    monkeypatch.setattr("app.openai_compat._run_and_collect", ledger)

    client = _client()
    try:
        for prompt in TITLE_PROMPTS:
            r = client.post(
                "/v1/chat/completions",
                headers={
                    "Authorization": "Bearer pico-dev",
                    "X-Pico-Membership-Id": "test-member",
                },
                json={
                    "model": "pico-agent",
                    "messages": [{"role": "user", "content": prompt}],
                    "stream": False,
                },
            )
            assert r.status_code == 200, r.text
            content = r.json()["choices"][0]["message"]["content"]
            assert content
            assert "文件已创建" not in content
        assert ledger.await_count == 0
    finally:
        app.dependency_overrides.pop(get_settings, None)


def test_title_generation_stream_skips_ledger(monkeypatch) -> None:
    ledger = AsyncMock(side_effect=AssertionError("ledger must not be called for title requests"))
    monkeypatch.setattr("app.openai_compat._ledger_task_run", ledger)

    client = _client()
    try:
        r = client.post(
            "/v1/chat/completions",
            headers={
                "Authorization": "Bearer pico-dev",
                "X-Pico-Membership-Id": "test-member",
            },
            json={
                "model": "pico-agent",
                "messages": [{"role": "user", "content": TITLE_PROMPTS[1]}],
                "stream": True,
            },
        )
        assert r.status_code == 200, r.text
        assert "data:" in r.text
        assert ledger.await_count == 0
    finally:
        app.dependency_overrides.pop(get_settings, None)
