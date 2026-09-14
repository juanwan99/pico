from pathlib import Path

from ingest import (
    classify_convert_error,
    pdf_ocr_settings,
    rapidocr_onnx_paths,
    slices_from_markdown,
)


def test_slices_headers_and_paragraphs():
    rows = slices_from_markdown("# 班\n语文,5\n\n说明一段", "课时表")
    assert rows
    assert rows[0]["title"] == "课时表"
    blob = " ".join(r["excerpt"] for r in rows)
    assert "班" in blob or "语文" in blob or "说明" in blob
    assert all(r["excerpt"] for r in rows)


def test_empty_falls_back_to_title():
    rows = slices_from_markdown("  ", "只有名")
    assert rows[0]["excerpt"] == "只有名"


def test_ingest_bytes_unread_without_docling_or_empty():
    from ingest import ingest_bytes

    out = ingest_bytes(filename="x.bin", data=b"not-a-document", title="x.bin")
    assert out["ok"] is False
    assert out.get("unread") is True
    assert out.get("slices") == []
    assert out.get("code") == "unsupported_format"
    assert "读不了" in out["error"]
    assert "docx" in out["error"]


def test_legacy_ole_suffix_is_unsupported_with_hint():
    from ingest import ingest_bytes

    out = ingest_bytes(filename="老教案.doc", data=b"\xd0\xcf\x11\xe0", title="老教案")
    assert out["code"] == "unsupported_format"
    assert ".docx" in out["error"]


def test_office_backend_dispatch_never_imports_document_converter(monkeypatch):
    """Live 2026-09-14 (#997): docling.document_converter import pulls docling_parse,
    which the no-torch image lacks; every Office ingest died there."""
    import sys

    import ingest as mod

    seen = {}

    class FakeInputFormat:
        DOCX = "DOCX"
        XLSX = "XLSX"
        PPTX = "PPTX"
        MD = "MD"
        HTML = "HTML"

        def __class_getitem__(cls, item):
            return getattr(cls, item)

    class FakeDoc:
        def export_to_markdown(self):
            return "## 课时\n\n语文 数学"

    class FakeBackend:
        def __init__(self, in_doc, path):
            seen["backend_path"] = path

        def convert(self):
            return FakeDoc()

    class FakeInputDocument:
        def __init__(self, **kw):
            seen["fmt"] = kw.get("format")

    import types

    pkg = types.ModuleType("docling")
    dm = types.ModuleType("docling.datamodel")
    bm = types.ModuleType("docling.datamodel.base_models")
    bm.InputFormat = FakeInputFormat
    dd = types.ModuleType("docling.datamodel.document")
    dd.InputDocument = FakeInputDocument
    be = types.ModuleType("docling.backend")
    word = types.ModuleType("docling.backend.msword_backend")
    word.MsWordDocumentBackend = FakeBackend
    dc = types.ModuleType("docling.document_converter")

    def boom(*_a, **_k):
        raise AssertionError("DocumentConverter must not be touched")

    dc.DocumentConverter = boom
    for name, m in {
        "docling": pkg,
        "docling.datamodel": dm,
        "docling.datamodel.base_models": bm,
        "docling.datamodel.document": dd,
        "docling.backend": be,
        "docling.backend.msword_backend": word,
        "docling.document_converter": dc,
    }.items():
        monkeypatch.setitem(sys.modules, name, m)

    out = mod.ingest_bytes(filename="课时表.docx", data=b"PK\x03\x04", title="课时表")
    assert out["ok"] is True
    assert out["engine"] == "docling"
    assert seen["fmt"] == "DOCX"
    assert "语文" in " ".join(s["excerpt"] for s in out["slices"])


