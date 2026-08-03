"""P-DAYUSE-100 REVISE: started_at on running runs + S7 change_proposal finalize."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "api"))
sys.path.insert(0, str(ROOT / "services" / "orchestrator"))


@pytest.mark.asyncio
async def test_ledger_task_run_sets_started_at_when_running(tmp_path, monkeypatch):
    from app import db as db_mod
    from app.auth import Principal
    from app.openai_compat import _ledger_task_run

    db_path = tmp_path / "pico.db"
    monkeypatch.setenv("PICO_DATABASE_URL", f"sqlite+aiosqlite:///{db_path}")
    # reset engine
    db_mod._engine = None
    db_mod._Session = None

    principal = Principal(
        school_id="school-a",
        membership_id="m1",
        scopes=["ai:run", "ai:read", "ai:confirm"],
        iss="t",
        aud="pico-api",
        exp=9999999999,
        raw={},
    )
    task_id, run_id = await _ledger_task_run(
        principal=principal,
        prompt="hello",
        model="pico-agent",
        conversation_id="c1",
        workspace_id=None,
        status="running",
    )
    assert task_id and run_id
    factory = db_mod.session_factory()
    async with factory() as session:
        run = await session.get(db_mod.RunRow, run_id)
        assert run is not None
        assert run.status == "running"
        assert run.started_at is not None


@pytest.mark.asyncio
async def test_finalize_persists_tool_change_proposal(tmp_path, monkeypatch):
    from app import db as db_mod
    from app.auth import Principal
    from app.db import ChangeProposalRow, RunRow
    from app.openai_compat import _finalize_run, _ledger_task_run

    db_path = tmp_path / "pico.db"
    monkeypatch.setenv("PICO_DATABASE_URL", f"sqlite+aiosqlite:///{db_path}")
    db_mod._engine = None
    db_mod._Session = None

    principal = Principal(
        school_id="school-a",
        membership_id="m1",
        scopes=["ai:run", "ai:read", "ai:confirm"],
        iss="t",
        aud="pico-api",
        exp=9999999999,
        raw={},
    )
    task_id, run_id = await _ledger_task_run(
        principal=principal,
        prompt="propose",
        model="pico-agent",
        conversation_id=None,
        workspace_id=None,
    )
    await _finalize_run(
        run_id,
        status="succeeded",
        final_text="ok",
        task_id=task_id,
        change_proposal={
            "proposal": {
                "title": "REVISE-S7-TEST",
                "summary": "audit only",
                "payload": {"k": 1},
            }
        },
    )
    factory = db_mod.session_factory()
    async with factory() as session:
        from sqlalchemy import select

        rows = (
            await session.execute(
                select(ChangeProposalRow).where(ChangeProposalRow.run_id == run_id)
            )
        ).scalars().all()
        assert len(rows) == 1
        assert rows[0].title == "REVISE-S7-TEST"
        assert rows[0].status == "proposed"
        run = await session.get(RunRow, run_id)
        assert run is not None
        assert run.ended_at is not None
        assert run.status == "succeeded"
