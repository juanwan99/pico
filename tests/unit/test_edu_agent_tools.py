"""T-PICO-EDU-AGENT-PROVIDER (#1068): thin edu catalog/run_pack tools."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from pico_orchestrator.capability_loading import CORE_VISIBLE_TOOLS
from pico_orchestrator.edu_agent_tools import (
    _ETAG_CACHE,
    CATALOG_DESCRIBE,
    RUN_PACK,
    catalog_command_id,
    catalog_describe,
    register_edu_agent_tools,
    run_pack,
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


@pytest.mark.asyncio
async def test_budget_500_not_swallowed():
    principal = SimpleNamespace(school_id="s1", membership_id="m1")

    async def boom(*_a, **_k):
        raise ToolError("catalog_budget_exceeded", "describe token budget 2000 exceeded")

    with (
        patch("pico_orchestrator.edu_agent_tools.edu_request", new=boom),
        pytest.raises(ToolError) as ei,
    ):
        await catalog_describe(principal, {"domain": "HOME"})
    assert ei.value.code == "catalog_budget_exceeded"


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
