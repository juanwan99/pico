"""Hung tool watchdog: abort a tool call that never ends, then resume the session.

LH3 (2026-10-01): the model ran its own endless search loop in bash; Pi's bash
has no default timeout and the wall clock is gone (#1104 E), so the run sat 33
minutes until a deploy killed it. Pico aborts the call and re-prompts instead.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "api"))
sys.path.insert(0, str(ROOT / "services" / "orchestrator"))

from pico_orchestrator.run_types import RunCaps
from pico_orchestrator.true_pi import runtime
from pico_orchestrator.true_pi.client import FakeTransport, RpcEvent
from pico_orchestrator.true_pi.config import tool_hang_seconds
from pico_orchestrator.true_pi.runtime import hung_tool, run_true_pi_agent, track_open_tool


class Principal:
    def __init__(self) -> None:
        self.school_id = "school-a"
        self.membership_id = "member-a"
        self.scopes = ["ai:run"]


async def _not_cancelled() -> bool:
    return False


def _hanging_bash() -> list[dict[str, Any]]:
    return [
        {"type": "agent_start"},
        {"type": "turn_start"},
        {
            "type": "tool_execution_start",
            "toolName": "bash",
            "toolCallId": "b1",
            "args": {"command": "python3 search.py"},
        },
    ]


def _aborted_turn() -> list[dict[str, Any]]:
    return [
        {
            "type": "tool_execution_end",
            "toolName": "bash",
            "toolCallId": "b1",
            "isError": True,
            "result": {"content": [{"type": "text", "text": "Command aborted"}]},
        },
        {"type": "message_end", "message": {"role": "assistant", "content": [], "stopReason": "aborted"}},
        {"type": "agent_end", "willRetry": False, "messages": []},
    ]


def _finish() -> list[dict[str, Any]]:
    done = {"role": "assistant", "content": [{"type": "text", "text": "换成剪枝搜索，课表已排好。"}]}
    return [
        {"type": "agent_start"},
        {"type": "turn_start"},
        {"type": "message_end", "message": done},
        {"type": "turn_end", "message": done},
        {"type": "agent_end", "willRetry": False, "messages": []},
    ]


class AbortingTransport(FakeTransport):
    """Pi ends the aborted turn the way 0.84 does (or not at all when ``mute``)."""

    mute: bool = False

    async def send(self, command: Any) -> None:
        await super().send(command)
        if dict(command).get("type") == "abort" and not self.mute:
            for item in _aborted_turn():
                await self._event_q.put(RpcEvent(item))


async def _run(transport: FakeTransport, events: list[tuple[str, dict[str, Any]]]):
    async def emit(kind: str, payload: dict[str, Any]) -> None:
        events.append((kind, payload))

    return await run_true_pi_agent(
        prompt="排课",
        principal=Principal(),
        emit=emit,
        is_cancelled=_not_cancelled,
        caps=RunCaps(min_artifacts=0, max_seconds=60),
        transport=transport,
        run_id="hang-t",
    )


def _prompts(transport: FakeTransport) -> list[str]:
    return [str(c.get("message") or "") for c in transport.sent if c.get("type") == "prompt"]


def test_open_tool_deadline_and_bookkeeping() -> None:
    open_tools: dict[str, tuple[str, float, float]] = {}
    start = {"toolName": "bash", "toolCallId": "a", "args": {"command": "x"}}
    track_open_tool(open_tools, "tool_execution_start", start, 0.0, 600)
    assert hung_tool(open_tools, 599) == ""
    assert hung_tool(open_tools, 600) == "bash 命令运行超过 10 分钟没有结束"
    track_open_tool(open_tools, "tool_execution_end", {"toolCallId": "a"}, 601, 600)
    assert open_tools == {}
    asked = {"toolName": "bash", "toolCallId": "b", "args": {"command": "make", "timeout": 1800}}
    track_open_tool(open_tools, "tool_execution_start", asked, 0.0, 600)
    assert hung_tool(open_tools, 1000) == "" and hung_tool(open_tools, 1830) != ""
    track_open_tool(open_tools, "agent_end", {}, 1831, 600)
    assert open_tools == {}
    track_open_tool(open_tools, "tool_execution_start", start, 0.0, 0)
    assert hung_tool(open_tools, 10**6) == ""


def test_tool_hang_seconds_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("PICO_TOOL_HANG_SECONDS", raising=False)
    assert tool_hang_seconds() == 600
    monkeypatch.setenv("PICO_TOOL_HANG_SECONDS", "0")
    assert tool_hang_seconds() == 0
    monkeypatch.setenv("PICO_TOOL_HANG_SECONDS", "junk")
    assert tool_hang_seconds() == 600


@pytest.mark.asyncio
async def test_hung_tool_is_aborted_and_the_session_resumes(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PICO_TOOL_HANG_SECONDS", "1")
    events: list[tuple[str, dict[str, Any]]] = []
    transport = AbortingTransport(scripted=_hanging_bash(), scripted_after_prompt=[_finish()])
    result = await _run(transport, events)
    assert result.status == "succeeded", result.error
    assert any(c.get("type") == "abort" for c in transport.sent)
    prompts = _prompts(transport)
    assert len(prompts) == 2
    assert "bash 命令运行超过" in prompts[1] and "不要原样重跑" in prompts[1] and "timeout" in prompts[1]
    resumes = [p for k, p in events if k == "run.resume"]
    assert resumes and "bash 命令运行超过" in resumes[0]["reason"]
    assert any("跑太久" in str(p.get("text")) for k, p in events if k == "message.delta")
    assert [p["status"] for k, p in events if k == "run.status"][-1] == "succeeded"


@pytest.mark.asyncio
async def test_pi_that_never_ends_the_aborted_turn_still_resumes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PICO_TOOL_HANG_SECONDS", "1")
    monkeypatch.setattr(runtime, "_HANG_ABORT_GRACE", 0.3)
    events: list[tuple[str, dict[str, Any]]] = []
    transport = AbortingTransport(scripted=_hanging_bash(), scripted_after_prompt=[_finish()])
    transport.mute = True
    result = await _run(transport, events)
    assert result.status == "succeeded", result.error
    assert len(_prompts(transport)) == 2


@pytest.mark.asyncio
async def test_hang_without_resume_budget_fails_with_the_reason(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PICO_TOOL_HANG_SECONDS", "1")
    monkeypatch.setenv("PICO_RUN_RESUME_MAX", "0")
    events: list[tuple[str, dict[str, Any]]] = []
    transport = AbortingTransport(scripted=_hanging_bash(), scripted_after_prompt=[_finish()])
    result = await _run(transport, events)
    assert result.status == "failed"
    assert len(_prompts(transport)) == 1
    assert "bash 命令运行超过" in str(result.error)