def test_image_suffix_goes_to_ocr(monkeypatch):
    import ingest as mod

    monkeypatch.setattr(mod, "_ocr_image", lambda path: "板书：细胞膜")
    monkeypatch.setattr(mod, "_convert_path", lambda path: (_ for _ in ()).throw(AssertionError("no docling")))
    out = mod.ingest_bytes(filename="板书.png", data=b"\x89PNG", title="板书")
    assert out["ok"] is True
    assert out["engine"] == "rapidocr"
    assert "ocr" in out["tags"]
    assert "细胞膜" in out["slices"][0]["excerpt"]


def test_blank_image_is_empty_with_ocr_copy(monkeypatch):
    import ingest as mod

    monkeypatch.setattr(mod, "_ocr_image", lambda path: "")
    out = mod.ingest_bytes(filename="空白.jpg", data=b"\xff\xd8", title="空白")
    assert out["ok"] is False
    assert out["code"] == "empty"
    assert "OCR" in out["error"]


def test_bundled_rapidocr_paths_from_wheel(monkeypatch, tmp_path):
    import sys
    import types

    import ingest as mod

    models = tmp_path / "rapidocr" / "models"
    models.mkdir(parents=True)
    for n in ("PP-OCRv6_det_small.onnx", "PP-OCRv6_rec_small.onnx", "ch_ppocr_mobile_v2.0_cls_mobile.onnx"):
        (models / n).write_bytes(b"onnx")
    fake = types.ModuleType("rapidocr")
    fake.__file__ = str(tmp_path / "rapidocr" / "__init__.py")
    monkeypatch.setitem(sys.modules, "rapidocr", fake)
    monkeypatch.setenv("DOCLING_ARTIFACTS_PATH", str(tmp_path / "empty-artifacts"))
    got = mod.resolve_rapidocr_onnx()
    assert set(got) == {"det", "rec", "cls"}
    assert got["det"].endswith("PP-OCRv6_det_small.onnx")


def test_ocr_max_pages_env(monkeypatch):
    import ingest as mod

    monkeypatch.delenv("PICO_KB_OCR_MAX_PAGES", raising=False)
    assert mod.ocr_max_pages() == mod.DEFAULT_OCR_MAX_PAGES
    monkeypatch.setenv("PICO_KB_OCR_MAX_PAGES", "5")
    assert mod.ocr_max_pages() == 5
    monkeypatch.setenv("PICO_KB_OCR_MAX_PAGES", "junk")
    assert mod.ocr_max_pages() == mod.DEFAULT_OCR_MAX_PAGES


def test_pdf_ocr_settings_full_page():
    flags = pdf_ocr_settings()
    assert flags["do_ocr"] is True
    assert flags["force_full_page_ocr"] is True
    assert flags["engine"] == "rapidocr"
    assert flags["renderer"] == "pypdfium2"
    assert flags["artifacts_path"]


def test_rapidocr_onnx_paths_absent(tmp_path, monkeypatch):
    monkeypatch.setenv("DOCLING_ARTIFACTS_PATH", str(tmp_path))
    assert rapidocr_onnx_paths() == {}


def test_classify_ocr_and_hf():
    assert classify_convert_error(RuntimeError("No OCR engine found")) == "ocr_missing"
    assert classify_convert_error(ImportError("libxcb.so.1: cannot open shared object")) == (
        "ocr_missing"
    )
    assert (
        classify_convert_error(RuntimeError("LocalEntryNotFoundError snapshot_download Hub"))
        == "hf_offline"
    )
    assert classify_convert_error(OSError("Network is unreachable huggingface")) == "hf_offline"


def test_ingest_bytes_empty_md_does_not_use_filename(monkeypatch):
    import ingest as mod

    monkeypatch.setattr(mod, "_pdf_text_layer", lambda path: "")
    monkeypatch.setattr(mod, "_ocr_pdf_pages", lambda path: "")
    out = mod.ingest_bytes(
        filename="通知.pdf",
        data=b"%PDF-1.3 fake",
        title="关于组织开展株洲市中小学教师人工智能素养市级培训的通知(1).pdf",
    )
    assert out["ok"] is False
    assert out["unread"] is True
    assert out["code"] == "empty"
    assert out["slices"] == []
    joined = " ".join(s.get("excerpt") or "" for s in out["slices"])
    assert "通知" not in joined


