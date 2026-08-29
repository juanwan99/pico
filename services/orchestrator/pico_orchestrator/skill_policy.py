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
    "skill-deliverable": SkillPolicy(
        id="skill-deliverable",
        name="skill.deliverable",
        requested_tools=(
            "generate_html_document",
            "generate_docx_document",
            "generate_pptx_document",
            "sandbox_pptx_lib",
            "generate_xlsx_document",
            "edit_docx_document",
            "edit_pptx_document",
            "edit_xlsx_document",
            "render_document",
            "inspect_document",
            "verify_document",
            "generate_image",
            "generate_diagram",
            "workspace_write_file",
            "workspace_list_files",
            "workspace_read_file",
            "verify_html_document",
            "sandbox_preview_inspect",
            "publish_html_page",
            "unpublish_html_page",
            "sandbox_browser_open",
            "sandbox_browser_screenshot",
            "sandbox_document_open",
            "kb_search",
        ),
        risk="low",
        instruction=(
            "老师要真实文件或改已有文件。工具已挂载，你自己决定调哪个。"
            "工具返回 ok 不算完：读 observation（落地了什么），不对就再调。"
            "禁止空壳、禁止编造文件。不要向用户复读机读字段或 Artifact ID。"
            "HTML 必须页内脚本与 canvas，禁止 CDN / Three.js / Chart.js / ECharts 外链。"
            "只有老师问学校材料时才 kb_search；工具在列表不代表必须调用。"
            "honest_miss 就老实说没找到，禁止编造。"
        ),
    ),
    "skill-engineering-delivery": SkillPolicy(
        id="skill-engineering-delivery",
        name="skill.engineering_delivery",
        requested_tools=(
            "workspace_write_file",
            "workspace_list_files",
            "workspace_read_file",
            "generate_html_document",
            "generate_docx_document",
            "generate_pptx_document",
            "sandbox_pptx_lib",
            "generate_xlsx_document",
            "edit_docx_document",
            "edit_pptx_document",
            "edit_xlsx_document",
            "render_document",
            "inspect_document",
            "verify_document",
            "generate_image",
            "generate_diagram",
            "verify_html_document",
            "structured_outline",
            "sandbox_preview_inspect",
            "publish_html_page",
            "unpublish_html_page",
            "sandbox_browser_open",
            "sandbox_browser_screenshot",
            "sandbox_document_open",
            "kb_search",
        ),
        risk="low",
        instruction=(
            "老师要多份文件或一套东西。工具已挂载，你自己决定怎么拆、怎么写。"
            "工具返回 ok 不算完：读 observation，不对就再调。"
            "禁止空壳、禁止编造。不要向用户复读机读字段。"
            "HTML 必须页内脚本与 canvas，禁止 CDN / Three.js / Chart.js / ECharts 外链。"
            "只有老师问学校材料时才 kb_search；工具在列表不代表必须调用。"
            "禁止编造未命中内容。"
        ),
    ),
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
            "sandbox_pptx_lib",
        ),
        risk="low",
        instruction=(
            "老师挂了这份 Skill。按老师的话做，不要发明一套总结流程。"
            "工具在列表不代表必须调用。不得补写原文中不存在的事实。"
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
            "sandbox_pptx_lib",
        ),
        risk="low",
        instruction=(
            "老师挂了这份 Skill。按老师的话做，不要发明一套教案流程。"
            "工具在列表不代表必须调用。"
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
            "sandbox_pptx_lib",
        ),
        risk="low",
        instruction=(
            "老师挂了这份 Skill。按老师的话做，不要发明一套出题流程。"
            "工具在列表不代表必须调用。"
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
            "sandbox_pptx_lib",
        ),
        risk="low",
        instruction=(
            "老师挂了这份 Skill。按老师的话做，不要发明一套翻译流程。"
            "工具在列表不代表必须调用。不确定术语应标注而非臆造。"
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
            "sandbox_pptx_lib",
        ),
        risk="low",
        instruction=(
            "老师挂了这份 Skill。按老师的话做，不要发明一套会议纪要流程。"
            "工具在列表不代表必须调用。"
        ),
    ),
    "skill-kb-ask": SkillPolicy(
        id="skill-kb-ask",
        name="skill.kb_ask",
        requested_tools=(
            "kb_search",
            "workspace_list_files",
            "workspace_read_file",
        ),
        risk="read",
        instruction=(
            "本轮使用 skill.kb_ask：老师问学校材料时才 kb_search；"
            "回答必须带出处（标题+摘录）；honest_miss=true 时诚实说明未命中，禁止编造。"
            "Pico 对话随传文件不是学校库。工具在列表不代表必须调用。"
        ),
    ),
}

_ALIASES = {
    "deliverable": "skill-deliverable",
    "skill.deliverable": "skill-deliverable",
    "skill-deliverable": "skill-deliverable",
    "engineering": "skill-engineering-delivery",
    "engineering-delivery": "skill-engineering-delivery",
    "engineering_delivery": "skill-engineering-delivery",
    "skill.engineering_delivery": "skill-engineering-delivery",
    "skill-engineering-delivery": "skill-engineering-delivery",
    "package": "skill-engineering-delivery",
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
    "kb-ask": "skill-kb-ask",
    "kb_ask": "skill-kb-ask",
    "skill.kb_ask": "skill-kb-ask",
    "skill-kb-ask": "skill-kb-ask",
    "pico-kb-ask": "skill-kb-ask",
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
