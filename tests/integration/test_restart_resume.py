"""#1133: workspace runs cut off by a pico-api restart resume in the same Pi session."""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "api"))
sys.path.insert(0, str(ROOT / "services" / "orchestrator"))

from app import run_resume
from app.auth import Principal
from app.db import EventRow, RunRow, TaskRow, init_db, new_id, session_factory
from app.run_service import reconcile_orphaned_runs
from app.settings import get_settings
from pico_orchestrator.run_types import RunCaps, RunResult
from sqlalchemy import select


def _principal() -> Principal:
    return Principal(
        school_id="school-a",
        membership_id="member-a",
        scopes=["pico:chat"],
        iss="edu",
        aud="pico",
        exp=int(time.time()) + 3600,
        raw={"points_allowance": 100},
    )


@pytest.fixture
async def db(tmp_path, monkeypatch):
    monkeypatch.setenv("PICO_DATABASE_URL", f"sqlite+aiosqlite:///{tmp_path / 'resume.db'}")
    monkeypatch.setenv("PICO_RUNNER_URL", "http://runner.test:18790")
    monkeypatch.delenv("PICO_RUNNER_MEMBERSHIPS", raising=False)
    monkeypatch.delenv("PICO_RUN_RESTART_RESUME_MAX", raising=False)
    from app import db as dbmod

    get_settings.cache_clear()
    dbmod._engine = None
    dbmod._Session = None
    monkeypatch.setattr(run_resume, "_shutting_down", False)
    await init_db()
    yield session_factory()
    get_settings.cache_clear()


def _spec(**over: Any) -> dict[str, Any]:
    caps = RunCaps(max_seconds=21_600, min_artifacts=1, ui_model="pico-deep", images=[{"x": 1}])
    spec = run_resume.build_spec(caps=caps, principal=_principal(), conversation_id="conv-1", task_id="t")
    assert spec is not None
    spec.update(over)
    return spec


async def _add_run(factory, *, spec: dict[str, Any] | None, cancel: int = 0) -> tuple[str, str]:
    async with factory() as session:
        task = TaskRow(id=new_id(), school_id="school-a", membership_id="member-a", title="long")
        blob = {"skill_snapshot": {"id": "s"}}
        if spec is not None:
            spec = {**spec, "task_id": task.id}
            blob[run_resume.SPEC_KEY] = spec
        run = RunRow(
            id=new_id(),
            task_id=task.id,
            status="running",
            prompt="做 20 页 PPT",
            cancel_requested=cancel,
            token_usage_json=json.dumps(blob),
        )
        session.add_all((task, run))
        await session.commit()
        return task.id, run.id


async def _events(factory, run_id: str, kind: str) -> list[dict[str, Any]]:
    async with factory() as session:
        rows = (
            await session.execute(select(EventRow).where(EventRow.run_id == run_id, EventRow.type == kind))
        ).scalars()
        return [r.payload for r in rows]


def test_spec_needs_workspace_and_conversation(monkeypatch) -> None:
    caps = RunCaps(images=[{"b64": "x"}])
    monkeypatch.setenv("PICO_RUNNER_URL", "http://runner.test:18790")
    monkeypatch.delenv("PICO_RUNNER_MEMBERSHIPS", raising=False)
    spec = run_resume.build_spec(caps=caps, principal=_principal(), conversation_id="c", task_id="t")
    assert spec is not None
    assert "images" not in spec["caps"] and "millipoints_for_usage" not in spec["caps"]
    assert spec["principal"]["raw"] == {"points_allowance": 100}
    json.dumps(spec)
    assert run_resume.build_spec(caps=caps, principal=_principal(), conversation_id=None, task_id="t") is None
    monkeypatch.delenv("PICO_RUNNER_URL")
    assert run_resume.build_spec(caps=caps, principal=_principal(), conversation_id="c", task_id="t") is None


