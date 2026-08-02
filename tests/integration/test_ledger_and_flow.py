"""Integration: Task/Run/Event ledger, cross-school, confirm, cancel."""

from __future__ import annotations

import asyncio
import json
import os
import sys
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "api"))
sys.path.insert(0, str(ROOT / "services" / "orchestrator"))

# isolated DB per test module
os.environ["PICO_DATABASE_URL"] = "sqlite+aiosqlite:///./data/test-pico.db"
os.environ["PICO_JWT_SECRET"] = "test-secret-at-least-32-bytes-long!!"
os.environ["PICO_ENV"] = "development"

from app import run_service
from app.auth import Principal
from app.db import AuditRow, ChangeProposalRow, init_db, session_factory
from app.main import app


@pytest.fixture()
def client(tmp_path, monkeypatch):
    db = tmp_path / "t.db"
    monkeypatch.setenv("PICO_DATABASE_URL", f"sqlite+aiosqlite:///{db}")
    # reset settings cache + engine
    from app import db as dbmod
    from app.settings import get_settings

    get_settings.cache_clear()
    dbmod._engine = None
    dbmod._Session = None

    with TestClient(app) as c:
        yield c


def _token(client: TestClient, school="school-a", member="m1") -> str:
    r = client.post(
        "/v1/dev/token",
        json={"school_id": school, "membership_id": member},
    )
    assert r.status_code == 200
    return r.json()["access_token"]


def test_health_and_safety(client: TestClient):
    assert client.get("/health").json()["ok"] is True
    s = client.get("/v1/meta/agent-safety").json()
    assert s["proof"]["dangerous_off"] is True


