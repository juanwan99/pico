from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "orchestrator"))

from pico_orchestrator.skill_policy import snapshot_for_skill, snapshot_from_prompt
from pico_orchestrator.tools_builtin import build_default_gateway, openai_tool_schemas


@dataclass
class P:
    school_id: str
    membership_id: str
    scopes: list[str]


@pytest.mark.asyncio
async def test_schemas_and_propose():
    gw = build_default_gateway()
    schemas = openai_tool_schemas(gw)
    names = {s["function"]["name"] for s in schemas}
    assert "fake_edu_list_classes" in names
    assert "pico_propose_change" in names
    assert "web_search" in names
    assert "web_fetch" in names
    p = P("school-a", "m", ["ai:run"])
    out = await gw.invoke(
        p,
        "pico_propose_change",
        {"title": "t", "summary": "s", "payload": {"a": 1}},
    )
    assert out["proposal"]["status"] == "proposed"


def test_skill_snapshot_intersects_global_allowlist():
    snap = snapshot_for_skill("skill.read")
    assert snap is not None
    assert snap["id"] == "skill-read"
    assert snap["tools"] == [
        "workspace_read_file",
        "workspace_list_files",
        "fake_edu_list_classes",
    ]
    assert snap["risk"] == "read"
    assert len(snap["prompt_hash"]) == 64

    chat = snapshot_for_skill("skill.chat")
    assert chat is not None
    assert chat["tools"] == []

    prompt, write = snapshot_from_prompt("【Pico-Skill:skill.write_s7】\n请改班级名")
    assert prompt == "请改班级名"
    assert write is not None
    assert write["requires_s7"] is True
    assert write["tools"] == ["pico_propose_change"]


def test_skill_schema_filter_only_exposes_intersection():
    gw = build_default_gateway()
    read_names = {
        schema["function"]["name"]
        for schema in openai_tool_schemas(gw, allowed_tools=["fake_edu_list_classes", "missing"])
    }
    assert read_names == {"fake_edu_list_classes"}
    assert openai_tool_schemas(gw, allowed_tools=[]) == []


def test_misspelled_skill_exposes_no_tool_schemas():
    _, snapshot = snapshot_from_prompt("【Pico-Skill:skill-reead】\n读取文件")

    assert snapshot is not None
    assert snapshot["name"] == "skill.unknown"
    assert openai_tool_schemas(
        build_default_gateway(),
        allowed_tools=snapshot["tools"],
    ) == []
