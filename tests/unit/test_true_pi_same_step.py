"""pico#1322: Pi re-sending the same call and getting the same result stops the run.

Ruler lp (10-18): R20 sent one bash command 37 times with one IndexError each
time, R08 one base64 decode 50 times; both ran on until the wall clock. The
third identical (tool, args, result) in a row now stops Pi as an honest failure.
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
from pico_orchestrator.true_pi.client import FakeTransport
from pico_orchestrator.true_pi.runtime import SAME_STEP_CODE, SameStep, run_true_pi_agent

STOP_TEXT = "Pico 卡在同一步、反复得到同样的结果，已停下。"


class Principal:
    def __init__(self) -> None:
        self.school_id = "school-a"
        self.membership_id = "member-a"
        self.scopes = ["ai:run"]


async def _not_cancelled() -> bool:
    return False


def _call(n: int, cmd: str, out: str, tool: str = "bash") -> list[dict[str, Any]]:
    cid = f"c{n}"
    return [
        {"type": "tool_execution_start", "toolName": tool, "toolCallId": cid, "args": {"command": cmd}},
        {
            "type": "tool_execution_end",
            "toolName": tool,
            "toolCallId": cid,
            "isError": True,
            "result": {
                "content": [{"type": "text", "text": out}],
                # Pi names a fresh temp file per call; the model never reads it.
                "details": {"fullOutputPath": f"/tmp/pi-bash-{n}.log"},
            },
        },
    ]


def _ends(calls: list[tuple[str, str, str]]) -> list[bool]:
    watch = SameStep()
    hits = []
    for n, (tool, cmd, out) in enumerate(calls):
        for ev in _call(n, cmd, out, tool):
            hit = watch.see(ev["type"], ev)
            if ev["type"] == "tool_execution_end":
                hits.append(hit)
    return hits


BAD = ("bash", "python make.py", "IndexError: tuple index out of range")


def test_third_identical_call_in_a_row_stops() -> None:
    assert _ends([BAD, BAD, BAD]) == [False, False, True]


def test_changed_args_never_stop() -> None:
    calls = [("bash", f"python make.py --try {i}", BAD[2]) for i in range(6)]
    assert not any(_ends(calls))


def test_changed_results_never_stop() -> None:
    calls = [("bash", BAD[1], f"IndexError at line {i}") for i in range(6)]
    assert not any(_ends(calls))


def test_a_different_call_in_between_starts_the_count_over() -> None:
    other = ("read", "make.py", "def main(): ...")
    assert _ends([BAD, BAD, other, BAD, BAD, other, BAD, BAD]) == [False] * 8
    assert _ends([BAD, BAD, other, BAD, BAD, BAD]) == [False] * 5 + [True]


def test_anything_said_in_between_starts_the_count_over() -> None:
    """A resume prompt or a teacher's steer is new input: the next call may differ."""
    for said in (
        {"type": "agent_start"},
        {"type": "message_start", "message": {"role": "user", "content": "换个办法"}},
    ):
        watch = SameStep()
        hits = []
        for n in range(4):
            if n == 2:
                watch.see(said["type"], said)
            for ev in _call(n, BAD[1], BAD[2]):
                hits.append(watch.see(ev["type"], ev))
        assert not any(hits)


def test_same_command_through_another_tool_is_another_step() -> None:
    assert not any(_ends([BAD, ("sandbox_bash", *BAD[1:]), BAD]))


def _write() -> list[dict[str, Any]]:
    return [
        {
            "type": "tool_execution_start",
            "toolName": "workspace_write_file",
            "toolCallId": "w1",
            "args": {"title": "a.md", "content": "part 1"},
        },
        {
            "type": "tool_execution_end",
            "toolName": "workspace_write_file",
            "toolCallId": "w1",
            "isError": False,
            "result": {"content": [{"type": "text", "text": '{"title":"a.md"}'}]},
        },
    ]


async def _run(steps: list[dict[str, Any]]) -> tuple[Any, list[tuple[str, dict[str, Any]]], FakeTransport]:
    events: list[tuple[str, dict[str, Any]]] = []

    async def emit(kind: str, payload: dict[str, Any]) -> None:
        events.append((kind, payload))

    scripted = [
        {"type": "agent_start"},
        {"type": "turn_start"},
        *steps,
        {"type": "agent_end", "willRetry": False, "messages": []},
    ]
    transport = FakeTransport(scripted=scripted)
    result = await run_true_pi_agent(
        prompt="做成绩表和柱状图",
        principal=Principal(),
        emit=emit,
        is_cancelled=_not_cancelled,
        caps=RunCaps(max_seconds=60, max_steps=48),
        transport=transport,
        run_id="tp-same-step",
    )
    return result, events, transport


@pytest.mark.asyncio
async def test_run_stops_as_honest_failure_with_the_fixed_sentence() -> None:
    steps = [ev for n in range(5) for ev in _call(n, BAD[1], BAD[2])]
    result, events, transport = await _run(steps)
    assert result.status == "failed"
    assert result.code == SAME_STEP_CODE
    failed = [p for k, p in events if k == "run.status" and p.get("status") == "failed"]
    assert failed and failed[0]["code"] == SAME_STEP_CODE
    assert failed[0]["user_message"] == STOP_TEXT
    assert any(c.get("type") == "abort" for c in transport.sent)
    # Stopped at the third: the fourth and fifth calls were never read.
    assert sum(1 for k, _ in events if k == "tool.result") == 3


@pytest.mark.asyncio
async def test_saved_files_are_pointed_to() -> None:
    steps = [*_write(), *[ev for n in range(3) for ev in _call(n, BAD[1], BAD[2])]]
    result, events, _ = await _run(steps)
    assert result.code == SAME_STEP_CODE
    failed = [p for k, p in events if k == "run.status" and p.get("status") == "failed"]
    assert failed[0]["user_message"].startswith(STOP_TEXT.rstrip("。"))
    assert "已经生成的文件" in failed[0]["user_message"]


@pytest.mark.asyncio
async def test_retries_that_change_something_run_on() -> None:
    steps = [ev for n in range(4) for ev in _call(n, f"python make.py --try {n}", BAD[2])]
    result, _, _ = await _run(steps)
    assert result.code != SAME_STEP_CODE
