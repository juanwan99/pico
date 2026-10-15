"""pico#1271 · the one door to the relay: request counts per teacher message.

Four cases the card names — in order, concurrent, 503, model switch — on both
roads out: the direct path (``provider.stream_chat``: sidebar chat, steward)
and the Pi run proxy (``ws_proxy_router``). Each asserts how many upstream
requests one message may cost.
"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

import httpx
import pytest
from pico_orchestrator import brain_ha, upstream
from pico_orchestrator.provider import stream_chat


async def _never_discard(_x) -> None:
    raise AssertionError("nothing to discard")


# --- schedule and race --------------------------------------------------------


def test_one_hedge_at_p95_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ("PICO_HEDGE_FAST_S", "PICO_HEDGE_MEDIUM_S", "PICO_HEDGE_DEEP_S"):
        monkeypatch.delenv(name, raising=False)
    assert upstream.hedge_after() == [25.0]
    assert upstream.hedge_after("medium") == [25.0]
    assert upstream.hedge_after("high") == [60.0]
    monkeypatch.setenv("PICO_HEDGE_FAST_S", "off")
    assert upstream.hedge_after() == []
    monkeypatch.setenv("PICO_HEDGE_FAST_S", "1.5,4,8")  # the old three-hedge list keeps one
    assert upstream.hedge_after() == [1.5]


@pytest.mark.asyncio
async def test_slow_attempt_gets_one_hedge_and_is_cancelled() -> None:
    cancelled: list[int] = []

    async def attempt(k: int) -> str:
        try:
            await asyncio.sleep(5.0 if k == 0 else 0.01)
        except asyncio.CancelledError:
            cancelled.append(k)
            raise
        return f"a{k}"

    call = upstream.Call("t")
    assert await upstream.race(
        attempt, call, hedge=[0.02], relaunch=lambda _e: True, discard=_never_discard
    ) == ("a1", 1)
    assert cancelled == [0] and call.sent == 2


@pytest.mark.asyncio
async def test_failure_replaced_at_once_bad_request_stops_budget_caps() -> None:
    started: list[int] = []

    async def flaky(k: int) -> str:
        started.append(k)
        if k == 0:
            raise RuntimeError("upstream 502")
        return "ok"

    t0 = asyncio.get_running_loop().time()
    out = await upstream.race(
        flaky, upstream.Call("t"), hedge=[30.0], relaunch=lambda _e: True, discard=_never_discard
    )
    assert out == ("ok", 1) and asyncio.get_running_loop().time() - t0 < 1

    async def bad(_k: int) -> str:
        raise ValueError("400 bad request")

    with pytest.raises(ValueError):
        await upstream.race(
            bad, upstream.Call("t"), relaunch=lambda _e: False, discard=_never_discard
        )

    tries: list[int] = []

    async def down(k: int) -> str:
        tries.append(k)
        raise RuntimeError(f"down {k}")

    with pytest.raises(RuntimeError, match="down 2"):
        await upstream.race(
            down, upstream.Call("t"), relaunch=lambda _e: True, discard=_never_discard
        )
    assert tries == [0, 1, 2]  # CALL_BUDGET, however willing relaunch is


def test_run_spare_pool_is_shared_by_every_call_of_the_run() -> None:
    sent = 0
    for _ in range(5):
        call = upstream.Call("pi_step", run_id="run-1")
        while call.allow():
            sent += 1
    # 5 firsts + the run's 6 spares, not 5 × 3.
    assert sent == 5 + upstream.RUN_SPARE
    assert upstream.stats()["calls"]["pi_step"]["budget_spent"] >= 1


# --- direct path ----------------------------------------------------------------


def _env(monkeypatch: pytest.MonkeyPatch, fallbacks: str = "gemini-3.8-flash") -> None:
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test")
    monkeypatch.setenv("DEEPSEEK_MODEL", "gemini-3.8-pro")
    monkeypatch.setenv("DEEPSEEK_BASE_URL", "http://127.0.0.1:3000/v1")
    monkeypatch.setenv("PICO_MODEL_PROVIDER", "deepseek")
    monkeypatch.setenv("PICO_BRAIN_FALLBACKS", fallbacks)
    monkeypatch.delenv("KIMI_API_KEY", raising=False)
    for name in ("PICO_HEDGE_FAST_S", "PICO_HEDGE_MEDIUM_S"):
        monkeypatch.delenv(name, raising=False)


class _Chunks:
    def __init__(self, text: str, wait: float = 0.0) -> None:
        self._items = [text]
        self._wait = wait

    def __aiter__(self) -> _Chunks:
        return self

    async def __anext__(self):
        if self._wait:
            await asyncio.sleep(self._wait)
            self._wait = 0.0
        if self._items:
            choice = SimpleNamespace(
                delta=SimpleNamespace(content=self._items.pop(0)), finish_reason="stop"
            )
            return SimpleNamespace(usage=None, choices=[choice])
        raise StopAsyncIteration


class _Status(Exception):
    def __init__(self, status: int, text: str) -> None:
        super().__init__(f"Error code: {status} - {text}")
        self.status_code = status


def _relay(monkeypatch: pytest.MonkeyPatch, answer) -> list[str]:
    """Fake New API: ``answer(model, n)`` returns a stream or raises. Returns the request log."""
    calls: list[str] = []

    class _Completions:
        async def create(self, **kwargs):
            calls.append(kwargs["model"])
            return answer(kwargs["model"], len(calls))

    monkeypatch.setattr(
        "pico_orchestrator.provider.AsyncOpenAI",
        lambda **_kw: SimpleNamespace(chat=SimpleNamespace(completions=_Completions())),
    )
    return calls


async def _ask(text: str = "hi") -> list[str]:
    return [p async for p in stream_chat(text, model="pico-fast", thinking=False)]


@pytest.mark.asyncio
async def test_direct_in_order_one_request_per_message(monkeypatch: pytest.MonkeyPatch) -> None:
    _env(monkeypatch)
    calls = _relay(monkeypatch, lambda _m, _n: _Chunks("好"))
    for _ in range(5):
        assert await _ask() == ["好"]
    assert len(calls) == 5
    assert upstream.stats()["calls"]["direct"] == {"sent": 5}


@pytest.mark.asyncio
async def test_direct_concurrent_messages_wait_for_a_key_slot(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _env(monkeypatch)
    monkeypatch.setenv("PICO_UPSTREAM_KEY_MAX", "2")
    calls = _relay(monkeypatch, lambda _m, _n: _Chunks("好", wait=0.05))
    outs = await asyncio.gather(*(_ask() for _ in range(6)))
    assert outs == [["好"]] * 6
    assert len(calls) == 6  # no hedge, no retry
    assert max(upstream.stats()["peak"].values()) == 2


@pytest.mark.asyncio
async def test_direct_503_costs_three_requests_then_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    _env(monkeypatch)

    def overloaded(_m, _n):
        raise _Status(503, "system cpu overloaded")

    calls = _relay(monkeypatch, overloaded)
    with pytest.raises(RuntimeError):
        await _ask()
    assert len(calls) == upstream.CALL_BUDGET == 3  # was 4 hedges × 7 overload tries


@pytest.mark.asyncio
async def test_direct_dead_key_switches_model_once(monkeypatch: pytest.MonkeyPatch) -> None:
    """A bare relay 403 (no 'suspended' words, #1263) still means: next model, and skip this one."""
    _env(monkeypatch)

    def answer(model, _n):
        if model == "gemini-3.8-pro":
            raise _Status(403, "{}")
        return _Chunks("备用")

    calls = _relay(monkeypatch, answer)
    assert await _ask() == ["备用"]
    assert calls == ["gemini-3.8-pro", "gemini-3.8-flash"]
    assert brain_ha.is_down("gemini-3.8-pro")
    assert await _ask() == ["备用"]
    assert calls[2:] == ["gemini-3.8-flash"]  # the dead one is not tried again


# --- Pi run proxy ---------------------------------------------------------------


def _upstream(monkeypatch: pytest.MonkeyPatch, handler) -> list[bytes]:
    from app import ws_proxy_router as mod

    hits: list[bytes] = []

    async def wrapped(request: httpx.Request) -> httpx.Response:
        hits.append(request.content)
        return await handler(request, len(hits))

    real = httpx.AsyncClient
    monkeypatch.setattr(
        mod.httpx, "AsyncClient", lambda **kw: real(transport=httpx.MockTransport(wrapped), **kw)
    )
    return hits


async def _proxy_step(run_id: str, body: bytes = b'{"model":"m"}', hedge=None):
    from app import ws_proxy_router as mod

    resp = await mod._stream(
        "POST",
        "http://relay/v1/chat/completions",
        {},
        body,
        hedge=hedge,
        call=upstream.Call("pi_step", run_id=run_id),
        key="sk-box",
        run_id=run_id,
    )
    if hasattr(resp, "body_iterator"):
        return resp.status_code, b"".join([c async for c in resp.body_iterator])
    return resp.status_code, resp.body


@pytest.mark.asyncio
async def test_proxy_in_order_and_slow_first_token(monkeypatch: pytest.MonkeyPatch) -> None:
    async def handler(_req, n):
        if n == 2:
            await asyncio.sleep(5)  # this copy is stuck in the relay queue
        return httpx.Response(
            200, content=b"data: tok\n\n", headers={"content-type": "text/event-stream"}
        )

    hits = _upstream(monkeypatch, handler)
    assert await _proxy_step("run-a") == (200, b"data: tok\n\n")
    assert len(hits) == 1
    stream = b'{"model":"m","stream":true}'
    assert await _proxy_step("run-a", stream, hedge=[0.05]) == (200, b"data: tok\n\n")
    assert len(hits) == 3  # one hedge for the stuck step, no more


@pytest.mark.asyncio
async def test_proxy_concurrent_steps_share_the_key_cap(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PICO_UPSTREAM_KEY_MAX", "3")

    async def handler(_req, _n):
        await asyncio.sleep(0.05)
        return httpx.Response(200, content=b"ok")

    hits = _upstream(monkeypatch, handler)
    outs = await asyncio.gather(*(_proxy_step(f"run-{i}") for i in range(8)))
    assert outs == [(200, b"ok")] * 8 and len(hits) == 8
    assert max(upstream.stats()["peak"].values()) == 3


@pytest.mark.asyncio
async def test_proxy_503_three_per_step_and_the_run_pool_runs_dry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def handler(_req, _n):
        return httpx.Response(503, content=b'{"error":{"message":"overloaded"}}')

    hits = _upstream(monkeypatch, handler)
    assert (await _proxy_step("run-503"))[0] == 503
    assert len(hits) == 3
    for _ in range(4):  # Pi resumes / next steps of the same run
        assert (await _proxy_step("run-503"))[0] == 503
    assert len(hits) == 5 + upstream.RUN_SPARE  # 11, not 15 — and Pi itself no longer retries 8×


@pytest.mark.asyncio
async def test_proxy_relay_403_is_noted_and_not_retried(monkeypatch: pytest.MonkeyPatch) -> None:
    async def handler(_req, _n):
        return httpx.Response(403, content=b"")  # bare relay 403, no words

    hits = _upstream(monkeypatch, handler)
    assert (await _proxy_step("run-403"))[0] == 403
    assert len(hits) == 1
    relay = upstream.upstream_error("run-403")
    assert relay.startswith("upstream 403")
    # Brain fail-over reads the note: next model. Our own proxy 403 has no note.
    failed = SimpleNamespace(
        status="failed", error="OpenAI API error (403): 403 status code (no body)", code=""
    )
    assert brain_ha.should_failover(failed, relay=relay)
    assert not brain_ha.should_failover(failed, relay=upstream.upstream_error("run-other"))
    assert not brain_ha.is_model_dead('{"ok": false, "code": "proxy.no_run"}')


def test_proxy_skips_hedge_when_the_run_switches_model_on_stall() -> None:
    from app.ws_proxy_router import model_hedge

    step = b'{"model":"m","stream":true}'
    assert model_hedge(step, "run-x") == [25.0]
    upstream.run_state("run-x").no_hedge = True
    assert model_hedge(step, "run-x") == []
    assert model_hedge(b'{"model":"m"}') == []  # JSON reply: no first token to wait on