def test_ingest_bytes_title_only_markdown_is_unread(monkeypatch):
    import ingest as mod

    title = "通知.pdf"
    monkeypatch.setattr(mod, "_pdf_text_layer", lambda path: "")
    monkeypatch.setattr(mod, "_ocr_pdf_pages", lambda path: title)
    out = mod.ingest_bytes(filename=title, data=b"%PDF-1.3 x", title=title)
    assert out["ok"] is False
    assert out["code"] == "empty"
    assert out["slices"] == []


def test_pdf_empty_layer_falls_back_to_ocr(monkeypatch):
    """#994 S2 (owner 2026-09-14): scan PDF = empty text layer → RapidOCR page render.
    Supersedes the §29 「empty layer does not OCR」 contract."""
    import ingest as mod

    called = {"ocr": 0, "docling": 0, "layer": 0}

    def fake_ocr(path):
        called["ocr"] += 1
        return "人工智能素养\n\n送教培训"

    def fake_docling(path):
        called["docling"] += 1
        return "SHOULD_NOT"

    def fake_layer(path):
        called["layer"] += 1
        return ""

    monkeypatch.setattr(mod, "_pdf_text_layer", fake_layer)
    monkeypatch.setattr(mod, "_ocr_pdf_pages", fake_ocr)
    monkeypatch.setattr(mod, "_convert_path", fake_docling)
    monkeypatch.setattr(mod, "_pdf_page_count", lambda path: 1)
    out = mod.ingest_bytes(filename="scan.pdf", data=b"%PDF-1.3 x", title="通知")
    assert called == {"ocr": 1, "docling": 0, "layer": 1}
    assert out["ok"] is True
    assert out["engine"] == "rapidocr"
    assert {"pdfium", "empty-layer", "ocr"} <= set(out["tags"])
    assert "ocr-truncated" not in out["tags"]
    assert "送教培训" in " ".join(s["excerpt"] for s in out["slices"])


def test_ocr_false_never_renders_pages(monkeypatch):
    """Live 2026-09-14: deploy-time reindex-all OCR'd every stored scan → 400% CPU,
    event loop blocked. Projection/rebuild must pass ocr=False and get a fast miss."""
    import ingest as mod

    monkeypatch.setattr(mod, "_pdf_text_layer", lambda path: "")
    monkeypatch.setattr(mod, "_ocr_pdf_pages", lambda path: (_ for _ in ()).throw(AssertionError("OCR ran")))
    monkeypatch.setattr(mod, "_ocr_image", lambda path: (_ for _ in ()).throw(AssertionError("OCR ran")))
    scan = mod.ingest_bytes(filename="scan.pdf", data=b"%PDF-1.3 x", title="通知", ocr=False)
    assert scan["ok"] is False and scan["code"] == "empty"
    img = mod.ingest_bytes(filename="板书.png", data=b"\x89PNG", title="板书", ocr=False)
    assert img["ok"] is False and img["code"] == "empty"


def test_ocr_threads_env(monkeypatch):
    import ingest as mod

    monkeypatch.delenv("PICO_KB_OCR_THREADS", raising=False)
    assert mod.ocr_threads() == 2
    monkeypatch.setenv("PICO_KB_OCR_THREADS", "1")
    assert mod.ocr_threads() == 1


def test_pdf_ocr_truncation_is_tagged(monkeypatch):
    import ingest as mod

    monkeypatch.setattr(mod, "_pdf_text_layer", lambda path: "")
    monkeypatch.setattr(mod, "_ocr_pdf_pages", lambda path: "第一页")
    monkeypatch.setattr(mod, "_pdf_page_count", lambda path: 500)
    monkeypatch.setenv("PICO_KB_OCR_MAX_PAGES", "40")
    out = mod.ingest_bytes(filename="厚.pdf", data=b"%PDF-1.3 x", title="厚")
    assert out["ok"] is True
    assert "ocr-truncated" in out["tags"]


