"""T-PICO-WIRE (Pico half · #975): left-page proposals from the edu sidebar.

The page reports affordances; the model may stage mutations against those ids
only; Pico records them in its ledger shape and hands the envelope back.
Nothing here executes a school command.
"""

from __future__ import annotations

import asyncio
import json
import sys
from dataclasses import dataclass
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "api"))
sys.path.insert(0, str(ROOT / "services" / "orchestrator"))

from pico_orchestrator.capability_loading import (
    CORE_VISIBLE_TOOLS,
    EXTENDED_TOOLS,
    resolve_visible_tools,
)
from pico_orchestrator.gateway import ToolError
from pico_orchestrator.page_mutations import (
    SIDEBAR_PAGE_HANDS_HINT,
    TOOL_NAME,
    PageMutationBook,
    affordances_from_request,
    normalize_affordances,
    page_title_from_request,
)
from pico_orchestrator.run_types import RunCaps
from pico_orchestrator.tools_builtin import build_default_gateway
from pico_orchestrator.true_pi.config import ALLOWED_GATEWAY_TOOLS

AFFORDANCES = [
    {"id": "cell:c1:mon:3", "kind": "cell", "label": "周一第3节", "tier": "work", "writable": True},
    {"id": "input:lesson:l1:weekly", "kind": "input", "label": "英语 周课时", "current": 4},
    {"id": "action:writeback", "kind": "action", "label": "回写日常", "tier": "final"},
    {"id": "check:rule:9", "kind": "check", "label": "硬规则9", "writable": False},
]


@dataclass
class _P:
    school_id: str = "s1"
    membership_id: str = "m1"
    scopes: tuple[str, ...] = ("ai:run",)


def test_normalize_keeps_ids_and_dedups() -> None:
    rows = normalize_affordances(AFFORDANCES + [{"affordanceId": "x:1"}, {"id": "cell:c1:mon:3"}, "junk", {}])
    ids = [r["id"] for r in rows]
    assert ids == ["cell:c1:mon:3", "input:lesson:l1:weekly", "action:writeback", "check:rule:9", "x:1"]
    assert normalize_affordances(None) == []
    assert normalize_affordances({"id": "not-a-list"}) == []


def test_affordances_from_request_sources() -> None:
    # metadata first
    assert affordances_from_request({"affordances": AFFORDANCES[:1]}, None, None)[0]["id"] == "cell:c1:mon:3"
    # then the 附属 system JSON (with prose before the object)
    system = "你是当前屏幕的助手。附属，不是用户要求。\n" + json.dumps(
        {"page": {"title": "排课工作台", "affordances": AFFORDANCES[:2]}}, ensure_ascii=False
    )
    got = affordances_from_request(None, system, "把周一第3节排上英语")
    assert [r["id"] for r in got] == ["cell:c1:mon:3", "input:lesson:l1:weekly"]
    assert page_title_from_request(system) == "排课工作台"
    # then the user JSON (json_only shape)
    user = json.dumps({"asked": "改成 5", "affordances": AFFORDANCES[1:2]}, ensure_ascii=False)
    assert affordances_from_request(None, "附属，不是用户要求", user)[0]["id"] == "input:lesson:l1:weekly"
    # nothing → empty, never invented
    assert affordances_from_request(None, "附属，不是用户要求\n{}", "你好") == []
    assert page_title_from_request("plain text") == ""


def test_book_stages_only_known_writable_ids() -> None:
    book = PageMutationBook(affordances=normalize_affordances(AFFORDANCES), page_title="排课工作台")
    out = book.propose({"affordance_id": "input:lesson:l1:weekly", "params": {"weekly_lessons": 5}})
    assert out["staged"] is True and out["count"] == 1
    assert book.mutations[0] == {
        "affordanceId": "input:lesson:l1:weekly",
        "params": {"weekly_lessons": 5},
        "label": "英语 周课时",
        "tier": "work",
        "status": "staged",
    }
    # final-tier affordance is still only a proposal; tier travels with it
    book.propose({"affordanceId": "action:writeback", "label": "回写"})
    assert book.mutations[1]["tier"] == "final"
    with pytest.raises(ToolError) as unknown:
        book.propose({"affordance_id": "cell:nope"})
    assert unknown.value.code == "page.affordance_unknown"
    with pytest.raises(ToolError) as readonly:
        book.propose({"affordance_id": "check:rule:9"})
    assert readonly.value.code == "page.affordance_readonly"
    with pytest.raises(ToolError) as empty:
        book.propose({})
    assert empty.value.code == "page.affordance_required"
    with pytest.raises(ToolError):
        book.propose({"affordance_id": "cell:c1:mon:3", "params": "not-an-object"})


