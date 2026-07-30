"""Skill thin policy unit tests."""

from pico_orchestrator.skill_policy import (
    normalize_skill_id,
    snapshot_for_skill,
    strip_skill_markers,
)


def test_normalize_aliases():
    assert normalize_skill_id("skill.chat") == "skill-chat"
    assert normalize_skill_id("write_s7") == "skill-write-s7"
    assert normalize_skill_id("") is None


def test_snapshot_tools_subset_of_gateway():
    chat = snapshot_for_skill("skill-chat")
    assert chat is not None
    assert chat["tools"] == []
    assert chat["requires_s7"] is False

    read = snapshot_for_skill("skill-read")
    assert read is not None
    assert "fake_edu_list_classes" in read["tools"]

    write = snapshot_for_skill("skill-write-s7")
    assert write is not None
    assert write["requires_s7"] is True
    assert "pico_propose_change" in write["tools"]


def test_strip_marker():
    raw = "hello 【Pico-Skill:skill-chat】 world"
    assert "Pico-Skill" not in strip_skill_markers(raw)
    assert "hello" in strip_skill_markers(raw)
