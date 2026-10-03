"""#1175 PR-3: run done + conversation bound to a school field → grey draft.

No bound field → nothing leaves Pico. edu failure → ledger event, run stays
succeeded. Bookkeeping / images never land.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "api"))
sys.path.insert(0, str(ROOT / "services" / "orchestrator"))

FIELD = "aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee"
EDU_ID = "11111111-2222-4333-8444-555555555555"


@pytest.fixture()
def client(tmp_path, monkeypatch):
    database = tmp_path / "auto-land.db"
    monkeypatch.setenv("PICO_DATABASE_URL", f"sqlite+aiosqlite:///{database}")
    monkeypatch.setenv("PICO_JWT_SECRET", "test-secret-at-least-32-bytes-long!!")
    monkeypatch.setenv("PICO_ENV", "development")
    monkeypatch.setenv("PICO_EDU_BASE_URL", "https://edu.example")
    monkeypatch.setenv("PICO_EDU_ISS", "edu-core")
    monkeypatch.setenv("PICO_EDU_JWT_SECRET", "edu-shared-secret-at-least-32-bytes!!")
    from app import db as dbmod
    from app.main import app
    from app.settings import get_settings as gs

    dbmod._engine = None
    dbmod._Session = None
    gs.cache_clear()
    with TestClient(app) as test_client:
        yield test_client
    dbmod._engine = None
    dbmod._Session = None
    gs.cache_clear()


def _seed(*, bound: bool, status: str = "succeeded", convo: str = "c-land") -> tuple[str, str]:
    """One task + run with three artifacts: a page, an image, a summary."""
    from app.db import (
        ArtifactRow,
        EduNamedBindRow,
        RunRow,
        TaskRow,
        new_id,
        session_factory,
    )

    async def _go() -> tuple[str, str]:
        async with session_factory()() as session:
            task = TaskRow(
                id=new_id(),
                school_id="school-a",
                membership_id="m-edu",
                title="通知",
                conversation_id=convo,
            )
            run = RunRow(id=new_id(), task_id=task.id, status=status, prompt="写通知")
            session.add_all([task, run])
            await session.flush()
            for title, kind, inline in (
                ("通知.html", "html", "<p>灰</p>"),
                ("配图.png", "png", "iVBOR"),
                ("回复摘要", "doc", "摘要"),
            ):
                session.add(
                    ArtifactRow(
                        id=new_id(),
                        task_id=task.id,
                        run_id=run.id,
                        kind=kind,
                        title=title,
                        inline=inline,
                        content_encoding="utf8",
                    )
                )
            if bound:
                session.add(
                    EduNamedBindRow(
                        id=new_id(),
                        school_id="school-a",
                        membership_id="m-edu",
                        conversation_id=convo,
                        item_ids_json="[]",
                        field_id=FIELD,
                    )
                )
            await session.commit()
            return task.id, run.id

    return asyncio.run(_go())


def _events(run_id: str) -> list[tuple[str, dict]]:
    from app.db import EventRow, session_factory
    from sqlalchemy import select

    async def _go() -> list[tuple[str, dict]]:
        async with session_factory()() as session:
            rows = (
                (
                    await session.execute(
                        select(EventRow).where(EventRow.run_id == run_id).order_by(EventRow.seq)
                    )
                )
                .scalars()
                .all()
            )
            return [(row.type, row.payload) for row in rows]

    return asyncio.run(_go())


def _run_status(run_id: str) -> str:
    from app.db import RunRow, session_factory

    async def _go() -> str:
        async with session_factory()() as session:
            row = await session.get(RunRow, run_id)
            return str(row.status)

    return asyncio.run(_go())


def _land(run_id: str) -> list[dict]:
    from app.db import session_factory
    from app.edu_auto_land import auto_land_run_artifacts

    async def _go() -> list[dict]:
        async with session_factory()() as session:
            return await auto_land_run_artifacts(session, run_id)

    return asyncio.run(_go())


def _hook(run_id: str) -> None:
    from app.db import session_factory
    from app.edu_auto_land import auto_land_after_run

    async def _go() -> None:
        async with session_factory()() as session:
            await auto_land_after_run(session, run_id)

    asyncio.run(_go())


def test_bound_field_lands_page_only_as_copy(client, monkeypatch) -> None:
    calls: list[tuple[str, dict]] = []

    async def fake_call(principal, method, path, *, body=None, write=False, **_):
        calls.append((path, dict(body or {})))
        assert write is True
        assert principal.school_id == "school-a"
        assert principal.membership_id == "m-edu"
        return {
            "ok": True,
            "landed": True,
            "kind": "page",
            "id": EDU_ID,
            "fieldId": FIELD,
            "zone": "draft",
            "publish_state": "draft",
            "configured": True,
        }

    monkeypatch.setattr("app.edu_school._edu_call", fake_call)
    _, run_id = _seed(bound=True)
    out = _land(run_id)
    assert [c[0] for c in calls] == ["/v1/pico/membership/land"]
    sent = calls[0][1]
    assert sent["field_id"] == FIELD
    assert sent["kind"] == "page"
    assert sent["filename"] == "通知.html"
    assert sent["body_html"] == "<p>灰</p>"
    assert sent["conversation_id"] == "c-land"
    assert len(out) == 1 and out[0]["landed"] is True and out[0]["edu_id"] == EDU_ID
    events = _events(run_id)
    assert [t for t, _ in events] == ["artifact.landed"]
    assert events[0][1]["field_id"] == FIELD
    assert events[0][1]["mode"] == "copy"
    # copy: the Pico artifact is still there
    from app.auth import issue_test_token
    from app.settings import get_settings

    token = issue_test_token(
        school_id="school-a", membership_id="m-edu", scopes=["ai:read"], settings=get_settings()
    )
    listed = client.get(
        "/v1/artifacts",
        params={"mine": True},
        headers={"Authorization": f"Bearer {token}", "X-Pico-Membership-Id": "school-a:m-edu"},
    )
    assert listed.status_code == 200, listed.text
    assert "通知.html" in [row["title"] for row in listed.json()["artifacts"]]


def test_no_bound_field_touches_nothing(client, monkeypatch) -> None:
    async def boom(*_a, **_k):
        raise AssertionError("edu must not be called without a bound field")

    monkeypatch.setattr("app.edu_school._edu_call", boom)
    _, run_id = _seed(bound=False)
    assert _land(run_id) == []
    assert _events(run_id) == []


def test_failed_run_does_not_land(client, monkeypatch) -> None:
    async def boom(*_a, **_k):
        raise AssertionError("failed run must not land")

    monkeypatch.setattr("app.edu_school._edu_call", boom)
    _, run_id = _seed(bound=True, status="failed")
    assert _land(run_id) == []
    assert _events(run_id) == []


def test_edu_refusal_is_a_ledger_line_not_a_failed_run(client, monkeypatch) -> None:
    async def refuse(*_a, **_k):
        raise HTTPException(
            status_code=403,
            detail={"code": "field_write_required", "message": "这场你没有写权"},
        )

    monkeypatch.setattr("app.edu_school._edu_call", refuse)
    _, run_id = _seed(bound=True)
    _hook(run_id)
    events = _events(run_id)
    assert [t for t, _ in events] == ["artifact.land_failed"]
    assert events[0][1]["code"] == "field_write_required"
    assert events[0][1]["landed"] is False
    assert _run_status(run_id) == "succeeded"


def test_silent_green_is_refused_and_recorded(client, monkeypatch) -> None:
    async def green(*_a, **_k):
        return {"ok": True, "landed": True, "green": True, "id": EDU_ID, "configured": True}

    monkeypatch.setattr("app.edu_school._edu_call", green)
    _, run_id = _seed(bound=True)
    out = _land(run_id)
    assert out[0]["landed"] is False
    assert out[0]["code"] == "silent_green"
    assert [t for t, _ in _events(run_id)] == ["artifact.land_failed"]


def test_scheduled_hook_lands_off_the_reply_path(client, monkeypatch) -> None:
    calls: list[str] = []

    async def fake_call(principal, method, path, *, body=None, write=False, **_):
        calls.append(path)
        return {"ok": True, "landed": True, "kind": "page", "id": EDU_ID, "configured": True}

    monkeypatch.setattr("app.edu_school._edu_call", fake_call)
    _, run_id = _seed(bound=True)
    from app.edu_auto_land import schedule_auto_land

    async def _go() -> None:
        task = schedule_auto_land(run_id)
        assert task is not None
        await task

    asyncio.run(_go())
    assert calls == ["/v1/pico/membership/land"]
    assert [t for t, _ in _events(run_id)] == ["artifact.landed"]


def test_over_cap_artifacts_are_recorded_not_dropped(client, monkeypatch) -> None:
    from app.db import ArtifactRow, new_id, session_factory
    from app.edu_auto_land import MAX_ARTIFACTS_PER_RUN

    async def fake_call(*_a, **_k):
        return {"ok": True, "landed": True, "kind": "page", "id": EDU_ID, "configured": True}

    monkeypatch.setattr("app.edu_school._edu_call", fake_call)
    task_id, run_id = _seed(bound=True)

    async def _more() -> None:
        async with session_factory()() as session:
            for i in range(MAX_ARTIFACTS_PER_RUN + 1):
                session.add(
                    ArtifactRow(
                        id=new_id(),
                        task_id=task_id,
                        run_id=run_id,
                        kind="html",
                        title=f"第{i}页.html",
                        inline="<p>x</p>",
                        content_encoding="utf8",
                    )
                )
            await session.commit()

    asyncio.run(_more())
    out = _land(run_id)
    assert len(out) == MAX_ARTIFACTS_PER_RUN
    events = _events(run_id)
    assert events[-1][0] == "artifact.land_skipped"
    assert events[-1][1]["skipped"] == 2
    assert len(events[-1][1]["titles"]) == 2


def test_hook_never_raises(client, monkeypatch) -> None:
    async def crash(*_a, **_k):
        raise RuntimeError("edu adapter exploded")

    monkeypatch.setattr("app.edu_auto_land.auto_land_run_artifacts", crash)
    _, run_id = _seed(bound=True)
    _hook(run_id)  # must not raise
    assert _run_status(run_id) == "succeeded"
