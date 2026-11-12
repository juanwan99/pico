"""edu-core#5288 (#5285 P0-2): usage rows carry the AI place the ticket came from."""

from __future__ import annotations

import asyncio
import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import jwt
import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "api"))
sys.path.insert(0, str(ROOT / "services" / "orchestrator"))

from app.usage_ledger import record_usage_event
from pico_orchestrator.usage_hook import (
    bind_usage_context,
    current_usage_entry,
    entry_of,
    reset_usage_context,
    use_entry_of,
)


@pytest.fixture()
async def usage_db(tmp_path, monkeypatch):
    from app import db as dbmod
    from app.db import init_db
    from app.settings import get_settings

    monkeypatch.setenv("PICO_DATABASE_URL", f"sqlite+aiosqlite:///{tmp_path / 'usage.db'}")
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


def _ticket(**extra) -> str:
    from app.settings import get_settings

    s = get_settings()
    now = datetime.now(UTC)
    payload = {
        "iss": s.pico_jwt_iss,
        "aud": s.pico_jwt_aud,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=5)).timestamp()),
        "school_id": "school-a",
        "membership_id": "m1",
        "scopes": ["ai:run", "ai:read", "ai:confirm"],
        **extra,
    }
    return jwt.encode(payload, s.pico_jwt_secret, algorithm="HS256")


async def _record(key: str, **kw) -> dict:
    row = await record_usage_event(
        school_id="school-a", membership_id="m1", kind="llm", model="gpt-4o",
        prompt_tokens=3, completion_tokens=2, total_tokens=5, idempotency_key=key, **kw,
    )
    assert row is not None
    return json.loads(row.extra_json)


def test_entry_of_principal() -> None:
    assert entry_of(SimpleNamespace(raw={"entry": "sidebar.propose"})) == "sidebar.propose"
    assert entry_of(SimpleNamespace(raw={"proxy": True})) == "workbench.web"
    assert entry_of(SimpleNamespace(raw={"automation_id": "a1"})) == "workbench.automation"
    for bad in [None, "", "propose", "office.web", "sidebar.", "Sidebar.x", "sidebar.中文", "sidebar." + "x" * 41, 7]:
        assert entry_of(SimpleNamespace(raw={"entry": bad})) == "unknown", bad
    assert entry_of(SimpleNamespace()) == "unknown"


@pytest.mark.asyncio
async def test_ticket_entry_lands_on_usage_row(usage_db) -> None:
    from app.auth import decode_token

    async def one(token: str, key: str) -> dict:
        decode_token(token)  # what every edu-ticket request does first
        return await _record(key, extra={"entry": "exam.grading"})  # caller's extra cannot set it

    # Each request runs in its own task / context, like FastAPI.
    tagged = await asyncio.create_task(one(_ticket(entry="sidebar.propose"), "llm:entry-tagged"))
    assert tagged["entry"] == "sidebar.propose"
    old = await asyncio.create_task(one(_ticket(), "llm:entry-old"))
    assert old["entry"] == "unknown", "old ticket without entry"
    bad = await asyncio.create_task(one(_ticket(entry="hack.me"), "llm:entry-bad"))
    assert bad["entry"] == "unknown", "malformed entry is not stored"


@pytest.mark.asyncio
async def test_tool_bind_entry_wins_outside_request(usage_db) -> None:
    async def tool_call() -> dict:
        tok = bind_usage_context(school_id="school-a", membership_id="m1", entry="sidebar.kb-ask")
        try:
            assert current_usage_entry() == "sidebar.kb-ask"
            return await _record("search:bind-entry")
        finally:
            reset_usage_context(tok)

    assert (await asyncio.create_task(tool_call()))["entry"] == "sidebar.kb-ask"

    async def bind_inherits() -> str:
        use_entry_of(SimpleNamespace(raw={"proxy": True}))
        tok = bind_usage_context(school_id="school-a", membership_id="m1")
        try:
            return current_usage_entry()
        finally:
            reset_usage_context(tok)

    assert await asyncio.create_task(bind_inherits()) == "workbench.web"


@pytest.mark.asyncio
async def test_rollups_by_entry(usage_db) -> None:
    from app.auth import Principal
    from app.db import session_factory
    from app.usage_ledger import owner_usage_today, school_month_usage

    async def tagged(entry: str, key: str) -> None:
        use_entry_of(SimpleNamespace(raw={"entry": entry}))
        await _record(key)

    await asyncio.create_task(tagged("sidebar.propose", "llm:r1"))
    await asyncio.create_task(tagged("sidebar.propose", "llm:r2"))
    await asyncio.create_task(tagged("exam.grading", "llm:r3"))
    async with session_factory()() as session:
        snap = await owner_usage_today(session)
        admin = Principal(
            school_id="school-a", membership_id="m9", scopes=["ai:read", "ai:admin"],
            iss="t", aud="pico-api", exp=0, raw={},
        )
        month = await school_month_usage(
            session, admin, month=(datetime.now(UTC) + timedelta(hours=8)).strftime("%Y-%m")
        )
    today = {e["entry"]: e for e in snap["entries"]}
    assert today["sidebar.propose"]["event_count"] == 2
    assert today["exam.grading"]["event_count"] == 1
    by = {e["entry"]: e for e in month["entries"]}
    assert by["sidebar.propose"]["event_count"] == 2
    assert by["sidebar.propose"]["total_tokens"] == 10
    assert by["exam.grading"]["event_count"] == 1
