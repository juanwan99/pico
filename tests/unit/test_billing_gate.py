"""#1042 T-BILLING-GATE: JWT feature switches + today's allowance gate.

Pico reads what edu signed into the token; stores no balance (USAGE-LEDGER §1).
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest
from fastapi import HTTPException

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "api"))
sys.path.insert(0, str(ROOT / "services" / "orchestrator"))

from app.auth import REGISTERED_SCOPES, decode_token, enforce_feature, issue_test_token
from app.channel_rates import load_rate_card
from app.points_meter import milli_from_row, quote_millipoints_from_input_len
from app.usage_ledger import enforce_allowance, record_usage_event, used_millipoints_today
from pico_orchestrator.features import (
    FEATURE_SCOPES,
    allowance_millipoints,
    feature_enabled,
    feature_for_tool,
)
from pico_orchestrator.gateway import ToolError
from pico_orchestrator.meili_kb import _rerank_usage, rerank_documents_with_usage
from pico_orchestrator.tools_builtin import build_default_gateway


@dataclass
class P:
    school_id: str = "school-a"
    membership_id: str = "m1"
    scopes: list[str] = field(default_factory=lambda: ["ai:run", "ai:read"])
    raw: dict[str, Any] = field(default_factory=dict)


def test_feature_scopes_registered_and_default_all_on() -> None:
    assert FEATURE_SCOPES <= REGISTERED_SCOPES
    p = P()
    for name in ("kb", "rerank", "image", "deep", "office"):
        assert feature_enabled(p, name) is True


def test_feature_allowlist_when_any_feat_scope_present() -> None:
    p = P(scopes=["ai:run", "feat:image"])
    assert feature_enabled(p, "image") is True
    assert feature_enabled(p, "kb") is False
    assert feature_enabled(p, "deep") is False
    assert feature_for_tool("kb_search") == "kb"
    assert feature_for_tool("generate_image") == "image"
    assert feature_for_tool("sandbox_office_lib") == "office"
    assert feature_for_tool("web_search") is None
    with pytest.raises(HTTPException) as ei:
        enforce_feature(p, "kb")
    assert ei.value.status_code == 403
    assert ei.value.detail["code"] == "feature.off"
    assert "设置" in ei.value.detail["message"]


@pytest.mark.asyncio
async def test_gateway_refuses_switched_off_tool_but_allows_others() -> None:
    gw = build_default_gateway()
    p = P(scopes=["ai:run", "feat:image"])
    with pytest.raises(ToolError) as ei:
        await gw.invoke(p, "kb_search", {"query": "校历"})
    assert ei.value.code == "feature.off"
    # unrelated tools are untouched
    out = await gw.invoke(p, "pico_echo", {"text": "hi"})
    assert out


def test_allowance_claim_parsing() -> None:
    assert allowance_millipoints(P()) is None
    assert allowance_millipoints(P(raw={"allowance_points_today": "12.345"})) == 12345
    assert allowance_millipoints(P(raw={"allowance_points_today": 3})) == 3000
    assert allowance_millipoints(P(raw={"allowance_points_today": 0})) == 0
    assert allowance_millipoints(P(raw={"allowance_points_today": "-5"})) == 0
    assert allowance_millipoints(P(raw={"allowance_points_today": "abc"})) == 0
    assert allowance_millipoints(P(raw={"allowance_points_today": None})) == 0


def test_edu_token_carries_feat_scopes_and_allowance(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.settings import get_settings

    monkeypatch.setenv("PICO_ACCEPT_TEST_ISSUER", "true")
    monkeypatch.setenv("PICO_ALLOW_TEST_ISSUER_BREAK_GLASS", "true")
    monkeypatch.setenv("PICO_JWT_SECRET", "x" * 40)
    get_settings.cache_clear()
    try:
        import jwt

        s = get_settings()
        token = issue_test_token(
            school_id="school-a", membership_id="m1", scopes=["ai:run", "feat:kb"], settings=s
        )
        claims = jwt.decode(token, s.pico_jwt_secret, algorithms=["HS256"], audience=s.pico_jwt_aud)
        claims["allowance_points_today"] = "0.500"
        token2 = jwt.encode(claims, s.pico_jwt_secret, algorithm="HS256")
        principal = decode_token(token2, s)
        assert feature_enabled(principal, "kb") is True
        assert feature_enabled(principal, "image") is False
        assert allowance_millipoints(principal) == 500
    finally:
        get_settings.cache_clear()


@pytest.fixture()
async def usage_db(tmp_path, monkeypatch):
    from app import db as dbmod
    from app.db import init_db
    from app.settings import get_settings

    monkeypatch.setenv("PICO_DATABASE_URL", f"sqlite+aiosqlite:///{tmp_path / 'gate.db'}")
    get_settings.cache_clear()
    dbmod._engine = None
    dbmod._Session = None
    await init_db()
    try:
        yield dbmod
    finally:
        assert dbmod._engine is not None
        await dbmod._engine.dispose()
        dbmod._engine = None
        dbmod._Session = None
        get_settings.cache_clear()


@pytest.mark.asyncio
async def test_allowance_gate_counts_only_this_member_and_not_school_rows(usage_db) -> None:
    from app.db import session_factory

    await record_usage_event(
        school_id="school-a", membership_id="m1", kind="llm", model="gpt-5.6-sol",
        prompt_tokens=100_000, completion_tokens=10_000, total_tokens=110_000,
        idempotency_key="llm:gate-1",
    )
    # school-billed row must not count against the personal allowance
    await record_usage_event(
        school_id="school-a", membership_id="m1", kind="llm", model="gpt-5.6-sol",
        prompt_tokens=100_000, completion_tokens=10_000, total_tokens=110_000,
        idempotency_key="llm:gate-2", bill_to="school",
    )
    # another member
    await record_usage_event(
        school_id="school-a", membership_id="m2", kind="llm", model="gpt-5.6-sol",
        prompt_tokens=100_000, completion_tokens=10_000, total_tokens=110_000,
        idempotency_key="llm:gate-3",
    )
    expected = milli_from_row(
        tokens_unknown=False, prompt_tokens=100_000, completion_tokens=10_000,
        total_tokens=110_000, kind="llm", model="gpt-5.6-sol",
    )
    assert expected and expected > 0
    async with session_factory()() as session:
        used = await used_millipoints_today(session, P())
        assert used == expected
        # no claim → no gate
        assert await enforce_allowance(session, P(), quote_milli=10**9) is None
        # generous allowance → passes and reports
        ok = await enforce_allowance(
            session, P(raw={"allowance_points_today": (expected * 10) / 1000}), quote_milli=0
        )
        assert ok["used_milli"] == expected
        # exhausted → 403 with the teacher sentence
        with pytest.raises(HTTPException) as ei:
            await enforce_allowance(
                session, P(raw={"allowance_points_today": (expected - 1) / 1000}), quote_milli=0
            )
        assert ei.value.status_code == 403
        assert ei.value.detail["code"] == "points.exhausted"
        assert "明天" in ei.value.detail["message"]
        # quote of the next turn is added before comparing
        with pytest.raises(HTTPException):
            await enforce_allowance(
                session, P(raw={"allowance_points_today": expected / 1000}), quote_milli=1
            )
    assert quote_millipoints_from_input_len(0) > 0


def test_rate_card_prices_rerank_and_ingest_per_file() -> None:
    card = load_rate_card(force=True)
    rerank = card.find(kind="search", model="rerank-pro")
    assert rerank is not None and rerank.priced()
    milli = milli_from_row(
        tokens_unknown=False, prompt_tokens=6000, completion_tokens=0, total_tokens=6000,
        kind="search", model="rerank-pro",
    )
    # 6000 tokens × ¥0.8/M = ¥0.0048 cost → ×2.5 → 12 points
    assert milli == 12000
    ingest = card.find(kind="api", model="kb-ingest-file")
    assert ingest is not None and ingest.per_call_yuan > 0
    per_file = milli_from_row(
        tokens_unknown=True, prompt_tokens=None, completion_tokens=None, total_tokens=None,
        kind="api", model="kb-ingest-file", extra={"query_count": 1, "ok": True},
    )
    assert per_file == 50000  # ¥0.02 × 2.5 × 1000
    failed = milli_from_row(
        tokens_unknown=True, prompt_tokens=None, completion_tokens=None, total_tokens=None,
        kind="api", model="kb-ingest-file", extra={"query_count": 1, "ok": False},
    )
    assert failed is None
    # plain kb search has no priced row: free by construction
    assert card.find(kind="search", model="kb_search") is None


def test_rerank_usage_parsed_from_new_api_body(monkeypatch: pytest.MonkeyPatch) -> None:
    assert _rerank_usage({"usage": {"prompt_tokens": 461, "completion_tokens": 5, "total_tokens": 461}}) == {
        "model": "rerank-pro", "prompt_tokens": 461, "completion_tokens": 5, "total_tokens": 461,
    }
    assert _rerank_usage({"usage": {}}) is None
    assert _rerank_usage({}) is None
    monkeypatch.setenv("DEEPSEEK_BASE_URL", "http://127.0.0.1:3000/v1")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-pico-gateway")

    class _Http:
        def request(self, method, url, *, json=None, headers=None, timeout=8.0):
            return 200, {
                "results": [{"index": 1, "relevance_score": 0.9}, {"index": 0, "relevance_score": 0.1}],
                "usage": {"prompt_tokens": 42, "total_tokens": 42},
            }

    monkeypatch.setattr("pico_orchestrator.meili_kb.HttpxClient", lambda: _Http())
    order, usage = rerank_documents_with_usage("q", ["甲", "乙"])
    assert order == [1, 0]
    assert usage["prompt_tokens"] == 42 and usage["model"] == "rerank-pro"
