"""spec → OOXML bytes. Upstream: python-docx / python-pptx."""

from __future__ import annotations

import base64
import io
from typing import Any

from pico_orchestrator.office.spec import SpecError, parse_spec


def render_spec(spec: dict[str, Any] | str, *, images: dict[str, bytes] | None = None) -> bytes:
    """Render a validated v1 spec. ``images`` maps artifact_id → bytes."""
    data = parse_spec(spec)
    resolved = images or {}
    if data["kind"] == "docx":
        return _render_docx(data, resolved)
    return _render_pptx(data, resolved)


def _render_docx(spec: dict[str, Any], images: dict[str, bytes]) -> bytes:
    from docx import Document
    from docx.enum.text import WD_BREAK
    from docx.oxml.ns import qn
    from docx.shared import Inches, Pt

    doc = Document()
    theme = spec.get("theme") or {}
    heading_font = str(theme.get("heading_font") or "").strip()
    body_font = str(theme.get("body_font") or "").strip()
    accent = _parse_accent(theme.get("accent"))

    for block in spec["blocks"]:
        typ = block["type"]
        if typ == "heading":
            level_raw = block.get("level")
            level_i = 0 if level_raw == 0 else int(level_raw or 1)
            para = doc.add_heading(block["text"], level=level_i)
            _apply_run_font(para, heading_font or body_font, accent, heading=True)
        elif typ == "para":
            para = doc.add_paragraph(block["text"])
            _apply_run_font(para, body_font, None, heading=False)
        elif typ == "table":
            _add_table(doc, block)
        elif typ == "image":
            blob = _image_bytes(block, images)
            doc.add_picture(io.BytesIO(blob), width=Inches(5))
            alt = str(block.get("alt") or "").strip()
            if alt:
                doc.add_paragraph(alt)
        elif typ == "page_break":
            para = doc.add_paragraph()
            run = para.add_run()
            run.add_break(WD_BREAK.PAGE)
        else:
            # parse_spec already mapped unknown types with text to para.
            continue

    if heading_font or body_font:
        _set_doc_default_font(doc, body_font or heading_font, qn, Pt)

    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def _render_pptx(spec: dict[str, Any], images: dict[str, bytes]) -> bytes:
    from pptx import Presentation
    from pptx.util import Inches, Pt

    deck = Presentation()
    layout = deck.slide_layouts[1] if len(deck.slide_layouts) > 1 else deck.slide_layouts[0]
    theme = spec.get("theme") or {}
    heading_font = str(theme.get("heading_font") or "").strip()
    body_font = str(theme.get("body_font") or "").strip()
    accent = _parse_accent(theme.get("accent"))

    for block in spec["blocks"]:
        if block.get("type") != "slide":
            continue
        slide = deck.slides.add_slide(layout)
        title_shape = getattr(slide.shapes, "title", None)
        if title_shape is not None and getattr(title_shape, "has_text_frame", False):
            title_shape.text = block["title"]
            if heading_font:
                _set_shape_font(title_shape, heading_font, Pt, accent)
        bullets = [str(b) for b in (block.get("bullets") or []) if str(b).strip()]
        body_shape = _body_placeholder(slide, title_shape)
        if body_shape is not None and getattr(body_shape, "has_text_frame", False):
            frame = body_shape.text_frame
            frame.clear()
            if bullets:
                frame.paragraphs[0].text = bullets[0]
                for extra in bullets[1:]:
                    p = frame.add_paragraph()
                    p.text = extra
                    p.level = 0
            if body_font:
                _set_shape_font(body_shape, body_font, Pt, None)
        image = block.get("image")
        if image:
            blob = _image_bytes(image, images)
            slide.shapes.add_picture(io.BytesIO(blob), Inches(1), Inches(3.6), width=Inches(5.5))
        notes = block.get("notes")
        notes_slide = getattr(slide, "notes_slide", None)
        if notes and notes_slide is not None:
            frame = getattr(notes_slide, "notes_text_frame", None)
            if frame is not None:
                frame.text = str(notes)

    buf = io.BytesIO()
    deck.save(buf)
    return buf.getvalue()


