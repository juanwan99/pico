"""Always-on CORE vs gateway ceiling. No tool_search. No scene auto-hang."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "orchestrator"))

from pico_orchestrator.capability_loading import (
    CORE_VISIBLE_TOOLS,
    EXTENDED_TOOLS,
    SCENE_SKILL_IDS,
    SKILL_WHEN,
    ppt_siblings_honest,
    resolve_visible_tools,
    skill_catalog_block,
    visible_tools_env,
)
from pico_orchestrator.skill_policy import (
    skill_catalog,
    skill_id_from_prompt,
    snapshot_for_skill,
)
from pico_orchestrator.true_pi.config import ALLOWED_GATEWAY_TOOLS
from pico_orchestrator.true_pi.runtime import pico_system_text


def test_core_and_extended_partition_gateway():
    assert set(CORE_VISIBLE_TOOLS) | set(EXTENDED_TOOLS) == set(ALLOWED_GATEWAY_TOOLS)
    assert set(CORE_VISIBLE_TOOLS) & set(EXTENDED_TOOLS) == set()
    assert "bash" not in CORE_VISIBLE_TOOLS
    assert "bash" not in EXTENDED_TOOLS
    assert len(CORE_VISIBLE_TOOLS) == 17
    assert len(EXTENDED_TOOLS) == 11
    assert "generate_diagram" in CORE_VISIBLE_TOOLS
    assert "generate_diagram" in ALLOWED_GATEWAY_TOOLS
    assert "sandbox_pptx_lib" in CORE_VISIBLE_TOOLS
    assert "sandbox_pptx_lib" not in EXTENDED_TOOLS
    assert "edit_docx_document" not in CORE_VISIBLE_TOOLS
    assert "edit_pptx_document" not in CORE_VISIBLE_TOOLS
    assert "edit_xlsx_document" not in CORE_VISIBLE_TOOLS
    assert "edit_docx_document" in EXTENDED_TOOLS
    assert "edit_pptx_document" in EXTENDED_TOOLS
    assert "edit_xlsx_document" in EXTENDED_TOOLS
    assert "sandbox_workspace_exec" in EXTENDED_TOOLS
    assert "sandbox_workspace_exec" not in CORE_VISIBLE_TOOLS
    assert "sandbox_browser_open" in CORE_VISIBLE_TOOLS
    assert "sandbox_document_open" in CORE_VISIBLE_TOOLS
    assert "sandbox_browser_open" not in EXTENDED_TOOLS
    assert "sandbox_document_open" not in EXTENDED_TOOLS
    assert "sandbox_browser_screenshot" in EXTENDED_TOOLS
    assert "publish_html_page" in EXTENDED_TOOLS
    assert "kb_search" in CORE_VISIBLE_TOOLS
    assert "ask_user" in CORE_VISIBLE_TOOLS
    assert ppt_siblings_honest(CORE_VISIBLE_TOOLS)


def test_default_visible_is_core_not_full_allowlist():
    visible = resolve_visible_tools(None)
    assert visible == list(CORE_VISIBLE_TOOLS)
    assert "sandbox_pptx_lib" in visible
    assert "generate_pptx_document" in visible
    assert "edit_docx_document" not in visible
    assert "sandbox_workspace_exec" not in visible
    assert "verify_html_document" not in visible
    assert "generate_docx_document" in visible
    assert "generate_diagram" in visible
    assert "publish_html_page" not in visible
    assert "unpublish_html_page" not in visible
    assert "sandbox_browser_open" in visible
    assert "sandbox_document_open" in visible
    assert "sandbox_browser_screenshot" not in visible
    assert "kb_search" in visible
    assert ppt_siblings_honest(visible)


def test_hung_skill_may_narrow_and_may_include_extended():
    deliver = snapshot_for_skill("skill-deliverable")
    assert deliver is not None
    visible = resolve_visible_tools(list(deliver["tools"]))
    assert "sandbox_pptx_lib" in visible
    assert "verify_html_document" in visible
    assert "generate_diagram" in visible
    assert "web_search" not in visible
    chat = snapshot_for_skill("skill-chat")
    assert chat is not None
    assert resolve_visible_tools(list(chat["tools"])) == []


def test_visible_env_is_comma_core():
    encoded = visible_tools_env(CORE_VISIBLE_TOOLS)
    assert encoded.startswith("workspace_list_files,")
    assert "sandbox_workspace_exec" not in encoded
    assert resolve_visible_tools([]) == []


def test_catalog_is_one_line_not_deliverable_body():
    block = skill_catalog_block()
    assert "`skill-deliverable`:" in block
    assert "Never auto-apply" in block
    assert "本轮交付真实文件" not in block
    assert "课件" not in block
    for sid in SCENE_SKILL_IDS:
        assert sid in SKILL_WHEN
        assert "Never auto-apply" in SKILL_WHEN[sid]


def test_system_md_slim_and_catalog_not_scene_weld():
    body = pico_system_text()
    assert "This block is **SYSTEM**" in body
    assert "Default is a chat answer" in body
    assert "Being listed does **not** mean you must call them" in body
    assert "Call `kb_search` only when the teacher asks about school materials" in body
    assert "generate_diagram" in body
    assert "If `publish_html_page` is listed this turn" in body
    assert "public_url" in body
    assert "third-party form backend" in body
    assert "page collect path" in body
    assert "`skill-deliverable`:" in body
    assert "本轮交付真实文件" not in body
    assert "Engineering delivery" not in body
    assert "Open a public website" not in body
    assert "sandbox_pptx_lib" in body
    assert "siblings" in body
    assert "课件" not in body
    assert "通知" not in body
    assert "这是什么" not in body
    assert "Landing requirement" not in body
    assert "A tool returning ok is not finished" in body


def test_hung_skill_body_only_when_mounted():
    empty = pico_system_text()
    hung = pico_system_text(skill="本轮交付真实文件：HTML/Word")
    assert "本轮交付真实文件" not in empty
    assert "本轮交付真实文件" in hung


def test_scene_skills_stay_opt_in_on_disk():
    skill_root = ROOT / "apps" / "librechat" / "skill"
    for sid in SCENE_SKILL_IDS:
        text = (skill_root / sid / "SKILL.md").read_text(encoding="utf-8")
        assert "always-apply: false" in text
        assert "课件" not in text


def test_bridge_and_runtimes_honor_visible_list():
    ts = (ROOT / "services" / "true_pi_bridge" / "pico-gateway-tools.ts").read_text(
        encoding="utf-8"
    )
    assert "PICO_TRUE_PI_VISIBLE_TOOLS" in ts
    assert "visibleAllowlist" in ts
    runtime = (
        ROOT
        / "services"
        / "orchestrator"
        / "pico_orchestrator"
        / "true_pi"
        / "runtime.py"
    ).read_text(encoding="utf-8")
    assert "resolve_visible_tools" in runtime
    assert "PICO_TRUE_PI_VISIBLE_TOOLS" in runtime
    hosted = (
        ROOT / "services" / "orchestrator" / "pico_orchestrator" / "pi_runtime.py"
    ).read_text(encoding="utf-8")
    assert "resolve_visible_tools" in hosted


def test_hung_skills_cannot_hide_office_ceiling():
    for row in skill_catalog():
        tools = list(row.get("tools") or [])
        assert ppt_siblings_honest(tools), row.get("id")
        visible = resolve_visible_tools(tools)
        assert ppt_siblings_honest(visible), row.get("id")
    chat = snapshot_for_skill("skill-chat")
    assert chat is not None
    assert chat["tools"] == []
    assert "sandbox_workspace_exec" not in (snapshot_for_skill("skill-engineering-delivery") or {}).get(
        "tools", []
    )


def test_plain_prompt_does_not_auto_hang_skill():
    for prompt in (
        "做个精美课件PPT",
        "精美",
        "课件",
        "做成 PPT",
        "这是什么",
        "通知",
    ):
        assert skill_id_from_prompt(prompt) is None, prompt
    assert skill_id_from_prompt("【Pico-Skill:skill-deliverable】做成 PPT") == (
        "skill-deliverable"
    )
