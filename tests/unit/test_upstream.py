"""pico#1271 · the one door to the relay: request counts per teacher message.

Four cases the card names — in order, concurrent, 503, model switch — on both
roads out: the direct path (``provider.stream_chat``: sidebar chat, steward)
and the Pi run proxy (``ws_proxy_router``). Each asserts how many upstream
requests one message may cost.
"""

from __future__ import annotations

import asyncio
import contextlib
from types import SimpleNamespace
from typing import Self

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
    # sol stands in for any Responses-wire model here; the AIProxy rule (#1344) has its own tests.
    monkeypatch.setenv("PICO_LONG_SESSION_MODELS", "")
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


class _Events(_Chunks):
    """Responses API stream: text arrives as output_text.delta events."""

    async def __anext__(self):
        if self._items:
            return SimpleNamespace(type="response.output_text.delta", delta=self._items.pop(0))
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


# --- review #1283: pauses, hang-ups, every road through the door -------------------


@pytest.mark.asyncio
async def test_retry_pauses_two_then_six_seconds_and_honours_retry_after(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(upstream, "RETRY_BACKOFF_S", (2.0, 6.0))
    slept: list[float] = []
    real_sleep = asyncio.sleep

    async def fake_sleep(s: float, *a):
        slept.append(s)
        await real_sleep(0)

    monkeypatch.setattr(upstream.asyncio, "sleep", fake_sleep)

    async def busy(k: int) -> str:
        raise _Status(503, "busy")

    with pytest.raises(_Status):
        await upstream.race(busy, upstream.Call("t"), relaunch=lambda _e: True, discard=_never_discard)
    assert slept == [2.0, 6.0]  # three requests, two pauses; none after the last

    slept.clear()
    told = httpx.Response(429, headers={"Retry-After": "3"})

    async def limited(k: int) -> str:
        if k == 0:
            err = _Status(429, "slow down")
            err.response = told
            raise err
        return "ok"

    assert await upstream.race(
        limited, upstream.Call("t"), relaunch=upstream.worth_retry, discard=_never_discard
    ) == ("ok", 1)
    assert slept == [3.0]
    assert upstream.retry_after(_Status(503, "x")) is None
    assert not upstream.worth_retry(_Status(400, "bad request"))
    assert upstream.worth_retry(httpx.ConnectError("refused"))


class _FakeRelay:
    """Real HTTP on 127.0.0.1 serving SSE chat replies, as a slow relay does.

    The first request gets no token until the hedge arrives; then both get their
    first token at the same moment and keep generating for ``rest`` s. A client
    that hangs up ends its request at once: ``hangups`` holds how long after the
    first token each hang-up came, ``open`` the requests still being served.
    """

    def __init__(self, rest: float = 3.0) -> None:
        self.rest = rest
        self.hangups: list[float] = []
        self.open = 0
        self.requests = 0
        self.both = asyncio.Event()
        self.server: asyncio.base_events.Server | None = None

    async def __aenter__(self) -> Self:
        self.server = await asyncio.start_server(self._serve, "127.0.0.1", 0)
        return self

    async def __aexit__(self, *_a) -> None:
        assert self.server is not None
        self.server.close()

    @property
    def url(self) -> str:
        assert self.server is not None
        return f"http://127.0.0.1:{self.server.sockets[0].getsockname()[1]}/v1"

    @staticmethod
    def _chunk(data: bytes) -> bytes:
        return b"%x\r\n%s\r\n" % (len(data), data)

    @staticmethod
    def _sse(text: str, finish: str | None = None) -> bytes:
        fin = f'"{finish}"' if finish else "null"
        return (
            'data: {"id":"c","object":"chat.completion.chunk","created":1,"model":"m",'
            f'"choices":[{{"index":0,"delta":{{"content":"{text}"}},"finish_reason":{fin}}}]}}\n\n'
        ).encode()

    async def _serve(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        try:
            while True:
                head = await reader.readuntil(b"\r\n\r\n")
                size = 0
                for line in head.split(b"\r\n"):
                    if line.lower().startswith(b"content-length:"):
                        size = int(line.split(b":", 1)[1])
                await reader.readexactly(size)
                self.requests += 1
                if self.requests == 2:
                    self.both.set()
                self.open += 1
                try:
                    writer.write(
                        b"HTTP/1.1 200 OK\r\ncontent-type: text/event-stream\r\n"
                        b"transfer-encoding: chunked\r\n\r\n"
                    )
                    await writer.drain()
                    await asyncio.wait_for(self.both.wait(), 30)
                    writer.write(self._chunk(self._sse("o")))
                    await writer.drain()
                    t0 = asyncio.get_running_loop().time()
                    with contextlib.suppress(TimeoutError):
                        if await asyncio.wait_for(reader.read(1), self.rest) == b"":
                            self.hangups.append(asyncio.get_running_loop().time() - t0)
                            return
                    writer.write(self._chunk(self._sse("k", "stop") + b"data: [DONE]\n\n"))
                    writer.write(b"0\r\n\r\n")
                    await writer.drain()
                finally:
                    self.open -= 1
        except (asyncio.IncompleteReadError, ConnectionError, TimeoutError):
            return
        finally:
            writer.close()


@pytest.mark.asyncio
async def test_hedge_loser_hangs_up_on_the_relay_within_a_second(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Review #1283 ②: the dropped copy closes its HTTP stream, not when GC gets to it."""
    _env(monkeypatch)
    monkeypatch.setenv("PICO_HEDGE_FAST_S", "0.2")
    async with _FakeRelay() as relay:
        monkeypatch.setenv("DEEPSEEK_BASE_URL", relay.url)
        assert "".join(await _ask()) == "ok"
        assert relay.requests == 2  # first stalls, the hedge goes out, both answer
        assert len(relay.hangups) == 1 and relay.hangups[0] < 1.0  # the loser, at once
        assert relay.open == 0
        assert upstream.stats()["inflight"] == {}


@pytest.mark.asyncio
async def test_direct_busy_relay_tells_the_teacher_in_plain_words(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from pico_orchestrator.upstream import BUSY_TEXT
    from pico_orchestrator.user_errors import user_message_for_error

    _env(monkeypatch)

    def overloaded(_m, _n):
        raise _Status(503, "system cpu overloaded")

    _relay(monkeypatch, overloaded)
    with pytest.raises(RuntimeError) as caught:
        await _ask()
    assert str(caught.value) == BUSY_TEXT == "Pico 这会儿忙，请稍后再试。"
    assert user_message_for_error("OpenAI API error (503): overloaded").startswith(BUSY_TEXT)


def _exam_relay(monkeypatch: pytest.MonkeyPatch, answer) -> list[str]:
    """Fake New API for non-streamed calls (exam pages, hosted Pi)."""
    from pico_orchestrator import provider

    provider._CLIENTS.clear()
    calls: list[str] = []

    class _Completions:
        async def create(self, **kwargs):
            calls.append(kwargs["model"])
            await asyncio.sleep(0.02)
            return answer(len(calls))

    monkeypatch.setattr(
        "pico_orchestrator.provider.AsyncOpenAI",
        lambda **_kw: SimpleNamespace(chat=SimpleNamespace(completions=_Completions())),
    )
    return calls


def _reply(text: str):
    return SimpleNamespace(
        usage=None, choices=[SimpleNamespace(message=SimpleNamespace(content=text))]
    )


@pytest.mark.asyncio
async def test_exam_page_reads_go_through_the_door(monkeypatch: pytest.MonkeyPatch) -> None:
    """Review #1283 ①: was 5 own tries × the door's 3 per page, 4 pages at once on top."""
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "packages" / "exam-answer-extract"))
    import extract as ex

    _env(monkeypatch)
    monkeypatch.setenv("PICO_UPSTREAM_KEY_MAX", "2")
    monkeypatch.delenv("PICO_EXAM_EXTRACT_ATTEMPTS", raising=False)
    calls = _exam_relay(monkeypatch, lambda _n: (_ for _ in ()).throw(_Status(503, "busy")))
    with pytest.raises(_Status):
        await ex.model_complete([{"role": "user", "content": "读题"}])
    assert len(calls) == upstream.CALL_BUDGET  # was 5 × 3 = 15

    one = '[{"number": 1, "type": "single_choice", "answer": "A", "score": 2}]'
    calls = _exam_relay(monkeypatch, lambda _n: _reply(one))
    pages = [{"page": i, "mime": "image/png", "data_b64": "iVBORw0KGgo="} for i in range(1, 7)]
    await ex.extract_pages(pages, concurrency=4, complete=ex.model_complete)
    assert len(calls) == 6
    assert upstream.stats()["peak"] == {upstream.key_id("sk-test"): 2}  # key cap, not 4


def _wire_relay(monkeypatch: pytest.MonkeyPatch) -> list[tuple[str, str]]:
    """Fake New API that 400s gpt/grok on chat/completions, as the live relay does."""
    from pico_orchestrator import provider

    provider._CLIENTS.clear()
    calls: list[tuple[str, str]] = []

    class _Completions:
        async def create(self, **kwargs):
            calls.append(("chat", kwargs["model"]))
            if provider.is_openai_responses_model(kwargs["model"]):
                raise _Status(400, "invalid_request")
            if kwargs.get("stream"):
                return _Chunks("好")
            return _reply("好")

    class _Responses:
        async def create(self, **kwargs):
            calls.append(("responses", kwargs["model"]))
            return _Events("好")

    monkeypatch.setattr(
        "pico_orchestrator.provider.AsyncOpenAI",
        lambda **_kw: SimpleNamespace(
            chat=SimpleNamespace(completions=_Completions()), responses=_Responses()
        ),
    )
    return calls


@pytest.mark.asyncio
async def test_every_road_picks_the_wire_by_the_model_it_sends(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """pico#1288: the exam road sent gpt-5.6-sol on chat/completions (Gemini brain) → 400.

    The chat backup was already right; pin both so a Gemini outage has a real backup.
    """
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "packages" / "exam-answer-extract"))
    import extract as ex
    from pico_orchestrator import provider

    _env(monkeypatch, fallbacks="gpt-5.6-sol")
    calls = _wire_relay(monkeypatch)
    real = provider.AsyncOpenAI

    def gemini_down(**kw):
        client = real(**kw)
        create = client.chat.completions.create

        async def chat(**kwargs):
            if kwargs["model"].startswith("gemini"):
                calls.append(("chat", kwargs["model"]))
                raise _Status(403, "channel suspended")
            return await create(**kwargs)

        client.chat.completions.create = chat
        return client

    monkeypatch.setattr("pico_orchestrator.provider.AsyncOpenAI", gemini_down)
    assert "".join([p async for p in provider.stream_chat("hi", model="pico-fast")]) == "好"
    assert calls == [("chat", "gemini-3.8-pro"), ("responses", "gpt-5.6-sol")]

    calls = _wire_relay(monkeypatch)
    monkeypatch.setattr(provider, "product_backend_model", lambda **_kw: "gpt-5.6-sol")
    assert await ex.model_complete([{"role": "user", "content": "读题"}]) == "好"
    assert calls == [("responses", "gpt-5.6-sol")]


def _gemini_fails(monkeypatch: pytest.MonkeyPatch, error) -> list[tuple[str, str]]:
    """Wire relay where every Gemini request raises ``error()``."""
    from pico_orchestrator import provider

    calls = _wire_relay(monkeypatch)
    real = provider.AsyncOpenAI

    def client(**kw):
        out = real(**kw)
        create = out.chat.completions.create

        async def chat(**kwargs):
            if kwargs["model"].startswith("gemini"):
                calls.append(("chat", kwargs["model"]))
                raise error()
            return await create(**kwargs)

        out.chat.completions.create = chat
        return out

    monkeypatch.setattr("pico_orchestrator.provider.AsyncOpenAI", client)
    return calls


def _extract():
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "packages" / "exam-answer-extract"))
    import extract

    return extract


