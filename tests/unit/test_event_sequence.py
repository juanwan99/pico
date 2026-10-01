from __future__ import annotations

import pytest
from app import db as dbmod
from app.db import EventRow, RunRow, TaskRow, append_event, init_db, new_id, session_factory
from app.settings import get_settings
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError


@pytest.fixture()
async def event_db(tmp_path, monkeypatch):
    monkeypatch.setenv("PICO_DATABASE_URL", f"sqlite+aiosqlite:///{tmp_path / 'events.db'}")
    get_settings.cache_clear()
    dbmod._engine = None
    dbmod._Session = None
    await init_db()
    try:
        yield
    finally:
        assert dbmod._engine is not None
        await dbmod._engine.dispose()
        dbmod._engine = None
        dbmod._Session = None
        get_settings.cache_clear()


async def test_event_sequence_is_unique_and_foreign_keys_are_enabled(event_db):
    async with session_factory()() as session:
        task = TaskRow(id=new_id(), school_id="school-a", membership_id="member-a")
        run = RunRow(id=new_id(), task_id=task.id)
        session.add_all([task, run])
        await session.commit()

        first = await append_event(session, run.id, "run.status", {"status": "running"})
        second = await append_event(session, run.id, "run.status", {"status": "succeeded"})
        assert (first.seq, second.seq) == (1, 2)

        session.add(EventRow(run_id=run.id, seq=2, type="duplicate"))
        with pytest.raises(IntegrityError):
            await session.commit()
        await session.rollback()

        foreign_keys = await session.scalar(text("PRAGMA foreign_keys"))
        assert foreign_keys == 1
        session.add(EventRow(run_id=new_id(), seq=1, type="orphan"))
        with pytest.raises(IntegrityError):
            await session.commit()


async def test_concurrent_runs_never_lose_events_to_sqlite_busy(event_db):
    """#1135 32-box load test: 30+ runs emitting at once must queue on the write
    lock, not fail fast. A read-then-write (SELECT max(seq), then INSERT) upgrade
    is refused at once under WAL when another writer committed in between."""
    import asyncio

    runs = []
    async with session_factory()() as session:
        for _ in range(40):
            task = TaskRow(id=new_id(), school_id="school-a", membership_id="member-a")
            run = RunRow(id=new_id(), task_id=task.id)
            session.add_all([task, run])
            runs.append(run.id)
        await session.commit()

    async def emit_many(run_id: str) -> None:
        for i in range(30):
            async with session_factory()() as session:
                await append_event(session, run_id, "agent.step", {"i": i})

    results = await asyncio.gather(*(emit_many(r) for r in runs), return_exceptions=True)
    errors = [r for r in results if isinstance(r, BaseException)]
    assert not errors, f"{len(errors)} runs lost events: {errors[0]!r}"
    async with session_factory()() as session:
        for run_id in runs:
            seqs = (
                await session.scalars(
                    text("select seq from events where run_id = :r order by seq").bindparams(r=run_id)
                )
            ).all()
            assert seqs == list(range(1, 31))
