"""pico#1296: look at the finished file before answering (and pico#1297: own up when it was not looked at).

The workspace rules say how to look (render pages, `read` the pictures), and
once per run, when the model starts writing a file the teacher will open,
Pico steers it to look before its final answer.
"""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "api"))
sys.path.insert(0, str(ROOT / "services" / "orchestrator"))

from pico_orchestrator.human_package import UNLOOKED_NOTE, note_unlooked
from pico_orchestrator.run_types import RunCaps
from pico_orchestrator.true_pi import runner
from pico_orchestrator.true_pi.client import FakeTransport
from pico_orchestrator.true_pi.runner import (
    LOOK_STEER,
    WORKSPACE_SYSTEM,
    look_read_call,
    visual_output_call,
)
from pico_orchestrator.true_pi.runtime import run_true_pi_agent


class Principal:
    def __init__(self) -> None:
        self.school_id = "school-a"
        self.membership_id = "member-a"
        self.scopes = ["ai:run"]


async def _not_cancelled() -> bool:
    return False


def test_workspace_rules_say_how_to_look() -> None:
    assert "`read` on a .png / .jpg shows you the picture" in WORKSPACE_SYSTEM
    assert "pdftoppm" in WORKSPACE_SYSTEM and "screenshot" in WORKSPACE_SYSTEM
    assert "at most 8 pictures" in WORKSPACE_SYSTEM
    assert "counting pages is not looking" in WORKSPACE_SYSTEM


@pytest.mark.parametrize(
    ("tool", "args", "hit"),
    [
        ("write", {"path": "/workspace/outputs/周报.html", "content": "<h1>x</h1>"}, True),
        ("write", {"path": "/workspace/work/build.py", "content": 'doc.save("/workspace/outputs/通知.docx")'}, True),
        ("bash", {"command": "soffice --headless --convert-to pdf --outdir /workspace/outputs a.docx"}, True),
        ("bash", {"command": "python /workspace/work/build.py"}, False),
        ("write", {"path": "/workspace/outputs/data.csv", "content": "a,b"}, False),
        ("write", {"path": "/workspace/work/content_01.json", "content": "{}"}, False),
        ("read", {"path": "/workspace/outputs/通知.docx"}, False),
    ],
)
def test_visual_output_call(tool: str, args: dict[str, Any], hit: bool) -> None:
    assert visual_output_call(tool, args) is hit


def test_look_read_call() -> None:
    assert look_read_call("read", {"path": "/workspace/work/look/p-1.png"})
    assert look_read_call("read", {"path": "/workspace/outputs/chart.JPG"})
    assert not look_read_call("read", {"path": "/workspace/attachments/学生作文.jpg"})
    assert not look_read_call("read", {"path": "/workspace/outputs/a.docx"})
    assert not look_read_call("bash", {"command": "ls p-1.png"})


def _call(cid: str, tool: str, args: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {"type": "tool_execution_start", "toolName": tool, "toolCallId": cid, "args": args},
        {
            "type": "tool_execution_end",
            "toolName": tool,
            "toolCallId": cid,
            "isError": False,
            "result": {"content": [{"type": "text", "text": "ok"}]},
        },
    ]


def _script(*calls: list[dict[str, Any]]) -> list[dict[str, Any]]:
    done = {"role": "assistant", "content": [{"type": "text", "text": "做好了。"}]}
    out: list[dict[str, Any]] = [{"type": "agent_start"}, {"type": "turn_start"}]
    for c in calls:
        out.extend(c)
    return out + [
        {"type": "message_end", "message": done},
        {"type": "turn_end", "message": done},
        {"type": "agent_end", "willRetry": False, "messages": []},
    ]


async def _no_land(**_kw: Any) -> list[tuple[str, dict[str, Any]]]:
    return []


async def _run(
    monkeypatch: pytest.MonkeyPatch,
    transport: FakeTransport,
    *,
    workspace: bool = True,
    land: Any = _no_land,
):
    async def fake_list(_key: Any) -> dict[str, Any]:
        return {}

    monkeypatch.setattr(runner, "list_outputs", fake_list)
    monkeypatch.setattr(runner, "land_outputs", land)
    if workspace:
        transport.runner = SimpleNamespace(key="ws-key")
    events: list[tuple[str, dict[str, Any]]] = []

    async def emit(kind: str, payload: dict[str, Any]) -> None:
        events.append((kind, payload))

    await run_true_pi_agent(
        prompt="做一份通知",
        principal=Principal(),
        emit=emit,
        is_cancelled=_not_cancelled,
        caps=RunCaps(min_artifacts=0, max_seconds=8),
        transport=transport,
        run_id="look-t",
    )
    return events


def _steers(transport: FakeTransport) -> list[str]:
    return [str(c.get("message")) for c in transport.sent if c.get("type") == "steer"]


