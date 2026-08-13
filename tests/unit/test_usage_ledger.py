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
    assert USAGE_KINDS == frozenset({"llm", "search", "sandbox", "api", "other"})


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


def test_extract_token_fields_estimated_flag() -> None:
    fields = extract_token_fields(
        {"prompt_tokens": 3, "completion_tokens": 1, "total_tokens": 4, "estimated": True}
    )
    assert fields.estimated is True
    assert fields.tokens_unknown is False


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
