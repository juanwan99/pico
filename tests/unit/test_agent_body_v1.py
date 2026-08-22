"""T-AGENT-BODY-V1: Pi session tree, official plan-mode hang, compaction human."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "api"))
sys.path.insert(0, str(ROOT / "services" / "orchestrator"))

from app.openai_compat import _sidebar_chat_only, _workbench_tool_step_line
from pico_orchestrator.run_types import RunCaps
from pico_orchestrator.true_pi.client import FakeTransport, RpcEvent, SubprocessTransport
from pico_orchestrator.true_pi.config import (
    persist_session_dir,
    plan_mode_extension_path,
    session_segment,
)
from pico_orchestrator.true_pi.events import COMPACTION_HUMAN, EventMapState, map_event
from pico_orchestrator.true_pi.runtime import _compose_prompt, run_true_pi_agent


class Principal:
    def __init__(self, school_id: str = "school-a", membership_id: str = "member-a") -> None:
        self.school_id = school_id
        self.membership_id = membership_id
        self.scopes = ["ai:run"]


async def _not_cancelled() -> bool:
    return False


def test_session_dir_isolated_by_school_and_convo(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("PICO_TRUE_PI_SESSION_ROOT", str(tmp_path))
    a = persist_session_dir(school_id="school-a", conversation_id="convo-1")
    b = persist_session_dir(school_id="school-b", conversation_id="convo-1")
    c = persist_session_dir(school_id="school-a", conversation_id="convo-2")
    assert a is not None and b is not None and c is not None
    assert a != b
    assert a != c
    assert a.parent.name == session_segment("school-a")
    assert persist_session_dir(school_id="", conversation_id="c") is None
    assert persist_session_dir(school_id="s", conversation_id=None) is None


def test_session_segment_blocks_dotdot() -> None:
    seg = session_segment("../etc/passwd")
    assert ".." not in seg
    p = persist_session_dir(school_id="../etc", conversation_id="x")
    assert p is not None
    assert ".." not in p.parts


def test_official_plan_mode_is_vendored() -> None:
    path = plan_mode_extension_path()
    assert path.is_file()
    text = path.read_text(encoding="utf-8")
    assert "pi-coding-agent@0.73.1" in text
    assert "PLAN_MODE_TOOLS" in text
    assert "workspace_write_file" in text
    assert "extractTodoItems" in text


def test_spawn_workbench_tree_flags() -> None:
    extra = Path("/tmp/plan-mode/index.ts")
    t = SubprocessTransport(
        session_dir=Path("/tmp/tp-sess"),
        tool_url="http://127.0.0.1:1",
        tool_token="tok",
        run_id="r1",
        continue_session=True,
        plan_flag=True,
        extra_extensions=[extra],
    )
    cmd = t.spawn_command()
    assert "--session-dir" in cmd
    assert "--continue" in cmd
    assert "--plan" in cmd
    assert "--no-extensions" in cmd
    assert "--no-context-files" in cmd
    assert cmd.count("-e") == 2
    assert str(extra) in cmd


def test_spawn_ephemeral_run_does_not_continue() -> None:
    t = SubprocessTransport(
        session_dir=Path("/tmp/tp-sess"),
        tool_url="http://127.0.0.1:1",
        tool_token="tok",
        run_id="r1",
    )
    cmd = t.spawn_command()
    assert "--continue" not in cmd
    assert "--plan" not in cmd
    assert cmd.count("-e") == 1


def test_compose_prompt_skips_history_when_none() -> None:
    text = _compose_prompt(
        prompt="把第三段改短",
        skill="",
        min_arts=0,
        history=None,
        allowed_tools=["workspace_write_file"],
    )
    assert "Recent conversation" not in text
    assert "把第三段改短" in text


def test_compose_prompt_history_still_available_without_tree() -> None:
    text = _compose_prompt(
        prompt="写文件",
        skill="",
        min_arts=0,
        history=[{"role": "user", "content": "你好"}, {"role": "assistant", "content": "您好"}],
        allowed_tools=["workspace_write_file"],
    )
    assert "Recent conversation" in text
    assert "你好" in text


def test_sidebar_chat_only_unchanged() -> None:
    assert _sidebar_chat_only(edu_sidebar=True, json_only=False) is True
    assert _sidebar_chat_only(edu_sidebar=False, json_only=False) is False
    assert _workbench_tool_step_line("generate_docx_document") == "正在写 Word"
    assert _workbench_tool_step_line("edit_docx_document") == "正在改 Word"
    assert _workbench_tool_step_line("generate_image") == "正在出图"
    assert _workbench_tool_step_line("workspace_list_files") == "正在列文件"
    assert _workbench_tool_step_line("unknown_tool") == "正在调工具"


@pytest.mark.asyncio
async def test_persist_session_prompt_is_current_user_only() -> None:
    events: list[tuple[str, dict[str, Any]]] = []

    async def emit(k: str, p: dict[str, Any]) -> None:
        events.append((k, p))

    transport = FakeTransport(
        scripted=[
            {"type": "agent_start"},
            {
                "type": "message_end",
                "message": {"role": "assistant", "content": "已把第三段改短。"},
            },
            {"type": "agent_end", "willRetry": False},
        ],
        assistant_text="已把第三段改短。",
    )
    result = await run_true_pi_agent(
        prompt="把第三段改短",
        principal=Principal(),
        emit=emit,
        is_cancelled=_not_cancelled,
        caps=RunCaps(min_artifacts=0, max_seconds=20),
        history=[
            {"role": "user", "content": "写一份三段教案提纲"},
            {"role": "assistant", "content": "第一段……第二段……第三段很长。"},
        ],
        transport=transport,
        conversation_id="convo-lesson",
        persist_pi_session=True,
    )
    assert result.status == "succeeded"
    prompt_cmd = next(item for item in transport.sent if item.get("type") == "prompt")
    message = str(prompt_cmd.get("message") or "")
    assert "把第三段改短" in message
    assert "Recent conversation" not in message
    assert "第一段" not in message


@pytest.mark.asyncio
async def test_compaction_end_emits_human_line() -> None:
    events: list[tuple[str, dict[str, Any]]] = []

    async def emit(k: str, p: dict[str, Any]) -> None:
        events.append((k, p))

    state = EventMapState()
    await map_event(RpcEvent({"type": "compaction_end", "reason": "threshold"}), emit=emit, state=state)
    kinds = [k for k, _ in events]
    assert "compaction.end" in kinds
    deltas = [p for k, p in events if k == "message.delta"]
    assert deltas
    assert COMPACTION_HUMAN in str(deltas[0].get("text"))


@pytest.mark.asyncio
async def test_plan_flag_waits_second_agent_end_before_landing() -> None:
    events: list[tuple[str, dict[str, Any]]] = []

    async def emit(k: str, p: dict[str, Any]) -> None:
        events.append((k, p))

    transport = FakeTransport(
        scripted=[
            {"type": "agent_start"},
            {
                "type": "message_end",
                "message": {
                    "role": "assistant",
                    "content": "Plan:\n1. Write outline\n2. Save file",
                },
            },
            {"type": "agent_end", "willRetry": False},
            {"type": "agent_settled"},
            {
                "type": "tool_execution_start",
                "toolName": "workspace_write_file",
                "toolCallId": "c1",
                "args": {"title": "教案.md", "content": "ok"},
            },
            {
                "type": "tool_execution_end",
                "toolName": "workspace_write_file",
                "toolCallId": "c1",
                "isError": False,
                "result": {"content": [{"type": "text", "text": '{"title":"教案.md"}'}]},
            },
            {
                "type": "message_end",
                "message": {"role": "assistant", "content": "已写入教案.md"},
            },
            {"type": "agent_end", "willRetry": False},
        ],
        assistant_text="已写入教案.md",
    )
    transport.plan_flag = True
    transport.plan_agent_ends = 0
    result = await run_true_pi_agent(
        prompt="教案并落盘",
        principal=Principal(),
        emit=emit,
        is_cancelled=_not_cancelled,
        caps=RunCaps(min_artifacts=1, max_seconds=20),
        transport=transport,
    )
    assert result.status == "succeeded"
    assert transport.plan_agent_ends >= 2


@pytest.mark.asyncio
async def test_plan_widget_maps_to_progress() -> None:
    events: list[tuple[str, dict[str, Any]]] = []

    async def emit(k: str, p: dict[str, Any]) -> None:
        events.append((k, p))

    state = EventMapState()
    await map_event(
        RpcEvent(
            {
                "type": "extension_ui_request",
                "method": "setWidget",
                "widgetLines": ["☐ 写教案", "☐ 落盘"],
            }
        ),
        emit=emit,
        state=state,
    )
    progress = [p for k, p in events if k == "plan.progress"]
    assert progress
    assert "写教案" in progress[0]["text"]
