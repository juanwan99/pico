"""Usage ledger: no billing columns, honest unknown tokens, fail-open writes."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "api"))
sys.path.insert(0, str(ROOT / "services" / "orchestrator"))

from app.db import UsageEventRow
from app.usage_ledger import (
    BILLING_COLUMN_NAMES,
    USAGE_KINDS,
    extract_token_fields,
    record_usage_event,
    schema_has_billing_columns,
    scrub_dirty_usage_events_sync,
)


def test_schema_has_no_price_currency_billing_columns() -> None:
    cols = {c.name.lower() for c in UsageEventRow.__table__.columns}
    assert not (cols & BILLING_COLUMN_NAMES)
    assert schema_has_billing_columns() is False
    joined = " ".join(cols)
    for forbidden in ("price", "currency", "billing", "charge", "payment"):
        assert forbidden not in joined
    assert "prompt_tokens" in cols
    assert "completion_tokens" in cols
    assert "tokens_unknown" in cols
    assert "kind" in cols


def test_reserved_kinds_include_llm_and_later_cards() -> None:
    assert USAGE_KINDS == frozenset({"llm", "search", "sandbox", "image", "api", "other"})


def test_extract_token_fields_unknown_when_missing() -> None:
    fields = extract_token_fields(None)
    assert fields.tokens_unknown is True
    assert fields.prompt_tokens is None
    assert fields.completion_tokens is None
    assert fields.total_tokens is None

    fields = extract_token_fields({"skill_snapshot": {"id": "x"}})
    assert fields.tokens_unknown is True


def test_extract_token_fields_uninitialized_zeros_are_unknown() -> None:
    fields = extract_token_fields(
        {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}
    )
    assert fields.tokens_unknown is True
    assert fields.prompt_tokens is None


def test_extract_token_fields_provider_and_openai_aliases() -> None:
    a = extract_token_fields({"prompt_tokens": 10, "completion_tokens": 4})
    assert a.tokens_unknown is False
    assert a.prompt_tokens == 10
    assert a.completion_tokens == 4
    assert a.total_tokens == 14

    b = extract_token_fields(
        {"input_tokens": 8, "output_tokens": 2, "total_tokens": 10, "estimated": False}
    )
    assert b.prompt_tokens == 8
    assert b.completion_tokens == 2
    assert b.total_tokens == 10
    assert b.estimated is False

    pi = extract_token_fields(
        {"input": 8, "output": 7, "totalTokens": 15, "cacheRead": 3, "cost": {"total": 1}}
    )
    assert pi.tokens_unknown is False
    assert pi.prompt_tokens == 8
    assert pi.completion_tokens == 7
    assert pi.total_tokens == 15
    assert pi.estimated is False

    split = extract_token_fields(
        {
            "prompt_tokens": 1058,
            "completion_tokens": 78,
            "total_tokens": 8816,
            "cached_tokens": 7680,
        }
    )
    assert split.prompt_tokens == 8738
    assert split.completion_tokens == 78
    assert split.total_tokens == 8816


def test_extract_token_fields_estimated_flag_is_unknown() -> None:
    fields = extract_token_fields(
        {"prompt_tokens": 3, "completion_tokens": 1, "total_tokens": 4, "estimated": True}
    )
    assert fields.tokens_unknown is True
    assert fields.estimated is False
    assert fields.prompt_tokens is None


@pytest.mark.asyncio
async def test_record_usage_event_swallows_write_failure() -> None:
    with patch("app.usage_ledger.session_factory", side_effect=RuntimeError("db down")):
        row = await record_usage_event(
            school_id="school-a",
            membership_id="m1",
            kind="llm",
            model="pico-fast",
            idempotency_key="llm:test-fail-open",
        )
    assert row is None


@pytest.mark.asyncio
async def test_record_rejects_unknown_kind_without_raising() -> None:
    row = await record_usage_event(
        school_id="school-a",
        membership_id="m1",
        kind="bitcoin",
        idempotency_key="bad-kind",
    )
    assert row is None


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


@pytest.mark.asyncio
async def test_record_drops_estimated_numbers_and_ui_lane(usage_db) -> None:
    dirty = await record_usage_event(
        school_id="school-a",
        membership_id="m1",
        kind="llm",
        model="pico-fast",
        prompt_tokens=3,
        completion_tokens=9,
        total_tokens=12,
        estimated=True,
        source="test",
        idempotency_key="llm:drop-estimate",
    )
    assert dirty is not None
    assert dirty.estimated == 0
    assert dirty.tokens_unknown == 1
    assert dirty.prompt_tokens is None
    assert dirty.completion_tokens is None
    assert dirty.total_tokens is None
    assert dirty.model is None
    extra = __import__("json").loads(dirty.extra_json)
    assert extra.get("ui_model") == "pico-fast"
    assert extra.get("rejected_estimate") is True


@pytest.mark.asyncio
async def test_scrub_estimated_and_recover_backend_from_events(usage_db) -> None:
    import json

    from app import db as dbmod
    from app.db import EventRow, RunRow, TaskRow, new_id, session_factory

    run_id = new_id()
    task_id = new_id()
    dirty_id = new_id()
    orphan_id = new_id()
    factory = session_factory()
    async with factory() as session:
        session.add(
            TaskRow(
                id=task_id,
                school_id="school-a",
                membership_id="m1",
                title="t",
            )
        )
        session.add(RunRow(id=run_id, task_id=task_id, model="pico-fast"))
        session.add(
            EventRow(
                run_id=run_id,
                seq=1,
                type="run.model",
                payload_json=json.dumps({"backend_model": "gpt-5.6-sol"}),
            )
        )
        session.add(
            UsageEventRow(
                id=dirty_id,
                school_id="school-a",
                membership_id="m1",
                kind="llm",
                model="pico-fast",
                prompt_tokens=4,
                completion_tokens=16,
                total_tokens=20,
                tokens_unknown=0,
                estimated=1,
                task_id=task_id,
                run_id=run_id,
                source="openai_compat",
                extra_json="{}",
                idempotency_key=f"llm:{run_id}",
            )
        )
        session.add(
            UsageEventRow(
                id=orphan_id,
                school_id="school-a",
                membership_id="m1",
                kind="llm",
                model="pico-deep",
                prompt_tokens=1,
                completion_tokens=8,
                total_tokens=9,
                tokens_unknown=0,
                estimated=1,
                source="openai_compat",
                extra_json="{}",
                idempotency_key="llm:orphan-lane",
            )
        )
        await session.commit()

    assert dbmod._engine is not None
    async with dbmod._engine.begin() as conn:
        stats = await conn.run_sync(scrub_dirty_usage_events_sync)
    assert stats["estimated"] == 2
    assert stats["ui_lane"] == 2
    assert stats["backend_recovered"] == 1

    async with factory() as session:
        recovered = await session.get(UsageEventRow, dirty_id)
        orphan = await session.get(UsageEventRow, orphan_id)
    assert recovered is not None
    assert recovered.estimated == 0
    assert recovered.tokens_unknown == 1
    assert recovered.prompt_tokens is None
    assert recovered.model == "gpt-5.6-sol"
    extra_r = json.loads(recovered.extra_json)
    assert extra_r.get("ui_model") == "pico-fast"
    assert extra_r.get("scrubbed") == "estimated_char4"
    assert orphan is not None
    assert orphan.model is None
    extra_o = json.loads(orphan.extra_json)
    assert extra_o.get("ui_model") == "pico-deep"
    assert extra_o.get("scrubbed_model") == "ui_lane"

    async with dbmod._engine.begin() as conn:
        again = await conn.run_sync(scrub_dirty_usage_events_sync)
    assert again == {"estimated": 0, "ui_lane": 0, "backend_recovered": 0}


@pytest.mark.asyncio
async def test_owner_usage_today_has_no_membership_ids(usage_db) -> None:
    from app.db import session_factory
    from app.usage_ledger import owner_usage_today

    await record_usage_event(
        school_id="school-a",
        membership_id="secret-member",
        kind="llm",
        model="gpt-5.6-sol",
        prompt_tokens=4,
        completion_tokens=6,
        total_tokens=10,
        source="test",
        idempotency_key="llm:owner-snap",
    )
    factory = session_factory()
    async with factory() as session:
        snap = await owner_usage_today(session)
    assert snap["billing"] is False
    assert snap["ok"] is True
    blob = str(snap)
    assert "secret-member" not in blob
    assert "school-a" not in blob
    llm = next(row for row in snap["kinds"] if row["kind"] == "llm")
    assert llm["event_count"] >= 1
    assert llm["total_tokens"] == 10