@pytest.mark.asyncio
async def test_steers_once_when_a_teacher_file_is_made(monkeypatch: pytest.MonkeyPatch) -> None:
    transport = FakeTransport(
        scripted=_script(
            _call("c1", "write", {"path": "/workspace/outputs/a.html", "content": "<p>1</p>"}),
            _call("c2", "write", {"path": "/workspace/outputs/b.html", "content": "<p>2</p>"}),
            _call("c3", "read", {"path": "/workspace/work/look/a.png"}),
        )
    )
    events = await _run(monkeypatch, transport)
    assert _steers(transport) == [LOOK_STEER]
    assert [k for k, _ in events].count("run.look_check") == 1


@pytest.mark.asyncio
async def test_no_steer_without_a_teacher_file(monkeypatch: pytest.MonkeyPatch) -> None:
    transport = FakeTransport(scripted=_script(_call("c1", "bash", {"command": "ls /workspace"})))
    events = await _run(monkeypatch, transport)
    assert _steers(transport) == []
    assert "run.look_check" not in [k for k, _ in events]


@pytest.mark.asyncio
async def test_no_steer_outside_the_workspace(monkeypatch: pytest.MonkeyPatch) -> None:
    transport = FakeTransport(
        scripted=_script(_call("c1", "write", {"path": "/workspace/outputs/a.html", "content": "x"}))
    )
    await _run(monkeypatch, transport, workspace=False)
    assert _steers(transport) == []


@pytest.mark.asyncio
async def test_a_failed_steer_never_fails_the_run(monkeypatch: pytest.MonkeyPatch) -> None:
    from pico_orchestrator.true_pi.client import TruePiRpcClient

    async def broken_steer(self: Any, message: str) -> None:
        raise TimeoutError

    monkeypatch.setattr(TruePiRpcClient, "steer", broken_steer)
    transport = FakeTransport(
        scripted=_script(_call("c1", "write", {"path": "/workspace/outputs/a.html", "content": "x"}))
    )
    events = await _run(monkeypatch, transport)
    kinds = [k for k, _ in events]
    assert "run.look_check" not in kinds
    assert "run.error" not in kinds


# pico#1297: a landed file nobody looked at → the reply says so plainly.


async def _final_text(monkeypatch: pytest.MonkeyPatch, *calls: list[dict[str, Any]]) -> str:
    async def fake_land(**_kw: Any) -> list[tuple[str, dict[str, Any]]]:
        return [("workspace_output", {"title": "a.html", "bytes": 3, "via": "workspace"})]

    transport = FakeTransport(scripted=_script(*calls))
    events = await _run(monkeypatch, transport, land=fake_land)
    texts = [p.get("text", "") for k, p in events if k == "message.delta"]
    return texts[-1] if texts else ""


@pytest.mark.asyncio
async def test_unlooked_file_is_owned_up_to(monkeypatch: pytest.MonkeyPatch) -> None:
    text = await _final_text(
        monkeypatch, _call("c1", "write", {"path": "/workspace/outputs/a.html", "content": "x"})
    )
    assert text.startswith("做好了。")
    assert UNLOOKED_NOTE in text


@pytest.mark.asyncio
async def test_looked_file_gets_no_note(monkeypatch: pytest.MonkeyPatch) -> None:
    text = await _final_text(
        monkeypatch,
        _call("c1", "write", {"path": "/workspace/outputs/a.html", "content": "x"}),
        _call("c2", "read", {"path": "/workspace/work/look/a.png"}),
    )
    assert text.startswith("做好了。")
    assert UNLOOKED_NOTE not in text


def test_note_unlooked() -> None:
    assert note_unlooked("好了", made_file=False, looked=0) == "好了"
    assert note_unlooked("好了", made_file=True, looked=2) == "好了"
    once = note_unlooked("好了", made_file=True, looked=0)
    assert once == f"好了\n\n{UNLOOKED_NOTE}"
    assert note_unlooked(once, made_file=True, looked=0) == once
    assert note_unlooked("", made_file=True, looked=0) == UNLOOKED_NOTE


@pytest.mark.asyncio
async def test_unlooked_note_reaches_the_live_bubble(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_land(**_kw: Any) -> list[tuple[str, dict[str, Any]]]:
        return [("workspace_output", {"title": "a.html", "bytes": 3, "via": "workspace"})]

    streamed = [{"type": "text_delta", "delta": "做好了。"}]
    transport = FakeTransport(
        scripted=_script(
            _call("c1", "write", {"path": "/workspace/outputs/a.html", "content": "x"}), streamed
        )
    )
    events = await _run(monkeypatch, transport, land=fake_land)
    live = "".join(p.get("text", "") for k, p in events if k == "message.stream")
    assert live == f"做好了。\n\n{UNLOOKED_NOTE}"


def test_reply_rules_ask_for_basis_and_no_unchecked_claims() -> None:
    from pico_orchestrator.true_pi.runtime import pico_system_text

    text = pico_system_text()
    assert "**依据**" in text
    assert "your own knowledge" in text and "check the facts" in text
    assert "No guarantees you did not check" in text
