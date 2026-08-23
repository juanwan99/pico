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
    out = extract_for_kb("空.pdf", b"%PDF-1.4")
    assert out["status"] == "unread"
    assert out["text"] == ""


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
