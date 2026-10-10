"""#1158: a run the teacher stopped still meters what it spent before the stop.

The stop endpoint writes ``cancelled`` first; the runtime returns its usage
afterwards, so the finisher's claim misses. The meter must not miss with it.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
from sqlalchemy import select

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "api"))
sys.path.insert(0, str(ROOT / "services" / "orchestrator"))

USAGE = {"input": 120_000, "output": 3_000, "totalTokens": 123_000}


async def _boot(tmp_path, monkeypatch):
    from app import db as db_mod
    from app.db import RunRow, TaskRow, init_db, new_id
    from app.run_service import request_cancel
    from app.settings import get_settings

    monkeypatch.setenv("PICO_DATABASE_URL", f"sqlite+aiosqlite:///{tmp_path / 'stop.db'}")
    get_settings.cache_clear()
    db_mod._engine = None
    db_mod._Session = None
    await init_db()
    factory = db_mod.session_factory()
    task_id, run_id = new_id(), new_id()
    async with factory() as session:
        session.add(
            TaskRow(id=task_id, school_id="school-a", membership_id="m-stop", title="t")
        )
        session.add(
            RunRow(
                id=run_id,
                task_id=task_id,
                status="running",
                prompt="长任务",
                model="pico-fast",
                token_usage_json=json.dumps({"resume_spec": {"x": 1}}),
            )
        )
        await session.commit()
        run = await session.get(RunRow, run_id)
        await request_cancel(session, run)  # teacher presses stop
    return factory, task_id, run_id


async def _rows(factory, run_id):
    from app.db import RunRow, UsageEventRow

    async with factory() as session:
        run = await session.get(RunRow, run_id)
        rows = (
            await session.execute(select(UsageEventRow).where(UsageEventRow.run_id == run_id))
        ).scalars().all()
    return run, rows


@pytest.mark.asyncio
async def test_compat_finalize_after_stop_meters_usage(tmp_path, monkeypatch) -> None:
    from app.openai_compat import _finalize_run

    factory, task_id, run_id = await _boot(tmp_path, monkeypatch)
    await _finalize_run(
        run_id, status="cancelled", task_id=task_id, token_usage=USAGE, bill_to="school-a"
    )
    # A second finisher (stream teardown) must not add a second row.
    await _finalize_run(run_id, status="cancelled", task_id=task_id)

    run, rows = await _rows(factory, run_id)
    assert run.status == "cancelled"
    stored = json.loads(run.token_usage_json)
    assert stored["totalTokens"] == 123_000
    assert "resume_spec" not in stored
    assert len(rows) == 1
    assert rows[0].kind == "llm"
    assert rows[0].tokens_unknown in (0, False)
    assert rows[0].prompt_tokens == 120_000
    assert rows[0].completion_tokens == 3_000
    assert rows[0].school_id == "school-a" and rows[0].membership_id == "m-stop"


@pytest.mark.asyncio
async def test_finished_run_is_not_rebilled_as_stopped(tmp_path, monkeypatch) -> None:
    from app.db import RunRow
    from app.run_service import bill_stopped_run

    factory, _task_id, run_id = await _boot(tmp_path, monkeypatch)
    async with factory() as session:
        run = await session.get(RunRow, run_id)
        run.status = "succeeded"
        await session.commit()

    await bill_stopped_run(run_id, USAGE, source="run_service")

    _run, rows = await _rows(factory, run_id)
    assert rows == []


@pytest.mark.asyncio
async def test_stopped_pi_turn_reports_the_calls_it_already_paid_for() -> None:
    """Stop lands mid-tool, before Pi's agent_end and the 2nd turn_end (#1195).

    Pi emits the assistant message_end (with usage) before it runs the tools and
    turn_end only after them, so the 2nd call is paid for but its turn never ends.
    """
    import asyncio
    import time

    from pico_orchestrator.run_types import RunCaps
    from pico_orchestrator.true_pi.client import FakeTransport
    from pico_orchestrator.true_pi.runtime import run_true_pi_agent

    class P:
        school_id, membership_id, scopes = "school-a", "m-stop", ("ai:run",)

    call = {"role": "assistant", "content": [{"type": "text", "text": "写第一部分"}],
            "usage": {"input": 50_000, "output": 1_000, "totalTokens": 51_000}}
    transport = FakeTransport(
        scripted=[
            {"type": "agent_start"},
            {"type": "turn_start"},
            {"type": "message_end", "message": call},
            {"type": "turn_end", "message": call},
            {"type": "turn_start"},
            {"type": "message_end", "message": call},
            {"type": "tool_execution_start", "toolCallId": "t2", "toolName": "bash",
             "args": {"command": "python build_ppt.py"}},
        ]
    )
    stop_at = time.monotonic() + 0.4

    async def stopped() -> bool:
        return time.monotonic() >= stop_at

    async def emit(kind, payload) -> None:
        del kind, payload

    result = await asyncio.wait_for(
        run_true_pi_agent(
            prompt="长任务",
            principal=P(),
            emit=emit,
            is_cancelled=stopped,
            caps=RunCaps(min_artifacts=0, max_seconds=30),
            transport=transport,
            run_id="stop-usage",
        ),
        timeout=10,
    )
    assert result.status == "cancelled"
    assert result.token_usage and result.token_usage["total_tokens"] == 102_000
