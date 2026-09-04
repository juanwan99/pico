"""Content-box HTML projection of Office files (Codex-style page/slide)."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "orchestrator"))

from pico_orchestrator.document_generators import build_docx_document
from pico_orchestrator.office.preview import preview_office_html
from pico_orchestrator.office.render import render_spec
from pico_orchestrator.office.spec import parse_spec

ONE_PNG = (
    b"\x89PNG\r\n\x1a\n"
    b"\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde"
    b"\x00\x00\x00\x0cIDATx\x9cc``\x00\x00\x00\x04\x00\x01\xa3\x0a\x0d\xe4"
    b"\x00\x00\x00\x00IEND\xaeB`\x82"
)


def test_docx_preview_is_page_not_writer_chrome():
    raw = build_docx_document(title="通知", marker="PREVIEW-DOCX-1", body="第一段\n第二段")
    html = preview_office_html(raw, ".docx")
    assert "第一段" in preview_office_html(raw, ".doc")
    assert "class='page'" in html or 'class="page"' in html
    assert "LibreOffice" not in html
    assert "Writer" not in html
    assert "第一段" in html
    assert "<h1>" in html
    assert "<script" not in html.lower()


def test_pptx_preview_is_slide_cards_with_image():
    spec = parse_spec(
        {
            "kind": "pptx",
            "title": "汇报",
            "blocks": [
                {"type": "slide", "title": "封面", "bullets": ["要点一"]},
                {
                    "type": "slide",
                    "title": "配图",
                    "bullets": ["见图"],
                    "image_artifact_id": "img-1",
                },
            ],
        }
    )
    raw = render_spec(spec, images={"img-1": ONE_PNG})
    html = preview_office_html(raw, ".pptx")
    assert "class='slide" in html or 'class="slide' in html
    assert "封面" in html
    assert "data:image/png" in html
    assert "Impress" not in html
    assert "LibreOffice" not in html
    assert html.count("aria-label") >= 2
    assert "deck-card" in html


def test_xlsx_preview_is_page_table():
    spec = parse_spec(
        {
            "kind": "xlsx",
            "title": "成绩",
            "sheets": [{"name": "Sheet1", "rows": [["科目", "分"], ["语文", "90"]]}],
        }
    )
    raw = render_spec(spec)
    html = preview_office_html(raw, ".xlsx")
    assert "class='page'" in html or 'class="page"' in html
    assert "语文" in html
    assert "<script" not in html.lower()


def test_preview_rejects_fake_office():
    import pytest

    with pytest.raises(ValueError):
        preview_office_html(b"not-zip", ".docx")


def test_preview_doc_name_with_ooxml_bytes_renders():
    raw = build_docx_document(title="计划.docx", marker="DOC-NAME", body="春游名单")
    html = preview_office_html(raw, ".doc")
    assert "春游名单" in html
    assert "class='page'" in html or 'class="page"' in html
