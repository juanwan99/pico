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


def test_pi_and_hosted_pptx_descriptions_are_siblings() -> None:
    ts = (ROOT / "services" / "true_pi_bridge" / "pico-gateway-tools.ts").read_text(
        encoding="utf-8"
    )
    assert "Sibling of sandbox_pptx_lib" in ts
    assert "Sibling of generate_pptx_document" in ts
    assert "Sibling of generate_image" in ts
    assert "they do not veto each other" in ts
    gw = build_default_gateway()
    pptx = gw.tools["generate_pptx_document"].description
    lib = gw.tools["sandbox_pptx_lib"].description
    diagram = gw.tools["generate_diagram"].description
    assert "Sibling of sandbox_pptx_lib" in pptx
    assert "stock python-pptx layouts" in pptx
    assert "Free shapes" in pptx
    assert "Sibling of generate_pptx_document" in lib
    assert "add_shape and RGBColor color blocks are this tool" in lib
    assert "Sibling of generate_image" in diagram
    assert "veto" in diagram
    assert "精美" not in lib
    assert "课件" not in lib
    assert "精美" not in pptx
    assert "Same title replaces the file the teacher opens" in pptx


def test_system_names_office_ceiling_without_scene_words() -> None:
    body = pico_system_text()
    assert "sandbox_pptx_lib" in body
    assert "siblings" in body
    assert "stock python-pptx layouts" in body
    assert "body bullets (not title-only walls)" not in body
    assert "课件" not in body
    assert "精美" not in body
    assert "通知" not in body
    assert "If `publish_html_page` is listed this turn" in body
    assert "Do not name or call publish tools that are not listed" in body
    assert "same title replaces the file the teacher opens" in body.lower()


def test_default_core_shows_office_not_programming() -> None:
    visible = resolve_visible_tools(None)
    assert "sandbox_pptx_lib" in visible
    assert "sandbox_workspace_exec" not in visible
    assert "sandbox_pptx_lib" in CORE_VISIBLE_TOOLS


def test_scene_words_do_not_hang_a_skill() -> None:
    assert skill_id_from_prompt("做个精美课件PPT") is None
    assert skill_id_from_prompt("请做一份精美课件") is None
    assert skill_id_from_prompt("做成 PPT 能交") is None
    assert skill_id_from_prompt("这是什么") is None
    assert skill_id_from_prompt("") is None
