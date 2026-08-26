"""spec → legal OOXML bytes via python-docx / python-pptx."""

from __future__ import annotations

import io

from pico_orchestrator.office.qa import verify_office_bytes
from pico_orchestrator.office.spec import OfficeSpec, Theme


def render_spec(spec: OfficeSpec, *, images: dict[str, bytes] | None = None) -> bytes:
    pictures = images or {}
    if spec.kind == "docx":
        raw = _render_docx(spec, pictures)
        check = verify_office_bytes(raw, ".docx")
        if not check["ok"]:
            raise ValueError(str(check.get("error") or "Word 渲染失败。"))
        return raw
    raw = _render_pptx(spec, pictures)
    check = verify_office_bytes(raw, ".pptx")
    if not check["ok"]:
        raise ValueError(str(check.get("error") or "PPT 渲染失败。"))
    return raw


def _render_docx(spec: OfficeSpec, images: dict[str, bytes]) -> bytes:
    from docx import Document
    from docx.oxml.ns import qn
    from docx.shared import Inches
    from docx.shared import RGBColor as DocxRGB

    doc = Document()
    _apply_docx_theme(doc, spec.theme)
    for block in spec.blocks:
        if block.type == "heading":
            level = 0 if block.level <= 0 else min(block.level, 4)
            doc.add_heading(block.text, level=level)
        elif block.type == "para":
            doc.add_paragraph(block.text)
        elif block.type == "table":
            table = doc.add_table(rows=len(block.rows), cols=len(block.rows[0]))
            table.style = "Table Grid"
            for r_i, row in enumerate(block.rows):
                for c_i, cell in enumerate(row):
                    table.rows[r_i].cells[c_i].text = cell
        elif block.type == "image":
            raw = _need_image(images, block.artifact_id)
            doc.add_picture(io.BytesIO(raw), width=Inches(4.5))
            if block.text:
                doc.add_paragraph(block.text)
        elif block.type == "page_break":
            doc.add_page_break()
    if spec.theme and spec.theme.accent:
        color = _rgb(spec.theme.accent)
        if color is not None:
            for para in doc.paragraphs:
                style = str(getattr(getattr(para, "style", None), "name", "") or "")
                if style.lower().startswith("heading"):
                    for run in para.runs:
                        run.font.color.rgb = DocxRGB(*color)
    if spec.theme and spec.theme.heading_font:
        for para in doc.paragraphs:
            style = str(getattr(getattr(para, "style", None), "name", "") or "")
            if style.lower().startswith("heading"):
                for run in para.runs:
                    run.font.name = spec.theme.heading_font
                    run._element.rPr.rFonts.set(qn("w:eastAsia"), spec.theme.heading_font)
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def _render_pptx(spec: OfficeSpec, images: dict[str, bytes]) -> bytes:
    from pptx import Presentation
    from pptx.dml.color import RGBColor
    from pptx.util import Inches, Pt

    deck = Presentation()
    layout = deck.slide_layouts[1] if len(deck.slide_layouts) > 1 else deck.slide_layouts[0]
    accent = _rgb(spec.theme.accent) if spec.theme else None
    body_font = spec.theme.body_font if spec.theme else None
    heading_font = spec.theme.heading_font if spec.theme else None
    for block in spec.blocks:
        if block.type != "slide":
            continue
        slide = deck.slides.add_slide(layout)
        title_shape = getattr(slide.shapes, "title", None)
        if title_shape is not None and getattr(title_shape, "has_text_frame", False):
            title_shape.text = block.title
            if heading_font or accent:
                for para in title_shape.text_frame.paragraphs:
                    for run in para.runs:
                        if heading_font:
                            run.font.name = heading_font
                            run.font.size = Pt(28)
                        if accent:
                            run.font.color.rgb = RGBColor(*accent)
        body = "\n".join(block.bullets)
        _set_pptx_body(slide, body, font_name=body_font)
        if block.image_artifact_id:
            raw = _need_image(images, block.image_artifact_id)
            slide.shapes.add_picture(io.BytesIO(raw), Inches(6.2), Inches(1.6), width=Inches(3.2))
    if not deck.slides:
        raise ValueError("PPT spec 没有可渲染的 slide。")
    buf = io.BytesIO()
    deck.save(buf)
    return buf.getvalue()


def _set_pptx_body(slide: object, body: str, *, font_name: str | None) -> None:
    from pptx.util import Pt

    placeholders = getattr(slide, "placeholders", None)
    target = None
    if placeholders is not None:
        for shape in placeholders:
            idx = getattr(getattr(shape, "placeholder_format", None), "idx", None)
            if idx == 1 and getattr(shape, "has_text_frame", False):
                target = shape
                break
    if target is None:
        for shape in getattr(slide, "shapes", []):
            if shape is getattr(getattr(slide, "shapes", None), "title", None):
                continue
            if getattr(shape, "has_text_frame", False):
                target = shape
                break
    if target is None:
        return
    target.text = body
    if font_name:
        for para in target.text_frame.paragraphs:
            for run in para.runs:
                run.font.name = font_name
                run.font.size = Pt(18)


def _apply_docx_theme(doc: object, theme: Theme | None) -> None:
    if theme is None or not theme.body_font:
        return
    from docx.oxml.ns import qn
    from docx.shared import Pt

    style = doc.styles["Normal"]
    style.font.name = theme.body_font
    style.font.size = Pt(12)
    style._element.rPr.rFonts.set(qn("w:eastAsia"), theme.body_font)


def _need_image(images: dict[str, bytes], artifact_id: str | None) -> bytes:
    if not artifact_id:
        raise ValueError("图缺少 artifact_id。")
    raw = images.get(artifact_id)
    if not raw:
        raise ValueError(f"找不到图片 {artifact_id}。请先 generate_image。")
    if raw[:8] != b"\x89PNG\r\n\x1a\n" and raw[:2] != b"\xff\xd8":
        raise ValueError("插入的图必须是 png 或 jpg。")
    return raw


def _rgb(value: str | None):
    if not value:
        return None
    text = value.strip().lstrip("#")
    if len(text) != 6:
        return None
    try:
        return tuple(int(text[i : i + 2], 16) for i in (0, 2, 4))
    except ValueError:
        return None
