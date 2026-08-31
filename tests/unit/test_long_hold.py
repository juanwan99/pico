"""T-LONG-HOLD: official Pi compact + pinned session tree, no self-built memory OS."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "api"))
sys.path.insert(0, str(ROOT / "services" / "orchestrator"))

from pico_orchestrator.run_types import RunCaps
from pico_orchestrator.true_pi.client import FakeTransport, RpcEvent, SubprocessTransport
from pico_orchestrator.true_pi.config import persist_session_file
from pico_orchestrator.true_pi.events import (
    COMPACTION_END_HUMAN,
    COMPACTION_HUMAN,
    EventMapState,
    map_event,
)
from pico_orchestrator.true_pi.runtime import _compose_prompt, run_true_pi_agent


class Principal:
    def __init__(self, school_id: str = "school-a", membership_id: str = "member-a") -> None:
        self.school_id = school_id
        self.membership_id = membership_id
        self.scopes = ["ai:run"]


async def _not_cancelled() -> bool:
    return False


def test_same_conversation_pins_same_session_file(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("PICO_TRUE_PI_SESSION_ROOT", str(tmp_path))
    first = persist_session_file(school_id="school-a", conversation_id="convo-hold")
    second = persist_session_file(school_id="school-a", conversation_id="convo-hold")
    other = persist_session_file(school_id="school-a", conversation_id="convo-other")
    assert first is not None and second is not None and other is not None
    assert first == second
    assert first.name == "pico.jsonl"
    assert first != other


def test_spawn_pins_session_not_most_recent_continue() -> None:
    session_file = Path("/tmp/pico-hold/pico.jsonl")
    t = SubprocessTransport(
        session_dir=Path("/tmp/pico-hold"),
        tool_url="http://127.0.0.1:1",
        tool_token="tok",
        run_id="r-hold",
        continue_session=True,
        session_file=session_file,
    )
    cmd = t.spawn_command()
    assert cmd[cmd.index("--session") + 1] == str(session_file)
    assert "--continue" not in cmd


def test_follow_up_prompt_stays_teacher_original() -> None:
    text = _compose_prompt(
        prompt="把刚才那份通知第三段改短",
        skill="",
        min_arts=0,
        history=[
            {"role": "user", "content": "写一份家长会通知.docx"},
            {"role": "assistant", "content": "已写家长会通知.docx"},
        ],
        allowed_tools=["edit_docx_document"],
    )
    assert text == "把刚才那份通知第三段改短"
    assert "家长会通知.docx" not in text
    assert "Recent conversation" not in text


@pytest.mark.asyncio
async def test_compaction_keeps_current_files_and_does_not_settle() -> None:
    events: list[tuple[str, dict[str, Any]]] = []

    async def emit(k: str, p: dict[str, Any]) -> None:
        events.append((k, p))

    state = EventMapState()
    await map_event(
        RpcEvent(
            {
                "type": "compaction_start",
                "reason": "threshold",
            }
        ),
        emit=emit,
        state=state,
    )
    await map_event(
        RpcEvent(
            {
                "type": "compaction_end",
                "reason": "threshold",
                "willRetry": True,
                "result": {
                    "summary": "prior turns",
                    "firstKeptEntryId": "kept-1",
                    "details": {
                        "readFiles": ["家长会通知.docx"],
                        "modifiedFiles": ["家长会通知.docx"],
                    },
                },
            }
        ),
        emit=emit,
        state=state,
    )
    assert state.settled is False
    assert COMPACTION_HUMAN == "在整理上文"
    begin = next(p for k, p in events if k == "compaction.begin")
    end = next(p for k, p in events if k == "compaction.end")
    assert begin["text"] == COMPACTION_HUMAN
    assert end["text"] == COMPACTION_END_HUMAN
    assert end["modifiedFiles"] == ["家长会通知.docx"]
    assert end["firstKeptEntryId"] == "kept-1"
    assert end["will_retry"] is True
    assert not any(k == "message.delta" for k, _ in events)


@pytest.mark.asyncio
async def test_after_compact_follow_up_is_current_question() -> None:
    events: list[tuple[str, dict[str, Any]]] = []

    async def emit(k: str, p: dict[str, Any]) -> None:
        events.append((k, p))

    transport = FakeTransport(
        scripted=[
            {"type": "agent_start"},
            {"type": "compaction_start", "reason": "threshold"},
            {
                "type": "compaction_end",
                "reason": "threshold",
                "willRetry": False,
                "result": {
                    "details": {"modifiedFiles": ["家长会通知.docx"]},
                },
            },
            {
                "type": "message_end",
                "message": {
                    "role": "assistant",
                    "content": "第三段已改短，还是这份家长会通知.docx。",
                },
            },
            {"type": "agent_end", "willRetry": False},
        ],
        assistant_text="第三段已改短，还是这份家长会通知.docx。",
    )
    result = await run_true_pi_agent(
        prompt="把刚才那份通知第三段改短",
        principal=Principal(),
        emit=emit,
        is_cancelled=_not_cancelled,
        caps=RunCaps(min_artifacts=0, max_seconds=20),
        transport=transport,
        conversation_id="convo-hold",
        persist_pi_session=True,
    )
    assert result.status == "succeeded"
    assert "家长会通知.docx" in result.final_text
    assert COMPACTION_HUMAN not in result.final_text
    prompt_cmd = next(item for item in transport.sent if item.get("type") == "prompt")
    assert prompt_cmd.get("message") == "把刚才那份通知第三段改短"
    compact_kinds = [k for k, _ in events if k.startswith("compaction.")]
    assert "compaction.begin" in compact_kinds
    assert not any(
        k == "message.delta" and COMPACTION_HUMAN in str(p.get("text")) for k, p in events
    )
