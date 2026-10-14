"""Hedged first-token race (pico#1257): a slow model call gets company, not a 60 s wait."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

import httpx
import pytest
from pico_orchestrator.hedge import hedge_delays, race_first
from pico_orchestrator.provider import stream_chat


def test_delays_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("PICO_HEDGE_FAST_S", raising=False)
    assert hedge_delays(deep=False) == [1.5, 4.0, 8.0]
    assert hedge_delays(deep=True)[0] >= 20
    monkeypatch.setenv("PICO_HEDGE_FAST_S", "off")
    assert hedge_delays(deep=False) == []
    monkeypatch.setenv("PICO_HEDGE_FAST_S", "4, 2,x")
    assert hedge_delays(deep=False) == [2.0, 4.0]


async def _never_discard(_x) -> None:
    raise AssertionError("nothing to discard")


@pytest.mark.asyncio
async def test_slow_attempt_gets_company_and_is_cancelled() -> None:
    cancelled: list[int] = []

    async def attempt(k: int, wait: float) -> str:
        try:
            await asyncio.sleep(wait)
        except asyncio.CancelledError:
            cancelled.append(k)
            raise
        return f"a{k}"

    waits = [5.0, 0.01, 5.0]
    out = await race_first(
        lambda k: attempt(k, waits[k]) if k < len(waits) else None,
        [0.02, 0.5],
        relaunch=lambda _e: True,
        discard=_never_discard,
    )
    assert out == ("a1", 1)
    assert cancelled == [0]  # attempt 2 was never needed


@pytest.mark.asyncio
async def test_failure_is_replaced_at_once_and_bad_request_stops() -> None:
    started: list[int] = []

    async def attempt(k: int) -> str:
        started.append(k)
        if k == 0:
            raise RuntimeError("upstream 502")
        return "ok"

    t0 = asyncio.get_running_loop().time()
    out = await race_first(attempt, [30.0], relaunch=lambda _e: True, discard=_never_discard)
    assert out == ("ok", 1) and asyncio.get_running_loop().time() - t0 < 1

    async def bad(_k: int) -> str:
        raise ValueError("400 bad request")

    with pytest.raises(ValueError):
        await race_first(bad, [30.0], relaunch=lambda _e: False, discard=_never_discard)


@pytest.mark.asyncio
async def test_all_fail_raises_last() -> None:
    async def attempt(k: int) -> str:
        raise RuntimeError(f"down {k}")

    with pytest.raises(RuntimeError, match="down 2"):
        await race_first(
            lambda k: attempt(k) if k < 3 else None, [], relaunch=lambda _e: True, discard=_never_discard
        )


# --- direct path (sidebar chat, steward suggest) ----------------------------


def _env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test")
    monkeypatch.setenv("DEEPSEEK_MODEL", "gpt-5.6-sol")
    monkeypatch.setenv("DEEPSEEK_BASE_URL", "http://127.0.0.1:3000/v1")
    monkeypatch.setenv("PICO_MODEL_PROVIDER", "deepseek")
    monkeypatch.setenv("PICO_BRAIN_FALLBACKS", "gemini-3.8-flash")
    monkeypatch.setenv("PICO_HEDGE_FAST_S", "0.05,0.1")
    monkeypatch.delenv("KIMI_API_KEY", raising=False)


class _Chunks:
    def __init__(self, items: list, wait: float = 0.0) -> None:
        self._items = items
        self._wait = wait

    def __aiter__(self) -> _Chunks:
        return self

    async def __anext__(self):
        if self._wait:
            await asyncio.sleep(self._wait)
            self._wait = 0.0
        if self._items:
            return self._items.pop(0)
        raise StopAsyncIteration


@pytest.mark.asyncio
async def test_slow_primary_raced_by_backup(monkeypatch: pytest.MonkeyPatch) -> None:
    _env(monkeypatch)
    calls: list[str] = []

    class _Responses:
        async def create(self, **kwargs):
            calls.append(kwargs["model"])
            await asyncio.sleep(5)  # the relay's 30 s tail
            raise AssertionError("slow primary should have been cancelled")

    class _Completions:
        async def create(self, **kwargs):
            calls.append(kwargs["model"])
            choice = SimpleNamespace(delta=SimpleNamespace(content="好"), finish_reason="stop")
            return _Chunks([SimpleNamespace(usage=None, choices=[choice])])

    class _Client:
        def __init__(self, **_kw) -> None:
            self.responses = _Responses()
            self.chat = SimpleNamespace(completions=_Completions())

    monkeypatch.setattr("pico_orchestrator.provider.AsyncOpenAI", _Client)
    finish: dict = {}
    t0 = asyncio.get_running_loop().time()
    out = [p async for p in stream_chat("hi", model="pico-fast", thinking=False, finish_out=finish)]
    assert out == ["好"]
    assert asyncio.get_running_loop().time() - t0 < 1
    assert calls == ["gpt-5.6-sol", "gemini-3.8-flash"]
    assert finish["model"] == "gemini-3.8-flash"


# --- Pi box path: ws-proxy ---------------------------------------------------


@pytest.mark.asyncio
async def test_proxy_races_identical_call(monkeypatch: pytest.MonkeyPatch) -> None:
    from app import ws_proxy_router as mod

    hits: list[bytes] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        hits.append(request.content)
        if len(hits) == 1:
            await asyncio.sleep(5)  # first copy stuck in the relay queue
        return httpx.Response(200, content=b"data: tok\n\n", headers={"content-type": "text/event-stream"})

    real = httpx.AsyncClient
    monkeypatch.setattr(
        mod.httpx, "AsyncClient", lambda **kw: real(transport=httpx.MockTransport(handler), **kw)
    )
    done: list[bool] = []
    body = b'{"model":"gpt-5.6-sol","stream":true}'
    resp = await mod._stream(
        "POST", "http://up/v1/responses", {}, body, on_done=lambda: done.append(True), hedge=[0.05]
    )
    chunks = [c async for c in resp.body_iterator]
    assert b"".join(chunks) == b"data: tok\n\n"
    assert hits == [body, body] and done == [True]


def test_proxy_hedge_schedule(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.ws_proxy_router import model_hedge

    monkeypatch.delenv("PICO_HEDGE_FAST_S", raising=False)
    monkeypatch.delenv("PICO_HEDGE_DEEP_S", raising=False)
    assert model_hedge(b'{"model":"m","stream":true}') == [1.5, 4.0, 8.0]
    deep = model_hedge(b'{"model":"m","stream":true,"reasoning":{"effort":"high"}}')
    assert deep and deep[0] >= 20
    assert model_hedge(b'{"model":"m"}') == []  # JSON reply: no first token to wait on
