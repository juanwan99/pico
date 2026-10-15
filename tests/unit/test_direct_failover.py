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


def _err(text: str, status: int = 400) -> Exception:
    exc = RuntimeError(text)
    exc.status_code = status  # type: ignore[attr-defined]
    return exc


def test_relay_400_fails_over() -> None:
    assert is_failover_error(AIPROXY_400)
    assert should_failover(SimpleNamespace(status="failed", error=AIPROXY_400, code=""))
    # A bad request moves one hop only; the backup rejecting it too is the answer.
    assert is_failover_error(BAD_REQUEST, first=True)
    assert not is_failover_error(BAD_REQUEST)


SUSPENDED_403 = (
    "Error code: 403 - {'error': {'message': 'API密钥已被暂停，请联系管理员', "
    "'type': 'permission_error', 'param': '', 'code': ''}}"
)


def test_dead_key_fails_over_from_any_hop() -> None:
    # 10-15 00:00: sol's upstream key suspended; flash on another channel was fine.
    from pico_orchestrator.brain_ha import is_model_dead

    for text in (
        SUSPENDED_403,
        'OpenAI API error (403): {"message":"API密钥已被暂停，请联系管理员","type":"permission_error"}',
        "Error code: 401 - invalid api key",
        "Error code: 429 - You exceeded your current quota (insufficient_quota)",
        "Error code: 402 - 余额不足",
    ):
        assert is_failover_error(text), text
        assert is_model_dead(text), text
    assert not is_model_dead("Error code: 429 - rate limit, slow down")
    assert not is_model_dead("timeout after 4030 ms")
    # Our own run proxy answers a bare 403 (proxy.no_run): not the model's key.
    assert not is_model_dead("OpenAI API error (403): 403 status code (no body)")
    assert not is_model_dead('{"ok": false, "code": "proxy.no_run"}')


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


def _client(calls: list, *, responses_error: str, chat_error: str | None = None, status=400):
    class _Responses:
        async def create(self, **kwargs):
            calls.append(("responses", kwargs))
            raise _err(responses_error, status)

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


@pytest.mark.asyncio
async def test_dead_channel_skips_overload_wait(monkeypatch: pytest.MonkeyPatch) -> None:
    """New API answers 503 when a model has no channel; that is not load to wait out."""
    _setup(monkeypatch, "gemini-3.8-flash")
    slept: list[float] = []

    async def _sleep(seconds: float) -> None:
        slept.append(seconds)

    monkeypatch.setattr("pico_orchestrator.provider.asyncio.sleep", _sleep)
    calls: list = []
    dead = "Error code: 503 - No available channel for model gpt-5.6-sol under group default"
    monkeypatch.setattr(
        "pico_orchestrator.provider.AsyncOpenAI",
        _client(calls, responses_error=dead, status=503),
    )
    out = [p async for p in stream_chat("hi", model="pico-fast", thinking=False)]
    assert out == ["ok"]
    assert slept == []
    assert [kind for kind, _ in calls] == ["responses", "chat"]


@pytest.mark.asyncio
async def test_suspended_key_falls_to_backup_at_once_and_stays_down(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A 403 from the primary's key answers in 0.3 s: the race must not end there."""
    _setup(monkeypatch, "gemini-3.8-flash")
    slept: list[float] = []

    async def _sleep(seconds: float) -> None:
        slept.append(seconds)

    monkeypatch.setattr("pico_orchestrator.provider.asyncio.sleep", _sleep)
    calls: list = []
    monkeypatch.setattr(
        "pico_orchestrator.provider.AsyncOpenAI",
        _client(calls, responses_error=SUSPENDED_403, status=403),
    )
    finish: dict = {}
    out = [p async for p in stream_chat("hi", model="pico-fast", thinking=False, finish_out=finish)]
    assert out == ["ok"]
    assert slept == []
    assert [kind for kind, _ in calls] == ["responses", "chat"]
    assert finish["model"] == "gemini-3.8-flash"
    # The next call goes straight to the backup instead of hitting the dead key.
    calls.clear()
    out = [p async for p in stream_chat("hi", model="pico-fast", thinking=False)]
    assert out == ["ok"]
    assert [kwargs["model"] for _, kwargs in calls] == ["gemini-3.8-flash"]


@pytest.mark.asyncio
async def test_unknown_primary_error_gets_one_backup(monkeypatch: pytest.MonkeyPatch) -> None:
    # 10-14 16:45 a 识字 call died on "Request could not be completed" with flash idle.

    _setup(monkeypatch, "gemini-3.8-flash")
    calls: list = []
    monkeypatch.setattr(
        "pico_orchestrator.provider.AsyncOpenAI",
        _client(calls, responses_error="Request could not be completed", status=500),
    )
    out = [p async for p in stream_chat("hi", model="pico-fast", thinking=False)]
    assert out == ["ok"]
    assert calls[-1][1]["model"] == "gemini-3.8-flash"
