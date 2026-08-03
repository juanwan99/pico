from __future__ import annotations

import io
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "orchestrator"))

from pico_orchestrator.document_generators import (
    build_docx_document,
    build_html_document,
    build_pptx_document,
)


def test_html_contains_marker_and_csp() -> None:
    marker = "P270_HTML_MARK"
    raw = build_html_document(title="demo.html", marker=marker, body="hello")
    text = raw.decode("utf-8")
    assert marker in text
    assert "Content-Security-Policy" in text
    assert "<script" not in text.lower()
    assert "http://evil" not in text


def test_docx_is_real_ooxml_zip() -> None:
    marker = "P270_DOCX_MARK"
    raw = build_docx_document(title="lesson.docx", marker=marker, body="body")
    assert raw[:2] == b"PK"
    with zipfile.ZipFile(io.BytesIO(raw)) as zf:
        names = set(zf.namelist())
        assert "[Content_Types].xml" in names
        assert "word/document.xml" in names
        doc = zf.read("word/document.xml").decode("utf-8")
        assert marker in doc


def test_pptx_is_real_ooxml_with_slide() -> None:
    marker = "P270_PPTX_MARK"
    raw = build_pptx_document(title="slides.pptx", marker=marker, body="slide body")
    assert raw[:2] == b"PK"
    with zipfile.ZipFile(io.BytesIO(raw)) as zf:
        names = set(zf.namelist())
        assert "[Content_Types].xml" in names
        assert "ppt/presentation.xml" in names
        assert "ppt/slides/slide1.xml" in names
        slide = zf.read("ppt/slides/slide1.xml").decode("utf-8")
        assert marker in slide
