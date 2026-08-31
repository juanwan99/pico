"""T-PLAN-WIRE: 先计划 toggle → --plan this turn; plan Artifact; HITL Execute."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "api"))
sys.path.insert(0, str(ROOT / "services" / "orchestrator"))

from app.openai_compat import ChatCompletionRequest, _caps_with_plan, _request_plan_on
from pico_orchestrator.run_types import RunCaps
from pico_orchestrator.true_pi.client import (
    PLAN_NEXT_QUESTION,
    RpcEvent,
    SubprocessTransport,
    choose_plan_select,
    display_plan_options,
    is_plan_select,
    plan_choice_pending,
)
from pico_orchestrator.true_pi.events import (
    EventMapState,
    map_event,
    maybe_write_plan_artifact,
    plan_artifact_title,
)
from pico_orchestrator.true_pi.runtime import (
    plan_settle_hold,
    run_true_pi_agent,
    want_plan_mode_extension,
)


class Principal:
    def __init__(self, school_id: str = "school-a", membership_id: str = "member-a") -> None:
        self.school_id = school_id
        self.membership_id = membership_id
        self.scopes = ["ai:run"]


class FakePlanStore:
    def __init__(self) -> None:
        self.writes: list[dict[str, Any]] = []

    async def write(self, principal: Any, *, title: str, content: str | bytes, kind: str) -> dict[str, Any]:
        row = {
            "id": f"art-{len(self.writes) + 1}",
            "title": title,
            "kind": kind,
            "content": content,
            "school_id": getattr(principal, "school_id", ""),
        }
        self.writes.append(row)
        return row


def test_request_plan_on_never_defaults() -> None:
    body = ChatCompletionRequest(messages=[{"role": "user", "content": "hi"}])
    assert _request_plan_on(body) is False
    assert _request_plan_on(body, "false") is False
    body.pico_plan = True
    assert _request_plan_on(body) is True
    off = ChatCompletionRequest(
        messages=[{"role": "user", "content": "hi"}],
        metadata={"pico_plan": True},
    )
    assert _request_plan_on(off) is True
    assert _request_plan_on(ChatCompletionRequest(messages=[{"role": "user", "content": "x"}]), "1") is True
    # FastAPI Header() default is a params object; missing header must stay off.
    from fastapi.params import Header as HeaderParam

    blank = ChatCompletionRequest(messages=[{"role": "user", "content": "hi"}])
    sentinel = HeaderParam(default=None, alias="X-Pico-Plan")
    assert _request_plan_on(blank, sentinel) is False  # type: ignore[arg-type]
    assert _request_plan_on(blank, None) is False


def test_caps_with_plan_is_opt_in() -> None:
    caps = RunCaps()
    assert caps.plan_on is False
    assert _caps_with_plan(caps, False).plan_on is False
    assert _caps_with_plan(caps, True).plan_on is True


def test_plan_mode_extension_only_when_this_spawn_plan_on() -> None:
    """T3: tree sessions must not load plan-mode and resurrect HITL after hi."""
    assert want_plan_mode_extension(plan_on=False) is False
    assert want_plan_mode_extension(plan_on=True) is True


def test_spawn_plan_flag_only_when_on() -> None:
    off = SubprocessTransport(
        session_dir=Path("/tmp/tp-sess"),
        tool_url="http://127.0.0.1:1",
        tool_token="tok",
        run_id="r1",
        plan_flag=False,
    )
    on = SubprocessTransport(
        session_dir=Path("/tmp/tp-sess"),
        tool_url="http://127.0.0.1:1",
        tool_token="tok",
        run_id="r1",
        plan_flag=True,
    )
    assert "--plan" not in off.spawn_command()
    assert "--plan" in on.spawn_command()


def test_display_plan_options_are_chinese() -> None:
    shown, reverse = display_plan_options(
        [
            "Execute the plan (track progress)",
            "Stay in plan mode",
            "Refine the plan",
        ]
    )
    assert shown == ["确认执行", "先不执行", "再改计划"]
    assert reverse["确认执行"].startswith("Execute")
    assert reverse["先不执行"].startswith("Stay")
    assert is_plan_select(["Execute the plan", "Stay in plan mode"])
    assert not is_plan_select(["red", "blue"])
    assert plan_choice_pending("Execute the plan (track progress)") is True
    assert plan_choice_pending("确认执行") is True
    assert plan_choice_pending("Stay in plan mode") is False


def test_plan_artifact_title_counts_steps() -> None:
    text = "**Plan Steps (2):**\n\n1. ☐ 写大纲\n2. ☐ 落盘"
    assert plan_artifact_title(text) == "计划（2 步）.md"
    assert plan_artifact_title("hello") == "计划.md"


@pytest.mark.asyncio
async def test_plan_todo_list_writes_kind_plan() -> None:
    store = FakePlanStore()
    events: list[tuple[str, dict[str, Any]]] = []

    async def emit(k: str, p: dict[str, Any]) -> None:
        events.append((k, p))

    raw = {
        "type": "message_end",
        "message": {
            "role": "assistant",
            "customType": "plan-todo-list",
            "content": "**Plan Steps (2):**\n\n1. ☐ 写大纲\n2. ☐ 落盘",
        },
    }
    written = await maybe_write_plan_artifact(
        raw, artifact_store=store, principal=Principal()
    )
    assert written is not None
    assert written["kind"] == "plan"
    assert written["title"].endswith(".md")
    assert "写大纲" in str(written["content"])

    state = EventMapState()
    await map_event(
        RpcEvent(raw),
        emit=emit,
        state=state,
        artifact_store=store,
        principal=Principal(),
    )
    assert any(k == "plan.progress" for k, _ in events)
    assert len(store.writes) == 2
    assert all(row["kind"] == "plan" for row in store.writes)


@pytest.mark.asyncio
async def test_hitl_select_maps_execute_and_stays_on_empty() -> None:
    t = SubprocessTransport(
        session_dir=Path("/tmp/tp-sess"),
        tool_url="http://127.0.0.1:1",
        tool_token="tok",
        run_id="r-hitl",
        plan_flag=True,
        plan_hitl=True,
    )
    t.send = AsyncMock()

    async def pick_execute(_q: str, opts: list[str]) -> str:
        assert "确认执行" in opts
        assert PLAN_NEXT_QUESTION
        return "确认执行"

    t.ui_select = pick_execute
    await t._reply_extension_ui(
        {
            "method": "select",
            "id": 7,
            "options": [
                "Execute the plan (track progress)",
                "Stay in plan mode",
                "Refine the plan",
            ],
        }
    )
    assert t.plan_execute_pending is True
    sent = t.send.await_args.args[0]
    assert sent["value"].lower().startswith("execute")

    async def pick_timeout(_q: str, _opts: list[str]) -> str:
        return ""

    t.ui_select = pick_timeout
    t.send.reset_mock()
    await t._reply_extension_ui(
        {
            "method": "select",
            "id": 8,
            "options": [
                "Execute the plan (track progress)",
                "Stay in plan mode",
            ],
        }
    )
    assert t.plan_execute_pending is False
    assert t.send.await_args.args[0]["value"].lower().startswith("stay")


@pytest.mark.asyncio
async def test_t3_plan_off_first_end_lands() -> None:
    from pico_orchestrator.true_pi.client import FakeTransport

    events: list[tuple[str, dict[str, Any]]] = []

    async def emit(k: str, p: dict[str, Any]) -> None:
        events.append((k, p))

    async def not_cancelled() -> bool:
        return False

    transport = FakeTransport(
        scripted=[
            {"type": "agent_start"},
            {
                "type": "message_end",
                "message": {"role": "assistant", "content": "北京今天多云。"},
            },
            {"type": "agent_end", "willRetry": False},
        ],
        assistant_text="北京今天多云。",
    )
    transport.plan_flag = False
    result = await run_true_pi_agent(
        prompt="今天天气？",
        principal=Principal(),
        emit=emit,
        is_cancelled=not_cancelled,
        caps=RunCaps(plan_on=False, min_artifacts=0, max_seconds=8),
        transport=transport,
    )
    assert result.status == "succeeded"
    assert "多云" in (result.final_text or "")
    hold, _, _ = plan_settle_hold(
        event_type="agent_end",
        plan_flag=False,
        plan_agent_ends=0,
        plan_execute_pending=True,
    )
    assert hold is False
    # Auto-select still prefers Stay on empty-plan passphrase.
    value, pending = choose_plan_select(
        ["Execute the plan", "Stay in plan mode", "Refine the plan"]
    )
    assert value.startswith("Stay")
    assert pending is False
