"""T-OFFICE-SKILL-VISIBILITY: catalog one line; craft on demand; no bash."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "orchestrator"))

from pico_orchestrator.capability_loading import (
    CORE_VISIBLE_TOOLS,
    office_skill_visible,
    resolve_visible_tools,
)
from pico_orchestrator.gateway import ToolError
from pico_orchestrator.office.skill_docs import (
    OFFICE_SKILL_IDS,
    load_office_skill_body,
    normalize_office_skill_id,
)
from pico_orchestrator.tools_builtin import build_default_gateway
from pico_orchestrator.true_pi.config import ALLOWED_GATEWAY_TOOLS
from pico_orchestrator.true_pi.runtime import pico_system_text
from pico_orchestrator.workbench_progress import (
    workbench_tool_result_line,
    workbench_tool_step_line,
)


def test_read_office_skill_is_core_not_bash() -> None:
    gw = build_default_gateway()
    assert "read_office_skill" in gw.tools
    assert "read_office_skill" in ALLOWED_GATEWAY_TOOLS
    assert "read_office_skill" in CORE_VISIBLE_TOOLS
    assert "bash" not in ALLOWED_GATEWAY_TOOLS
    assert workbench_tool_step_line("read_office_skill") == "正在读办公工艺"
    assert workbench_tool_result_line("read_office_skill", ok=True) == "已读办公工艺"
    assert office_skill_visible(resolve_visible_tools(None))


def test_system_catalog_is_one_line_not_craft_body() -> None:
    body = pico_system_text()
    assert "`docx`:" in body
    assert "`xlsx`:" in body
    assert "`pptx`:" in body
    assert "read_office_skill" in body
    assert "generate_* remains the fast path" not in body
    assert "artifact_id" in body
    assert "from docx import Document" not in body
    assert "from openpyxl import Workbook" not in body
    assert "add_heading" not in body
    assert "MSO_SHAPE" not in body
    assert "pi install" not in body
    assert "```bash" not in body
    assert "host bash" not in body.lower()


def test_office_skill_bodies_have_craft_without_shell() -> None:
    expected = {
        "docx": ("add_heading", "Table Grid", "section.header"),
        "xlsx": ("=SUM(", "create_sheet", "number_format"),
        "pptx": ("MSO_SHAPE", "RGBColor", "slide_layouts[6]"),
    }
    for sid in OFFICE_SKILL_IDS:
        text = load_office_skill_body(sid)
        assert "sandbox_office_lib" in text
        assert "pi install" not in text
        assert "```bash" not in text
        # v2 (#959): the box is a full Python; the craft must not pretend otherwise
        assert "Do not import os" not in text
        assert "Do not use a shell" not in text
        assert "isolated container" in text
        assert "Fast path remains" not in text
        assert "artifact_id" in text
        assert "load_" in text
        for needle in expected[sid]:
            assert needle in text, (sid, needle)


def test_normalize_office_skill_aliases() -> None:
    assert normalize_office_skill_id("Word") == "docx"
    assert normalize_office_skill_id("excel") == "xlsx"
    assert normalize_office_skill_id("slides") == "pptx"
    assert normalize_office_skill_id("office-docx") == "docx"
    assert normalize_office_skill_id("nope") is None


@pytest.mark.asyncio
async def test_read_office_skill_returns_body() -> None:
    gw = build_default_gateway()

    class P:
        def __init__(self) -> None:
            self.school_id = "school-a"
            self.membership_id = "member-a"
            self.scopes = ["ai:run"]

    out = await gw.invoke(P(), "read_office_skill", {"id": "docx"})
    assert out["ok"] is True
    assert out["id"] == "docx"
    assert "add_heading" in out["body"]
    assert out["execute_with"] == "sandbox_office_lib"
    with pytest.raises(ToolError) as ei:
        await gw.invoke(P(), "read_office_skill", {"id": "bash"})
    assert ei.value.code == "office_skill.unknown"
