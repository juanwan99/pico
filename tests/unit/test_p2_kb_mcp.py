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


def test_kb_search_hit_and_miss(monkeypatch: pytest.MonkeyPatch) -> None:
    store = _MemStore()
    principal = _P()
    green = [
        {
            "id": "aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee",
            "title": "校历要点.md",
            "excerpt": "春季学期于 3 月 1 日开学，期末考试在 6 月下旬。",
            "kind": "material",
            "fieldId": "ffffffff-1111-4222-8333-444444444444",
        }
    ]

    async def fake_green(p, *, query, field_id="", settings=None):
        _ = p, field_id, settings
        if "量子" in query:
            return {"configured": True, "items": [], "dumped": False, "status": 200}
        return {"configured": True, "items": green, "dumped": False, "status": 200}

    monkeypatch.setattr("app.edu_school.search_green_library", fake_green)

    async def _run() -> None:
        await store.write(
            principal,
            title="会话随传.md",
            content="春季学期于 3 月 1 日开学。这段只在 Pico 对话里。",
            kind="text",
        )
        gw = build_default_gateway(store)
        hit = await gw.invoke(principal, "kb_search", {"query": "开学"})
        assert hit["honest_miss"] is False
        assert hit["count"] == 1
        assert hit["hits"][0]["item_id"] == green[0]["id"]
        assert "artifact_id" not in hit["hits"][0]
        assert "开学" in hit["hits"][0]["excerpt"]
        assert hit["retrieved"] is True
        assert hit["sources"][0]["item_id"] == green[0]["id"]
        assert hit["sources"][0]["title"] == "校历要点.md"
        assert hit["mode"] == "edu_green"

        miss = await gw.invoke(principal, "kb_search", {"query": "量子隧穿"})
        assert miss["honest_miss"] is True
        assert miss["count"] == 0
        assert miss["sources"] == []
        assert "绿区" in miss["user_message"]

    asyncio.run(_run())


def test_kb_search_unconfigured_does_not_scan_pico_uploads(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_green(*_a, **_k):
        return {"configured": False, "items": [], "dumped": False, "status": 200}

    monkeypatch.setattr("app.edu_school.search_green_library", fake_green)
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
        out = await gw.invoke(principal, "kb_search", {"query": "开学"})
        assert out["honest_miss"] is True
        assert out["mode"] == "unconfigured"
        assert out["hits"] == []
        assert out["sources"] == []
        assert "不造第二套绿区" in out["user_message"]

    asyncio.run(_run())


def test_kb_search_ignores_client_filter(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, str] = {}

    async def fake_green(p, *, query, field_id="", settings=None):
        captured["school_id"] = p.school_id
        captured["membership_id"] = p.membership_id
        captured["query"] = query
        captured["field_id"] = field_id
        _ = settings
        return {
            "configured": True,
            "status": 200,
            "items": [
                {
                    "id": "aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee",
                    "title": "本校.md",
                    "excerpt": "开学典礼",
                    "kind": "material",
                }
            ],
        }

    monkeypatch.setattr("app.edu_school.search_green_library", fake_green)
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
        assert captured["query"] == "开学"
        assert captured["field_id"] == ""
        assert [h["item_id"] for h in out["hits"]] == [
            "aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee"
        ]
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


def test_kb_search_leave_green_is_honest_miss(monkeypatch: pytest.MonkeyPatch) -> None:
    items = [
        {
            "id": "aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee",
            "title": "校历要点.md",
            "excerpt": "三月开学",
            "kind": "material",
        }
    ]

    async def fake_green(*_a, **_k):
        return {"configured": True, "items": list(items), "dumped": False, "status": 200}

    monkeypatch.setattr("app.edu_school.search_green_library", fake_green)
    gw = build_default_gateway(_MemStore())
    principal = _P()

    async def _run() -> None:
        hit = await gw.invoke(principal, "kb_search", {"query": "开学"})
        assert hit["honest_miss"] is False
        items.clear()
        miss = await gw.invoke(principal, "kb_search", {"query": "开学"})
        assert miss["honest_miss"] is True
        assert miss["sources"] == []
        assert "出绿" in miss["user_message"]

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
