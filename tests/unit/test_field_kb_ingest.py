from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "packages" / "field-kb-ingest"))

from ingest import (
    classify_convert_error,
    ingest_bytes,
    pdf_ocr_settings,
    slices_from_markdown,
)


def make_image_only_pdf() -> bytes:
    """Minimal PDF with a gray image XObject and no fonts (scan stand-in)."""
    img = b"\x7f" * 64
    stream = img
    parts = [
        b"%PDF-1.3\n",
        b"1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n",
        b"2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n",
        b"3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 72 72]/Resources<</XObject<</Im0 4 0 R>>>>/Contents 5 0 R>>endobj\n",
        (
            b"4 0 obj<</Type/XObject/Subtype/Image/Width 8/Height 8"
            b"/ColorSpace/DeviceGray/BitsPerComponent 8/Length 64>>stream\n"
        ),
        stream,
        b"\nendstream\nendobj\n",
        b"5 0 obj<</Length 44>>stream\n",
        b"q 72 0 0 72 0 0 cm /Im0 Do Q\n",
        b"endstream\nendobj\n",
        b"xref\n0 6\n",
        b"trailer<</Size 6/Root 1 0 R>>\nstartxref\n0\n%%EOF\n",
    ]
    return b"".join(parts)


def test_scan_pdf_fixture_has_no_text_layer():
    raw = make_image_only_pdf()
    assert raw.startswith(b"%PDF")
    assert b"/Font" not in raw
    assert b"/Subtype/Image" in raw or b"/Subtype /Image" in raw


def test_pdf_ocr_settings_full_page():
    flags = pdf_ocr_settings()
    assert flags["do_ocr"] is True
    assert flags["force_full_page_ocr"] is True
    assert flags["engine"] == "rapidocr"


def test_classify_convert_error_codes():
    assert classify_convert_error(RuntimeError("No OCR engine found")) == "ocr_missing"
    assert classify_convert_error(ImportError("libxcb.so.1")) == "ocr_missing"
    assert classify_convert_error(RuntimeError("LocalEntryNotFoundError snapshot_download")) == (
        "hf_offline"
    )


def test_empty_convert_does_not_use_filename(monkeypatch):
    import ingest as mod

    monkeypatch.setattr(mod, "_ocr_pdf_pages", lambda path: "")
    title = "关于组织开展株洲市中小学教师人工智能素养市级培训的通知(1).pdf"
    out = ingest_bytes(filename=title, data=make_image_only_pdf(), title=title)
    assert out["ok"] is False
    assert out["unread"] is True
    assert out["code"] == "empty"
    assert out["slices"] == []


def test_scan_pdf_route_is_page_ocr(monkeypatch):
    import ingest as mod

    monkeypatch.setattr(mod, "_ocr_pdf_pages", lambda path: "生成式AI赋能的教学设计")
    monkeypatch.setattr(mod, "_convert_path", lambda path: "SHOULD_NOT")
    out = ingest_bytes(filename="scan.pdf", data=make_image_only_pdf(), title="通知")
    assert out["ok"] is True
    assert out["engine"] == "rapidocr"
    assert "生成式AI" in out["slices"][0]["excerpt"]


def test_slices_headers_and_paragraphs():
    rows = slices_from_markdown("# 班\n语文,5\n\n说明一段", "课时表")
    blob = " ".join(r["excerpt"] for r in rows)
    assert "班" in blob or "语文" in blob
