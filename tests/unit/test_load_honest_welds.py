"""S1 T-LOAD-HONEST: no winner-picking welds; office siblings stay visible."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "orchestrator"))

from pico_orchestrator.capability_loading import (
    CORE_VISIBLE_TOOLS,
    resolve_visible_tools,
)
from pico_orchestrator.skill_policy import skill_id_from_prompt
from pico_orchestrator.tools_builtin import build_default_gateway
from pico_orchestrator.true_pi.runtime import pico_system_text

WELD_PHRASES = (
    "Photos still use",
    "photos still use generate_image",
    "Prefer generate_pptx",
    "Prefer generate_pptx_document",
    "ordinary decks",
    "Ceiling isolated python-pptx",
)

SURFACES = (
    ROOT / "services" / "orchestrator" / "pico_orchestrator" / "agent_assets" / "system.md",
    ROOT / "services" / "orchestrator" / "pico_orchestrator" / "tools_builtin.py",
    ROOT / "services" / "true_pi_bridge" / "pico-gateway-tools.ts",
)


def test_three_surfaces_have_no_winner_welds() -> None:
    for path in SURFACES:
        text = path.read_text(encoding="utf-8")
        for phrase in WELD_PHRASES:
            assert phrase not in text, f"{path.name}: {phrase!r}"


def test_pi_and_hosted_office_ceiling_descriptions() -> None:
    ts = (ROOT / "services" / "true_pi_bridge" / "pico-gateway-tools.ts").read_text(
        encoding="utf-8"
    )
    assert "sandbox_office_lib" in ts
    assert "Sibling of generate_image" in ts
    assert "they do not veto each other" in ts
    assert "Sibling of sandbox_pptx_lib" not in ts
    assert "Sibling of generate_pptx_document" not in ts
    gw = build_default_gateway()
    assert "generate_pptx_document" not in gw.tools
    assert "sandbox_pptx_lib" not in gw.tools
    office = gw.tools["sandbox_office_lib"].description
    diagram = gw.tools["generate_diagram"].description
    assert "The office write path" in office
    assert "from pathlib import Path is a stub" in office
    assert "Sibling of generate_image" in diagram
    assert "veto" in diagram
    assert "精美" not in office
    assert "课件" not in office


def test_system_names_office_ceiling_without_scene_words() -> None:
    body = pico_system_text()
    assert "sandbox_office_lib" in body
    assert "read_office_skill" in body
    assert "`docx`:" in body
    assert "from docx import Document" not in body
    assert "siblings" in body
    assert "is routed to the ledger" in body
    assert "from pathlib import Path" in body
    assert "课件" not in body
    assert "精美" not in body
    assert "通知" not in body
    assert "家长会" not in body
    assert "分数练习" not in body
    assert "unmatched brackets" in body
    assert "`publish_html_page` is not a Pico capability" in body
    assert "school-admin approval" in body
    assert "If `publish_html_page` is listed this turn" not in body
    assert "same title replaces the file the teacher opens" in body.lower()


def test_xlsx_values_is_placeholder_fill_on_pi_surfaces() -> None:
    ts = (ROOT / "services" / "true_pi_bridge" / "pico-gateway-tools.ts").read_text(
        encoding="utf-8"
    )
    assert "cell/value or values" not in ts
    gw = build_default_gateway()
    assert "generate_xlsx_document" not in gw.tools
    exec_desc = gw.tools["sandbox_workspace_exec"].description
    assert "executed=false" in exec_desc
    assert "not a real runner" in exec_desc


def test_default_core_shows_office_not_programming() -> None:
    visible = resolve_visible_tools(None)
    assert "sandbox_office_lib" in visible
    assert "read_office_skill" in visible
    assert "verify_document" not in visible
    assert "sandbox_workspace_exec" not in visible
    assert "generate_pptx_document" not in visible
    assert "sandbox_pptx_lib" not in visible
    assert "sandbox_office_lib" in CORE_VISIBLE_TOOLS
    assert "read_office_skill" in CORE_VISIBLE_TOOLS
    assert "sandbox_pptx_lib" not in CORE_VISIBLE_TOOLS


def test_scene_words_do_not_hang_a_skill() -> None:
    assert skill_id_from_prompt("做个精美课件PPT") is None
    assert skill_id_from_prompt("请做一份精美课件") is None
    assert skill_id_from_prompt("做成 PPT 能交") is None
    assert skill_id_from_prompt("这是什么") is None
    assert skill_id_from_prompt("") is None
