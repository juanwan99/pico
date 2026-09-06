"""T-OFFICE-COMPUTER: isolated python-docx / openpyxl / python-pptx. No bash."""

from __future__ import annotations

import sys
from io import BytesIO
from pathlib import Path

import pytest
from docx import Document
from openpyxl import load_workbook

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "orchestrator"))

from pico_orchestrator.gateway import ToolError
from pico_orchestrator.office.inspect import inspect_office_bytes
from pico_orchestrator.office.sandbox_lib import (
    assert_office_lib_source,
    run_office_lib_source,
)
from pico_orchestrator.tools_builtin import build_default_gateway
from pico_orchestrator.true_pi.config import ALLOWED_GATEWAY_TOOLS
from pico_orchestrator.workbench_progress import (
    workbench_tool_result_line,
    workbench_tool_step_line,
)


def test_office_lib_on_allowlist_not_bash() -> None:
    gw = build_default_gateway()
    assert "sandbox_office_lib" in gw.tools
    assert "sandbox_office_lib" in ALLOWED_GATEWAY_TOOLS
    assert "bash" not in ALLOWED_GATEWAY_TOOLS
    assert workbench_tool_step_line("sandbox_office_lib") == "正在沙箱写办公文件"
    assert workbench_tool_result_line("sandbox_office_lib", ok=True) == "已沙箱写出办公文件"
    assert workbench_tool_result_line("sandbox_office_lib", ok=False) == "没沙箱写出办公文件"


def test_docx_script_writes_real_word() -> None:
    source = """
from docx import Document
doc = Document()
doc.add_heading("周报正文标题", level=1)
doc.add_paragraph("本周完成隔离办公库接线，老师打开这份 Word 必须看见这段话。")
save_doc(doc)
"""
    raw = run_office_lib_source(source, kind="docx")
    outline = inspect_office_bytes(raw, ".docx")
    assert int(outline.get("paragraphs") or 0) >= 1
    text = "\n".join(p.text for p in Document(BytesIO(raw)).paragraphs)
    assert "隔离办公库" in text


def test_xlsx_script_writes_real_sheet() -> None:
    source = """
from openpyxl import Workbook
wb = Workbook()
ws = wb.active
ws["A1"] = "分组"
ws["B1"] = "人数"
ws["A2"] = "甲"
ws["B2"] = 12
ws["A3"] = "乙"
ws["B3"] = 8
save_book(wb)
"""
    raw = run_office_lib_source(source, kind="xlsx")
    wb = load_workbook(BytesIO(raw), data_only=False)
    ws = wb.active
    assert ws["A1"].value == "分组"
    assert ws["B2"].value == 12


def test_office_kind_inferred_from_title_still_pptx() -> None:
    source = """
from pptx import Presentation
prs = Presentation()
add_title_slide(prs, "封面", "副题")
save_deck(prs)
"""
    raw = run_office_lib_source(source, kind="pptx")
    outline = inspect_office_bytes(raw, ".pptx")
    assert int(outline["slides"]) >= 1


def test_os_import_denied_for_office_lib() -> None:
    with pytest.raises(ToolError) as ei:
        assert_office_lib_source("import os\nprint(os.getcwd())", kind="docx")
    assert ei.value.code == "sandbox.exec_denied"
    with pytest.raises(ToolError) as ei:
        run_office_lib_source("import subprocess\nprint(1)", kind="xlsx")
    assert ei.value.code == "sandbox.exec_denied"


def test_empty_office_shells_fail() -> None:
    with pytest.raises(ToolError) as ei:
        run_office_lib_source("from docx import Document\ndoc = Document()\nsave_doc(doc)", kind="docx")
    assert ei.value.code == "sandbox.docx_shell"
    with pytest.raises(ToolError) as ei:
        run_office_lib_source("from openpyxl import Workbook\nwb = Workbook()\nsave_book(wb)", kind="xlsx")
    assert ei.value.code == "sandbox.xlsx_shell"
