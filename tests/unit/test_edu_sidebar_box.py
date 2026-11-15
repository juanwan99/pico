"""edu-core#5685: the lesson-prep rail is the one sidebar turn that gets the box."""

from __future__ import annotations

import base64
import sys
from pathlib import Path

import pytest
from fastapi import HTTPException

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "api"))
sys.path.insert(0, str(ROOT / "services" / "orchestrator"))

from app.edu_files import inline_workspace_files
from app.edu_sidebar_pi import _hint_caps
from app.openai_compat import (
    _caps_with_sidebar,
    _require_box_turn,
    _sidebar_step,
)
from pico_orchestrator.capability_loading import (
    NO_VISIBLE_TOOLS,
    resolve_visible_tools,
    visible_tools_env,
)
from pico_orchestrator.edu_sidebar import SIDEBAR_WORKBENCH_HINT, sidebar_box
from pico_orchestrator.run_types import RunCaps
from pico_orchestrator.true_pi.runtime import box_mode_for

MARK = "附属，不是用户要求\n{}"


def test_only_the_lesson_entry_on_a_marked_pi_turn_is_a_box_turn() -> None:
    assert sidebar_box(edu_sidebar=True, json_only=False, entry="sidebar.lesson-chat")
    # json_only stays one-shot (edu still uses it for the old ops answer).
    assert not sidebar_box(edu_sidebar=True, json_only=True, entry="sidebar.lesson-chat")
    # Every other sidebar keeps 11-11's no-box rule.
    assert not sidebar_box(edu_sidebar=True, json_only=False, entry="sidebar.page")
    # The entry alone, without the sidebar marker, is not a box turn.
    assert not sidebar_box(edu_sidebar=False, json_only=False, entry="sidebar.lesson-chat")


def test_box_turn_gets_the_box_and_keeps_thinking(monkeypatch) -> None:
    monkeypatch.setenv("PICO_RUNNER_URL", "http://runner")
    monkeypatch.delenv("PICO_RUNNER_MEMBERSHIPS", raising=False)
    base = RunCaps(system_prompt=MARK, thinking_on=True)
    box = _hint_caps(_caps_with_sidebar(base, edu_sidebar=True, box_turn=True))
    assert box.sidebar_box is True and box.edu_sidebar is False
    assert box.thinking_on is True
    assert SIDEBAR_WORKBENCH_HINT not in box.system_prompt
    assert box_mode_for(box, "s1", "m1") is True
    school = _hint_caps(_caps_with_sidebar(base, edu_sidebar=True, box_turn=False))
    assert school.edu_sidebar is True and school.thinking_on is False
    assert box_mode_for(school, "s1", "m1") is False


def test_no_pico_hands_means_the_bridge_registers_none() -> None:
    # Empty used to reach the bridge as "" = every gateway tool.
    assert resolve_visible_tools([]) == []
    assert visible_tools_env([]) == NO_VISIBLE_TOOLS
    assert visible_tools_env(["kb_search"]) == "kb_search"


def test_box_turn_needs_a_conversation_and_the_runner(monkeypatch) -> None:
    monkeypatch.setenv("PICO_RUNNER_URL", "http://runner")
    monkeypatch.delenv("PICO_RUNNER_MEMBERSHIPS", raising=False)
    with pytest.raises(HTTPException) as no_conv:
        _require_box_turn("", "m1")
    assert no_conv.value.status_code == 400
    _require_box_turn("c1", "m1")
    monkeypatch.delenv("PICO_RUNNER_URL")
    with pytest.raises(HTTPException) as off:
        _require_box_turn("c1", "m1")
    assert off.value.status_code == 503


def test_file_parts_of_the_last_user_turn_go_to_attachments() -> None:
    view = b'{"doc":{"order":[]}}'
    url = "data:application/json;base64," + base64.b64encode(view).decode()
    messages = [
        {"role": "user", "content": [{"type": "file", "file": {"filename": "old.json", "file_data": url}}]},
        {"role": "assistant", "content": "好"},
        {
            "role": "user",
            "content": [
                {"type": "text", "text": "把第 1 页标题改蓝"},
                {"type": "file", "file": {"filename": "view.json", "file_data": url}},
                {"type": "file", "file": {"filename": "cw.mjs", "file_data": base64.b64encode(b"//").decode()}},
                {"type": "file", "file": {"filename": "empty.txt", "file_data": ""}},
            ],
        },
    ]
    assert inline_workspace_files(messages) == [("view.json", view), ("cw.mjs", b"//")]


def test_box_step_lines_leave_content_for_the_answer() -> None:
    assert _sidebar_step("正在执行：node attachments/cw.mjs outline", box_turn=True) == (
        "progress",
        "\n正在执行：node attachments/cw.mjs outline\n",
    )
    assert _sidebar_step("正在读 表.xlsx", box_turn=False) == ("delta", "正在读 表.xlsx\n")


def test_stream_routes_box_text_to_progress() -> None:
    """Source lock: in a box turn model text and step lines never reach `content`."""
    src = (ROOT / "services" / "api" / "app" / "openai_compat.py").read_text(encoding="utf-8")
    assert src.count('("progress" if box_turn else "delta", text)') == 2
    assert 'yield chunk({}, extra={"pico_progress": str(payload)})' in src
