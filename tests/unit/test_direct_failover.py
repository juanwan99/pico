"""Direct path (exam grading, sidebar chat) falls to the next model on a dead relay (#1248)."""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from pico_orchestrator.brain_ha import is_failover_error, should_failover
from pico_orchestrator.provider import stream_chat

AIPROXY_400 = (
    "Error code: 400 - {'error': {'message': 'AIProxy request failed. Please try again "
    "later.', 'type': 'aiproxy_api_error', 'code': 'aiproxy_api_error'}}"
)
BAD_REQUEST = "Error code: 400 - {'error': {'type': 'invalid_request_error'}}"


def _err(text: str) -> Exception:
    exc = RuntimeError(text)
    exc.status_code = 400  # type: ignore[attr-defined]
    return exc


def test_relay_400_fails_over() -> None:
    assert is_failover_error(AIPROXY_400)
    assert should_failover(SimpleNamespace(status="failed", error=AIPROXY_400, code=""))
    # A bad request moves one hop only; the backup rejecting it too is the answer.
    assert is_failover_error(BAD_REQUEST, first=True)
    assert not is_failover_error(BAD_REQUEST)
    assert not is_failover_error("Error code: 401 - invalid api key")


def _setup(monkeypatch: pytest.MonkeyPatch, fallbacks: str) -> None:
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test")
    monkeypatch.setenv("DEEPSEEK_MODEL", "gpt-5.6-sol")
    monkeypatch.setenv("DEEPSEEK_BASE_URL", "http://127.0.0.1:3000/v1")
    monkeypatch.setenv("PICO_MODEL_PROVIDER", "deepseek")
    monkeypatch.setenv("PICO_BRAIN_FALLBACKS", fallbacks)
    monkeypatch.delenv("KIMI_API_KEY", raising=False)


class _Stream:
    def __init__(self, items: list) -> None:
        self._items = items

    def __aiter__(self) -> _Stream:
        return self

    async def __anext__(self):
        if self._items:
            return self._items.pop(0)
        raise StopAsyncIteration


def _client(calls: list, *, responses_error: str, chat_error: str | None = None):
    class _Responses:
        async def create(self, **kwargs):
            calls.append(("responses", kwargs))
            raise _err(responses_error)

    class _Completions:
        async def create(self, **kwargs):
            calls.append(("chat", kwargs))
            if chat_error:
                raise _err(chat_error)
            choice = SimpleNamespace(delta=SimpleNamespace(content="ok"), finish_reason="stop")
            return _Stream([SimpleNamespace(usage=None, choices=[choice])])

    class _Client:
        def __init__(self, **_kwargs) -> None:
            self.responses = _Responses()
            self.chat = SimpleNamespace(completions=_Completions())

    return _Client


@pytest.mark.asyncio
async def test_image_call_falls_to_gemini(monkeypatch: pytest.MonkeyPatch) -> None:
    # deepseek-chat cannot read the image, so it is skipped, not tried.
    _setup(monkeypatch, "deepseek-chat,gemini-3.8-flash")
    calls: list = []
    monkeypatch.setattr(
        "pico_orchestrator.provider.AsyncOpenAI", _client(calls, responses_error=AIPROXY_400)
    )
    finish: dict = {}
    image = {"url": "data:image/png;base64,iVBORw0KGgo=", "mime": "image/png"}
    out = [
        piece
        async for piece in stream_chat(
            "批这道题", model="pico-fast", thinking=False, finish_out=finish, images=[image]
        )
    ]
    assert out == ["ok"]
    assert [kind for kind, _ in calls] == ["responses", "chat"]
    gemini = calls[1][1]
    assert gemini["model"] == "gemini-3.8-flash"
    assert "thinking" not in gemini["extra_body"]
    assert finish["model"] == "gemini-3.8-flash"


@pytest.mark.asyncio
async def test_bad_request_stops_after_one_backup(monkeypatch: pytest.MonkeyPatch) -> None:
    _setup(monkeypatch, "gemini-3.8-flash,grok-4.6")
    calls: list = []
    monkeypatch.setattr(
        "pico_orchestrator.provider.AsyncOpenAI",
        _client(calls, responses_error=BAD_REQUEST, chat_error=BAD_REQUEST),
    )
    with pytest.raises(RuntimeError):
        _ = [piece async for piece in stream_chat("hi", model="pico-fast", thinking=False)]
    assert [kwargs["model"] for _, kwargs in calls] == ["gpt-5.6-sol", "gemini-3.8-flash"]
