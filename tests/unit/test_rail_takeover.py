"""#1250 ②: a teacher's new message stops the still-running turn of the same conversation.

Live 10-14: the old box held the workspace, the new turn waited ~65 s on the
outputs snapshot (10×0.5 s + 30×2 s on 409) and was then refused
``runner.workspace_busy``. The new turn now cancels the old one first.
"""

from __future__ import annotations

import inspect
import sys
from pathlib import Path

import pytest
from sqlalchemy import select

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "api"))
sys.path.insert(0, str(ROOT / "services" / "orchestrator"))


async def _boot(tmp_path, monkeypatch):
    from app import db as db_mod
    from app.db import init_db
    from app.settings import get_settings

    monkeypatch.setenv("PICO_DATABASE_URL", f"sqlite+aiosqlite:///{tmp_path / 'takeover.db'}")
    get_settings.cache_clear()
    db_mod._engine = None
    db_mod._Session = None
    await init_db()
    return db_mod.session_factory()


async def _add(factory, *, school="s1", member="m1", conv="c1", status="running") -> str:
    from app.db import RunRow, TaskRow, new_id

    task_id, run_id = new_id(), new_id()
    async with factory() as session:
        session.add(
            TaskRow(
                id=task_id, school_id=school, membership_id=member, title="t", conversation_id=conv
            )
        )
        session.add(
            RunRow(id=run_id, task_id=task_id, status=status, prompt="p", model="pico-fast")
        )
        await session.commit()
    return run_id


async def _status(factory, run_id: str) -> tuple[str, int]:
    from app.db import RunRow

    async with factory() as session:
        run = await session.get(RunRow, run_id)
        return run.status, int(run.cancel_requested or 0)


@pytest.mark.asyncio
async def test_cancels_only_this_teachers_active_runs_in_conversation(tmp_path, monkeypatch):
    from app.run_service import cancel_active_runs_for_conversation

    factory = await _boot(tmp_path, monkeypatch)
    old = await _add(factory)
    queued = await _add(factory, status="queued")
    done = await _add(factory, status="succeeded")
    other_conv = await _add(factory, conv="c2")
    other_member = await _add(factory, member="m2")
    other_school = await _add(factory, school="s2")

    async with factory() as session:
        results = await cancel_active_runs_for_conversation(
            session, school_id="s1", membership_id="m1", conversation_id="c1"
        )
    assert {str(r.run.id) for r in results} == {old, queued}
    assert await _status(factory, old) == ("cancelled", 1)
    assert await _status(factory, queued) == ("cancelled", 1)
    assert (await _status(factory, done))[0] == "succeeded"
    for rid in (other_conv, other_member, other_school):
        assert await _status(factory, rid) == ("running", 0)


@pytest.mark.asyncio
async def test_no_conversation_cancels_nothing(tmp_path, monkeypatch):
    from app.run_service import cancel_active_runs_for_conversation

    factory = await _boot(tmp_path, monkeypatch)
    rid = await _add(factory, conv=None)
    async with factory() as session:
        assert (
            await cancel_active_runs_for_conversation(
                session, school_id="s1", membership_id="m1", conversation_id=""
            )
            == []
        )
    assert await _status(factory, rid) == ("running", 0)


@pytest.mark.asyncio
async def test_supersede_writes_stop_events_and_releases_ask(tmp_path, monkeypatch):
    from app import openai_compat
    from app.auth import Principal
    from app.db import EventRow

    factory = await _boot(tmp_path, monkeypatch)
    old = await _add(factory)
    released: list[str] = []
    from pico_orchestrator import ask_user

    monkeypatch.setattr(ask_user, "cancel", lambda rid: released.append(rid))
    principal = Principal(
        school_id="s1", membership_id="m1", scopes=["ai:run"], iss="t", aud="t", exp=0, raw={}
    )

    assert await openai_compat._supersede_active_turns(principal, "c1") == 1
    assert released == [old]
    async with factory() as session:
        events = (
            (await session.execute(select(EventRow).where(EventRow.run_id == old))).scalars().all()
        )
    types = [e.type for e in events]
    assert "run.cancel_requested" in types and "run.status" in types
    # A second new message finds nothing left to stop.
    assert await openai_compat._supersede_active_turns(principal, "c1") == 0
    assert await openai_compat._supersede_active_turns(principal, None) == 0


@pytest.mark.asyncio
async def test_supersede_failure_never_blocks_new_turn(tmp_path, monkeypatch):
    from app import openai_compat, run_service
    from app.auth import Principal

    await _boot(tmp_path, monkeypatch)

    async def boom(*_a, **_k):
        raise RuntimeError("db gone")

    monkeypatch.setattr(run_service, "cancel_active_runs_for_conversation", boom)
    principal = Principal(
        school_id="s1", membership_id="m1", scopes=["ai:run"], iss="t", aud="t", exp=0, raw={}
    )
    assert await openai_compat._supersede_active_turns(principal, "c1") == 0


def test_agent_paths_supersede_before_ledger_row():
    """Both agent entries stop the old turn; the direct path never does."""
    from app import openai_compat

    src = inspect.getsource(openai_compat.chat_completions)
    assert src.count("_supersede_active_turns(principal, conversation_id)") == 2
    non_stream = src.index("if not use_direct:\n            await _supersede_active_turns")
    assert non_stream < src.index("task_id, run_id = await _ledger_task_run(", non_stream)
    stream = src.index("await init_db()\n        await _supersede_active_turns")
    assert stream < src.index("TaskRow(", stream)
