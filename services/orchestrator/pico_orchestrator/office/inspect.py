"""Bytes → addressable outline. Model must not guess paragraph indexes."""

from __future__ import annotations

import io

from pico_orchestrator.artifact_types import is_valid_ooxml_package
from pico_orchestrator.office.comment import list_docx_comments
from pico_orchestrator.office.fill import leftover_placeholders
from pico_orchestrator.office.legacy import require_supported_office_ext


def inspect_office_bytes(raw: bytes, ext: str) -> dict[str, object]:
    suffix = require_supported_office_ext(ext)
    if suffix == ".docx":
        return _inspect_docx(raw)
    if suffix == ".pptx":
        return _inspect_pptx(raw)
    return _inspect_xlsx(raw)


def _inspect_docx(raw: bytes) -> dict[str, object]:
    if not is_valid_ooxml_package(raw, ".docx"):
        raise ValueError("不是真 Word（OOXML）。")
    from docx import Document

    document = Document(io.BytesIO(raw))
    units: list[dict[str, object]] = []
    leftovers: list[str] = []
    para_n = 0
    table_n = 0
    image_n = 0
    for para in document.paragraphs:
        text = str(para.text or "").strip()
        if not text:
            continue
        para_n += 1
        leftovers.extend(leftover_placeholders(text))
        style = str(getattr(getattr(para, "style", None), "name", "") or "")
        kind = "heading" if style.lower().startswith("heading") else "para"
        units.append({"index": para_n, "kind": kind, "text": text[:240], "style": style})
    for table in document.tables:
        table_n += 1
        rows = [[(cell.text or "").strip() for cell in row.cells] for row in table.rows]
        for row in rows:
            for cell in row:
                leftovers.extend(leftover_placeholders(cell))
        preview = rows[0] if rows else []
        units.append(
            {
                "index": table_n,
                "kind": "table",
                "rows": len(rows),
                "cols": len(preview),
                "preview": preview[:8],
            }
        )
    for rel in document.part.rels.values():
        reltype = str(getattr(rel, "reltype", "") or "")
        if "image" in reltype.lower():
            image_n += 1
            units.append({"index": image_n, "kind": "image"})
    comments = list_docx_comments(raw)
    units.extend(comments)
    return {
        "kind": "docx",
        "paragraphs": para_n,
        "tables": table_n,
        "images": image_n,
        "comments": len(comments),
        "placeholders": _unique(leftovers),
        "units": units,
    }


def _inspect_pptx(raw: bytes) -> dict[str, object]:
    if not is_valid_ooxml_package(raw, ".pptx"):
        raise ValueError("不是真 PPT（OOXML）。")
    from pptx import Presentation
    from pptx.enum.shapes import MSO_SHAPE_TYPE

    deck = Presentation(io.BytesIO(raw))
    units: list[dict[str, object]] = []
    leftovers: list[str] = []
    image_n = 0
    for i, slide in enumerate(deck.slides, start=1):
        title = ""
        shape = getattr(slide.shapes, "title", None)
        if shape is not None:
            title = str(getattr(shape, "text", "") or "").strip()
        leftovers.extend(leftover_placeholders(title))
        bullets: list[str] = []
        slide_images = 0
        max_w = 0
        max_h = 0
        for item in slide.shapes:
            if item is shape:
                continue
            if getattr(item, "has_text_frame", False):
                text = str(getattr(item, "text", "") or "").strip()
                if text:
                    leftovers.extend(leftover_placeholders(text))
                    bullets.extend(ln.strip() for ln in text.splitlines() if ln.strip())
            if getattr(item, "shape_type", None) == MSO_SHAPE_TYPE.PICTURE:
                slide_images += 1
                image_n += 1
                max_w = max(max_w, int(getattr(item, "width", 0) or 0))
                max_h = max(max_h, int(getattr(item, "height", 0) or 0))
        unit: dict[str, object] = {
            "index": i,
            "kind": "slide",
            "title": title[:240],
            "bullets": bullets[:12],
            "images": slide_images,
        }
        if slide_images:
            unit["image_width_emu"] = max_w
            unit["image_height_emu"] = max_h
        units.append(unit)
    return {
        "kind": "pptx",
        "slides": len(units),
        "images": image_n,
        "placeholders": _unique(leftovers),
        "units": units,
    }


def _inspect_xlsx(raw: bytes) -> dict[str, object]:
    if not is_valid_ooxml_package(raw, ".xlsx"):
        raise ValueError("不是真 Excel（OOXML）。")
    from openpyxl import load_workbook

    book = load_workbook(io.BytesIO(raw), data_only=False)
    units: list[dict[str, object]] = []
    leftovers: list[str] = []
    formulas = 0
    for i, sheet in enumerate(book.worksheets, start=1):
        headers: list[str] = []
        sample: list[list[object]] = []
        sheet_formulas: list[str] = []
        for row_i, row in enumerate(sheet.iter_rows(values_only=False), start=1):
            values: list[object] = []
            for cell in row:
                raw_val = cell.value
                if isinstance(raw_val, str):
                    leftovers.extend(leftover_placeholders(raw_val))
                    if raw_val.startswith("="):
                        formulas += 1
                        sheet_formulas.append(f"{cell.coordinate}:{raw_val}")
                values.append(_cell_preview(raw_val))
            if row_i == 1:
                headers = [str(v) if v is not None else "" for v in values]
            if 2 <= row_i <= 6:
                sample.append(values)
        units.append(
            {
                "index": i,
                "kind": "sheet",
                "name": sheet.title,
                "rows": sheet.max_row or 0,
                "cols": sheet.max_column or 0,
                "headers": headers[:12],
                "preview": sample,
                "formulas": sheet_formulas[:12],
            }
        )
    return {
        "kind": "xlsx",
        "sheets": len(units),
        "formulas": formulas,
        "placeholders": _unique(leftovers),
        "units": units,
    }


def _cell_preview(value: object) -> object:
    if value is None:
        return ""
    if isinstance(value, str):
        return value[:80]
    if isinstance(value, (int, float)):
        return value
    return str(value)[:80]


def _unique(items: list[str]) -> list[str]:
    seen: list[str] = []
    for item in items:
        if item not in seen:
            seen.append(item)
    return seen
