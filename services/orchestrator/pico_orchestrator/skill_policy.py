"""Pico thin skill policy: LC catalog in, immutable Run snapshot out."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from typing import Any

from pico_orchestrator.tools_builtin import build_default_gateway

SKILL_MARKER_RE = re.compile(r"【Pico-Skill:([^】]+)】")
UNKNOWN_SKILL_INSTRUCTION = (
    "本轮请求的 Skill 不在 Pico 受控目录中，已降级为 skill.unknown（chat-only）；"
    "不得调用工具、臆造工具结果或声称已执行写入。"
)


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
            "本轮使用 skill.chat：这是纯对话（chat-only）技能，普通问答直接回答；"
            "不得臆造学校数据或声称已执行工具。"
        ),
    ),
    "skill-read": SkillPolicy(
        id="skill-read",
        name="skill.read",
        requested_tools=(
            "workspace_read_file",
            "workspace_list_files",
            "fake_edu_list_classes",
        ),
        risk="read",
        instruction=(
            "本轮使用 skill.read：只允许只读工具；优先列出或读取当前工作区产物，"
            "需要演示学校班级数据时才使用 fake_edu_list_classes；禁止提出或执行写入。"
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
    "skill-summarize": SkillPolicy(
        id="skill-summarize",
        name="skill.summarize",
        requested_tools=(
            "workspace_read_file",
            "structured_outline",
            "workspace_write_file",
            "generate_html_document",
            "generate_docx_document",
            "generate_pptx_document",
        ),
        risk="low",
        instruction=(
            "本轮使用 skill.summarize：提炼用户提供内容的要点、结论与待办；"
            "可读取工作区材料、生成结构化结果并把总结保存为工作区产物；"
            "需要交付 HTML/Word/PPT 时必须调用专用 generate_*_document 工具（真文件，禁止改后缀冒充）；"
            "不得补写原文中不存在的事实。"
        ),
    ),
    "skill-lesson-outline": SkillPolicy(
        id="skill-lesson-outline",
        name="skill.lesson_outline",
        requested_tools=(
            "structured_outline",
            "workspace_write_file",
            "generate_html_document",
            "generate_docx_document",
            "generate_pptx_document",
        ),
        risk="low",
        instruction=(
            "本轮使用 skill.lesson_outline：按教学目标、重点难点、活动与检查点生成课程大纲；"
            "缺少年级或课时信息时明确假设，可把大纲保存为工作区产物；"
            "需要 HTML/Word/PPT 交付时必须调用 generate_html_document / generate_docx_document / generate_pptx_document。"
        ),
    ),
    "skill-quiz-draft": SkillPolicy(
        id="skill-quiz-draft",
        name="skill.quiz_draft",
        requested_tools=(
            "workspace_read_file",
            "structured_outline",
            "workspace_write_file",
            "generate_html_document",
            "generate_docx_document",
            "generate_pptx_document",
        ),
        risk="low",
        instruction=(
            "本轮使用 skill.quiz_draft：根据用户给定材料起草题目、答案与简短解析；"
            "可读取工作区材料并保存草稿；题目仅为草稿，提醒用户发布前复核；"
            "需要 HTML/Word/PPT 交付时必须调用专用 generate_*_document 工具。"
        ),
    ),
    "skill-translate": SkillPolicy(
        id="skill-translate",
        name="skill.translate",
        requested_tools=(
            "workspace_read_file",
            "workspace_write_file",
            "generate_html_document",
            "generate_docx_document",
            "generate_pptx_document",
        ),
        risk="low",
        instruction=(
            "本轮使用 skill.translate：忠实翻译用户提供内容，保留格式、专名与语气；"
            "可读取工作区材料并保存译文；不确定术语应标注而非臆造；"
            "需要 HTML/Word/PPT 交付时必须调用专用 generate_*_document 工具。"
        ),
    ),
    "skill-meeting-notes": SkillPolicy(
        id="skill-meeting-notes",
        name="skill.meeting_notes",
        requested_tools=(
            "structured_outline",
            "workspace_write_file",
            "generate_html_document",
            "generate_docx_document",
            "generate_pptx_document",
        ),
        risk="low",
        instruction=(
            "本轮使用 skill.meeting_notes：把用户提供的会议内容整理为议题、决定、"
            "负责人和待办，并可保存为工作区产物；没有明确负责人的事项标为待确认。"
        ),
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
    "summarize": "skill-summarize",
    "skill.summarize": "skill-summarize",
    "skill-summarize": "skill-summarize",
    "lesson-outline": "skill-lesson-outline",
    "lesson_outline": "skill-lesson-outline",
    "skill.lesson_outline": "skill-lesson-outline",
    "skill-lesson-outline": "skill-lesson-outline",
    "quiz-draft": "skill-quiz-draft",
    "quiz_draft": "skill-quiz-draft",
    "skill.quiz_draft": "skill-quiz-draft",
    "skill-quiz-draft": "skill-quiz-draft",
    "translate": "skill-translate",
    "skill.translate": "skill-translate",
    "skill-translate": "skill-translate",
    "meeting-notes": "skill-meeting-notes",
    "meeting_notes": "skill-meeting-notes",
    "skill.meeting_notes": "skill-meeting-notes",
    "skill-meeting-notes": "skill-meeting-notes",
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


def _allowed_tools(policy: SkillPolicy) -> list[str]:
    global_tools = set(build_default_gateway().tools.keys())
    return [tool for tool in policy.requested_tools if tool in global_tools]


def snapshot_for_skill(skill_ref: str | None) -> dict[str, Any] | None:
    if not isinstance(skill_ref, str) or not skill_ref.strip():
        return None
    skill_id = normalize_skill_id(skill_ref)
    if not skill_id:
        return {
            "id": "skill-unknown",
            "name": "skill.unknown",
            "tools": [],
            "risk": "unknown",
            "requires_s7": False,
            "prompt_hash": hashlib.sha256(
                UNKNOWN_SKILL_INSTRUCTION.encode("utf-8")
            ).hexdigest(),
            "policy": {
                "source": "librechat-skills",
                "tool_rule": "deny-all",
                "reason": "skill.unknown",
            },
        }
    policy = _POLICIES.get(skill_id)
    if policy is None:
        return None
    return {
        "id": policy.id,
        "name": policy.name,
        "tools": _allowed_tools(policy),
        "risk": policy.risk,
        "requires_s7": policy.requires_s7,
        "prompt_hash": hashlib.sha256(policy.instruction.encode("utf-8")).hexdigest(),
        "policy": {
            "source": "librechat-skills",
            "tool_rule": "intersection-with-global-allowlist",
        },
    }


def declared_tools_for_skill(skill_ref: str | None) -> list[str] | None:
    """Return the catalog binding before the global allowlist intersection."""
    skill_id = normalize_skill_id(skill_ref)
    if not skill_id:
        return None
    policy = _POLICIES.get(skill_id)
    if policy is None:
        return None
    return list(policy.requested_tools)


def skill_catalog() -> list[dict[str, Any]]:
    """Return the user-safe, read-only catalog after allowlist intersection."""
    return [
        {
            "id": policy.id,
            "name": policy.name,
            "tools": _allowed_tools(policy),
            "risk": policy.risk,
            "requires_s7": policy.requires_s7,
        }
        for policy in _POLICIES.values()
    ]


def instruction_for_snapshot(snapshot: dict[str, Any] | None) -> str:
    if not snapshot:
        return ""
    if snapshot.get("name") == "skill.unknown":
        return UNKNOWN_SKILL_INSTRUCTION
    policy = _POLICIES.get(str(snapshot.get("id") or ""))
    return policy.instruction if policy else ""


def snapshot_from_prompt(prompt: str) -> tuple[str, dict[str, Any] | None]:
    match = SKILL_MARKER_RE.search(prompt or "")
    skill_ref = match.group(1) if match else None
    return strip_skill_markers(prompt), snapshot_for_skill(skill_ref)
