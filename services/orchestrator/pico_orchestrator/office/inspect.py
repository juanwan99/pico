"""Bytes → address outline. python-docx / python-pptx only."""

from __future__ import annotations

import io
from typing import Any

from pico_orchestrator.artifact_types import is_valid_ooxml_package


def inspect_bytes(raw: bytes, ext: str) -> dict[str, Any]:
    """Return kind + stable addresses. Fail closed on junk packages."""
    suffix = _ext(ext)
    if suffix == ".docx":
        return _inspect_docx(raw)
    if suffix == ".pptx":
        return _inspect_pptx(raw)
    if suffix == ".xlsx":
        raise ValueError("Excel 产品面是卡 2，本卡只 inspect Word/PPT。")
    raise ValueError("只支持 .docx / .pptx。")


def _ext(ext: str) -> str:
    suffix = (ext or "").lower()
    if suffix and not suffix.startswith("."):
        suffix = f".{suffix}"
    return suffix


def _inspect_docx(raw: bytes) -> dict[str, Any]:
    if not is_valid_ooxml_package(raw, ".docx"):
        raise ValueError("不是真 Word（OOXML）。")
    from docx import Document

    document = Document(io.BytesIO(raw))
    addresses: list[dict[str, Any]] = []
    para_i = 0
    for para in document.paragraphs:
        text = str(getattr(para, "text", "") or "").strip()
        if not text:
            continue
        para_i += 1
        style_name = ""
        style = getattr(para, "style", None)
        if style is not None:
            style_name = str(getattr(style, "name", "") or "")
        kind = "heading" if style_name.lower().startswith("heading") or style_name == "Title" else "para"
        addresses.append(
            {
                "addr": f"p:{para_i}",
                "kind": kind,
                "text": text[:240],
            }
        )
    table_i = 0
    for table in document.tables:
        table_i += 1
        grid: list[list[str]] = []
        for row in table.rows:
            grid.append([str(cell.text or "").strip() for cell in row.cells])
        nrows = len(grid)
        ncols = max((len(r) for r in grid), default=0)
        preview = " | ".join(grid[0]) if grid else ""
        addresses.append(
            {
                "addr": f"t:{table_i}",
                "kind": "table",
                "rows": nrows,
                "cols": ncols,
                "preview": preview[:240],
            }
        )
        for r_i, row in enumerate(grid, start=1):
            for c_i, cell in enumerate(row, start=1):
                if not cell:
                    continue
                addresses.append(
                    {
                        "addr": f"t:{table_i}.r{r_i}.c{c_i}",
                        "kind": "cell",
                        "text": cell[:240],
                    }
                )
    image_n = _docx_image_count(document)
    for img_i in range(1, image_n + 1):
        addresses.append({"addr": f"img:{img_i}", "kind": "image"})
    return {
        "ok": True,
        "kind": "docx",
        "addresses": addresses,
        "paragraph_count": para_i,
        "table_count": table_i,
        "image_count": image_n,
        "unsupported": [],
    }


def _inspect_pptx(raw: bytes) -> dict[str, Any]:
    if not is_valid_ooxml_package(raw, ".pptx"):
        raise ValueError("不是真 PPT（OOXML）。")
    from pptx import Presentation
    from pptx.enum.shapes import MSO_SHAPE_TYPE

    deck = Presentation(io.BytesIO(raw))
    addresses: list[dict[str, Any]] = []
    slide_n = 0
    image_n = 0
    for slide in deck.slides:
        slide_n += 1
        title_shape = _slide_title_shape(slide)
        title = ""
        if title_shape is not None and getattr(title_shape, "has_text_frame", False):
            title = str(title_shape.text or "").strip()
        addresses.append({"addr": f"s:{slide_n}", "kind": "slide", "title": title[:240]})
        if title:
            addresses.append({"addr": f"s:{slide_n}.title", "kind": "slide_title", "text": title[:240]})
        bullets = _slide_bullets(slide, title_shape)
        for b_i, bullet in enumerate(bullets, start=1):
            addresses.append(
                {
                    "addr": f"s:{slide_n}.b:{b_i}",
                    "kind": "bullet",
                    "text": bullet[:240],
                }
            )
        has_image = False
        for shape in slide.shapes:
            shape_type = getattr(shape, "shape_type", None)
            if shape_type == MSO_SHAPE_TYPE.PICTURE:
                has_image = True
                image_n += 1
        if has_image:
            addresses.append({"addr": f"s:{slide_n}.image", "kind": "image"})
    return {
        "ok": True,
        "kind": "pptx",
        "addresses": addresses,
        "slide_count": slide_n,
        "image_count": image_n,
        "unsupported": [],
    }


def _docx_image_count(document: object) -> int:
    inline = getattr(document, "inline_shapes", None)
    if inline is None:
        return 0
    try:
        return len(inline)
    except (TypeError, AttributeError):
        return 0


def _slide_title_shape(slide: object) -> object | None:
    title_shape = getattr(getattr(slide, "shapes", None), "title", None)
    if title_shape is not None:
        return title_shape
    for shape in getattr(slide, "shapes", []):
        idx = getattr(getattr(shape, "placeholder_format", None), "idx", None)
        if idx == 0 and getattr(shape, "has_text_frame", False):
            return shape
    return None


def _is_title_shape(shape: object, title_shape: object) -> bool:
    if title_shape is not None and shape is title_shape:
        return True
    idx = getattr(getattr(shape, "placeholder_format", None), "idx", None)
    if idx == 0:
        return True
    name = str(getattr(shape, "name", "") or "").lower()
    return name.startswith("title")


def _slide_bullets(slide: object, title_shape: object) -> list[str]:
    bullets: list[str] = []
    for shape in getattr(slide, "shapes", []):
        if _is_title_shape(shape, title_shape):
            continue
        if not getattr(shape, "has_text_frame", False):
            continue
        frame = shape.text_frame
        for para in getattr(frame, "paragraphs", []):
            text = str(getattr(para, "text", "") or "").strip()
            if text:
                bullets.append(text)
        if bullets:
            break
    return bullets
