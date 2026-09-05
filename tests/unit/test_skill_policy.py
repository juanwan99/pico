"""Skill thin policy unit tests."""

from pathlib import Path

from pico_orchestrator.skill_policy import (
    declared_tools_for_skill,
    instruction_for_snapshot,
    normalize_skill_id,
    snapshot_for_skill,
    snapshot_from_prompt,
    strip_skill_markers,
)
from pico_orchestrator.tools_builtin import build_default_gateway


def test_normalize_aliases():
    assert normalize_skill_id("skill.chat") == "skill-chat"
    assert normalize_skill_id("write_s7") == "skill-write-s7"
    assert normalize_skill_id("lesson_outline") == "skill-lesson-outline"
    assert normalize_skill_id("skill.meeting_notes") == "skill-meeting-notes"
    assert normalize_skill_id("engineering") == "skill-engineering-delivery"
    assert normalize_skill_id("package") == "skill-engineering-delivery"
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
        "skill-deliverable": (
            [
                "generate_html_document",
                "generate_docx_document",
                "generate_pptx_document",
                "sandbox_pptx_lib",
                "generate_xlsx_document",
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
                "web_search",
                "web_fetch",
                "ask_user",
            ],
            False,
        ),
        "skill-engineering-delivery": (
            [
                "workspace_write_file",
                "workspace_list_files",
                "workspace_read_file",
                "generate_html_document",
                "generate_docx_document",
                "generate_pptx_document",
                "sandbox_pptx_lib",
                "generate_xlsx_document",
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
                "web_search",
                "web_fetch",
                "ask_user",
            ],
            False,
        ),
        "skill-summarize": (
            [
                "workspace_read_file",
                "structured_outline",
                "workspace_write_file",
                "generate_html_document",
                "generate_docx_document",
                "generate_pptx_document",
                "sandbox_pptx_lib",
            ],
            False,
        ),
        "skill-lesson-outline": (
            [
                "structured_outline",
                "workspace_write_file",
                "generate_html_document",
                "generate_docx_document",
                "generate_pptx_document",
                "sandbox_pptx_lib",
            ],
            False,
        ),
        "skill-quiz-draft": (
            [
                "workspace_read_file",
                "structured_outline",
                "workspace_write_file",
                "generate_html_document",
                "generate_docx_document",
                "generate_pptx_document",
                "sandbox_pptx_lib",
            ],
            False,
        ),
        "skill-translate": (
            [
                "workspace_read_file",
                "workspace_write_file",
                "generate_html_document",
                "generate_docx_document",
                "generate_pptx_document",
                "sandbox_pptx_lib",
            ],
            False,
        ),
        "skill-meeting-notes": (
            [
                "structured_outline",
                "workspace_write_file",
                "generate_html_document",
                "generate_docx_document",
                "generate_pptx_document",
                "sandbox_pptx_lib",
            ],
            False,
        ),
    }
    from pico_orchestrator.true_pi.config import ALLOWED_GATEWAY_TOOLS

    global_tools = set(build_default_gateway().tools) | set(ALLOWED_GATEWAY_TOOLS)

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


def test_unknown_skill_fails_closed_as_chat_only():
    snapshot = snapshot_for_skill("skill-reead")

    assert snapshot is not None
    assert snapshot["id"] == "skill-unknown"
    assert snapshot["name"] == "skill.unknown"
    assert snapshot["tools"] == []
    assert snapshot["policy"]["tool_rule"] == "deny-all"
    assert snapshot["policy"]["reason"] == "skill.unknown"
    assert "workspace_write_file" not in snapshot["tools"]
    assert "skill.unknown" in instruction_for_snapshot(snapshot)


def test_unknown_prompt_marker_is_stripped_and_snapshotted():
    prompt, snapshot = snapshot_from_prompt(
        "【Pico-Skill:skill-reead】\n不要让我拿到全工具"
    )

    assert prompt == "不要让我拿到全工具"
    assert snapshot is not None
    assert snapshot["name"] == "skill.unknown"
    assert snapshot["tools"] == []


def test_prompt_without_skill_marker_preserves_default_policy():
    prompt, snapshot = snapshot_from_prompt("普通对话")

    assert prompt == "普通对话"
    assert snapshot is None


def test_deliverable_skills_keep_search_and_ask_user():
    for skill_id in ("skill-deliverable", "skill-engineering-delivery"):
        snap = snapshot_for_skill(skill_id)
        assert snap is not None
        tools = list(snap["tools"])
        for name in ("web_search", "web_fetch", "ask_user"):
            assert name in tools, (skill_id, name)


def test_kb_search_only_when_asking_school_materials():
    gw = build_default_gateway()
    assert "这是什么" not in gw.tools["kb_search"].description
    assert "Call only when the teacher asks about school materials" in gw.tools[
        "kb_search"
    ].description
    assert "does not mean you must call" in gw.tools["kb_search"].description
    for skill_id in (
        "skill-deliverable",
        "skill-engineering-delivery",
        "skill-kb-ask",
    ):
        text = instruction_for_snapshot(snapshot_for_skill(skill_id))
        assert "必须先 kb_search" not in text
        assert "这是什么" not in text
        assert "问学校材料" in text
        assert "才 kb_search" in text
        assert "工具在列表不代表必须调用" in text
    kb = snapshot_for_skill("skill-kb-ask")
    assert "kb_search" in kb["tools"]
    assert "出处" in instruction_for_snapshot(kb)
    ts = (
        Path(__file__).resolve().parents[2]
        / "services"
        / "true_pi_bridge"
        / "pico-gateway-tools.ts"
    ).read_text(encoding="utf-8")
    assert "Call only when the teacher asks about school materials" in ts
    assert "does not mean you must call" in ts
    assert "uploaded/generated" not in ts
    assert "去搜库" not in ts
    assert "材料/文档" not in ts
    assert "这是什么" not in ts
    skill_md = (
        Path(__file__).resolve().parents[2]
        / "apps"
        / "librechat"
        / "skill"
        / "skill-kb-ask"
        / "SKILL.md"
    ).read_text(encoding="utf-8")
    assert "Always search first" not in skill_md
    assert "Call `kb_search` first" not in skill_md
    assert "does not mean you must call" in skill_md
    assert "这是什么" not in skill_md
