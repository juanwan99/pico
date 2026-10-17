"""pico#1296 look cap, after pico#1320 slimmed the rules.

Pico no longer orders the model to look at its files, and no longer appends
notes to the reply. What stays: `read` on a picture works, and the hard cap of
8 pictures / 2 rounds (owner 10-16) with one steer when it is hit.
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

from pico_orchestrator.run_types import RunCaps
from pico_orchestrator.true_pi import runner
from pico_orchestrator.true_pi.client import FakeTransport
from pico_orchestrator.true_pi.runner import (
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


def test_workspace_rules_are_facts_not_orders() -> None:
    assert "`read` on a .png / .jpg shows you the picture" in WORKSPACE_SYSTEM
    assert "/workspace/outputs/" in WORKSPACE_SYSTEM
    assert "Look at what you made" not in WORKSPACE_SYSTEM
    assert len(WORKSPACE_SYSTEM) < 1200


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


def _script(*calls: list[dict[str, Any]], final: str = "做好了。") -> list[dict[str, Any]]:
    done = {"role": "assistant", "content": [{"type": "text", "text": final}]}
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
async def test_no_look_steer_when_a_teacher_file_is_made(monkeypatch: pytest.MonkeyPatch) -> None:
    transport = FakeTransport(
        scripted=_script(
            _call("c1", "write", {"path": "/workspace/outputs/a.html", "content": "<p>1</p>"}),
        )
    )
    events = await _run(monkeypatch, transport)
    assert _steers(transport) == []
    assert "run.look_check" not in [k for k, _ in events]


async def _final_text(monkeypatch: pytest.MonkeyPatch, *calls: list[dict[str, Any]], final: str) -> str:
    async def fake_land(**_kw: Any) -> list[tuple[str, dict[str, Any]]]:
        return [("workspace_output", {"title": "a.html", "bytes": 3, "via": "workspace"})]

    transport = FakeTransport(scripted=_script(*calls, final=final))
    events = await _run(monkeypatch, transport, land=fake_land)
    texts = [p.get("text", "") for k, p in events if k == "message.delta"]
    return texts[-1] if texts else ""


@pytest.mark.asyncio
async def test_reply_stands_as_written(monkeypatch: pytest.MonkeyPatch) -> None:
    reply = "做好了，共三页。\n步骤 1：打开文件\n依据：按《某某指南》整理。"
    text = await _final_text(
        monkeypatch,
        _call("c1", "write", {"path": "/workspace/outputs/a.html", "content": "x"}),
        final=reply,
    )
    assert text == reply


def test_reply_rules_keep_one_basis_line() -> None:
    from pico_orchestrator.true_pi.runtime import pico_system_text

    text = pico_system_text()
    assert "where its content came from" in text
    assert "ask_user" not in text and "2–5" not in text
    assert "captcha" not in text.lower() and "human-only" not in text.lower()


# pico#1296 hard cap: 8 pictures or 2 rounds, then the box answers a picture read with text.


def _look(state: Any, path: str = "/workspace/work/look/p-1.png") -> None:
    state.look_call("read", {"path": path})


def test_look_cap_after_eight_pictures() -> None:
    from pico_orchestrator.true_pi.events import EventMapState

    state = EventMapState()
    for _ in range(9):
        _look(state)
    assert (state.look_reads, state.look_rounds, state.look_capped) == (8, 1, 1)


def test_look_cap_on_a_third_round() -> None:
    from pico_orchestrator.true_pi.events import EventMapState

    state = EventMapState()
    _look(state)
    state.look_call("bash", {"command": "pdftoppm -r 90 -png -f 2 -l 2 a.pdf p"})
    _look(state)  # re-rendering is not a fix: same round
    state.look_call("edit", {"path": "/workspace/work/content_01.json"})
    _look(state)
    state.look_call("write", {"path": "/workspace/work/content_02.json", "content": "{}"})
    _look(state)
    _look(state, "/workspace/attachments/学生作文.jpg")  # the teacher's picture is not a look
    assert (state.look_reads, state.look_rounds, state.look_capped) == (3, 2, 1)


def test_look_cap_rule_matches_the_box_extension() -> None:
    from pathlib import Path

    from pico_orchestrator.true_pi.config import look_cap_extension_path
    from pico_orchestrator.true_pi.runner import (
        LOOK_CAP_TEXT,
        LOOK_MAX_PICTURES,
        LOOK_MAX_ROUNDS,
    )

    ts = Path(look_cap_extension_path()).read_text(encoding="utf-8")
    assert f"const MAX_PICTURES = {LOOK_MAX_PICTURES};" in ts
    assert f"const MAX_ROUNDS = {LOOK_MAX_ROUNDS};" in ts
    assert f'const CAP_TEXT = "{LOOK_CAP_TEXT}";' in ts
    assert '"write" || event.toolName === "edit"' in ts and "/attachments/" in ts


@pytest.mark.asyncio
async def test_steers_once_when_the_look_cap_is_hit(monkeypatch: pytest.MonkeyPatch) -> None:
    from pico_orchestrator.true_pi.runner import LOOK_CAP_STEER

    reads = [_call(f"r{i}", "read", {"path": f"/workspace/work/look/p-{i}.png"}) for i in range(10)]
    transport = FakeTransport(
        scripted=_script(
            _call("c1", "write", {"path": "/workspace/outputs/a.docx", "content": "x"}), *reads
        )
    )
    events = await _run(monkeypatch, transport)
    assert _steers(transport) == [LOOK_CAP_STEER]
    caps = [p for k, p in events if k == "run.look_cap"]
    assert len(caps) == 1 and caps[0]["capped"] == 1


@pytest.mark.asyncio
async def test_no_cap_steer_within_the_cap(monkeypatch: pytest.MonkeyPatch) -> None:
    reads = [_call(f"r{i}", "read", {"path": f"/workspace/work/look/p-{i}.png"}) for i in range(8)]
    transport = FakeTransport(
        scripted=_script(
            _call("c1", "write", {"path": "/workspace/outputs/a.docx", "content": "x"}), *reads
        )
    )
    events = await _run(monkeypatch, transport)
    assert _steers(transport) == []
    assert "run.look_cap" not in [k for k, _ in events]
