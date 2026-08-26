"""Bytes → addressable outline. Model must not guess paragraph indexes."""

from __future__ import annotations

import io

from pico_orchestrator.artifact_types import is_valid_ooxml_package


def inspect_office_bytes(raw: bytes, ext: str) -> dict[str, object]:
    suffix = ext if ext.startswith(".") else f".{ext}"
    if suffix == ".docx":
        return _inspect_docx(raw)
    if suffix == ".pptx":
        return _inspect_pptx(raw)
    raise ValueError(f"inspect 本卡只支持 .docx / .pptx，不支持 {suffix}。")


def _inspect_docx(raw: bytes) -> dict[str, object]:
    if not is_valid_ooxml_package(raw, ".docx"):
        raise ValueError("不是真 Word（OOXML）。")
    from docx import Document

    document = Document(io.BytesIO(raw))
    units: list[dict[str, object]] = []
    para_n = 0
    table_n = 0
    image_n = 0
    for para in document.paragraphs:
        text = str(para.text or "").strip()
        if not text:
            continue
        para_n += 1
        style = str(getattr(getattr(para, "style", None), "name", "") or "")
        kind = "heading" if style.lower().startswith("heading") else "para"
        units.append({"index": para_n, "kind": kind, "text": text[:240], "style": style})
    for table in document.tables:
        table_n += 1
        rows = [[(cell.text or "").strip() for cell in row.cells] for row in table.rows]
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
    return {
        "kind": "docx",
        "paragraphs": para_n,
        "tables": table_n,
        "images": image_n,
        "units": units,
    }


def _inspect_pptx(raw: bytes) -> dict[str, object]:
    if not is_valid_ooxml_package(raw, ".pptx"):
        raise ValueError("不是真 PPT（OOXML）。")
    from pptx import Presentation
    from pptx.enum.shapes import MSO_SHAPE_TYPE

    deck = Presentation(io.BytesIO(raw))
    units: list[dict[str, object]] = []
    image_n = 0
    for i, slide in enumerate(deck.slides, start=1):
        title = ""
        shape = getattr(slide.shapes, "title", None)
        if shape is not None:
            title = str(getattr(shape, "text", "") or "").strip()
        bullets: list[str] = []
        slide_images = 0
        for item in slide.shapes:
            if item is shape:
                continue
            if getattr(item, "has_text_frame", False):
                text = str(getattr(item, "text", "") or "").strip()
                if text:
                    bullets.extend(ln.strip() for ln in text.splitlines() if ln.strip())
            if getattr(item, "shape_type", None) == MSO_SHAPE_TYPE.PICTURE:
                slide_images += 1
                image_n += 1
        units.append(
            {
                "index": i,
                "kind": "slide",
                "title": title[:240],
                "bullets": bullets[:12],
                "images": slide_images,
            }
        )
    return {
        "kind": "pptx",
        "slides": len(units),
        "images": image_n,
        "units": units,
    }
