"""P2 KB pilot + MCP allowlist bridge unit tests."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any

import pytest
from pico_orchestrator.mcp_bridge import (
    DEFAULT_MCP_ALLOWLIST,
    mcp_health_fields,
    mcp_tool_specs,
    parse_mcp_allowlist,
)
from pico_orchestrator.skill_policy import snapshot_for_skill
from pico_orchestrator.tools_builtin import build_default_gateway
from pico_orchestrator.user_errors import user_message_for_error


@dataclass
class _P:
    school_id: str = "school-a"
    membership_id: str = "m1"
    scopes: list[str] | None = None

    def __post_init__(self) -> None:
        if self.scopes is None:
            self.scopes = ["ai:run", "ai:read"]


class _MemStore:
    def __init__(self) -> None:
        self.rows: list[dict[str, Any]] = []

    async def write(
        self, principal: Any, *, title: str, content: str | bytes, kind: str
    ) -> dict[str, Any]:
        art_id = f"art-{len(self.rows) + 1}"
        row = {
            "artifact_id": art_id,
            "title": title,
            "kind": kind,
            "content": content if isinstance(content, str) else None,
            "content_base64": None,
        }
        self.rows.append(row)
        return dict(row)

    async def read(
        self, principal: Any, *, artifact_id: str | None, title: str | None
    ) -> dict[str, Any] | None:
        for row in reversed(self.rows):
            if artifact_id and row["artifact_id"] == artifact_id:
                return dict(row)
            if title and row["title"] == title:
                return dict(row)
        return None

    async def list(self, principal: Any, *, limit: int) -> list[dict[str, Any]]:
        return [
            {
                "artifact_id": r["artifact_id"],
                "title": r["title"],
                "kind": r["kind"],
            }
            for r in self.rows[:limit]
        ]


def test_parse_mcp_allowlist_filters_unknown() -> None:
    assert parse_mcp_allowlist("mcp_time,evil_shell,mcp_workspace_stat") == [
        "mcp_time",
        "mcp_workspace_stat",
    ]
    assert parse_mcp_allowlist("") == []
    assert parse_mcp_allowlist(DEFAULT_MCP_ALLOWLIST) == [
        "mcp_time",
        "mcp_workspace_stat",
    ]


def test_mcp_health_fields() -> None:
    body = mcp_health_fields("mcp_time")
    assert body["mcp_allowlist_enabled"] is True
    assert body["mcp_allowlist_count"] == 1
    assert body["mcp_tools"] == ["mcp_time"]


def test_build_gateway_registers_mcp_and_kb() -> None:
    gw = build_default_gateway(_MemStore())
    names = set(gw.tools)
    assert "kb_search" in names
    assert "mcp_time" in names
    assert "mcp_workspace_stat" in names


def test_mcp_tools_respect_empty_allowlist(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PICO_MCP_ALLOWLIST", "")
    specs = mcp_tool_specs(_MemStore(), allowlist=parse_mcp_allowlist(""))
    assert specs == []
    gw = build_default_gateway(_MemStore())
    # build_default_gateway re-reads env
    assert "mcp_time" not in gw.tools
    assert "kb_search" in gw.tools  # KB always on


def test_kb_search_hit_and_miss() -> None:
    store = _MemStore()
    principal = _P()

    async def _run() -> None:
        await store.write(
            principal,
            title="校历要点.md",
            content="春季学期于 3 月 1 日开学，期末考试在 6 月下旬。",
            kind="text",
        )
        gw = build_default_gateway(store)
        hit = await gw.invoke(principal, "kb_search", {"query": "开学"})
        assert hit["honest_miss"] is False
        assert hit["count"] >= 1
        assert hit["hits"][0]["artifact_id"]
        assert "3 月" in hit["hits"][0]["excerpt"] or "开学" in hit["hits"][0]["excerpt"]
        assert hit["retrieved"] is True
        assert hit["sources"][0]["artifact_id"] == hit["hits"][0]["artifact_id"]

        miss = await gw.invoke(principal, "kb_search", {"query": "量子隧穿"})
        assert miss["honest_miss"] is True
        assert miss["count"] == 0
        assert "未在已挂载" in miss["user_message"]

    asyncio.run(_run())


def test_kb_search_meili_down_degraded_scan(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MEILI_MASTER_KEY", "unit-key")
    monkeypatch.setattr(
        "pico_orchestrator.tools_builtin.search_materials",
        lambda *_a, **_k: (_ for _ in ()).throw(RuntimeError("meili down")),
    )
    store = _MemStore()
    principal = _P()

    async def _run() -> None:
        await store.write(
            principal,
            title="校历要点.md",
            content="春季学期于 3 月 1 日开学。",
            kind="text",
        )
        gw = build_default_gateway(store)
        hit = await gw.invoke(principal, "kb_search", {"query": "开学"})
        assert hit["degraded"] is True
        assert hit["honest_miss"] is False
        assert hit["hits"][0]["artifact_id"]
        miss = await gw.invoke(principal, "kb_search", {"query": "量子隧穿"})
        assert miss["degraded"] is True
        assert miss["honest_miss"] is True
        assert miss["hits"] == []
        assert miss["sources"] == []

    asyncio.run(_run())


def test_kb_search_drops_foreign_tenant_and_ignores_args_filter(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("MEILI_MASTER_KEY", "unit-key")
    captured: dict[str, str] = {}

    def fake_search(query, *, school_id, membership_id, limit, client=None):
        captured["school_id"] = school_id
        captured["membership_id"] = membership_id
        captured["query"] = query
        return {
            "hybrid": False,
            "hits": [
                {
                    "artifact_id": "good",
                    "title": "本校.md",
                    "text": "开学典礼",
                    "school_id": school_id,
                    "membership_id": membership_id,
                },
                {
                    "artifact_id": "bad",
                    "title": "外校.md",
                    "text": "开学典礼",
                    "school_id": "other-school",
                    "membership_id": "other-m",
                },
            ],
        }

    monkeypatch.setattr("pico_orchestrator.tools_builtin.search_materials", fake_search)
    gw = build_default_gateway(_MemStore())
    principal = _P()

    async def _run() -> None:
        out = await gw.invoke(
            principal,
            "kb_search",
            {"query": "开学", "filter": 'school_id = "other-school"'},
        )
        assert captured["school_id"] == principal.school_id
        assert captured["membership_id"] == principal.membership_id
        ids = [h["artifact_id"] for h in out["hits"]]
        assert ids == ["good"]
        assert out["honest_miss"] is False

    asyncio.run(_run())


def test_mcp_time_and_workspace_stat() -> None:
    store = _MemStore()
    principal = _P()

    async def _run() -> None:
        await store.write(principal, title="a.txt", content="hello", kind="text")
        gw = build_default_gateway(store)
        t = await gw.invoke(principal, "mcp_time", {})
        assert t["mcp"] == "mcp_time"
        assert "T" in t["utc"]
        st = await gw.invoke(principal, "mcp_workspace_stat", {"limit": 10})
        assert st["mcp"] == "mcp_workspace_stat"
        assert st["count"] >= 1

    asyncio.run(_run())


def test_skill_kb_ask_snapshot() -> None:
    snap = snapshot_for_skill("skill-kb-ask")
    assert snap is not None
    assert snap["id"] == "skill-kb-ask"
    assert "kb_search" in snap["tools"]
    assert snap["risk"] == "read"


def test_user_message_kb_miss() -> None:
    msg = user_message_for_error("未在已挂载材料中命中", code="kb.miss")
    assert "材料" in msg