def test_cross_school_deny_events(client: TestClient):
    tok = _token(client)
    r = client.post(
        "/v1/demo/cross-school-deny",
        headers={"Authorization": f"Bearer {tok}"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["denied"] is True
    types = [e["type"] for e in body["events"]]
    assert "auth.deny" in types
    assert "tool.call" in types


def test_change_confirm_reject_and_membership_isolation(client: TestClient):
    owner = {"Authorization": f"Bearer {_token(client)}"}
    outsider = {"Authorization": f"Bearer {_token(client, member='m2')}"}
    other_school = {
        "Authorization": f"Bearer {_token(client, school='school-b', member='m1')}"
    }
    proposed = client.post(
        "/v1/changes",
        headers=owner,
        json={
            "title": "t1",
            "summary": "s1",
            "payload": {"x": 1},
        },
    )
    assert proposed.status_code == 200
    confirmed_id = proposed.json()["change"]["id"]
    assert proposed.json()["change"]["status"] == "proposed"

    detail = client.get(f"/v1/changes/{confirmed_id}", headers=owner)
    assert detail.status_code == 200
    assert detail.json()["change"]["id"] == confirmed_id
    pending = client.get(
        "/v1/changes",
        headers=owner,
        params={"status": "proposed"},
    ).json()["changes"]
    assert [item["id"] for item in pending] == [confirmed_id]

    for denied in (outsider, other_school):
        assert client.get(f"/v1/changes/{confirmed_id}", headers=denied).status_code == 404
        assert (
            client.post(
                f"/v1/changes/{confirmed_id}/confirm",
                headers=denied,
                json={},
            ).status_code
            == 404
        )
        assert (
            client.post(
                f"/v1/changes/{confirmed_id}/reject",
                headers=denied,
                json={},
            ).status_code
            == 404
        )
        assert client.get("/v1/changes", headers=denied).json()["changes"] == []

    confirmed = client.post(
        f"/v1/changes/{confirmed_id}/confirm",
        headers=owner,
        json={},
    )
    assert confirmed.status_code == 200
    assert confirmed.json()["change"]["status"] == "confirmed"
    assert confirmed.json()["change"]["confirmed_by"] == "m1"
    assert confirmed.json()["change"]["audit"][-1]["action"] == "confirmed"

    second = client.post(
        "/v1/changes",
        headers=owner,
        json={"title": "t2", "summary": "s2", "payload": {"x": 2}},
    )
    rejected_id = second.json()["change"]["id"]
    rejected = client.post(
        f"/v1/changes/{rejected_id}/reject",
        headers=owner,
        json={},
    )
    assert rejected.status_code == 200
    assert rejected.json()["change"]["status"] == "rejected"
    assert rejected.json()["change"]["audit"][-1]["action"] == "rejected"


def test_change_task_filter_and_task_ownership(
    client: TestClient,
    monkeypatch,
) -> None:
    async def no_background_start(*_args, **_kwargs) -> None:
        return None

    monkeypatch.setattr(
        "app.run_service.start_run_background",
        no_background_start,
    )
    owner = {"Authorization": f"Bearer {_token(client)}"}
    outsider = {"Authorization": f"Bearer {_token(client, member='m2')}"}
    task = client.post(
        "/v1/tasks",
        headers=owner,
        json={"title": "S7 task", "prompt": "create a proposal"},
    )
    assert task.status_code == 200
    task_id = task.json()["task"]["id"]

    created = client.post(
        "/v1/changes",
        headers=owner,
        json={
            "title": "task-scoped",
            "summary": "same task",
            "payload": {},
            "task_id": task_id,
        },
    )
    assert created.status_code == 200
    change = created.json()["change"]
    assert change["task_id"] == task_id

    scoped = client.get(
        "/v1/changes",
        headers=owner,
        params={"task_id": task_id},
    )
    assert [item["id"] for item in scoped.json()["changes"]] == [change["id"]]

    denied = client.post(
        "/v1/changes",
        headers=outsider,
        json={
            "title": "forged task",
            "summary": "must fail",
            "payload": {},
            "task_id": task_id,
        },
    )
    assert denied.status_code == 404


@pytest.mark.asyncio
async def test_change_terminal_transition_has_one_winner() -> None:
    await init_db()

    principal = Principal(
        school_id="school-a",
        membership_id="m1",
        scopes=["ai:run", "ai:read", "ai:confirm"],
        iss="pico",
        aud="pico-api",
        exp=2_000_000_000,
        raw={},
    )
    factory = session_factory()
    async with factory() as session:
        change = await run_service.create_change(
            session,
            principal,
            title="single winner",
            summary="confirm or reject",
            payload={},
        )
        change_id = change.id

    async def confirm():
        async with factory() as session:
            return await run_service.confirm_change(session, principal, change_id)

    async def reject():
        async with factory() as session:
            return await run_service.reject_change(session, principal, change_id)

    results = await asyncio.gather(confirm(), reject(), return_exceptions=True)
    winners = [result for result in results if isinstance(result, ChangeProposalRow)]
    losers = [result for result in results if isinstance(result, ValueError)]
    assert len(winners) == 1
    assert len(losers) == 1

    async with factory() as session:
        from sqlalchemy import select

        stored = await session.get(ChangeProposalRow, change_id)
        assert stored is not None
        assert stored.status in {"confirmed", "rejected"}
        history = [
            item
            for item in json.loads(stored.audit_json or "[]")
            if item.get("action") in {"confirmed", "rejected"}
        ]
        assert len(history) == 1
        assert history[0]["action"] == stored.status
        assert bool(stored.confirmed_by) is (stored.status == "confirmed")
        terminal_audits = list(
            (
                await session.execute(
                    select(AuditRow).where(
                        AuditRow.subject_id == change_id,
                        AuditRow.action.in_(
                            ("change.confirmed", "change.rejected")
                        ),
                    )
                )
            )
            .scalars()
            .all()
        )
        assert len(terminal_audits) == 1
        assert terminal_audits[0].action == f"change.{stored.status}"


def test_cancel_queued_run(client: TestClient, monkeypatch):
    """Cancel is immediately terminal and repeated requests do not duplicate events."""
    tok = _token(client)
    h = {"Authorization": f"Bearer {tok}"}

    async def no_background_start(*_args, **_kwargs) -> None:
        return None

    monkeypatch.setattr(run_service, "start_run_background", no_background_start)

    r = client.post(
        "/v1/tasks",
        headers=h,
        json={"title": "c", "prompt": "hello"},
    )
    assert r.status_code == 200
    run_id = r.json()["run"]["id"]
    first = client.post(f"/v1/runs/{run_id}/cancel", headers=h, json={})
    assert first.status_code == 200, first.text
    assert first.json()["run"]["status"] == "cancelled"
    assert first.json()["run"]["cancel_requested"] is True

    repeated = client.post(f"/v1/runs/{run_id}/cancel", headers=h, json={})
    assert repeated.status_code == 200, repeated.text
    assert repeated.json()["run"]["status"] == "cancelled"

    events = client.get(f"/v1/runs/{run_id}/events", headers=h).json()["events"]
    assert [event["type"] for event in events].count("run.cancel_requested") == 1
    cancelled = [
        event
        for event in events
        if event["type"] == "run.status" and event["payload"].get("status") == "cancelled"
    ]
    assert len(cancelled) == 1


def test_cancel_responses_survive_expired_orm_state(
    client: TestClient,
    monkeypatch,
):
    """Concurrent event retry must not turn a durable cancel into HTTP 500."""
    tok = _token(client)
    h = {"Authorization": f"Bearer {tok}"}

    async def no_background_start(*_args, **_kwargs) -> None:
        return None

    monkeypatch.setattr(run_service, "start_run_background", no_background_start)
    created = client.post(
        "/v1/tasks",
        headers=h,
        json={"title": "cancel-active", "prompt": "long task"},
    )
    assert created.status_code == 200, created.text
    task_id = created.json()["task"]["id"]
    run_id = created.json()["run"]["id"]

    from app import db as dbmod

    async def expire_after_event(session, *_args, **_kwargs):
        # append_event may call session.rollback() while retrying a concurrent
        # event sequence collision; rollback expires previously loaded rows.
        session.expire_all()

    monkeypatch.setattr(dbmod, "append_event", expire_after_event)
    response = client.post(
        f"/v1/tasks/{task_id}/cancel-active",
        headers=h,
        json={},
    )
    assert response.status_code == 200, response.text
    assert response.json() == {
        "runs": [
            {
                **created.json()["run"],
                "status": "cancelled",
                "cancel_requested": True,
                "ended_at": response.json()["runs"][0]["ended_at"],
            }
        ],
        "cancelled": 1,
    }
    assert response.json()["runs"][0]["id"] == run_id

    single_created = client.post(
        "/v1/tasks",
        headers=h,
        json={"title": "cancel-single", "prompt": "another long task"},
    )
    assert single_created.status_code == 200, single_created.text
    single_run_id = single_created.json()["run"]["id"]
    single_response = client.post(
        f"/v1/runs/{single_run_id}/cancel",
        headers=h,
        json={},
    )
    assert single_response.status_code == 200, single_response.text
    assert single_response.json()["run"]["id"] == single_run_id
    assert single_response.json()["run"]["status"] == "cancelled"
    assert single_response.json()["run"]["cancel_requested"] is True


@pytest.mark.skipif(
    not os.environ.get("KIMI_API_KEY"),
    reason="S1 real key required for multi-step loop",
)
def test_task_run_with_real_model(client: TestClient):
    tok = _token(client)
    h = {"Authorization": f"Bearer {tok}"}
    r = client.post(
        "/v1/tasks",
        headers=h,
        json={
            "title": "classes",
            "prompt": "请调用工具列出我学校的班级，然后用一句话总结。",
        },
    )
    assert r.status_code == 200
    run_id = r.json()["run"]["id"]
    task_id = r.json()["task"]["id"]
    status = "queued"
    for _ in range(90):
        time.sleep(1)
        status = client.get(f"/v1/runs/{run_id}", headers=h).json()["run"]["status"]
        if status in ("succeeded", "failed", "cancelled"):
            break
    assert status == "succeeded", status
    events = client.get(f"/v1/runs/{run_id}/events", headers=h).json()["events"]
    types = [e["type"] for e in events]
    assert "run.status" in types
    assert any(t.startswith("agent.") or t == "tool.call" or t == "message.delta" for t in types)
    # Prefer tool path but model may answer without tools occasionally
    task = client.get(f"/v1/tasks/{task_id}", headers=h).json()
    assert task["task"]["id"] == task_id


def test_list_task_runs_endpoint(client: TestClient):
    tok = _token(client)
    h = {"Authorization": f"Bearer {tok}"}
    # no model needed for cross-school demo task
    r = client.post("/v1/demo/cross-school-deny", headers=h)
    assert r.status_code == 200
    task_id = r.json()["task_id"]
    runs = client.get(f"/v1/tasks/{task_id}/runs", headers=h)
    assert runs.status_code == 200
    assert len(runs.json()["runs"]) >= 1
