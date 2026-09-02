"""T-KB-CATCH: pdf/docx extract-for-kb copies text into the ledger path."""

from __future__ import annotations

from app.edu_files import extract_for_kb


def test_extract_for_kb_pdf_uses_field_ingest(monkeypatch) -> None:
    from app import edu_files as mod

    monkeypatch.setattr(mod, "parse_office_bytes", lambda **_k: "寒假从一月二十日开始。通知全体家长。")
    out = extract_for_kb("家长通知.pdf", b"%PDF-1.4 fake")
    assert out["status"] == "ok"
    assert out["kind"] == "pdf"
    assert "一月二十日" in out["text"]
    assert out["text"] != "家长通知.pdf"


def test_extract_for_kb_pdf_unread_when_empty(monkeypatch) -> None:
    from app import edu_files as mod

    monkeypatch.setattr(mod, "parse_office_bytes", lambda **_k: "")
    monkeypatch.setattr(mod, "render_pdf_page_pngs", lambda *_a, **_k: [])
    out = extract_for_kb("空.pdf", b"%PDF-1.4")
    assert out["status"] == "unread"
    assert out["text"] == ""
    assert not out.get("page_pngs")
    assert not out.get("error")


def test_extract_for_kb_scan_pdf_attaches_page_pngs(monkeypatch) -> None:
    from app import edu_files as mod

    png = (
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
        b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01"
        b"\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
    )
    monkeypatch.setattr(mod, "parse_office_bytes", lambda **_k: "")
    monkeypatch.setattr(mod, "render_pdf_page_pngs", lambda *_a, **_k: [png])
    out = extract_for_kb("地理答案.pdf", b"%PDF-1.4 scan")
    assert out["status"] == "unread"
    assert out["text"] == ""
    assert out.get("page_count") == 1
    assert out["page_pngs"][0].startswith(b"\x89PNG")
    assert not out.get("error")
    assert "没抽出" not in str(out.get("headline") or "")
    assert "读不了" not in str(out.get("error") or "")


def test_extract_for_kb_docx_falls_back_when_ingest_empty(monkeypatch) -> None:
    from app import edu_files as mod

    monkeypatch.setattr(mod, "parse_office_bytes", lambda **_k: "")
    monkeypatch.setattr(
        mod,
        "extract_office",
        lambda _n, _d: {
            "filename": "三段.docx",
            "kind": "docx",
            "status": "ok",
            "headline": "第一段",
            "rows": None,
            "cols": None,
            "sheets": [],
            "text": "第一段\n第二段\n第三段",
            "error": None,
        },
    )
    out = extract_for_kb("三段.docx", b"PK\x03\x04fake")
    assert out["status"] == "ok"
    assert "第一段" in out["text"]


def test_extract_for_kb_md_still_office_extract() -> None:
    out = extract_for_kb("校历.md", "春季学期三月开学。".encode())
    assert out["status"] == "ok"
    assert "三月" in (out.get("text") or "")


def test_extract_for_kb_txt_xlsx_via_office_extract(monkeypatch) -> None:
    from app import edu_files as mod

    monkeypatch.setattr(
        mod,
        "extract_office",
        lambda name, _d: {
            "filename": name,
            "kind": name.rsplit(".", 1)[-1],
            "status": "ok",
            "headline": "抽出",
            "rows": 1,
            "cols": 1,
            "sheets": [],
            "text": f"正文来自{name}",
            "error": None,
        },
    )
    txt = extract_for_kb("备忘.txt", b"hello")
    assert txt["status"] == "ok"
    assert "备忘.txt" in (txt.get("text") or "")
    xlsx = extract_for_kb("课时.xlsx", b"PK")
    assert xlsx["status"] == "ok"
    assert "课时.xlsx" in (xlsx.get("text") or "")
    pptx = extract_for_kb("封面.pptx", b"PK")
    assert pptx["status"] == "ok"
    assert "封面.pptx" in (pptx.get("text") or "")


def test_extract_for_kb_pdf_unread_when_docling_missing(monkeypatch) -> None:
    from app import edu_files as mod

    monkeypatch.setattr(mod, "parse_office_bytes", lambda **_k: "")
    monkeypatch.setattr(
        mod,
        "extract_office",
        lambda _n, _d: {
            "filename": "空.pdf",
            "kind": "pdf",
            "status": "unsupported",
            "headline": "抽不出",
            "rows": None,
            "cols": None,
            "sheets": [],
            "text": "",
            "error": "这种格式抽不出正文",
        },
    )
    monkeypatch.setattr(mod, "render_pdf_page_pngs", lambda *_a, **_k: [])
    out = extract_for_kb("空.pdf", b"%PDF-1.4")
    assert out["status"] == "unread"
    assert out["text"] == ""
    assert not out.get("error")