def test_pdf_ocr_empty_is_honest(monkeypatch):
    import ingest as mod

    monkeypatch.setattr(mod, "_pdf_text_layer", lambda path: "")
    monkeypatch.setattr(mod, "_ocr_pdf_pages", lambda path: "")
    monkeypatch.setattr(mod, "_pdf_page_count", lambda path: 1)
    out = mod.ingest_bytes(filename="scan.pdf", data=b"%PDF-1.3 x", title="通知")
    assert out["ok"] is False
    assert out["code"] == "empty"
    assert "OCR" in out["error"]
    assert out["slices"] == []


def test_pdf_text_layer_skips_ocr(monkeypatch):
    import ingest as mod

    called = {"ocr": 0}

    monkeypatch.setattr(mod, "_pdf_text_layer", lambda path: "TOKEN HELLO PDF BODY")
    monkeypatch.setattr(
        mod, "_ocr_pdf_pages", lambda path: called.__setitem__("ocr", 1) or "OCR-HIT"
    )
    out = mod.ingest_bytes(filename="notice.pdf", data=b"%PDF-1.3 x", title="notice.pdf")
    assert called["ocr"] == 0
    assert out["ok"] is True
    assert out["engine"] == "pdfium-text"
    blob = " ".join(s["excerpt"] for s in out["slices"])
    assert "HELLO PDF BODY" in blob
    assert "OCR-HIT" not in blob
    assert all("pdfium" in (s.get("tags") or []) for s in out["slices"])


def test_pdf_text_layer_fixture_without_ocr(monkeypatch):
    import pytest

    pytest.importorskip("pypdfium2")
    import ingest as mod

    fixture = Path(__file__).resolve().parent / "fixtures" / "text-layer.pdf"
    raw = fixture.read_bytes()
    monkeypatch.setattr(
        mod, "_ocr_pdf_pages", lambda path: (_ for _ in ()).throw(RuntimeError("OCR must not run"))
    )
    out = mod.ingest_bytes(filename="text-layer.pdf", data=raw, title="text-layer.pdf")
    assert out["ok"] is True
    assert out["engine"] == "pdfium-text"
    blob = " ".join(s["excerpt"] for s in out["slices"])
    assert "PICO857-LANTERN-ORANGE-20260902" in blob
    assert "PDF body" in blob


def test_office_still_docling(monkeypatch):
    import ingest as mod

    called = {"ocr": 0, "docling": 0}
    monkeypatch.setattr(mod, "_ocr_pdf_pages", lambda path: called.__setitem__("ocr", 1) or "SHOULD_NOT")
    monkeypatch.setattr(mod, "_convert_path", lambda path: called.__setitem__("docling", 1) or "课时 语文")
    out = mod.ingest_bytes(filename="课时表.docx", data=b"PK\x03\x04", title="课时表")
    assert called == {"ocr": 0, "docling": 1}
    assert out["ok"] is True
    assert out["engine"] == "docling"
    assert "语文" in out["slices"][0]["excerpt"]


def test_rapidocr_no_text_sentinel_is_empty():
    """Live 2026-09-14: blank PNG → 200 with「没有检测到任何文本。」as the slice."""
    import ingest as mod

    class NoTxts:
        txts = None

        def to_markdown(self):
            return "没有检测到任何文本。"

    class Legacy:
        def to_markdown(self):
            return "没有检测到任何文本。"

    class Hit:
        txts = ("胰岛素", "", "血糖")

    assert mod._rapidocr_text(NoTxts()) == ""
    assert mod._rapidocr_text(Legacy()) == ""
    assert mod._rapidocr_text(Hit()) == "胰岛素\n血糖"
    assert mod._rapidocr_text(None) == ""