def test_change_proposal_shape_matches_handoff_contract() -> None:
    book = PageMutationBook(affordances=normalize_affordances(AFFORDANCES), page_title="排课工作台")
    assert book.change_proposal() is None
    book.propose({"affordance_id": "cell:c1:mon:3", "params": {"subject": "英语"}})
    prop = book.change_proposal()["proposal"]
    assert prop["title"].startswith("页内改动提案")
    assert "排课工作台" in prop["title"]
    assert prop["status"] == "proposed"
    assert prop["payload"]["domain"] == "page"
    assert prop["payload"]["mutations"][0]["affordanceId"] == "cell:c1:mon:3"
    assert "周一第3节" in prop["summary"]


def test_gateway_hand_fails_closed_without_a_page() -> None:
    gw = build_default_gateway()
    assert TOOL_NAME in gw.tools
    with pytest.raises(ToolError) as exc:
        asyncio.run(gw.invoke(_P(), TOOL_NAME, {"affordance_id": "cell:c1:mon:3"}))
    assert exc.value.code == "page.no_affordances"


def test_gateway_hand_records_into_the_run_book() -> None:
    book = PageMutationBook(affordances=normalize_affordances(AFFORDANCES))
    gw = build_default_gateway(page_mutations=book)
    out = asyncio.run(
        gw.invoke(_P(), TOOL_NAME, {"affordance_id": "cell:c1:mon:3", "params": {"subject": "英语"}})
    )
    assert out["staged"] is True
    assert len(book.mutations) == 1


def test_tool_is_extended_not_core_and_on_every_surface() -> None:
    assert TOOL_NAME in ALLOWED_GATEWAY_TOOLS
    assert TOOL_NAME in EXTENDED_TOOLS
    assert TOOL_NAME not in CORE_VISIBLE_TOOLS
    # Default visibility (no page) never shows it.
    assert TOOL_NAME not in resolve_visible_tools(None)
    ts = (ROOT / "services" / "true_pi_bridge" / "pico-gateway-tools.ts").read_text(encoding="utf-8")
    assert f'"{TOOL_NAME}"' in ts


def test_compat_caps_and_envelope() -> None:
    from app.openai_compat import _caps_with_page_hands, _mutations_envelope

    caps = RunCaps()
    same = _caps_with_page_hands(caps, [], "")
    assert same is caps
    hands = _caps_with_page_hands(caps, normalize_affordances(AFFORDANCES), "排课工作台")
    assert hands.page_affordances and hands.page_title == "排课工作台"
    # No affordances → no field at all (workbench / plain sidebar unchanged).
    assert _mutations_envelope([], [{"affordanceId": "x"}]) is None
    # Affordances present → field always present; empty list is a real answer.
    assert _mutations_envelope(AFFORDANCES, None) == {"pico_mutations": []}
    assert _mutations_envelope(AFFORDANCES, [{"affordanceId": "x"}]) == {
        "pico_mutations": [{"affordanceId": "x"}]
    }


@pytest.mark.asyncio
async def test_true_pi_run_widens_hands_only_with_a_page() -> None:
    from pico_orchestrator.true_pi.client import FakeTransport, scripted_open_domain_success
    from pico_orchestrator.true_pi.runtime import run_true_pi_agent

    async def _run(caps: RunCaps):
        events: list[tuple[str, dict]] = []

        async def emit(kind: str, payload: dict) -> None:
            events.append((kind, payload))

        result = await run_true_pi_agent(
            prompt="把周一第3节排上英语",
            principal=_P(),
            emit=emit,
            is_cancelled=_no,
            caps=caps,
            transport=FakeTransport(
                scripted=scripted_open_domain_success(), assistant_text="已拟好，请确认。"
            ),
            run_id="pm-1",
        )
        visible = next(p["visible_tools"] for k, p in events if k == "run.model")
        return result, visible

    plain, visible_plain = await _run(RunCaps(max_seconds=30, max_steps=8))
    assert TOOL_NAME not in visible_plain
    assert plain.page_mutations is None
    assert plain.change_proposal is None

    paged, visible_paged = await _run(
        RunCaps(
            max_seconds=30,
            max_steps=8,
            page_affordances=normalize_affordances(AFFORDANCES),
            page_title="排课工作台",
        )
    )
    assert TOOL_NAME in visible_paged
    assert set(CORE_VISIBLE_TOOLS) <= set(visible_paged)
    # Scripted run never called the hand: empty list is the honest answer.
    assert paged.page_mutations == []
    assert paged.change_proposal is None


async def _no() -> bool:
    return False


def test_hint_mentions_page_hands_only_when_page_has_them() -> None:
    from app.edu_sidebar_pi import _hint_caps

    plain = RunCaps(system_prompt="附属，不是用户要求\n{}")
    assert SIDEBAR_PAGE_HANDS_HINT not in _hint_caps(plain).system_prompt
    with_hands = RunCaps(
        system_prompt="附属，不是用户要求\n{}",
        page_affordances=normalize_affordances(AFFORDANCES),
    )
    hinted = _hint_caps(with_hands).system_prompt
    assert SIDEBAR_PAGE_HANDS_HINT in hinted
    assert TOOL_NAME in hinted
    assert _hint_caps(_hint_caps(with_hands)).system_prompt == hinted
