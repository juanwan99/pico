"""T-PICO-EDU-AGENT-PROVIDER (#1068): thin edu catalog/run_pack tools."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from pico_orchestrator.capability_loading import CORE_VISIBLE_TOOLS
from pico_orchestrator.edu_agent_tools import (
    _ETAG_CACHE,
    CATALOG_DESCRIBE,
    MEMBERSHIP_CATALOG,
    RUN_PACK,
    STEWARD_CORPUS,
    _mint_steward,
    catalog_command,
    catalog_command_id,
    catalog_describe,
    catalog_find,
    register_edu_agent_tools,
    run_pack,
    steward_public_corpus,
)
from pico_orchestrator.gateway import AllowlistGateway, ToolError
from pico_orchestrator.page_mutations import PageMutationBook, register_propose_page_mutation
from pico_orchestrator.true_pi.config import ALLOWED_GATEWAY_TOOLS


def test_tools_on_gateway_and_core():
    for name in (CATALOG_DESCRIBE, RUN_PACK, "edu_catalog_find", "edu_catalog_command"):
        assert name in ALLOWED_GATEWAY_TOOLS
        assert name in CORE_VISIBLE_TOOLS
    gw = AllowlistGateway()
    register_edu_agent_tools(gw)
    assert CATALOG_DESCRIBE in gw.tools
    assert STEWARD_CORPUS not in ALLOWED_GATEWAY_TOOLS


def test_catalog_command_id():
    assert catalog_command_id("home.draft.grey")
    assert not catalog_command_id("save")
    assert not catalog_command_id("home draft")


@pytest.mark.asyncio
async def test_describe_etag_second_call_cached():
    _ETAG_CACHE.clear()
    principal = SimpleNamespace(school_id="s1", membership_id="m1")
    payload = {
        "domain": "HOME",
        "etag": "home-v1",
        "commands": [{"id": "home.draft.grey", "label": "起草灰稿"}],
    }
    with patch(
        "pico_orchestrator.edu_agent_tools.edu_request",
        new=AsyncMock(return_value=payload),
    ) as req:
        first = await catalog_describe(principal, {"domain": "HOME"})
        second = await catalog_describe(principal, {"domain": "HOME"})
    assert first["etag"] == "home-v1"
    assert second.get("cache") == "etag"
    assert req.await_count == 1
    assert second["domain"] == "HOME"
    assert req.await_args.args[2] == f"{MEMBERSHIP_CATALOG}/describe"


@pytest.mark.asyncio
async def test_budget_500_not_swallowed():
    _ETAG_CACHE.clear()
    principal = SimpleNamespace(school_id="s1", membership_id="m2")

    async def boom(*_a, **_k):
        raise ToolError("catalog_budget_exceeded", "describe token budget 2000 exceeded")

    with (
        patch("pico_orchestrator.edu_agent_tools.edu_request", new=boom),
        pytest.raises(ToolError) as ei,
    ):
        await catalog_describe(principal, {"domain": "HOME"})
    assert ei.value.code == "catalog_budget_exceeded"


@pytest.mark.asyncio
async def test_catalog_uses_membership_mouth_when_school_present():
    _ETAG_CACHE.clear()
    principal = SimpleNamespace(school_id="s1", membership_id="m1")
    with patch(
        "pico_orchestrator.edu_agent_tools.edu_request",
        new=AsyncMock(return_value={"items": []}),
    ) as req:
        await catalog_find(principal, {"q": "能干"})
        await catalog_command(principal, {"id": "home.draft.grey"})
    paths = [call.args[2] for call in req.await_args_list]
    assert paths == [
        f"{MEMBERSHIP_CATALOG}/find",
        f"{MEMBERSHIP_CATALOG}/command",
    ]
    assert all("/schools/" not in p for p in paths)


@pytest.mark.asyncio
async def test_run_pack_omits_grant_id_when_live():
    principal = SimpleNamespace(school_id="s1", membership_id="m1")
    with patch(
        "pico_orchestrator.edu_agent_tools.edu_request",
        new=AsyncMock(return_value={"receipts": [{"status": "ok", "command": "field.display.draft"}]}),
    ) as req:
        out = await run_pack(
            principal,
            {
                "steps": [
                    {
                        "command": "field.display.draft",
                        "params": {
                            "field_id": "f1",
                            "title": "生物",
                            "q": "生物",
                            "body_md": "细胞膜控制物质进出。",
                        },
                    }
                ],
            },
        )
    assert out["receipts"][0]["status"] == "ok"
    sent = req.await_args.kwargs["body"]
    assert "grant_id" not in sent
    assert sent["steps"][0]["params"]["body_md"].startswith("细胞膜")


@pytest.mark.asyncio
async def test_run_pack_no_ticket_asks_to_issue():
    principal = SimpleNamespace(school_id="s1", membership_id="m1")

    async def missing(*_a, **_k):
        raise ToolError("agent_grant_missing", "没有可用的活票，先在工作台开票")

    with (
        patch("pico_orchestrator.edu_agent_tools.edu_request", new=missing),
        pytest.raises(ToolError) as ei,
    ):
        await run_pack(principal, {"steps": [{"command": "field.display.draft", "params": {}}]})
    assert ei.value.code == "agent_grant_missing"
    assert "开票" in str(ei.value)


@pytest.mark.asyncio
async def test_run_pack_submit_forbidden():
    principal = SimpleNamespace(school_id="s1", membership_id="m1")

    async def forbid(*_a, **_k):
        raise ToolError("ai_final_effect_forbidden", "高风险命令不能按票自动执行")

    with (
        patch("pico_orchestrator.edu_agent_tools.edu_request", new=forbid),
        pytest.raises(ToolError) as ei,
    ):
        await run_pack(
            principal,
            {
                "grant_id": "g1",
                "steps": [{"command": "home.collect.submit", "params": {}}],
            },
        )
    assert ei.value.code == "ai_final_effect_forbidden"


@pytest.mark.asyncio
async def test_propose_accepts_catalog_id_without_page():
    gw = AllowlistGateway()
    register_propose_page_mutation(gw, None)
    spec = gw.tools["propose_page_mutation"]
    out = await spec.handler(
        SimpleNamespace(school_id="s1", membership_id="m1"),
        {"affordance_id": "home.draft.grey", "params": {"title": "教研组计划"}},
    )
    assert out["source"] == "catalog"
    assert out["affordanceId"] == "home.draft.grey"


def test_propose_book_accepts_catalog_id():
    book = PageMutationBook(affordances=[], page_title="x")
    out = book.propose({"affordance_id": "home.draft.grey", "params": {}})
    assert out["source"] == "catalog"


def test_detach_on_disconnect_default():
    import os

    raw = (os.environ.get("PICO_RUN_DETACH_ON_DISCONNECT") or "1").strip().lower()
    assert raw not in {"0", "false", "no"}


def test_mint_steward_has_no_membership(monkeypatch):
    import jwt

    monkeypatch.setenv("PICO_EDU_ISS", "https://edu.example/iss/pico")
    monkeypatch.setenv("PICO_EDU_JWT_SECRET", "edu-secret-at-least-32-bytes-long!!!")
    token = _mint_steward("s1")
    payload = jwt.decode(token, "edu-secret-at-least-32-bytes-long!!!", algorithms=["HS256"], audience="pico-api")
    assert payload["school_id"] == "s1"
    assert payload["scopes"] == ["ai:steward-public"]
    assert "membership_id" not in payload


@pytest.mark.asyncio
async def test_steward_corpus_hits_public_mouth(monkeypatch):
    monkeypatch.setenv("PICO_EDU_ISS", "https://edu.example/iss/pico")
    monkeypatch.setenv("PICO_EDU_JWT_SECRET", "edu-secret-at-least-32-bytes-long!!!")
    monkeypatch.setenv("PICO_EDU_BASE_URL", "https://edu.weiyuji.cn")
    principal = SimpleNamespace(school_id="s1", membership_id="must-not-be-used")

    class FakeResp:
        status_code = 200

        def json(self):
            return {"field": {"name": "全校教职工"}, "files": [], "chats": [], "tables": [], "dumped": False}

    class FakeClient:
        def __init__(self, *a, **k):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def get(self, url, headers=None):
            assert url.endswith("/v1/pico/steward/public-corpus")
            import jwt

            payload = jwt.decode(
                headers["Authorization"].split()[1],
                "edu-secret-at-least-32-bytes-long!!!",
                algorithms=["HS256"],
                audience="pico-api",
            )
            assert "membership_id" not in payload
            assert payload["scopes"] == ["ai:steward-public"]
            return FakeResp()

    with patch("pico_orchestrator.edu_agent_tools.httpx.AsyncClient", FakeClient):
        out = await steward_public_corpus(principal, {})
    assert out["field"]["name"] == "全校教职工"
    assert out["dumped"] is False