@pytest.mark.asyncio
async def test_reconcile_leaves_resumable_runs_running(db) -> None:
    _, keep = await _add_run(db, spec=_spec())
    _, stopped = await _add_run(db, spec=_spec(), cancel=1)
    _, old = await _add_run(db, spec=_spec(started=time.time() - 30_000))
    _, plain = await _add_run(db, spec=None)
    async with db() as session:
        counts = await reconcile_orphaned_runs(session)
    assert counts == {"cancelled": 1, "failed": 2, "resumable": 1}
    async with db() as session:
        assert (await session.get(RunRow, keep)).status == "running"
        assert (await session.get(RunRow, stopped)).status == "cancelled"
        assert (await session.get(RunRow, old)).status == "failed"
        assert (await session.get(RunRow, plain)).status == "failed"


@pytest.mark.asyncio
async def test_restart_resume_off_is_the_old_failure(db, monkeypatch) -> None:
    monkeypatch.setenv("PICO_RUN_RESTART_RESUME_MAX", "0")
    get_settings.cache_clear()
    await _add_run(db, spec=_spec())
    async with db() as session:
        counts = await reconcile_orphaned_runs(session)
    assert counts["failed"] == 1 and counts["resumable"] == 0
    assert await run_resume.resume_orphaned_runs() == 0


@pytest.mark.asyncio
async def test_resume_budget_runs_out(db) -> None:
    _, run_id = await _add_run(db, spec=_spec())
    async with db() as session:
        for _ in range(2):
            from app.db import append_event

            await append_event(session, run_id, "run.resume", {"reason": "api.restart"}, commit=False)
        await append_event(session, run_id, "run.resume", {"reason": "upstream"}, commit=False)
        await session.commit()
    async with db() as session:
        counts = await reconcile_orphaned_runs(session)
    assert counts["failed"] == 1


@pytest.mark.asyncio
async def test_startup_resumes_in_the_same_session(db, monkeypatch) -> None:
    task_id, run_id = await _add_run(db, spec=_spec())
    calls: list[dict[str, Any]] = []

    async def fake_runtime(**kw: Any) -> RunResult:
        calls.append(kw)
        await kw["emit"]("message.stream", {"text": "x"})
        await kw["emit"]("tool.result", {"tool": "workspace_output", "ok": True})
        return RunResult(status="succeeded", final_text="做好了，20 页。")

    async def no_wait() -> None:
        return None

    import pico_orchestrator.runtime as rt

    monkeypatch.setattr(rt, "run_agent_runtime", fake_runtime)
    monkeypatch.setattr(run_resume, "_wait_runner", no_wait)
    assert await run_resume.resume_orphaned_runs() == 1
    resumes = await _events(db, run_id, "run.resume")
    assert resumes == [
        {"reason": "api.restart", "attempt": 1, "max": 2, "user_message": run_resume.TEACHER_NOTE}
    ]
    import asyncio

    from app.run_service import _inflight_run_tasks

    await asyncio.gather(*list(_inflight_run_tasks))
    assert len(calls) == 1
    kw = calls[0]
    assert kw["run_id"] == run_id and kw["conversation_id"] == "conv-1"
    assert kw["prompt"] == run_resume.RESTART_PROMPT
    assert kw["persist_pi_session"] is True and kw["history"] is None
    caps = kw["caps"]
    assert caps.ui_model == "pico-deep" and caps.min_artifacts == 1 and caps.images is None
    assert caps.outputs_since > 0 and caps.millipoints_for_usage is not None
    assert kw["principal"].membership_id == "member-a"
    async with db() as session:
        run = await session.get(RunRow, run_id)
        assert run.status == "succeeded"
        blob = json.loads(run.token_usage_json)
        assert run_resume.SPEC_KEY not in blob and blob["skill_snapshot"] == {"id": "s"}
    assert not await _events(db, run_id, "message.stream")
    assert await _events(db, run_id, "tool.result")
    assert task_id


@pytest.mark.asyncio
async def test_shutdown_keeps_resumable_run_running(db, monkeypatch) -> None:
    _, run_id = await _add_run(db, spec=_spec())
    assert await run_resume.keep_for_resume(run_id) is True
    assert await _events(db, run_id, "run.interrupted") == [{"reason": "api.restart"}]
    _, plain = await _add_run(db, spec=None)
    assert await run_resume.keep_for_resume(plain) is False
    async with db() as session:
        assert (await session.get(RunRow, run_id)).status == "running"
