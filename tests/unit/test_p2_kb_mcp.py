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
    assert parse_mcp_allowlist(DEFAULT_MCP_ALLOWLIST) == []
    assert parse_mcp_allowlist("mcp_time,mcp_workspace_stat") == [
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
    assert "mcp_time" not in names
    assert "mcp_workspace_stat" not in names


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
    monkeypatch.setenv("MEILI_MASTER_KEY", "test-master")
    monkeypatch.setenv("PICO_MEILI_URL", "http://127.0.0.1:7700")
    monkeypatch.delenv("SILICONFLOW_API_KEY", raising=False)

    def fake_search(query, *, school_id, membership_id, limit=8, client=None, rerank_ok=True, include_school=False):
        _ = client
        assert school_id == principal.school_id
        assert membership_id == principal.membership_id
        if "量子" in query:
            return {"hits": [], "hybrid": False}
        return {
            "hybrid": False,
            "hits": [
                {
                    "artifact_id": "art-cal",
                    "title": "校历要点.md",
                    "text": "春季学期于 3 月 1 日开学，期末考试在 6 月下旬。",
                    "school_id": principal.school_id,
                    "membership_id": principal.membership_id,
                }
            ],
        }

    monkeypatch.setattr(
        "pico_orchestrator.tools_builtin.search_materials", fake_search
    )

    async def _run() -> None:
        gw = build_default_gateway(store)
        hit = await gw.invoke(principal, "kb_search", {"query": "开学"})
        assert hit["honest_miss"] is False
        assert hit["count"] == 1
        assert hit["hits"][0]["artifact_id"] == "art-cal"
        assert "开学" in hit["hits"][0]["excerpt"]
        assert hit["retrieved"] is True
        assert hit["sources"][0]["artifact_id"] == "art-cal"
        assert hit["sources"][0]["title"] == "校历要点.md"
        assert hit["mode"] == "keyword"

        miss = await gw.invoke(principal, "kb_search", {"query": "量子隧穿"})
        assert miss["honest_miss"] is True
        assert miss["count"] == 0
        assert miss["sources"] == []
        assert "已入库" in miss["user_message"]

    asyncio.run(_run())


def test_kb_search_excerpt_covers_sibling_passages(monkeypatch: pytest.MonkeyPatch) -> None:
    """#1006 knife 3: the evidence line is often the file's 2nd/3rd pooled chunk."""
    store = _MemStore()
    principal = _P()
    monkeypatch.setenv("MEILI_MASTER_KEY", "test-master")
    monkeypatch.setenv("PICO_MEILI_URL", "http://127.0.0.1:7700")

    def fake_search(query, *, school_id, membership_id, limit=8, client=None, rerank_ok=True, include_school=False):
        _ = (query, school_id, membership_id, limit, client)
        return {
            "hybrid": True,
            "hits": [
                {
                    "artifact_id": "art-rule",
                    "title": "考务细则.docx",
                    "text": "第一章 总则",
                    "school_id": principal.school_id,
                    "membership_id": principal.membership_id,
                    "passages": [
                        {"chunk_id": "r_0", "text": "第一章 总则"},
                        {"chunk_id": "r_5", "text": "监考老师须提前二十分钟到场领取试卷。"},
                        {"chunk_id": "r_5", "text": "监考老师须提前二十分钟到场领取试卷。"},
                    ],
                }
            ],
        }

    monkeypatch.setattr("pico_orchestrator.tools_builtin.search_materials", fake_search)

    async def _run() -> None:
        gw = build_default_gateway(store)
        hit = await gw.invoke(principal, "kb_search", {"query": "监考几点到"})
        assert hit["count"] == 1
        excerpt = hit["hits"][0]["excerpt"]
        assert "第一章 总则" in excerpt
        assert "提前二十分钟" in excerpt
        assert excerpt.count("提前二十分钟") == 1
        assert hit["sources"][0]["snippet"] == excerpt

    asyncio.run(_run())


def test_kb_search_meili_down_is_honest_miss(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("MEILI_MASTER_KEY", "test-master")
    monkeypatch.setenv("PICO_MEILI_URL", "http://127.0.0.1:7700")

    def boom(*_a, **_k):
        raise RuntimeError("meili unavailable")

    monkeypatch.setattr("pico_orchestrator.tools_builtin.search_materials", boom)
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
        assert out["mode"] == "down"
        assert out["degraded"] is True
        assert out["hits"] == []
        assert "不能编造" in out["user_message"]

    asyncio.run(_run())


def test_kb_search_ignores_client_filter(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, Any] = {}
    monkeypatch.setenv("MEILI_MASTER_KEY", "test-master")
    monkeypatch.setenv("PICO_MEILI_URL", "http://127.0.0.1:7700")

    def fake_search(query, *, school_id, membership_id, limit=8, client=None, rerank_ok=True, include_school=False):
        captured["school_id"] = school_id
        captured["membership_id"] = membership_id
        captured["query"] = query
        _ = limit, client
        return {
            "hybrid": False,
            "hits": [
                {
                    "artifact_id": "art-1",
                    "title": "本校.md",
                    "text": "开学典礼",
                    "school_id": school_id,
                    "membership_id": membership_id,
                }
            ],
        }

    monkeypatch.setattr(
        "pico_orchestrator.tools_builtin.search_materials", fake_search
    )
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
        assert [h["artifact_id"] for h in out["hits"]] == ["art-1"]
        assert out["honest_miss"] is False

    asyncio.run(_run())


def test_mcp_time_and_workspace_stat(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PICO_MCP_ALLOWLIST", "mcp_time,mcp_workspace_stat")
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


def test_kb_search_drops_other_tenant_hits(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MEILI_MASTER_KEY", "test-master")
    monkeypatch.setenv("PICO_MEILI_URL", "http://127.0.0.1:7700")

    def fake_search(query, *, school_id, membership_id, limit=8, client=None, rerank_ok=True, include_school=False):
        _ = query, school_id, membership_id, limit, client
        return {
            "hybrid": False,
            "hits": [
                {
                    "artifact_id": "art-other",
                    "title": "别校.md",
                    "text": "三月开学",
                    "school_id": "other-school",
                    "membership_id": "other-member",
                }
            ],
        }

    monkeypatch.setattr(
        "pico_orchestrator.tools_builtin.search_materials", fake_search
    )
    gw = build_default_gateway(_MemStore())
    principal = _P()

    async def _run() -> None:
        miss = await gw.invoke(principal, "kb_search", {"query": "开学"})
        assert miss["honest_miss"] is True
        assert miss["hits"] == []
        assert miss["sources"] == []

    asyncio.run(_run())


_EDU_OK = "11111111-2222-4333-8444-555555555555"
_EDU_HIDDEN = "66666666-7777-4888-9999-aaaaaaaaaaaa"


def _school_scope_on(monkeypatch: pytest.MonkeyPatch) -> None:
    """Teacher ticked 全校可检索; no real DB needed for the named-bind lookup."""

    class _Session:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc):
            return False

    async def fake_scope(principal, conversation_id, session=None, settings=None):
        return {"include_school": True, "allow_ids": None, "search_school": True, "field_ids": []}

    monkeypatch.setattr("app.db.session_factory", lambda: _Session)
    monkeypatch.setattr("app.edu_school.load_kb_search_scope", fake_scope)


def _school_hits(principal: _P) -> list[dict[str, Any]]:
    def row(art: str, scope: str, member: str) -> dict[str, Any]:
        return {
            "artifact_id": art,
            "title": f"{art}.md",
            "text": "开学典礼 9 月 1 日举行。",
            "scope": scope,
            "school_id": principal.school_id,
            "membership_id": member,
        }

    return [
        row(_EDU_OK, "school", "uploader-x"),
        row(_EDU_HIDDEN, "school", "uploader-y"),
        row("art-mine", "member", principal.membership_id),
    ]


def test_kb_search_school_hits_bound_by_edu(monkeypatch: pytest.MonkeyPatch) -> None:
    """#1175: 全校可检索 must not leak other teachers' private fields."""
    store = _MemStore()
    principal = _P()
    monkeypatch.setenv("MEILI_MASTER_KEY", "test-master")
    monkeypatch.setenv("PICO_MEILI_URL", "http://127.0.0.1:7700")
    _school_scope_on(monkeypatch)
    captured: dict[str, Any] = {}

    def fake_search(query, *, school_id, membership_id, limit=8, client=None, rerank_ok=True, include_school=False):
        _ = query, client
        captured["limit"] = limit
        captured["include_school"] = include_school
        return {"hybrid": False, "hits": _school_hits(principal)}

    async def fake_post(principal_, path, *, body=None, settings=None):
        captured["ids"] = list(body["ids"])
        return {"configured": True, "items": [{"id": _EDU_OK}], "dumped": False}

    monkeypatch.setattr("pico_orchestrator.tools_builtin.search_materials", fake_search)
    monkeypatch.setattr("app.edu_school._edu_post", fake_post)

    async def _run() -> None:
        gw = build_default_gateway(store)
        out = await gw.invoke(principal, "kb_search", {"query": "开学", "limit": 5})
        assert captured["include_school"] is True
        assert captured["limit"] == 10
        assert captured["ids"] == [_EDU_OK, _EDU_HIDDEN]
        assert [h["artifact_id"] for h in out["hits"]] == [_EDU_OK, "art-mine"]
        assert out["school_bind"] == "ok"
        assert out["degraded"] is False

    asyncio.run(_run())


def test_kb_search_edu_down_drops_school_rows_and_says_so(monkeypatch: pytest.MonkeyPatch) -> None:
    from fastapi import HTTPException

    store = _MemStore()
    principal = _P()
    monkeypatch.setenv("MEILI_MASTER_KEY", "test-master")
    monkeypatch.setenv("PICO_MEILI_URL", "http://127.0.0.1:7700")
    _school_scope_on(monkeypatch)

    def fake_search(query, *, school_id, membership_id, limit=8, client=None, rerank_ok=True, include_school=False):
        _ = query, client, limit, include_school
        return {"hybrid": False, "hits": _school_hits(principal)}

    async def fake_post(principal_, path, *, body=None, settings=None):
        raise HTTPException(status_code=502, detail={"code": "edu.unreachable"})

    monkeypatch.setattr("pico_orchestrator.tools_builtin.search_materials", fake_search)
    monkeypatch.setattr("app.edu_school._edu_post", fake_post)

    async def _run() -> None:
        gw = build_default_gateway(store)
        out = await gw.invoke(principal, "kb_search", {"query": "开学"})
        assert [h["artifact_id"] for h in out["hits"]] == ["art-mine"]
        assert out["school_bind"] == "unavailable"
        assert out["degraded"] is True
        assert "核验" in out["user_message"]

    asyncio.run(_run())


def test_kb_search_is_meili_not_edu_green() -> None:
    import inspect

    from pico_orchestrator import tools_builtin

    src = inspect.getsource(tools_builtin)
    assert "search_materials" in src
    assert "search_green_library" not in src
    gw = build_default_gateway(_MemStore())
    assert "这是什么" not in gw.tools["kb_search"].description
    assert "does not mean you must call" in gw.tools["kb_search"].description


def test_skill_kb_ask_snapshot() -> None:
    snap = snapshot_for_skill("skill-kb-ask")
    assert snap is not None
    assert snap["id"] == "skill-kb-ask"
    assert "kb_search" in snap["tools"]
    assert snap["risk"] == "read"


def test_user_message_kb_miss() -> None:
    msg = user_message_for_error("未在已挂载材料中命中", code="kb.miss")
    assert "材料" in msg