@pytest.mark.asyncio
async def test_exam_falls_to_the_backup_brain_when_gemini_is_dead(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A dead Gemini key / channel no longer stops every exam read until someone switches."""
    ex = _extract()
    _env(monkeypatch, fallbacks="gpt-5.6-sol")
    calls = _gemini_fails(monkeypatch, lambda: _Status(403, "channel suspended"))
    picked: dict = {}
    assert await ex.model_complete([{"role": "user", "content": "读题"}], model_out=picked) == "好"
    assert calls == [("chat", "gemini-3.8-pro"), ("responses", "gpt-5.6-sol")]
    assert picked == {"model": "gpt-5.6-sol"}  # billed as the model that answered

    # Marked down: the next page goes straight to the backup.
    calls.clear()
    assert await ex.model_complete([{"role": "user", "content": "读题"}]) == "好"
    assert calls == [("responses", "gpt-5.6-sol")]


@pytest.mark.asyncio
async def test_exam_stays_on_gemini_when_it_is_only_busy(monkeypatch: pytest.MonkeyPatch) -> None:
    """429 (Vertex shared quota) is retried on the same model, never switched."""
    ex = _extract()
    _env(monkeypatch, fallbacks="gpt-5.6-sol")
    calls = _gemini_fails(monkeypatch, lambda: _Status(429, "Resource exhausted. quota"))
    with pytest.raises(_Status):
        await ex.model_complete([{"role": "user", "content": "读题"}])
    assert calls == [("chat", "gemini-3.8-pro")] * upstream.CALL_BUDGET


@pytest.mark.asyncio
async def test_exam_image_page_skips_a_backup_that_cannot_see(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A text-only backup is never sent a page image."""
    ex = _extract()
    _env(monkeypatch, fallbacks="deepseek-chat,gpt-5.6-sol")
    calls = _gemini_fails(monkeypatch, lambda: _Status(403, "suspended"))
    page = [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": "读这页"},
                {"type": "image", "mime": "image/png", "data_b64": "iVBORw0KGgo="},
            ],
        }
    ]
    assert await ex.model_complete(page) == "好"
    assert calls == [("chat", "gemini-3.8-pro"), ("responses", "gpt-5.6-sol")]

    # Only a text backup left: a dead Gemini fails the page, no blind call.
    _env(monkeypatch, fallbacks="deepseek-chat")
    calls = _gemini_fails(monkeypatch, lambda: _Status(403, "suspended"))
    with pytest.raises(_Status):
        await ex.model_complete(page)
    assert calls == [("chat", "gemini-3.8-pro")]


