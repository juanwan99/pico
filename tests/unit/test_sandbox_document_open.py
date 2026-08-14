import base64
from dataclasses import dataclass

import pytest
from pico_orchestrator.document_generators import build_docx_document
from pico_orchestrator.tools_builtin import build_default_gateway
from sandbox_worker.office import resolve_kind


@dataclass
class P:
    school_id: str
    membership_id: str
    scopes: list[str] | None = None


def test_resolve_kind_from_filename():
    assert resolve_kind("a.docx", "") == "writer"
    assert resolve_kind("a.xlsx", "") == "calc"
    assert resolve_kind("a.pptx", "") == "impress"
    assert resolve_kind("x", "writer") == "writer"


def test_docx_is_real_ooxml_not_html():
    raw = build_docx_document(title="课堂笔记.docx", marker="word-is-word", body="沙箱里的这份 Word 正文")
    assert raw[:2] == b"PK"
    assert b"word/document.xml" in raw
    assert b"PDF" not in raw
    assert b"<html" not in raw


@pytest.mark.asyncio
async def test_document_open_sends_ooxml_not_pdf(monkeypatch):
    captured: dict = {}

    async def fake_sidecar(method, path, **kwargs):
        captured["body"] = kwargs.get("json_body") or {}
        return {
            "ok": True,
            "session_id": "sbox_cccccccccccccccccccccccc",
            "kind": "writer",
            "title": "LibreOffice Writer · 课堂笔记.docx",
            "engine": "libreoffice-writer",
            "human_copy": "沙箱已用 LibreOffice 打开这份文档。",
        }

    monkeypatch.setattr(
        "pico_orchestrator.tools_builtin.sidecar_json",
        fake_sidecar,
    )
    gw = build_default_gateway()
    owner = P(school_id="sch", membership_id="mem")
    out = await gw.invoke(owner, "sandbox_document_open", {"kind": "writer", "filename": "课堂笔记.docx"})
    assert out["session_id"].startswith("sbox_")
    raw = base64.b64decode(captured["body"]["document_base64"])
    assert raw[:2] == b"PK"
    assert captured["body"]["kind"] == "writer"
    assert b"%PDF" not in raw


@pytest.mark.asyncio
async def test_document_open_calc_sends_xlsx_with_known_cell(monkeypatch):
    captured: dict = {}

    async def fake_sidecar(method, path, **kwargs):
        captured["body"] = kwargs.get("json_body") or {}
        return {
            "ok": True,
            "session_id": "sbox_dddddddddddddddddddddddd",
            "kind": "calc",
            "title": "LibreOffice Calc · 课堂成绩.xlsx",
            "engine": "libreoffice-writer",
        }

    monkeypatch.setattr("pico_orchestrator.tools_builtin.sidecar_json", fake_sidecar)
    gw = build_default_gateway()
    owner = P(school_id="sch", membership_id="mem")
    out = await gw.invoke(
        owner,
        "sandbox_document_open",
        {"kind": "calc", "filename": "课堂成绩.xlsx", "body": "NIGHT-P4-CELL-ALPHA"},
    )
    assert out["session_id"].startswith("sbox_")
    raw = base64.b64decode(captured["body"]["document_base64"])
    assert raw[:2] == b"PK"
    assert captured["body"]["kind"] == "calc"
    import zipfile
    import io

    with zipfile.ZipFile(io.BytesIO(raw)) as zf:
        sheet = zf.read("xl/worksheets/sheet1.xml")
        assert b"NIGHT-P4-CELL-ALPHA" in sheet
    assert b"%PDF" not in raw
