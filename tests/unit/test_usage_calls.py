"""edu-core#4350: a chat run's row counts the requests the relay answered (New API logs each)."""

from __future__ import annotations

import sys
from pathlib import Path

import httpx
import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "api"))
sys.path.insert(0, str(ROOT / "services" / "orchestrator"))

from app import ws_proxy_router as wpr
from pico_orchestrator import upstream


def _client_with(monkeypatch: pytest.MonkeyPatch, status: int) -> None:
    def handler(_req: httpx.Request) -> httpx.Response:
        return httpx.Response(status, content=b'data: {"ok":1}\n\n')

    real = httpx.AsyncClient

    def make(*args, **kwargs):
        kwargs["transport"] = httpx.MockTransport(handler)
        return real(*args, **kwargs)

    monkeypatch.setattr(wpr.httpx, "AsyncClient", make)


async def _drain(resp) -> None:
    if hasattr(resp, "body_iterator"):
        async for _ in resp.body_iterator:
            pass


async def test_answered_request_counts_on_its_run(monkeypatch: pytest.MonkeyPatch) -> None:
    _client_with(monkeypatch, 200)
    for _ in range(2):
        resp = await wpr._stream(
            "POST", "http://relay/v1/responses", {}, b"{}",
            call=upstream.Call("pi_step", run_id="run-a", budget=1),
            key="sk-relay", run_id="run-a", bill_run="run-a",
        )
        await _drain(resp)
    assert upstream.answered_calls("run-a") == 2


async def test_error_status_and_own_hop_do_not_count(monkeypatch: pytest.MonkeyPatch) -> None:
    _client_with(monkeypatch, 403)
    resp = await wpr._stream(
        "POST", "http://relay/v1/responses", {}, b"{}",
        call=upstream.Call("pi_step", run_id="run-b", budget=1),
        key="sk-relay", run_id="run-b", bill_run="run-b",
    )
    assert resp.status_code == 403
    _client_with(monkeypatch, 200)
    # our own llm-pass hop (no key): the hop counts it, not the run proxy
    resp = await wpr._stream(
        "POST", "http://127.0.0.1/internal/llm-pass/run-b/responses", {}, b"{}",
        call=upstream.Call("pi_step", run_id="run-b", budget=1),
        key="", run_id="run-b", bill_run="run-b",
    )
    await _drain(resp)
    assert upstream.answered_calls("run-b") == 0


def test_direct_path_counts_through_caller_scope() -> None:
    assert upstream.answered_calls("run-c") is None
    with upstream.caller_scope(conversation_id="c1", run_id="run-c", membership_id="m1"):
        upstream.note_answered()
        upstream.note_answered()
    upstream.note_answered()  # outside any run: nobody to count on
    assert upstream.answered_calls("run-c") == 2
