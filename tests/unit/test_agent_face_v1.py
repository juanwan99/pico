"""T-AGENT-FACE-V1: map Pi tool events to Chinese progress; fail in Chinese."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "api"))
sys.path.insert(0, str(ROOT / "services" / "orchestrator"))

from app.openai_compat import _sidebar_chat_only, _workbench_tool_step_line
from pico_orchestrator.human_package import sanitize_user_facing_text
from pico_orchestrator.image_generate import NO_KEY_MESSAGE
from pico_orchestrator.run_types import RunCaps
from pico_orchestrator.true_pi.client import FakeTransport, RpcEvent
from pico_orchestrator.true_pi.events import EventMapState, map_event
from pico_orchestrator.true_pi.runtime import run_true_pi_agent
from pico_orchestrator.user_errors import user_message_for_error
from pico_orchestrator.workbench_progress import (
    failed_write_user_message,
    workbench_tool_step_line,
)


class Principal:
    def __init__(self, school_id: str = "school-a", membership_id: str = "member-a") -> None:
        self.school_id = school_id
        self.membership_id = membership_id
        self.scopes = ["ai:run"]


async def _not_cancelled() -> bool:
    return False


def test_progress_lines_are_chinese_no_percent() -> None:
    assert workbench_tool_step_line("generate_docx_document") == "正在写 Word"
    assert workbench_tool_step_line("edit_docx_document") == "正在改 Word"
    assert workbench_tool_step_line("generate_image") == "正在出图"
    assert workbench_tool_step_line("mystery_tool") == "正在调工具"
    assert workbench_tool_step_line("") == ""
    assert "%" not in workbench_tool_step_line("generate_docx_document")
    assert _workbench_tool_step_line("generate_docx_document") == "正在写 Word"


def test_sidebar_chat_only_unchanged() -> None:
    assert _sidebar_chat_only(edu_sidebar=True, json_only=False) is True
    assert _sidebar_chat_only(edu_sidebar=False, json_only=False) is False


def test_image_no_key_not_swallowed_as_model_key() -> None:
    msg = user_message_for_error(NO_KEY_MESSAGE, code="image.unconfigured")
    assert "不能编造" in msg
    assert "DEEPSEEK" not in msg
    assert "KIMI" not in msg


def test_missing_word_is_chinese() -> None:
    msg = user_message_for_error(
        "找不到这份文件。请先在工作台上传原件再改。",
        code="artifact.not_found",
    )
    assert "找不到" in msg
    assert "Artifact" not in msg
    assert "not found" not in msg.lower()


def test_failed_write_message_from_image_error() -> None:
    msg = failed_write_user_message(
        [
            (
                "generate_image",
                {"error": NO_KEY_MESSAGE, "code": "image.unconfigured"},
            )
        ]
    )
    assert msg is not None
    assert "不能编造" in msg


def test_failed_write_ignored_when_a_write_succeeded() -> None:
    assert (
        failed_write_user_message(
            [
                ("generate_image", {"error": NO_KEY_MESSAGE, "code": "image.unconfigured"}),
                ("workspace_write_file", {"title": "notes.md"}),
            ]
        )
        is None
    )


def test_human_package_strips_in_flight_progress() -> None:
    out = sanitize_user_facing_text("正在写 Word\n教案已写好。")
    assert "正在写" not in out
    assert "教案已写好" in out


@pytest.mark.asyncio
async def test_tool_call_emits_chinese_step_line() -> None:
    events: list[tuple[str, dict[str, Any]]] = []

    async def emit(k: str, p: dict[str, Any]) -> None:
        events.append((k, p))

    state = EventMapState()
    await map_event(
        RpcEvent(
            {
                "type": "tool_execution_start",
                "toolName": "generate_docx_document",
                "toolCallId": "c1",
                "args": {"title": "教案.docx"},
            }
        ),
        emit=emit,
        state=state,
    )
    calls = [p for k, p in events if k == "tool.call"]
    assert calls
    assert calls[0]["step_line"] == "正在写 Word"
    assert "%" not in calls[0]["step_line"]


@pytest.mark.asyncio
async def test_image_tool_error_is_chinese_not_ok() -> None:
    events: list[tuple[str, dict[str, Any]]] = []

    async def emit(k: str, p: dict[str, Any]) -> None:
        events.append((k, p))

    state = EventMapState()
    await map_event(
        RpcEvent(
            {
                "type": "tool_execution_end",
                "toolName": "generate_image",
                "toolCallId": "c1",
                "isError": False,
                "result": {
                    "content": [
                        {
                            "type": "text",
                            "text": json.dumps(
                                {
                                    "error": NO_KEY_MESSAGE,
                                    "code": "image.unconfigured",
                                },
                                ensure_ascii=False,
                            ),
                        }
                    ]
                },
            }
        ),
        emit=emit,
        state=state,
    )
    results = [p for k, p in events if k == "tool.result"]
    assert results
    assert results[0]["ok"] is False
    assert "不能编造" in str(results[0].get("user_message"))
    assert "Traceback" not in str(results[0])


@pytest.mark.asyncio
async def test_image_write_fail_does_not_mark_run_succeeded() -> None:
    events: list[tuple[str, dict[str, Any]]] = []

    async def emit(k: str, p: dict[str, Any]) -> None:
        events.append((k, p))

    transport = FakeTransport(
        scripted=[
            {"type": "agent_start"},
            {
                "type": "tool_execution_start",
                "toolName": "generate_image",
                "toolCallId": "c1",
                "args": {"prompt": "分数的初步认识"},
            },
            {
                "type": "tool_execution_end",
                "toolName": "generate_image",
                "toolCallId": "c1",
                "result": {
                    "content": [
                        {
                            "type": "text",
                            "text": json.dumps(
                                {
                                    "error": NO_KEY_MESSAGE,
                                    "code": "image.unconfigured",
                                },
                                ensure_ascii=False,
                            ),
                        }
                    ]
                },
            },
            {
                "type": "message_end",
                "message": {"role": "assistant", "content": NO_KEY_MESSAGE},
            },
            {"type": "agent_end", "willRetry": False},
        ],
        assistant_text=NO_KEY_MESSAGE,
    )
    result = await run_true_pi_agent(
        prompt="画一张分数的初步认识课堂示意图",
        principal=Principal(),
        emit=emit,
        is_cancelled=_not_cancelled,
        caps=RunCaps(min_artifacts=0, max_seconds=20),
        transport=transport,
    )
    assert result.status == "failed"
    assert "不能编造" in (result.error or "")
    statuses = [p.get("status") for k, p in events if k == "run.status"]
    assert "failed" in statuses
    assert "succeeded" not in statuses
    fail_events = [p for k, p in events if k in {"run.error", "run.status"}]
    joined = " ".join(str(p.get("user_message") or "") for p in fail_events)
    assert "不能编造" in joined
    assert "traceback" not in joined.lower()
