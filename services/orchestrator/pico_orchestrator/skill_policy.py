"""Pico thin skill policy: LC catalog in, immutable Run snapshot out."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from typing import Any

from pico_orchestrator.tools_builtin import build_default_gateway

SKILL_MARKER_RE = re.compile(r"【Pico-Skill:([^】]+)】")


@dataclass(frozen=True)
class SkillPolicy:
    id: str
    name: str
    requested_tools: tuple[str, ...]
    risk: str
    instruction: str
    requires_s7: bool = False


_POLICIES: dict[str, SkillPolicy] = {
    "skill-chat": SkillPolicy(
        id="skill-chat",
        name="skill.chat",
        requested_tools=(),
        risk="low",
        instruction=(
            "本轮使用 skill.chat：少工具或无工具，普通问答直接回答；"
            "不得臆造学校数据或声称已执行工具。"
        ),
    ),
    "skill-read": SkillPolicy(
        id="skill-read",
        name="skill.read",
        requested_tools=("fake_edu_list_classes",),
        risk="read",
        instruction=(
            "本轮使用 skill.read：只允许只读工具；需要学校班级数据时使用 "
            "fake_edu_list_classes；禁止提出或执行写入。"
        ),
    ),
    "skill-write-s7": SkillPolicy(
        id="skill-write-s7",
        name="skill.write_s7",
        requested_tools=("pico_propose_change",),
        risk="write_s7",
        instruction=(
            "本轮使用 skill.write_s7：业务变更必须生成待人工确认的 S7 提案；"
            "禁止声称已经写入学校业务系统。"
        ),
        requires_s7=True,
    ),
}

_ALIASES = {
    "chat": "skill-chat",
    "skill.chat": "skill-chat",
    "skill-chat": "skill-chat",
    "pico-chat": "skill-chat",
    "read": "skill-read",
    "skill.read": "skill-read",
    "skill-read": "skill-read",
    "pico-read": "skill-read",
    "write-s7": "skill-write-s7",
    "write_s7": "skill-write-s7",
    "skill.write_s7": "skill-write-s7",
    "skill.write-s7": "skill-write-s7",
    "skill-write-s7": "skill-write-s7",
    "pico-write-s7": "skill-write-s7",
}


def normalize_skill_id(value: str | None) -> str | None:
    if not isinstance(value, str):
        return None
    raw = (value or "").strip().lower()
    if not raw:
        return None
    compact = raw.replace("_", "-")
    return _ALIASES.get(raw) or _ALIASES.get(compact)


def strip_skill_markers(prompt: str) -> str:
    return SKILL_MARKER_RE.sub("", prompt or "").strip()


def skill_id_from_prompt(prompt: str) -> str | None:
    match = SKILL_MARKER_RE.search(prompt or "")
    if not match:
        return None
    return normalize_skill_id(match.group(1))


def snapshot_for_skill(skill_ref: str | None) -> dict[str, Any] | None:
    skill_id = normalize_skill_id(skill_ref)
    if not skill_id:
        return None
    policy = _POLICIES.get(skill_id)
    if policy is None:
        return None
    global_tools = set(build_default_gateway().tools.keys())
    allowed_tools = [tool for tool in policy.requested_tools if tool in global_tools]
    return {
        "id": policy.id,
        "name": policy.name,
        "tools": allowed_tools,
        "risk": policy.risk,
        "requires_s7": policy.requires_s7,
        "prompt_hash": hashlib.sha256(policy.instruction.encode("utf-8")).hexdigest(),
        "policy": {
            "source": "librechat-skills",
            "tool_rule": "intersection-with-global-allowlist",
        },
    }


def instruction_for_snapshot(snapshot: dict[str, Any] | None) -> str:
    if not snapshot:
        return ""
    policy = _POLICIES.get(str(snapshot.get("id") or ""))
    return policy.instruction if policy else ""


def snapshot_from_prompt(prompt: str) -> tuple[str, dict[str, Any] | None]:
    return strip_skill_markers(prompt), snapshot_for_skill(skill_id_from_prompt(prompt))
