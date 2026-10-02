"""Turn label (#1151): Pi's compaction summary keeps no turn count; Pico stamps it per message."""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "api"))
sys.path.insert(0, str(ROOT / "services" / "orchestrator"))

from pico_orchestrator.run_types import RunCaps
from pico_orchestrator.true_pi.client import FakeTransport
from pico_orchestrator.true_pi.runtime import _compose_prompt, run_true_pi_agent


@dataclass
class Principal:
    school_id: str = "school-a"
    membership_id: str = "member-a"
    scopes: list[str] | None = None


async def _not_cancelled() -> bool:
    return False


async def _noop_emit(_k: str, _p: dict[str, Any]) -> None:
    return None


def _compose(turn_no: int) -> str:
    return _compose_prompt(
        prompt="信里加一个表格", skill="", min_arts=0, history=None, allowed_tools=[], turn_no=turn_no
    )


def test_label_leads_the_teacher_original() -> None:
    assert _compose(9) == "〔本对话第 9 轮〕\n信里加一个表格"
    assert _compose(0) == "信里加一个表格"


@pytest.mark.asyncio
async def test_pi_gets_the_label_once() -> None:
    transport = FakeTransport(
        scripted=[
            {"type": "agent_start"},
            {"type": "message_end", "message": {"role": "assistant", "content": "好的"}},
            {"type": "agent_end", "willRetry": False},
        ],
        assistant_text="好的",
    )
    await run_true_pi_agent(
        prompt="核实一下平均分",
        principal=Principal(),
        emit=_noop_emit,
        is_cancelled=_not_cancelled,
        caps=RunCaps(max_seconds=20, turn_no=9),
        transport=transport,
    )
    sent = [c["message"] for c in transport.sent if c.get("type") == "prompt"]
    assert sent == ["〔本对话第 9 轮〕\n核实一下平均分"]


@pytest.mark.asyncio
async def test_turn_counts_this_members_messages_in_the_conversation(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("PICO_DATABASE_URL", f"sqlite+aiosqlite:///{tmp_path / 'turn.db'}")
    from app import db as dbmod
    from app.db import TaskRow, init_db, new_id, session_factory
    from app.openai_compat import _caps_with_turn
    from app.settings import get_settings

    get_settings.cache_clear()
    dbmod._engine = None
    dbmod._Session = None
    await init_db()
    async with session_factory()() as session:
        for school, member, convo in [
            ("school-a", "member-a", "c1"),
            ("school-a", "member-a", "c1"),
            ("school-a", "member-a", "c1"),
            ("school-a", "member-a", "c2"),
            ("school-a", "member-b", "c1"),
            ("school-b", "member-a", "c1"),
        ]:
            session.add(TaskRow(id=new_id(), school_id=school, membership_id=member, conversation_id=convo))
        await session.commit()

    caps = await _caps_with_turn(RunCaps(), Principal(), "c1")
    assert caps.turn_no == 3
    assert (await _caps_with_turn(RunCaps(), Principal(), None)).turn_no == 0
