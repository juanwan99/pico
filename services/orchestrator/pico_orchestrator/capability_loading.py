"""Capability loading — always-on verbs vs skill-extended.

ADR: docs/ADR-CAPABILITY-LOADING.md (Accepted).
Thin adapter only. Not a tool_search kernel. Not a scene router.

Gateway ceiling stays ALLOWED_GATEWAY_TOOLS (execute).
Pi-visible default is CORE_VISIBLE_TOOLS (model sees these).
A hung skill may narrow to its snapshot tools (still ⊆ gateway).
Extended verbs appear only when that snapshot asks for them.
"""

from __future__ import annotations

from collections.abc import Iterable

from pico_orchestrator.true_pi.config import ALLOWED_GATEWAY_TOOLS

# Always-on: teacher-said verbs. Do not add a scheduler / tool_search.
# Office ceiling is sandbox_office_lib (full Python in the pico-office
# container). generate_*/inspect/edit/render and the parse-only
# sandbox_workspace_exec are unregistered (not EXTENDED aliases).
# sandbox_browser_open / sandbox_document_open are pane doors, not a PDF kernel.
CORE_VISIBLE_TOOLS: tuple[str, ...] = (
    "workspace_list_files",
    "workspace_read_file",
    "workspace_write_file",
    "generate_html_document",
    "sandbox_office_lib",
    "read_office_skill",
    "generate_image",
    "generate_diagram",
    "web_search",
    "web_fetch",
    "kb_search",
    "ask_user",
    "sandbox_browser_open",
    "sandbox_document_open",
)

# Same gateway, not registered unless a hung skill lists them.
EXTENDED_TOOLS: tuple[str, ...] = (
    "publish_html_page",
    "unpublish_html_page",
    "verify_html_document",
    "sandbox_preview_inspect",
    "sandbox_browser_screenshot",
)

# Never auto-apply. Catalog may name them; Pico does not hang them from keywords.
SCENE_SKILL_IDS: frozenset[str] = frozenset(
    {
        "skill-lesson-outline",
        "skill-quiz-draft",
    }
)

# Name + one "when to use" line. Full bodies stay in skill_policy / SKILL.md.
SKILL_WHEN: dict[str, str] = {
    "skill-deliverable": "Teacher asked for a real downloadable file, or to change one.",
    "skill-engineering-delivery": "Teacher asked for a multi-file package or pipeline.",
    "skill-chat": "Chat only. No tools.",
    "skill-read": "Read workspace files. No writes.",
    "skill-write-s7": "School business change that needs S7 confirmation.",
    "skill-summarize": "Teacher asked to summarize supplied or saved content.",
    "skill-translate": "Teacher asked to translate supplied or saved content.",
    "skill-meeting-notes": "Teacher asked to turn talk into meeting notes.",
    "skill-kb-ask": "Teacher asked about school library materials.",
    "skill-lesson-outline": "Only when the teacher asked for a lesson outline. Never auto-apply.",
    "skill-quiz-draft": "Only when the teacher asked for a quiz draft. Never auto-apply.",
}


def _intersect_gateway(names: Iterable[str]) -> list[str]:
    allowed = ALLOWED_GATEWAY_TOOLS
    out: list[str] = []
    seen: set[str] = set()
    for name in names:
        if name in allowed and name not in seen:
            seen.add(name)
            out.append(name)
    return out


def ppt_siblings_honest(names: Iterable[str]) -> bool:
    """Spec PPT without isolated python-pptx is a hidden picker."""
    visible = set(names)
    if "generate_pptx_document" not in visible:
        return True
    return "sandbox_office_lib" in visible or "sandbox_pptx_lib" in visible


def office_siblings_honest(names: Iterable[str]) -> bool:
    """Spec Word/Excel without isolated office libs is a hidden picker."""
    visible = set(names)
    if "generate_docx_document" not in visible and "generate_xlsx_document" not in visible:
        return True
    return "sandbox_office_lib" in visible


def office_skill_visible(names: Iterable[str]) -> bool:
    """Office write without on-demand craft is a hidden picker."""
    visible = set(names)
    if "sandbox_office_lib" not in visible:
        return True
    return "read_office_skill" in visible


def resolve_visible_tools(allowed_tools: list[str] | tuple[str, ...] | None) -> list[str]:
    """None = CORE always-on. Explicit list = that list ∩ gateway (skill may narrow)."""
    if allowed_tools is None:
        return _intersect_gateway(CORE_VISIBLE_TOOLS)
    return _intersect_gateway(allowed_tools)


def visible_tools_env(names: Iterable[str]) -> str:
    return ",".join(_intersect_gateway(names))


def skill_catalog_block() -> str:
    """Catalog layer: name + when. Not full SKILL.md. Not a second store."""
    from pico_orchestrator.skill_policy import skill_catalog

    lines: list[str] = []
    for row in skill_catalog():
        sid = str(row.get("id") or "")
        when = SKILL_WHEN.get(sid, "").strip()
        if not sid or not when:
            continue
        lines.append(f"- `{sid}`: {when}")
    return "\n".join(lines)


def office_craft_catalog_block() -> str:
    from pico_orchestrator.office.skill_docs import office_skill_catalog_block

    return office_skill_catalog_block()