@pytest.mark.asyncio
async def test_exam_backup_shares_the_three_request_budget(monkeypatch: pytest.MonkeyPatch) -> None:
    from pico_orchestrator import provider

    ex = _extract()
    _env(monkeypatch, fallbacks="gpt-5.6-sol")
    provider._CLIENTS.clear()
    gemini = iter([_Status(503, "busy"), _Status(403, "suspended")])
    calls: list[str] = []

    async def chat(**kwargs):
        calls.append(kwargs["model"])
        raise next(gemini)

    async def responses(**kwargs):
        calls.append(kwargs["model"])
        raise _Status(503, "busy")

    monkeypatch.setattr(
        "pico_orchestrator.provider.AsyncOpenAI",
        lambda **_kw: SimpleNamespace(
            chat=SimpleNamespace(completions=SimpleNamespace(create=chat)),
            responses=SimpleNamespace(create=responses),
        ),
    )
    with pytest.raises(_Status):
        await ex.model_complete([{"role": "user", "content": "读题"}])
    assert calls == ["gemini-3.8-pro", "gemini-3.8-pro", "gpt-5.6-sol"]  # 3, not 2 + 3


@pytest.mark.asyncio
async def test_hosted_rollback_steps_go_through_the_door(monkeypatch: pytest.MonkeyPatch) -> None:
    """Review #1283 ⑤: PICO_HOSTED_LOOP=1 no longer builds its own retrying client."""
    from pico_orchestrator.provider import call_once, resolve_provider

    _env(monkeypatch)
    calls = _exam_relay(monkeypatch, lambda _n: (_ for _ in ()).throw(_Status(503, "busy")))
    cfg = resolve_provider()
    with pytest.raises(_Status):
        await call_once(cfg, "hosted", lambda: _client(cfg).chat.completions.create(model="m"))
    assert len(calls) == upstream.CALL_BUDGET
    assert upstream.stats()["calls"]["hosted"]["sent"] == 3


