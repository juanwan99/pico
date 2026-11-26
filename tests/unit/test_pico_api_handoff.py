"""Exercise the production lifespan in two API processes sharing one SQLite ledger."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import socket
import subprocess
import sys
import time
from contextlib import ExitStack
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[2]
logger = logging.getLogger(__name__)


def _serve(port: int, events_file: Path) -> None:
    import uvicorn
    from app import automation_service, main, run_resume
    from app.auth import Principal
    from app.db import EventRow, RunRow, session_factory
    from app.run_service import create_task
    from pico_orchestrator.run_types import RunCaps
    from sqlalchemy import select

    sha = os.environ["PICO_GIT_SHA"]

    def record(event: str) -> None:
        with events_file.open("a") as stream:
            print(f"{sha} {event}", file=stream)

    async def tick() -> int:
        record("scheduler")
        return 0

    async def resume(run_id: str) -> None:
        async with session_factory()() as session:
            row = await session.get(RunRow, run_id)
            row.status = "succeeded"
            await session.commit()
        record(f"resume {run_id}")

    async def rebuild(*_args, **_kwargs) -> dict:
        record("reindex")
        await asyncio.sleep(60)
        return {"ok": True}

    automation_service._fire_due = tick
    run_resume.resume_run = resume
    main.rebuild_materials = rebuild

    principal = Principal(
        school_id="school-a", membership_id="member-a", iss="edu", aud="pico",
        scopes=["ai:run"], exp=0, raw={},
    )

    @main.app.post("/test/run")
    async def add_run(resumable: bool) -> str:
        async with session_factory()() as session:
            task, run = await create_task(session, principal, "handoff", "handoff")
            if resumable:
                spec = run_resume.build_spec(
                    caps=RunCaps(), principal=principal, conversation_id="test", task_id=task.id
                )
                assert spec is not None
                run.token_usage_json = json.dumps({run_resume.SPEC_KEY: spec})
            run.status = "running"
            await session.commit()
            return run.id

    @main.app.get("/test/run/{run_id}")
    async def get_run(run_id: str) -> dict:
        async with session_factory()() as session:
            run = await session.get(RunRow, run_id)
            events = (
                await session.scalars(select(EventRow.type).where(EventRow.run_id == run_id))
            ).all()
            return {"status": run.status, "events": list(events)}

    @main.app.get("/test/slow")
    async def slow() -> str:
        record("slow started")
        release = events_file.with_name(f"release-{sha}")
        while not release.exists():
            await asyncio.sleep(0.05)
        return sha

    uvicorn.run(main.app, host="127.0.0.1", port=port)


def _eventually(check, timeout: float = 10) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if check():
            return
        time.sleep(0.05)
    assert check()


def test_two_processes_recover_only_the_retired_owners_runs(tmp_path: Path) -> None:
    events_file = tmp_path / "events"
    events_file.touch()
    env = {
        "PATH": os.environ["PATH"],
        "PYTHONPATH": os.pathsep.join(str(ROOT / p) for p in ("services/api", "services/orchestrator")),
        "PICO_DATABASE_URL": f"sqlite+aiosqlite:///{tmp_path / 'handoff.db'}",
        "PICO_RUNNER_URL": "http://runner.invalid:18790",
        "PICO_OFFICE_URL": "embedded",
    }

    with ExitStack() as stack:
        def start(sha: str) -> tuple[subprocess.Popen, httpx.Client]:
            with socket.socket() as sock:
                sock.bind(("127.0.0.1", 0))
                port = sock.getsockname()[1]
            log = stack.enter_context((tmp_path / f"{sha}.log").open("w"))
            proc = subprocess.Popen(
                [sys.executable, __file__, str(port), str(events_file)],
                env={**env, "PICO_GIT_SHA": sha},
                stdout=log, stderr=subprocess.STDOUT,
            )

            def stop() -> None:
                if proc.poll() is None:
                    proc.terminate()
                    proc.wait(timeout=10)

            stack.callback(stop)
            client = stack.enter_context(httpx.Client(base_url=f"http://127.0.0.1:{port}"))

            def healthy() -> bool:
                assert proc.poll() is None, (tmp_path / f"{sha}.log").read_text()
                try:
                    response = client.get("/health")
                except httpx.ConnectError as exc:
                    logger.debug("API %s is not accepting connections yet: %s", sha, exc)
                    return False
                return response.raise_for_status().json()["git_sha"] == sha

            _eventually(healthy)
            return proc, client

        old, old_api = start("old")
        _eventually(lambda: "old scheduler" in events_file.read_text())
        assert events_file.read_text().splitlines() == ["old scheduler"]
        new, new_api = start("new")
        old_run = old_api.post("/test/run?resumable=true").raise_for_status().json()
        new_run = new_api.post("/test/run?resumable=true").raise_for_status().json()
        assert new_api.get(f"/test/run/{old_run}").json() == {"status": "running", "events": []}
        assert old_api.post("/v1/kb/reindex-all").status_code == 202
        assert new_api.post("/v1/kb/reindex-all").json()["already_running"] is True
        assert new_api.post("/v1/kb/reindex-all?force=1").status_code == 409
        _eventually(lambda: "old reindex" in events_file.read_text())
        assert events_file.read_text().splitlines() == ["old scheduler", "old reindex"]

        old.terminate()
        old.wait(timeout=10)
        _eventually(lambda: f"new resume {old_run}" in events_file.read_text())
        _eventually(lambda: "new scheduler" in events_file.read_text())
        assert new.poll() is None
        assert new_api.get(f"/test/run/{old_run}").json() == {
            "status": "succeeded", "events": ["run.resume"],
        }
        assert new_api.get(f"/test/run/{new_run}").json() == {"status": "running", "events": []}
        assert new_api.post("/v1/kb/reindex-all").json().get("already_running") is None
        _eventually(lambda: "new reindex" in events_file.read_text())

        events = events_file.read_text().splitlines()
        assert events.count("old scheduler") == events.count("new scheduler") == 1
        assert [item for item in events if "resume" in item] == [f"new resume {old_run}"]
        assert events.count("old reindex") == events.count("new reindex") == 1


if __name__ == "__main__":
    _serve(int(sys.argv[1]), Path(sys.argv[2]))
