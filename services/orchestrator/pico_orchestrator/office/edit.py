"""Path B: addressable edit of an uploaded OOXML. Rest of the file stays."""

from __future__ import annotations

import io
import re

from pico_orchestrator.artifact_types import is_valid_ooxml_package
from pico_orchestrator.office.comment import add_docx_comment
from pico_orchestrator.office.legacy import reject_legacy_office

_CELL_RE = re.compile(r"^([A-Za-z]+)(\d+)$")


def _nonempty_paragraphs(document: object) -> list[object]:
    paras = getattr(document, "paragraphs", None) or []
    return [p for p in paras if str(getattr(p, "text", "") or "").strip()]


def edit_docx_bytes(
    raw: bytes,
    *,
    paragraph_index: int,
    text: str,
) -> bytes:
    """Replace one 1-based nonempty paragraph. Other paragraphs stay."""
    reject_legacy_office(".docx")
    if not is_valid_ooxml_package(raw, ".docx"):
        raise ValueError("不是真 Word（OOXML）。请上传已有的 .docx。")
    new_text = (text or "").strip()
    if not new_text:
        raise ValueError("新段落不能为空。")
    if paragraph_index < 1:
        raise ValueError("段落序号从 1 起。")
    from docx import Document

    document = Document(io.BytesIO(raw))
    paras = _nonempty_paragraphs(document)
    if not paras:
        raise ValueError("这份 Word 没有可改的段落。")
    if paragraph_index > len(paras):
        raise ValueError(f"没有第 {paragraph_index} 段（共 {len(paras)} 段）。")
    paras[paragraph_index - 1].text = new_text
    out = io.BytesIO()
    document.save(out)
    data = out.getvalue()
    if not is_valid_ooxml_package(data, ".docx"):
        raise ValueError("改完后不是真 Word，未保存。")
    return data


def edit_pptx_title_bytes(
    raw: bytes,
    *,
    slide_index: int,
    new_title: str,
) -> bytes:
    """Replace the title of one 1-based slide. Other slides stay."""
    if not is_valid_ooxml_package(raw, ".pptx"):
        raise ValueError("不是真 PPT（OOXML）。请上传已有的 .pptx。")
    title = (new_title or "").strip()
    if not title:
        raise ValueError("新标题不能为空。")
    if slide_index < 1:
        raise ValueError("页码从 1 起。")
    from pptx import Presentation

    deck = Presentation(io.BytesIO(raw))
    slides = list(deck.slides)
    if not slides:
        raise ValueError("这份 PPT 没有可改的页。")
    if slide_index > len(slides):
        raise ValueError(f"没有第 {slide_index} 页（共 {len(slides)} 页）。")
    slide = slides[slide_index - 1]
    shape = getattr(slide.shapes, "title", None)
    if shape is not None and getattr(shape, "has_text_frame", False):
        shape.text = title
    else:
        replaced = False
        for item in slide.shapes:
            if getattr(item, "has_text_frame", False):
                item.text = title
                replaced = True
                break
        if not replaced:
            raise ValueError("该页没有标题可改。")
    out = io.BytesIO()
    deck.save(out)
    data = out.getvalue()
    if not is_valid_ooxml_package(data, ".pptx"):
        raise ValueError("改完后不是真 PPT，未保存。")
    return data


def edit_xlsx_cell_bytes(
    raw: bytes,
    *,
    cell: str,
    value: str,
    sheet: str | int | None = None,
) -> bytes:
    """Set one cell (A1-style). Other cells stay. Formulas start with =."""
    if not is_valid_ooxml_package(raw, ".xlsx"):
        raise ValueError("不是真 Excel（OOXML）。请上传已有的 .xlsx。")
    coord = (cell or "").strip().upper()
    if not _CELL_RE.match(coord):
        raise ValueError("请用单元格地址，例如 A1、D2。")
    from openpyxl import load_workbook

    book = load_workbook(io.BytesIO(raw))
    worksheet = _pick_sheet(book, sheet)
    from pico_orchestrator.office.render import _write_xlsx_cell

    _write_xlsx_cell(worksheet[coord], value)
    out = io.BytesIO()
    book.save(out)
    data = out.getvalue()
    if not is_valid_ooxml_package(data, ".xlsx"):
        raise ValueError("改完后不是真 Excel，未保存。")
    return data


def comment_docx_bytes(raw: bytes, *, paragraph_index: int, text: str) -> bytes:
    return add_docx_comment(raw, paragraph_index=paragraph_index, text=text)


def _pick_sheet(book: object, sheet: str | int | None) -> object:
    sheets = list(getattr(book, "worksheets", []) or [])
    if not sheets:
        raise ValueError("这份 Excel 没有工作表。")
    if sheet is None or sheet == "":
        return sheets[0]
    if isinstance(sheet, int) or (isinstance(sheet, str) and str(sheet).isdigit()):
        index = int(sheet)
        if index < 1:
            raise ValueError("工作表序号从 1 起。")
        if index > len(sheets):
            raise ValueError(f"没有第 {index} 张表（共 {len(sheets)} 张）。")
        return sheets[index - 1]
    name = str(sheet).strip()
    for item in sheets:
        if str(getattr(item, "title", "")) == name:
            return item
    raise ValueError(f"没有名为 {name} 的工作表。")
