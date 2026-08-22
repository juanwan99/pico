"""T-AGENT-PLAIN-V1: multi-turn work finishes; hide plan passphrase / ANSI."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "api"))
sys.path.insert(0, str(ROOT / "services" / "orchestrator"))

from pico_orchestrator.human_package import (
    is_plan_passphrase,
    public_progress_delta,
    sanitize_user_facing_text,
    strip_ansi,
)
from pico_orchestrator.run_types import RunCaps
from pico_orchestrator.true_pi.client import FakeTransport, RpcEvent, choose_plan_select
from pico_orchestrator.true_pi.events import EventMapState, map_event
from pico_orchestrator.true_pi.runtime import plan_settle_hold, run_true_pi_agent


class Principal:
    def __init__(self, school_id: str = "school-a", membership_id: str = "member-a") -> None:
        self.school_id = school_id
        self.membership_id = membership_id
        self.scopes = ["ai:run"]


async def _not_cancelled() -> bool:
    return False


def test_choose_plan_select_tracks_real_todos_only() -> None:
    value, pending = choose_plan_select(
        [
            "Execute the plan (track progress)",
            "Stay in plan mode",
            "Refine the plan",
        ]
    )
    assert value.startswith("Execute")
    assert pending is True


def test_choose_plan_select_empty_plan_stays() -> None:
    value, pending = choose_plan_select(
        ["Execute the plan", "Stay in plan mode", "Refine the plan"]
    )
    assert value.startswith("Stay")
    assert pending is False


def test_plan_settle_first_end_holds_second_lands() -> None:
    hold1, ends1, _ = plan_settle_hold(
        event_type="agent_end",
        plan_flag=True,
        plan_agent_ends=0,
        plan_execute_pending=True,
    )
    assert hold1 is True
    assert ends1 == 1
    hold2, ends2, _ = plan_settle_hold(
        event_type="agent_end",
        plan_flag=True,
        plan_agent_ends=1,
        plan_execute_pending=True,
    )
    assert hold2 is False
    assert ends2 == 2


def test_plan_settle_without_flag_never_holds() -> None:
    hold, ends, _ = plan_settle_hold(
        event_type="agent_end",
        plan_flag=False,
        plan_agent_ends=0,
        plan_execute_pending=True,
    )
    assert hold is False
    assert ends == 0


def test_strip_ansi_and_execute_passphrase() -> None:
    painted = "\x1b[38;5;226m⏸ plan\x1b[39m"
    assert "\x1b" not in strip_ansi(painted)
    assert is_plan_passphrase(painted)
    assert is_plan_passphrase("Execute the plan you just created.")
    assert is_plan_passphrase("Execute the plan. Start with: 写教案")
    assert not is_plan_passphrase("三年级二班 42 人，识字两极分化。")
    out = sanitize_user_facing_text(
        "Execute the plan you just created.\n本单元是《春天来了》。",
        artifact_titles=[],
    )
    assert "Execute the plan" not in out
    assert "春天来了" in out


def test_public_progress_hides_passphrase() -> None:
    assert public_progress_delta({"text": "Execute the plan you just created.", "customType": "plan-mode-execute"}) == ""
    assert public_progress_delta({"text": "\x1b[38;5;226m⏸ plan\x1b[39m", "method": "setStatus"}) == ""
    assert public_progress_delta({"text": "**Plan Steps (2):**\n1. ☐ 写", "customType": "plan-todo-list"}) == "正在整理步骤"


@pytest.mark.asyncio
async def test_plan_internal_message_not_in_final_parts() -> None:
    state = EventMapState()
    events: list[tuple[str, dict[str, Any]]] = []

    async def emit(k: str, p: dict[str, Any]) -> None:
        events.append((k, p))

    await map_event(
        RpcEvent(
            {
                "type": "message_end",
                "message": {
                    "role": "assistant",
                    "customType": "plan-mode-execute",
                    "content": "Execute the plan you just created.",
                },
            }
        ),
        emit=emit,
        state=state,
    )
    await map_event(
        RpcEvent(
            {
                "type": "message_end",
                "message": {"role": "assistant", "content": "两份材料已读：三年级二班，单元《春天来了》。"},
            }
        ),
        emit=emit,
        state=state,
    )
    assert "Execute the plan" not in " ".join(state.final_parts)
    assert any("春天来了" in part for part in state.final_parts)


@pytest.mark.asyncio
async def test_plan_flag_single_end_lands_without_second() -> None:
    events: list[tuple[str, dict[str, Any]]] = []

    async def emit(k: str, p: dict[str, Any]) -> None:
        events.append((k, p))

    transport = FakeTransport(
        scripted=[
            {"type": "agent_start"},
            {
                "type": "message_end",
                "message": {"role": "assistant", "content": "班情是三年级二班 42 人；要点是《春天来了》。"},
            },
            {"type": "agent_end", "willRetry": False},
        ],
        assistant_text="班情是三年级二班 42 人；要点是《春天来了》。",
    )
    transport.plan_flag = True
    transport.plan_agent_ends = 0
    transport.plan_execute_pending = False
    result = await run_true_pi_agent(
        prompt="先读这两份，各用一句话概括",
        principal=Principal(),
        emit=emit,
        is_cancelled=_not_cancelled,
        caps=RunCaps(min_artifacts=0, max_seconds=8),
        transport=transport,
    )
    assert result.status == "succeeded"
    assert "春天来了" in (result.final_text or "")
    assert "Execute the plan" not in (result.final_text or "")
    assert "\x1b" not in (result.final_text or "")
    assert transport.plan_agent_ends == 1


@pytest.mark.asyncio
async def test_plan_flag_two_ends_lands_not_third() -> None:
    events: list[tuple[str, dict[str, Any]]] = []

    async def emit(k: str, p: dict[str, Any]) -> None:
        events.append((k, p))

    transport = FakeTransport(
        scripted=[
            {"type": "agent_start"},
            {
                "type": "message_end",
                "message": {"role": "assistant", "content": "Plan:\n1. 写教案\n2. 落盘"},
            },
            {"type": "agent_end", "willRetry": False},
            {
                "type": "tool_execution_start",
                "toolName": "generate_docx_document",
                "toolCallId": "c1",
                "args": {"title": "教案.docx", "body": "ok"},
            },
            {
                "type": "tool_execution_end",
                "toolName": "generate_docx_document",
                "toolCallId": "c1",
                "isError": False,
                "result": {"content": [{"type": "text", "text": '{"title":"教案.docx"}'}]},
            },
            {
                "type": "message_end",
                "message": {"role": "assistant", "content": "已写入教案.docx"},
            },
            {"type": "agent_end", "willRetry": False},
        ],
        assistant_text="已写入教案.docx",
    )
    transport.plan_flag = True
    transport.plan_agent_ends = 0
    transport.plan_execute_pending = True
    result = await run_true_pi_agent(
        prompt="教案并落盘",
        principal=Principal(),
        emit=emit,
        is_cancelled=_not_cancelled,
        caps=RunCaps(min_artifacts=1, max_seconds=8),
        transport=transport,
    )
    assert result.status == "succeeded"
    assert transport.plan_agent_ends == 2
    assert "Execute the plan" not in (result.final_text or "")
    statuses = [p.get("status") for k, p in events if k == "run.status"]
    assert "succeeded" in statuses
    assert statuses[-1] == "succeeded"
