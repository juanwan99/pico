from __future__ import annotations

import importlib.util
import io
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
_PATH = (
    ROOT
    / "services"
    / "orchestrator"
    / "pico_orchestrator"
    / "document_generators.py"
)
_SPEC = importlib.util.spec_from_file_location("document_generators", _PATH)
_mod = importlib.util.module_from_spec(_SPEC)
assert _SPEC.loader is not None
_SPEC.loader.exec_module(_mod)
build_docx_document = _mod.build_docx_document
build_html_document = _mod.build_html_document
build_pptx_document = _mod.build_pptx_document


def test_html_contains_marker_and_csp() -> None:
    marker = "P270_HTML_MARK"
    raw = build_html_document(title="demo.html", marker=marker, body="hello")
    text = raw.decode("utf-8")
    assert marker in text
    assert "Content-Security-Policy" in text
    assert "<script" not in text.lower()
    assert "http://evil" not in text


def test_html_multi_paragraph_body_for_courseware() -> None:
    marker = "MENDEL_HTML_MARK"
    body = "分离定律：一对相对性状。\n\n自由组合：两对独立遗传。"
    raw = build_html_document(title="mendel.html", marker=marker, body=body)
    text = raw.decode("utf-8")
    assert text.count("<p>") >= 3  # marker line + 2 body paragraphs
    assert "分离定律" in text
    assert "自由组合" in text
    assert "<script" not in text.lower()


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
