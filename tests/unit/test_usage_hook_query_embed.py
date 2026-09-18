from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "orchestrator"))
sys.path.insert(0, str(ROOT / "services" / "api"))

from pico_orchestrator.usage_hook import emit_query_embed_usage


def test_query_embed_skips_keyword_only(monkeypatch) -> None:
    called = {"n": 0}

    async def boom(**kwargs):
        called["n"] += 1

    monkeypatch.setattr("app.usage_ledger.record_usage_event", boom)
    principal = SimpleNamespace(school_id="s1", membership_id="m1")
    asyncio.run(emit_query_embed_usage(principal, hybrid=False))
    assert called["n"] == 0


def test_query_embed_emits_honest_unknown(monkeypatch) -> None:
    captured: dict = {}

    async def fake_record(**kwargs):
        captured.update(kwargs)

    monkeypatch.setattr("app.usage_ledger.record_usage_event", fake_record)
    principal = SimpleNamespace(school_id="s1", membership_id="m1")
    asyncio.run(emit_query_embed_usage(principal, hybrid=True, query_count=2, model="embedding-3"))
    assert captured["kind"] == "search"
    assert captured["model"] == "embedding-3"
    assert captured["tokens_unknown"] is True
    assert captured["source"] == "kb_query_embed"
    assert captured["extra"]["reason"] == "meili_owns_query_embed_tokens"
    assert captured["prompt_tokens"] is None if "prompt_tokens" in captured else True
