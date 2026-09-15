"""Prompt-ack must not hold Pi stream events (A5 TTFB)."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "orchestrator"))

from pico_orchestrator.true_pi.client import SubprocessTransport


def _bare_transport() -> SubprocessTransport:
    t = SubprocessTransport.__new__(SubprocessTransport)
    t._queue = asyncio.Queue()
    t._resp_q = asyncio.Queue()
    t._stream_seen = 0
    t._think_seen = 0
    t._stderr_tail = []
    t.run_id = "t"
    return t


def _text_update(text: str, *, official: str | None = None) -> dict:
    body: dict = {
        "type": "message_update",
        "message": {"role": "assistant", "content": [{"type": "text", "text": text}]},
    }
    if official is not None:
        body["assistantMessageEvent"] = {"type": "text_delta", "delta": official}
    return body


@pytest.mark.asyncio
async def test_ingest_routes_prompt_ack_off_event_queue() -> None:
    t = _bare_transport()
    await t._ingest_rpc(_text_update("培", official="培"))
    await t._ingest_rpc({"type": "response", "command": "prompt", "success": True, "id": "p-1"})
    ev = t._queue.get_nowait()
    assert ev.type == "text_delta"
    assert ev.raw["delta"] == "培"
    with pytest.raises(asyncio.QueueEmpty):
        t._queue.get_nowait()
    ack = t._resp_q.get_nowait()
    assert ack["command"] == "prompt"
    assert ack["id"] == "p-1"


@pytest.mark.asyncio
async def test_ingest_thinking_snapshot_becomes_thinking_delta() -> None:
    t = _bare_transport()
    await t._ingest_rpc(
        {
            "type": "message_update",
            "message": {
                "role": "assistant",
                "content": [{"type": "thinking", "thinking": "先"}],
            },
        }
    )
    ev = t._queue.get_nowait()
    assert ev.type == "thinking_delta"
    assert ev.raw["delta"] == "先"


@pytest.mark.asyncio
async def test_wait_response_leaves_stream_on_event_queue() -> None:
    t = _bare_transport()
    await t._ingest_rpc(_text_update("hello", official="hello"))
    await t._ingest_rpc({"type": "response", "command": "prompt", "success": True, "id": "p-1"})
    raw = await t.wait_response("prompt", req_id="p-1", timeout=1.0)
    assert raw["success"] is True
    ev = t._queue.get_nowait()
    assert ev.type == "text_delta"
    assert ev.raw["delta"] == "hello"


@pytest.mark.asyncio
async def test_wait_response_concurrent_does_not_drain_stream() -> None:
    t = _bare_transport()
    waiter = asyncio.create_task(t.wait_response("prompt", req_id="p-1", timeout=2.0))
    await asyncio.sleep(0)
    await t._ingest_rpc(_text_update("hello", official="hello"))
    await t._ingest_rpc({"type": "response", "command": "prompt", "success": True, "id": "p-1"})
    raw = await waiter
    assert raw["success"] is True
    ev = await asyncio.wait_for(t._queue.get(), timeout=0.2)
    assert ev.type == "text_delta"
    assert ev.raw["delta"] == "hello"


def test_runtime_starts_consume_before_prompt() -> None:
    runtime = (ROOT / "services/orchestrator/pico_orchestrator/true_pi/runtime.py").read_text()
    client = (ROOT / "services/orchestrator/pico_orchestrator/true_pi/client.py").read_text()
    i_cons = runtime.find("consumer = asyncio.create_task(_consume())")
    i_prompt = runtime.find("await client.prompt(")
    assert 0 <= i_cons < i_prompt
    assert "self._resp_q" in client
    assert "_resp_q.get" in client
    assert "async def _ingest_rpc" in client