def _client(cfg):
    from pico_orchestrator.provider import _llm_client

    return _llm_client(cfg)


@pytest.mark.asyncio
async def test_llm_pass_races_unless_the_run_proxy_already_did(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Review #1283 ④: Pi without a box comes here directly and gets the door's retry;
    the box's steps arrive already raced (``x-pico-door``) and are sent once."""
    from app import llm_pass_router as lp
    from starlette.requests import Request

    async def handler(_req, _n):
        return httpx.Response(503, content=b'{"error":{"message":"overloaded"}}')

    hits = _upstream(monkeypatch, handler)
    monkeypatch.setattr(lp, "_loopback", lambda _r: True)

    def request(extra: list[tuple[bytes, bytes]]) -> Request:
        body = b'{"model":"m","stream":true}'

        async def receive():
            return {"type": "http.request", "body": body, "more_body": False}

        return Request(
            {
                "type": "http",
                "method": "POST",
                "path": "/internal/llm-pass/r/v1/chat/completions",
                "headers": [(b"authorization", b"Bearer sk-box"), *extra],
                "query_string": b"",
            },
            receive,
        )

    assert (await lp.llm_pass("run-np", "chat/completions", request([]))).status_code == 503
    assert len(hits) == 3
    assert upstream.upstream_error("run-np").startswith("upstream 503")
    raced = request([(b"x-pico-door", b"raced")])
    assert (await lp.llm_pass("run-box", "chat/completions", raced)).status_code == 503
    assert len(hits) == 4  # once: the run proxy in front holds the retry
