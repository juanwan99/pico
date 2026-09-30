"""Long tool-call arguments stream as throttled tool.drafting progress (#1111)."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "orchestrator"))

from pico_orchestrator.true_pi.client import RpcEvent, SubprocessTransport
from pico_orchestrator.true_pi.events import EventMapState, map_event
from pico_orchestrator.true_pi.thinking import toolcall_progress_from_update
from pico_orchestrator.workbench_progress import workbench_drafting_line


def _bare_transport() -> SubprocessTransport:
    t = SubprocessTransport.__new__(SubprocessTransport)
    t._queue = asyncio.Queue()
    t._resp_q = asyncio.Queue()
    t._stream_seen = 0
    t._think_seen = 0
    t._toolcall_seen = {}
    t._stderr_tail = []
    t.run_id = "t"
    return t


def _update(kind: str, *, delta: str = "", name: str = "write", idx: int = 0) -> dict[str, Any]:
    content: list[dict[str, Any]] = [{"type": "thinking", "thinking": ""}] * idx
    content = content + [{"type": "toolCall", "name": name, "arguments": {}}]
    return {
        "type": "message_update",
        "message": {"role": "assistant", "content": content},
        "assistantMessageEvent": {"type": kind, "contentIndex": idx, "delta": delta},
    }


def test_progress_throttled_and_counts_chars() -> None:
    seen: dict[int, list[float]] = {}
    first = toolcall_progress_from_update(_update("toolcall_start"), seen, 100.0)
    assert first == {"type": "toolcall_progress", "tool": "write", "chars": 0}
    assert toolcall_progress_from_update(_update("toolcall_delta", delta="x" * 3000), seen, 102.0) is None
    later = toolcall_progress_from_update(_update("toolcall_delta", delta="y" * 2000), seen, 105.5)
    assert later == {"type": "toolcall_progress", "tool": "write", "chars": 5000}


def test_progress_ignores_text_and_thinking() -> None:
    seen: dict[int, list[float]] = {}
    body = _update("text_delta", delta="hi")
    assert toolcall_progress_from_update(body, seen, 1.0) is None
    assert seen == {}


def test_progress_names_the_right_content_block() -> None:
    seen: dict[int, list[float]] = {}
    got = toolcall_progress_from_update(_update("toolcall_start", name="bash", idx=2), seen, 1.0)
    assert got is not None and got["tool"] == "bash"


@pytest.mark.asyncio
async def test_ingest_queues_progress_and_resets_per_message() -> None:
    t = _bare_transport()
    await t._ingest_rpc(_update("toolcall_start"))
    await t._ingest_rpc(_update("toolcall_delta", delta="z" * 10))
    ev = t._queue.get_nowait()
    assert ev.type == "toolcall_progress" and ev.raw["tool"] == "write"
    assert t._queue.empty(), "second slice within 5s is throttled"
    await t._ingest_rpc({"type": "message_start", "message": {"role": "assistant"}})
    assert t._queue.get_nowait().type == "message_start"
    await t._ingest_rpc(_update("toolcall_start", name="edit"))
    ev = t._queue.get_nowait()
    assert ev.raw == {"type": "toolcall_progress", "tool": "edit", "chars": 0}


@pytest.mark.asyncio
async def test_map_event_emits_tool_drafting_not_tool_call() -> None:
    events: list[tuple[str, dict[str, Any]]] = []

    async def emit(kind: str, payload: dict[str, Any]) -> None:
        events.append((kind, payload))

    state = EventMapState()
    await map_event(
        RpcEvent({"type": "toolcall_progress", "tool": "write", "chars": 12_700}),
        emit=emit,
        state=state,
    )
    assert [k for k, _ in events] == ["tool.drafting"]
    assert events[0][1]["step_line"] == "正在写文件（已写 12 KB）"
    assert state.tool_calls == 0


def test_drafting_line() -> None:
    assert workbench_drafting_line("write", 0) == "正在写文件…"
    assert workbench_drafting_line("bash", 2048) == "正在写脚本（已写 2 KB）"
    assert workbench_drafting_line("generate_html_document", 5000) == "正在写网页（已写 4 KB）"
    assert workbench_drafting_line("", 0) == "正在调工具…"
