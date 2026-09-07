"""T-OFFICE-COMPUTER + T-OFFICE-OBJECT-IDENTITY: isolated office libs. No bash."""

from __future__ import annotations

import sys
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import Any

import pytest
from docx import Document
from openpyxl import Workbook, load_workbook
from pptx import Presentation

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "orchestrator"))

from pico_orchestrator.capability_loading import CORE_VISIBLE_TOOLS
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
    assert "verify_document" in CORE_VISIBLE_TOOLS
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


def _grade_xlsx() -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.title = "成绩"
    ws["A1"] = "姓名"
    ws["B1"] = "分数"
    ws["C1"] = "等级"
    ws["A2"] = "甲"
    ws["B2"] = 90
    ws["C2"] = "A"
    ws["A3"] = "乙"
    ws["B3"] = 80
    ws["C3"] = "B"
    buf = BytesIO()
    wb.save(buf)
    return buf.getvalue()


def _notice_docx() -> bytes:
    doc = Document()
    doc.add_heading("通知标题", level=1)
    doc.add_paragraph("原第二段不得改。")
    doc.add_paragraph("原第三段不得改。")
    table = doc.add_table(rows=2, cols=2)
    table.rows[0].cells[0].text = "甲"
    table.rows[0].cells[1].text = "乙"
    table.rows[1].cells[0].text = "1"
    table.rows[1].cells[1].text = "2"
    buf = BytesIO()
    doc.save(buf)
    return buf.getvalue()


def _deck_pptx() -> bytes:
    prs = Presentation()
    s1 = prs.slides.add_slide(prs.slide_layouts[0])
    s1.shapes.title.text = "封面原标题"
    s2 = prs.slides.add_slide(prs.slide_layouts[1])
    s2.shapes.title.text = "第二页原标题"
    body = s2.shapes.placeholders[1].text_frame
    body.paragraphs[0].text = "第二页要点保留"
    buf = BytesIO()
    prs.save(buf)
    return buf.getvalue()


def test_xlsx_load_existing_adds_column_keeps_grid() -> None:
    out = run_office_lib_source(
        """
wb = load_book()
ws = wb["成绩"]
ws["D1"] = "营收"
ws["D2"] = 100
ws["D3"] = 80
save_book(wb)
""",
        kind="xlsx",
        input_bytes=_grade_xlsx(),
    )
    wb = load_workbook(BytesIO(out), data_only=False)
    ws = wb["成绩"]
    assert ws["A1"].value == "姓名"
    assert ws["B1"].value == "分数"
    assert ws["C1"].value == "等级"
    assert ws["A2"].value == "甲"
    assert ws["B2"].value == 90
    assert ws["C2"].value == "A"
    assert ws["A3"].value == "乙"
    assert ws["B3"].value == 80
    assert ws["C3"].value == "B"
    assert ws["D1"].value == "营收"
    assert ws["D2"].value == 100
    assert ws["D3"].value == 80


def test_docx_load_existing_changes_only_second_paragraph() -> None:
    out = run_office_lib_source(
        """
doc = load_doc()
paras = [p for p in doc.paragraphs if p.text.strip()]
paras[1].text = "第二段已改。"
save_doc(doc)
""",
        kind="docx",
        input_bytes=_notice_docx(),
    )
    doc = Document(BytesIO(out))
    texts = [p.text for p in doc.paragraphs if p.text.strip()]
    assert texts[0] == "通知标题"
    assert texts[1] == "第二段已改。"
    assert texts[2] == "原第三段不得改。"
    cells = [c.text for row in doc.tables[0].rows for c in row.cells]
    assert cells == ["甲", "乙", "1", "2"]


def test_pptx_load_existing_changes_only_cover_title() -> None:
    out = run_office_lib_source(
        """
prs = load_deck()
prs.slides[0].shapes.title.text = "封面已改"
save_deck(prs)
""",
        kind="pptx",
        input_bytes=_deck_pptx(),
    )
    prs = Presentation(BytesIO(out))
    assert len(prs.slides) == 2
    assert prs.slides[0].shapes.title.text == "封面已改"
    assert prs.slides[1].shapes.title.text == "第二页原标题"
    assert "第二页要点保留" in prs.slides[1].shapes.placeholders[1].text_frame.paragraphs[0].text


def test_bad_input_bytes_fail_closed() -> None:
    with pytest.raises(ToolError) as ei:
        run_office_lib_source(
            "from docx import Document\ndoc = Document()\ndoc.add_paragraph('x')\nsave_doc(doc)",
            kind="docx",
            input_bytes=b"not-a-zip",
        )
    assert ei.value.code == "sandbox.input_invalid"


@dataclass
class _P:
    school_id: str = "school-a"
    membership_id: str = "member-a"
    scopes: list[str] | None = None

    def __post_init__(self) -> None:
        if self.scopes is None:
            self.scopes = ["ai:run"]


class _MemoryStore:
    def __init__(self) -> None:
        self.rows: list[dict[str, Any]] = []

    async def write(
        self,
        principal: _P,
        *,
        title: str,
        content: str | bytes,
        kind: str,
    ) -> dict[str, Any]:
        del principal
        aid = f"art-{len(self.rows) + 1}"
        row = {
            "artifact_id": aid,
            "title": title,
            "content": content,
            "kind": kind,
            "byte_size": len(content) if isinstance(content, bytes) else len(content.encode("utf-8")),
        }
        self.rows.append(row)
        return {k: v for k, v in row.items() if k != "content"}

    async def read(
        self,
        principal: _P,
        *,
        artifact_id: str | None,
        title: str | None,
    ) -> dict[str, Any] | None:
        del principal, title
        for row in reversed(self.rows):
            if artifact_id and row["artifact_id"] == artifact_id:
                return row
        return None

    async def list(self, principal: _P, *, limit: int) -> list[dict[str, Any]]:
        del principal
        return list(reversed(self.rows))[:limit]


@pytest.mark.asyncio
async def test_office_lib_missing_artifact_does_not_write() -> None:
    store = _MemoryStore()
    gw = build_default_gateway(store)
    with pytest.raises(ToolError) as ei:
        await gw.invoke(
            _P(),
            "sandbox_office_lib",
            {
                "kind": "xlsx",
                "artifact_id": "missing",
                "source": "wb = load_book()\nsave_book(wb)\n",
            },
        )
    assert ei.value.code == "artifact.not_found"
    assert store.rows == []


@pytest.mark.asyncio
async def test_office_lib_gateway_loads_artifact_id() -> None:
    store = _MemoryStore()
    gw = build_default_gateway(store)
    first = await store.write(_P(), title="成绩.xlsx", content=_grade_xlsx(), kind="xlsx")
    out = await gw.invoke(
        _P(),
        "sandbox_office_lib",
        {
            "kind": "xlsx",
            "artifact_id": first["artifact_id"],
            "source": (
                "wb = load_book()\n"
                'ws = wb["成绩"]\n'
                'ws["D1"] = "营收"\n'
                "save_book(wb)\n"
            ),
        },
    )
    assert out.get("loaded_existing") is True
    assert out.get("source_artifact_id") == first["artifact_id"]
    row = await store.read(_P(), artifact_id=out["artifact_id"], title=None)
    assert row is not None
    wb = load_workbook(BytesIO(row["content"]), data_only=False)
    assert wb["成绩"]["A2"].value == "甲"
    assert wb["成绩"]["D1"].value == "营收"
