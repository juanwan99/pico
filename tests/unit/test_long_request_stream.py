"""Long GPT Responses calls must stay streamed; idle SSE must not die."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "orchestrator"))

from pico_orchestrator.provider import (
    _responses_completed_text,
    _responses_input_from_messages,
    _responses_text_delta,
    stream_chat,
)
from pico_orchestrator.sse_keepalive import (
    SSE_COMMENT_KEEPALIVE,
    SSE_STREAM_HEADERS,
    is_proxy_first_byte_timeout,
    iter_with_idle_ticks,
)
from pico_orchestrator.true_pi.runtime import should_trip_true_pi_idle_breaker
from pico_orchestrator.user_errors import user_message_for_error


def test_sse_keepalive_is_comment_not_bubble() -> None:
    assert SSE_COMMENT_KEEPALIVE.startswith(b": ")
    assert b"data:" not in SSE_COMMENT_KEEPALIVE
    assert SSE_STREAM_HEADERS["X-Accel-Buffering"] == "no"


def test_524_is_first_byte_timeout() -> None:
    class _E(Exception):
        status_code = 524

    assert is_proxy_first_byte_timeout(_E("x"))
    assert is_proxy_first_byte_timeout(
        RuntimeError("AIProxy service is temporarily unavailable")
    )
    assert not is_proxy_first_byte_timeout(RuntimeError("429 rate limit"))


def test_524_user_copy_is_honest() -> None:
    msg = user_message_for_error("HTTP 524: AIProxy service is temporarily unavailable")
    assert "首包" in msg
    assert "流式" in msg
    assert "temporarily unavailable" not in msg.lower()


def test_openai_thinking_does_not_trip_180s_empty_loop() -> None:
    assert not should_trip_true_pi_idle_breaker(
        thinking_on=True,
        openai_responses_brain=True,
        tool_oks=0,
        tool_gap=600,
        progress_gap=600,
        breaker_seconds=180,
    )
    assert should_trip_true_pi_idle_breaker(
        thinking_on=True,
        openai_responses_brain=False,
        tool_oks=0,
        tool_gap=180,
        progress_gap=180,
        breaker_seconds=180,
    )
    assert not should_trip_true_pi_idle_breaker(
        thinking_on=False,
        openai_responses_brain=False,
        tool_oks=0,
        tool_gap=180,
        progress_gap=180,
        breaker_seconds=180,
    )


def test_responses_message_split() -> None:
    instructions, items = _responses_input_from_messages(
        [
            {"role": "system", "content": "you are pico"},
            {"role": "user", "content": "hello"},
        ]
    )
    assert instructions == "you are pico"
    assert items == [{"role": "user", "content": "hello"}]


def test_responses_delta_and_completed() -> None:
    assert _responses_text_delta({"type": "response.output_text.delta", "delta": "Hi"}) == "Hi"
    full = _responses_completed_text(
        {
            "type": "response.completed",
            "response": {
                "output": [
                    {"content": [{"type": "output_text", "text": "<!DOCTYPE html>"}]}
                ]
            },
        }
    )
    assert "<!DOCTYPE html>" in full


@pytest.mark.asyncio
async def test_idle_ticks_do_not_cancel_inner_stream() -> None:
    async def slow():
        await asyncio.sleep(0.25)
        yield "ok"

    seen: list[object] = []
    async for item in iter_with_idle_ticks(slow(), poll_s=0.05, idle_s=0.12):
        seen.append(item)
    assert None in seen
    assert "ok" in seen


@pytest.mark.asyncio
async def test_stream_chat_gpt_uses_responses_not_completions(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test")
    monkeypatch.setenv("DEEPSEEK_MODEL", "gpt-5.6-sol")
    monkeypatch.setenv("DEEPSEEK_BASE_URL", "https://superaichao.xin/openai")
    monkeypatch.setenv("PICO_MODEL_PROVIDER", "deepseek")
    monkeypatch.delenv("KIMI_API_KEY", raising=False)

    captured: dict[str, object] = {}

    class _Stream:
        def __init__(self, events: list[dict]) -> None:
            self._events = events

        def __aiter__(self) -> _Stream:
            return self

        async def __anext__(self) -> dict:
            if not self._events:
                raise StopAsyncIteration
            return self._events.pop(0)

    class _Responses:
        async def create(self, **kwargs: object) -> _Stream:
            captured.update(kwargs)
            return _Stream(
                [{"type": "response.output_text.delta", "delta": "hello-gpt"}]
            )

    class _Client:
        def __init__(self, **kwargs: object) -> None:
            captured["client"] = kwargs
            self.responses = _Responses()
            self.chat = SimpleNamespace(
                completions=SimpleNamespace(
                    create=lambda **_k: (_ for _ in ()).throw(
                        AssertionError("chat.completions must not be used for GPT")
                    )
                )
            )

    monkeypatch.setattr("pico_orchestrator.provider.AsyncOpenAI", _Client)
    chunks = [piece async for piece in stream_chat("hi", max_tokens=32)]
    assert chunks == ["hello-gpt"]
    assert captured.get("stream") is True
    assert captured.get("store") is False
    assert captured.get("model") == "gpt-5.6-sol"


@pytest.mark.asyncio
async def test_stream_chat_retries_524_once(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test")
    monkeypatch.setenv("DEEPSEEK_MODEL", "gpt-5.6-sol")
    monkeypatch.setenv("DEEPSEEK_BASE_URL", "https://superaichao.xin/openai")
    monkeypatch.setenv("PICO_MODEL_PROVIDER", "deepseek")
    monkeypatch.delenv("KIMI_API_KEY", raising=False)

    calls = {"n": 0}

    class _GoodStream:
        def __init__(self) -> None:
            self._once = True

        def __aiter__(self) -> _GoodStream:
            return self

        async def __anext__(self) -> dict:
            if self._once:
                self._once = False
                return {"type": "response.output_text.delta", "delta": "ok"}
            raise StopAsyncIteration

    class _Responses:
        async def create(self, **_kwargs: object) -> object:
            calls["n"] += 1
            if calls["n"] == 1:
                err = RuntimeError("AIProxy service is temporarily unavailable")
                err.status_code = 524  # type: ignore[attr-defined]
                raise err
            return _GoodStream()

    class _Client:
        def __init__(self, **_kwargs: object) -> None:
            self.responses = _Responses()

    monkeypatch.setattr("pico_orchestrator.provider.AsyncOpenAI", _Client)
    chunks = [piece async for piece in stream_chat("hi")]
    assert chunks == ["ok"]
    assert calls["n"] == 2