def _add_table(doc: object, block: dict[str, Any]) -> None:
    headers = [str(h) for h in (block.get("headers") or [])]
    rows = [[str(c) for c in r] for r in (block.get("rows") or [])]
    width = len(headers) if headers else (max((len(r) for r in rows), default=1))
    n_header = 1 if headers else 0
    table = doc.add_table(rows=n_header + len(rows), cols=max(1, width))
    styles = getattr(doc, "styles", None)
    if styles is not None and "Table Grid" in [getattr(s, "name", "") for s in styles]:
        table.style = "Table Grid"
    if headers:
        for i, cell in enumerate(headers):
            table.rows[0].cells[i].text = cell
        data_start = 1
    else:
        data_start = 0
    for r_i, row in enumerate(rows):
        for c_i in range(width):
            value = row[c_i] if c_i < len(row) else ""
            table.rows[data_start + r_i].cells[c_i].text = value
    caption = str(block.get("caption") or "").strip()
    if caption:
        doc.add_paragraph(caption)


def _image_bytes(ref: dict[str, Any], images: dict[str, bytes]) -> bytes:
    aid = str(ref.get("artifact_id") or "").strip()
    if aid and aid in images:
        blob = images[aid]
        if blob:
            return blob
    b64 = str(ref.get("bytes_b64") or "").strip()
    if b64:
        try:
            return base64.b64decode(b64.encode("ascii"), validate=False)
        except (ValueError, TypeError) as exc:
            raise SpecError("image bytes_b64 无法解码。") from exc
    if aid:
        raise SpecError(f"找不到图 artifact_id={aid}。请先 generate_image。")
    raise SpecError("image 没有可用字节。")


def _body_placeholder(slide: object, title_shape: object) -> object | None:
    placeholders = getattr(slide, "placeholders", None)
    if placeholders is not None:
        for shape in placeholders:
            idx = getattr(getattr(shape, "placeholder_format", None), "idx", None)
            if idx == 1 and getattr(shape, "has_text_frame", False):
                return shape
    for shape in getattr(slide, "shapes", []):
        if shape is title_shape:
            continue
        if getattr(shape, "has_text_frame", False):
            return shape
    return None


def _apply_run_font(para: object, font_name: str, accent: tuple[int, int, int] | None, *, heading: bool) -> None:
    if not font_name and not accent:
        return
    from docx.oxml.ns import qn
    from docx.shared import RGBColor

    for run in getattr(para, "runs", []) or []:
        font = getattr(run, "font", None)
        if font is None:
            continue
        if font_name:
            font.name = font_name
            rpr = getattr(getattr(run, "_element", None), "get_or_add_rPr", None)
            if callable(rpr):
                fonts = rpr().get_or_add_rFonts()
                fonts.set(qn("w:eastAsia"), font_name)
        if heading and accent:
            font.color.rgb = RGBColor(*accent)


def _set_doc_default_font(doc: object, font_name: str, qn: Any, pt: Any) -> None:
    styles = getattr(doc, "styles", None)
    if styles is None or "Normal" not in [getattr(s, "name", "") for s in styles]:
        return
    style = styles["Normal"]
    style.font.name = font_name
    style.font.size = pt(12)
    rpr = style.element.get_or_add_rPr()
    rfonts = rpr.get_or_add_rFonts()
    rfonts.set(qn("w:eastAsia"), font_name)


def _set_shape_font(shape: object, font_name: str, pt: Any, accent: tuple[int, int, int] | None) -> None:
    from pptx.dml.color import RGBColor
    from pptx.util import Pt as PptPt

    frame = getattr(shape, "text_frame", None)
    if frame is None:
        return
    for para in frame.paragraphs:
        for run in para.runs:
            run.font.name = font_name
            run.font.size = PptPt(18) if accent else PptPt(16)
            if accent:
                run.font.color.rgb = RGBColor(*accent)


def _parse_accent(raw: Any) -> tuple[int, int, int] | None:
    if not isinstance(raw, str) or not raw.strip():
        return None
    text = raw.strip().lstrip("#")
    if len(text) != 6:
        return None
    try:
        return int(text[0:2], 16), int(text[2:4], 16), int(text[4:6], 16)
    except ValueError:
        return None
