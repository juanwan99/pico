"""latest_runs_for_tasks picks newest run per task."""

from __future__ import annotations

from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "api"))

from app.db import RunRow, TaskRow, init_db, new_id, session_factory
from app.run_service import latest_runs_for_tasks
from app.settings import get_settings


@pytest.mark.asyncio
async def test_latest_runs_for_tasks_picks_newest(tmp_path, monkeypatch) -> None:
    db = tmp_path / "latest-runs.db"
    monkeypatch.setenv("PICO_DATABASE_URL", f"sqlite+aiosqlite:///{db}")
    from app import db as dbmod

    get_settings.cache_clear()
    dbmod._engine = None
    dbmod._Session = None
    await init_db()
    factory = session_factory()

    async with factory() as session:
        t1 = TaskRow(
            id=new_id(),
            school_id="school-a",
            membership_id="m1",
            title="t1",
        )
        t2 = TaskRow(
            id=new_id(),
            school_id="school-a",
            membership_id="m1",
            title="t2",
        )
        session.add_all([t1, t2])
        await session.flush()
        old = RunRow(id=new_id(), task_id=t1.id, status="succeeded")
        new = RunRow(id=new_id(), task_id=t1.id, status="running")
        other = RunRow(id=new_id(), task_id=t2.id, status="failed")
        session.add_all([old, new, other])
        await session.commit()

        latest = await latest_runs_for_tasks(session, [t1.id, t2.id, "missing"])
        assert set(latest) == {t1.id, t2.id}
        assert latest[t1.id].status == "running"
        assert latest[t1.id].id == new.id
        assert latest[t2.id].status == "failed"
