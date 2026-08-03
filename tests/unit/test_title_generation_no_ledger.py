"""LibreChat auto-title short-circuit: high precision, no durable Task/Run.

Stage #260 REVISE: must not swallow real user title-writing tasks.
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import AsyncMock

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "api"))
sys.path.insert(0, str(ROOT / "services" / "orchestrator"))

from app.main import app
from app.openai_compat import (
    ChatMessage,
    _is_title_generation_request,
    _synthetic_title_from_messages,
)
from app.settings import Settings, get_settings

# Exact LibreChat / agents scaffold shapes (must short-circuit).
AUTO_TITLE_PROMPTS = [
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

# Real teacher tasks that mention "title" / 「标题」 — must go through ledger/agent.
REAL_USER_TITLE_TASKS = [
    "请帮我生成一个短标题，主题是期末考试复习计划",
    "写一个短标题，用于班级周报首页",
    "generate a short title for my class newsletter about spring sports day",
    "write a short title for this essay about photosynthesis",
    "请生成简洁的课程标题：三年级数学分数入门",
    "用计算器算 1+1，并把结果写入 notes.txt",
]


def test_detector_matches_only_librechat_scaffolds() -> None:
    for prompt in AUTO_TITLE_PROMPTS:
        assert _is_title_generation_request(
            prompt, [ChatMessage(role="user", content=prompt)]
        ), prompt[:80]


def test_detector_does_not_swallow_real_user_title_tasks() -> None:
    for prompt in REAL_USER_TITLE_TASKS:
        assert not _is_title_generation_request(
            prompt, [ChatMessage(role="user", content=prompt)]
        ), prompt


def test_synthetic_title_prefers_user_turn() -> None:
    title = _synthetic_title_from_messages(
        [ChatMessage(role="user", content=AUTO_TITLE_PROMPTS[0])],
        AUTO_TITLE_PROMPTS[0],
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


def test_auto_title_does_not_touch_ledger(monkeypatch) -> None:
    ledger = AsyncMock(side_effect=AssertionError("ledger must not be called for auto-title"))
    monkeypatch.setattr("app.openai_compat._ledger_task_run", ledger)
    monkeypatch.setattr("app.openai_compat._run_and_collect", ledger)

    client = _client()
    try:
        for prompt in AUTO_TITLE_PROMPTS:
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


def test_auto_title_stream_skips_ledger(monkeypatch) -> None:
    ledger = AsyncMock(side_effect=AssertionError("ledger must not be called for auto-title"))
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
                "messages": [{"role": "user", "content": AUTO_TITLE_PROMPTS[1]}],
                "stream": True,
            },
        )
        assert r.status_code == 200, r.text
        assert "data:" in r.text
        assert ledger.await_count == 0
    finally:
        app.dependency_overrides.pop(get_settings, None)


def test_real_user_title_task_enters_ledger_path(monkeypatch) -> None:
    """Reverse: real user title-writing tasks must not be short-circuited."""
    calls: list[dict] = []

    async def fake_ledger(**kwargs):  # type: ignore[no-untyped-def]
        calls.append(kwargs)
        return "task-real-1", "run-real-1"

    async def fake_run_and_collect(*_a, **_k):  # type: ignore[no-untyped-def]
        class R:
            status = "succeeded"
            final_text = "建议标题：期末复习周计划"
            error = None

        return R()

    async def fake_finalize(*_a, **_k):  # type: ignore[no-untyped-def]
        return None

    monkeypatch.setattr("app.openai_compat._ledger_task_run", fake_ledger)
    monkeypatch.setattr("app.openai_compat._run_and_collect", fake_run_and_collect)
    monkeypatch.setattr("app.openai_compat._finalize_run", fake_finalize)

    client = _client()
    try:
        prompt = "请帮我生成一个短标题，主题是期末考试复习计划"
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
        assert len(calls) == 1, f"expected exactly one Task/Run, got {len(calls)}"
        body = r.json()
        assert "建议标题" in body["choices"][0]["message"]["content"] or body["choices"][0][
            "message"
        ]["content"]
    finally:
        app.dependency_overrides.pop(get_settings, None)
