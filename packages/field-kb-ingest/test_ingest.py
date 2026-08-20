from ingest import classify_convert_error, pdf_ocr_settings, slices_from_markdown


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
    assert out.get("code") in {"ocr_missing", "hf_offline", "empty", "ingest.failed"}


def test_pdf_ocr_settings_full_page():
    flags = pdf_ocr_settings()
    assert flags["do_ocr"] is True
    assert flags["force_full_page_ocr"] is True
    assert flags["engine"] == "rapidocr"
    assert flags["artifacts_path"]


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

    monkeypatch.setattr(mod, "_convert_path", lambda path: "")
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
    monkeypatch.setattr(mod, "_convert_path", lambda path: title)
    out = mod.ingest_bytes(filename=title, data=b"%PDF-1.3 x", title=title)
    assert out["ok"] is False
    assert out["code"] == "empty"
    assert out["slices"] == []
