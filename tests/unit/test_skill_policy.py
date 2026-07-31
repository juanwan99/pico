"""Skill thin policy unit tests."""

from pico_orchestrator.skill_policy import (
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
    expected = {
        "skill-chat": ([], False),
        "skill-read": (["fake_edu_list_classes"], False),
        "skill-write-s7": (["pico_propose_change"], True),
        "skill-summarize": ([], False),
        "skill-lesson-outline": ([], False),
        "skill-quiz-draft": ([], False),
        "skill-translate": ([], False),
        "skill-meeting-notes": ([], False),
    }
    global_tools = set(build_default_gateway().tools)

    for skill_id, (tools, requires_s7) in expected.items():
        snapshot = snapshot_for_skill(skill_id)
        assert snapshot is not None
        assert snapshot["tools"] == tools
        assert set(snapshot["tools"]) <= global_tools
        assert snapshot["requires_s7"] is requires_s7


def test_strip_marker():
    raw = "hello 【Pico-Skill:skill-chat】 world"
    assert "Pico-Skill" not in strip_skill_markers(raw)
    assert "hello" in strip_skill_markers(raw)
