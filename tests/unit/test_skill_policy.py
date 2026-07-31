"""Skill thin policy unit tests."""

from pico_orchestrator.skill_policy import (
    declared_tools_for_skill,
    normalize_skill_id,
    snapshot_for_skill,
    strip_skill_markers,
)
from pico_orchestrator.tools_builtin import build_default_gateway


def test_normalize_aliases():
    assert normalize_skill_id("skill.chat") == "skill-chat"
    assert normalize_skill_id("write_s7") == "skill-write-s7"
    assert normalize_skill_id("lesson_outline") == "skill-lesson-outline"
    assert normalize_skill_id("skill.meeting_notes") == "skill-meeting-notes"
    assert normalize_skill_id("") is None


def test_snapshot_tools_subset_of_gateway():
    declared = {
        "skill-chat": ([], False),
        "skill-read": (
            [
                "workspace_read_file",
                "workspace_list_files",
                "fake_edu_list_classes",
            ],
            False,
        ),
        "skill-write-s7": (["pico_propose_change"], True),
        "skill-summarize": (
            [
                "workspace_read_file",
                "structured_outline",
                "workspace_write_file",
            ],
            False,
        ),
        "skill-lesson-outline": (
            ["structured_outline", "workspace_write_file"],
            False,
        ),
        "skill-quiz-draft": (
            [
                "workspace_read_file",
                "structured_outline",
                "workspace_write_file",
            ],
            False,
        ),
        "skill-translate": (
            ["workspace_read_file", "workspace_write_file"],
            False,
        ),
        "skill-meeting-notes": (
            ["structured_outline", "workspace_write_file"],
            False,
        ),
    }
    global_tools = set(build_default_gateway().tools)

    for skill_id, (tools, requires_s7) in declared.items():
        snapshot = snapshot_for_skill(skill_id)
        assert snapshot is not None
        assert declared_tools_for_skill(skill_id) == tools
        assert snapshot["tools"] == [tool for tool in tools if tool in global_tools]
        assert set(snapshot["tools"]) <= global_tools
        assert snapshot["requires_s7"] is requires_s7

    assert sum(bool(tools) for tools, _ in declared.values()) >= 5


def test_strip_marker():
    raw = "hello 【Pico-Skill:skill-chat】 world"
    assert "Pico-Skill" not in strip_skill_markers(raw)
    assert "hello" in strip_skill_markers(raw)
