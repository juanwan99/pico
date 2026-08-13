"""Usage ledger API: cross-account isolation, honest tokens, no billing fields."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "api"))
sys.path.insert(0, str(ROOT / "services" / "orchestrator"))

os.environ.setdefault("PICO_JWT_SECRET", "test-secret-at-least-32-bytes-long!!")
os.environ.setdefault("PICO_ENV", "development")

from app.main import app
from app.usage_ledger import emit_llm_usage_after_run, record_usage_event


@pytest.fixture()
async def client(tmp_path, monkeypatch):
    db = tmp_path / "usage.db"
    monkeypatch.setenv("PICO_DATABASE_URL", f"sqlite+aiosqlite:///{db}")
    from app import db as dbmod
    from app.db import init_db
    from app.settings import get_settings

    get_settings.cache_clear()
    dbmod._engine = None
    dbmod._Session = None
    await init_db()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    get_settings.cache_clear()
    dbmod._engine = None
    dbmod._Session = None


async def _token(client: AsyncClient, school="school-a", member="m1", scopes=None) -> str:
    body: dict = {"school_id": school, "membership_id": member}
    if scopes is not None:
        body["scopes"] = scopes
    r = await client.post("/v1/dev/token", json=body)
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


async def _auth(client: AsyncClient, **kwargs) -> dict[str, str]:
    return {"Authorization": f"Bearer {await _token(client, **kwargs)}"}


async def _seed_llm(*, school: str, member: str, run_id: str, tokens: dict | None) -> str:
    row = await record_usage_event(
        school_id=school,
        membership_id=member,
        kind="llm",
        model="pico-fast",
        prompt_tokens=None if tokens is None else tokens.get("prompt_tokens"),
        completion_tokens=None if tokens is None else tokens.get("completion_tokens"),
        total_tokens=None if tokens is None else tokens.get("total_tokens"),
        tokens_unknown=tokens is None,
        estimated=bool(tokens and tokens.get("estimated")),
        task_id="task-1",
        run_id=run_id,
        source="test",
        extra={"price": 9.9, "currency": "CNY", "query_count": 1},
        idempotency_key=f"llm:{run_id}",
    )
    assert row is not None
    return row.id


async def test_cross_account_cannot_read_detail(client: AsyncClient):
    owner = await _auth(client, member="m1")
    other = await _auth(client, member="m2")
    other_school = await _auth(client, school="school-b", member="m1")

    event_id = await _seed_llm(
        school="school-a",
        member="m1",
        run_id="run-owner",
        tokens={"prompt_tokens": 12, "completion_tokens": 8, "total_tokens": 20},
    )

    mine = await client.get("/v1/usage/events", headers=owner)
    assert mine.status_code == 200, mine.text
    body = mine.json()
    assert body["billing"] is False
    ids = [e["id"] for e in body["events"]]
    assert event_id in ids
    row = next(e for e in body["events"] if e["id"] == event_id)
    assert row["kind"] == "llm"
    assert row["model"] == "pico-fast"
    assert row["prompt_tokens"] == 12
    assert row["completion_tokens"] == 8
    assert row["tokens_unknown"] is False
    assert "price" not in row
    assert "currency" not in row
    assert "price" not in (row.get("extra") or {})
    assert "currency" not in (row.get("extra") or {})
    assert (row.get("extra") or {}).get("query_count") == 1

    other_list = await client.get("/v1/usage/events", headers=other)
    assert other_list.status_code == 200
    assert event_id not in [e["id"] for e in other_list.json()["events"]]

    other_school_list = await client.get("/v1/usage/events", headers=other_school)
    assert other_school_list.status_code == 200
    assert event_id not in [e["id"] for e in other_school_list.json()["events"]]

    denied = await client.get(f"/v1/usage/events/{event_id}", headers=other)
    assert denied.status_code == 404

    denied_school = await client.get(f"/v1/usage/events/{event_id}", headers=other_school)
    assert denied_school.status_code == 404

    probe = await client.get(
        "/v1/usage/events", headers=other, params={"membership_id": "m1"}
    )
    assert probe.status_code == 403

    ok = await client.get(f"/v1/usage/events/{event_id}", headers=owner)
    assert ok.status_code == 200
    assert ok.json()["event"]["id"] == event_id
    assert ok.json()["billing"] is False


async def test_admin_same_school_can_read_other_membership(client: AsyncClient):
    await _seed_llm(
        school="school-a",
        member="m1",
        run_id="run-admin",
        tokens={"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
    )
    admin = await _auth(client, member="admin-1", scopes=["ai:read", "ai:admin"])
    r = await client.get("/v1/usage/events", headers=admin, params={"membership_id": "m1"})
    assert r.status_code == 200, r.text
    assert any(e["run_id"] == "run-admin" for e in r.json()["events"])


async def test_honest_unknown_tokens_and_summary(client: AsyncClient):
    await _seed_llm(school="school-a", member="m1", run_id="run-unk", tokens=None)
    headers = await _auth(client)
    r = await client.get("/v1/usage/events", headers=headers)
    assert r.status_code == 200
    row = next(e for e in r.json()["events"] if e["run_id"] == "run-unk")
    assert row["tokens_unknown"] is True
    assert row["prompt_tokens"] is None
    assert row["completion_tokens"] is None
    assert row["total_tokens"] is None

    summary = await client.get("/v1/usage/summary", headers=headers)
    assert summary.status_code == 200
    body = summary.json()
    assert body["billing"] is False
    assert "price" not in body
    assert "currency" not in body
    assert any(d["kind"] == "llm" and d["unknown_count"] >= 1 for d in body["days"])
    for day_row in body["days"]:
        assert "price" not in day_row
        assert "currency" not in day_row
        assert "cost" not in day_row


async def test_idempotent_retry_does_not_duplicate(client: AsyncClient):
    a = await record_usage_event(
        school_id="school-a",
        membership_id="m1",
        kind="llm",
        model="pico-deep",
        prompt_tokens=5,
        completion_tokens=5,
        total_tokens=10,
        run_id="run-dup",
        source="test",
        idempotency_key="llm:run-dup",
    )
    b = await record_usage_event(
        school_id="school-a",
        membership_id="m1",
        kind="llm",
        model="pico-deep",
        prompt_tokens=5,
        completion_tokens=5,
        total_tokens=10,
        run_id="run-dup",
        source="test",
        idempotency_key="llm:run-dup",
    )
    assert a is not None and b is not None
    assert a.id == b.id
    headers = await _auth(client)
    r = await client.get("/v1/usage/events", headers=headers, params={"kind": "llm"})
    matches = [e for e in r.json()["events"] if e["run_id"] == "run-dup"]
    assert len(matches) == 1


async def test_my_usage_page_is_readonly_html(client: AsyncClient):
    headers = await _auth(client)
    r = await client.get("/v1/usage", headers=headers)
    assert r.status_code == 200
    assert "text/html" in r.headers.get("content-type", "")
    assert "不做钱" in r.text
    assert "暂无用量记录" in r.text or "llm" in r.text
    assert "¥" not in r.text
    assert "price" not in r.text.lower()


async def test_search_kind_can_be_written_for_later_cards(client: AsyncClient):
    row = await record_usage_event(
        school_id="school-a",
        membership_id="m1",
        kind="search",
        source="web_search",
        extra={"provider": "deepseek", "query_count": 1},
        idempotency_key="search:run-s:call-1",
        run_id="run-s",
    )
    assert row is not None
    headers = await _auth(client)
    r = await client.get("/v1/usage/events", headers=headers, params={"kind": "search"})
    assert r.status_code == 200
    assert any(e["kind"] == "search" for e in r.json()["events"])


async def test_emit_after_run_is_idempotent_and_estimated(client: AsyncClient):
    from app.auth import Principal
    from app.db import session_factory
    from app.run_service import create_task

    principal = Principal(
        school_id="school-a",
        membership_id="m1",
        scopes=["ai:run", "ai:read"],
        iss="pico-test-issuer",
        aud="pico-api",
        exp=0,
        raw={},
    )
    factory = session_factory()
    async with factory() as session:
        task, run = await create_task(session, principal, "t", "hello world")
        run_id = run.id
        task_id = task.id

    await emit_llm_usage_after_run(
        run_id,
        prompt="hello world",
        completion="hi there",
        source="openai_compat",
        school_id="school-a",
        membership_id="m1",
        task_id=task_id,
    )
    await emit_llm_usage_after_run(
        run_id,
        prompt="hello world",
        completion="hi there",
        source="openai_compat",
        school_id="school-a",
        membership_id="m1",
        task_id=task_id,
    )
    headers = await _auth(client)
    r = await client.get("/v1/usage/events", headers=headers, params={"kind": "llm"})
    matches = [e for e in r.json()["events"] if e["run_id"] == run_id]
    assert len(matches) == 1
    assert matches[0]["estimated"] is True
    assert matches[0]["tokens_unknown"] is False
    assert matches[0]["prompt_tokens"] is not None
    assert matches[0]["completion_tokens"] is not None
