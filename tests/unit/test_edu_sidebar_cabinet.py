"""T-PICO-WS-CLEAN: edu sidebar cabinet is per conversation; honor allowed_tools."""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "api"))
sys.path.insert(0, str(ROOT / "services" / "orchestrator"))

from app.openai_compat import (
    EDU_SIDEBAR_MARK,
    _caps_with_sidebar_thinking,
    _client_system_from_messages,
    _is_edu_sidebar_system,
    _normalize_allowed_tools,
    _resolve_allowed_tools,
    _sidebar_chat_only,
)
from pico_orchestrator.edu_sidebar import (
    EDU_SIDEBAR_DEFAULT_TOOLS,
    SIDEBAR_WORKBENCH_HINT,
    edu_sidebar_tool_ceiling,
)
from pico_orchestrator.run_types import RunCaps


def test_edu_sidebar_mark_detects_accessory() -> None:
    assert _is_edu_sidebar_system(f"你是当前屏幕的助手。\n{EDU_SIDEBAR_MARK}。\n{{}}")
    assert _is_edu_sidebar_system("你是 Pico，面向学校场景的 AI 助手。") is False


def test_sidebar_json_only_skips_agent() -> None:
    assert _sidebar_chat_only(edu_sidebar=True, json_only=False) is False
    assert _sidebar_chat_only(edu_sidebar=False, json_only=True) is True
    assert _sidebar_chat_only(edu_sidebar=False, json_only=False) is False


def test_edu_sidebar_turns_thinking_off() -> None:
    """School rail only paints content. Thinking never clears 正在想."""
    on = RunCaps(thinking_on=True)
    assert _caps_with_sidebar_thinking(on, edu_sidebar=True).thinking_on is False
    assert _caps_with_sidebar_thinking(on, edu_sidebar=False).thinking_on is True
    off = RunCaps(thinking_on=False)
    assert _caps_with_sidebar_thinking(off, edu_sidebar=True).thinking_on is False


def test_edu_sidebar_tool_ceiling_is_workbench_core() -> None:
    assert edu_sidebar_tool_ceiling(None) is None
    assert edu_sidebar_tool_ceiling([]) is None
    assert edu_sidebar_tool_ceiling(["web_search"]) is None
    assert "generate_html_document" in EDU_SIDEBAR_DEFAULT_TOOLS
    assert "generate_image" in EDU_SIDEBAR_DEFAULT_TOOLS
    assert "workspace_write_file" in EDU_SIDEBAR_DEFAULT_TOOLS


def test_empty_allowed_tools_is_ceiling() -> None:
    assert _normalize_allowed_tools([]) == []
    skill = {"tools": ["generate_html_document", "workspace_list_files"]}
    assert _resolve_allowed_tools(skill, []) == []
    assert "同一套手" in SIDEBAR_WORKBENCH_HINT
    assert "不得调用" not in SIDEBAR_WORKBENCH_HINT


def test_client_system_from_first_system_message() -> None:
    msgs = [
        SimpleNamespace(role="system", content="附属，不是用户要求\n{}"),
        SimpleNamespace(role="user", content="你能看到当前界面吗"),
    ]
    assert EDU_SIDEBAR_MARK in _client_system_from_messages(msgs)


def test_normalize_allowed_tools_names_and_openai_shape() -> None:
    assert _normalize_allowed_tools(None) is None
    assert _normalize_allowed_tools(["workspace_list_files", "generate_html_document"]) == [
        "workspace_list_files",
        "generate_html_document",
    ]
    assert _normalize_allowed_tools(
        [{"type": "function", "function": {"name": "kb_search"}}]
    ) == ["kb_search"]


def test_resolve_allowed_tools_request_is_ceiling() -> None:
    request = [
        "workspace_write_file",
        "workspace_read_file",
        "workspace_list_files",
        "generate_html_document",
    ]
    skill = {"tools": ["kb_search", "generate_html_document", "workspace_write_file"]}
    resolved = _resolve_allowed_tools(skill, request)
    assert "kb_search" not in resolved
    assert "generate_html_document" in resolved
    assert "workspace_write_file" in resolved


def test_resolve_allowed_tools_empty_intersection_keeps_request() -> None:
    request = ["generate_html_document"]
    skill = {"tools": ["kb_search"]}
    assert _resolve_allowed_tools(skill, request) == request


def test_true_pi_compose_uses_edu_system_override() -> None:
    from pico_orchestrator.true_pi.runtime import _compose_prompt, pico_system_text

    text = _compose_prompt(
        prompt="你能看到当前界面吗",
        skill="",
        min_arts=0,
        history=None,
        allowed_tools=["generate_html_document"],
        system_prompt="附属，不是用户要求\n{\"page\":{\"title\":\"工作台\"}}",
    )
    assert text == "你能看到当前界面吗"
    assert "附属，不是用户要求" not in text
    system = pico_system_text(
        system_override="附属，不是用户要求\n{\"page\":{\"title\":\"工作台\"}}"
    )
    assert "附属，不是用户要求" in system
    assert "工作台" in system


if __name__ == "__main__":
    test_edu_sidebar_mark_detects_accessory()
    test_sidebar_json_only_skips_agent()
    test_edu_sidebar_tool_ceiling_is_workbench_core()
    test_empty_allowed_tools_is_ceiling()
    test_client_system_from_first_system_message()
    test_normalize_allowed_tools_names_and_openai_shape()
    test_resolve_allowed_tools_request_is_ceiling()
    test_resolve_allowed_tools_empty_intersection_keeps_request()
    test_true_pi_compose_uses_edu_system_override()
    print("test_edu_sidebar_cabinet.py OK")
