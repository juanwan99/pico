import base64
import io
import zipfile
from dataclasses import dataclass
from typing import Any

import pytest
from pico_orchestrator.document_generators import build_docx_document
from pico_orchestrator.sandbox_persist import write_owner_disk_file
from pico_orchestrator.tools_builtin import OFFICE_CONTENT_BOX_COPY, build_default_gateway
from sandbox_worker.office import resolve_kind


@dataclass
class P:
    school_id: str
    membership_id: str
    scopes: list[str] | None = None


class MemoryArtifactStore:
    def __init__(self) -> None:
        self.rows: list[dict[str, Any]] = []
        self.blobs: dict[str, bytes] = {}

    async def write(
        self,
        principal: P,
        *,
        title: str,
        content: str | bytes,
        kind: str,
    ) -> dict[str, Any]:
        del principal
        raw = content if isinstance(content, bytes) else content.encode("utf-8")
        row = {
            "artifact_id": f"art-{len(self.rows) + 1}",
            "title": title,
            "kind": kind,
            "byte_size": len(raw),
            "content_encoding": "base64",
        }
        self.rows.append(row)
        self.blobs[row["artifact_id"]] = raw
        return dict(row)

    async def read(
        self,
        principal: P,
        *,
        artifact_id: str | None = None,
        title: str | None = None,
    ) -> dict[str, Any] | None:
        del principal
        for row in self.rows:
            if artifact_id and row["artifact_id"] == artifact_id:
                out = dict(row)
                out["content_base64"] = base64.b64encode(self.blobs[row["artifact_id"]]).decode(
                    "ascii"
                )
                return out
            if title and row["title"] == title:
                out = dict(row)
                out["content_base64"] = base64.b64encode(self.blobs[row["artifact_id"]]).decode(
                    "ascii"
                )
                return out
        return None

    async def list(self, principal: P, *, limit: int) -> list[dict[str, Any]]:
        del principal, limit
        return list(self.rows)


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
async def test_document_open_is_content_box_not_libreoffice(monkeypatch):
    async def fake_sidecar(method, path, **kwargs):
        raise AssertionError(f"office content-box must not call sidecar {method} {path}")

    monkeypatch.setattr("pico_orchestrator.tools_builtin.sidecar_json", fake_sidecar)
    store = MemoryArtifactStore()
    gw = build_default_gateway(store)
    owner = P(school_id="sch", membership_id="mem")
    out = await gw.invoke(
        owner,
        "sandbox_document_open",
        {
            "kind": "writer",
            "filename": "notes.docx",
            "body": "沙箱里的这份 Word 正文。打开 = 内容框，不是 Writer 整窗。",
        },
    )
    assert out["view"] == "content-box"
    assert out["artifact_id"] == "art-1"
    assert out["engine"] == "office-content-box"
    assert "session_id" not in out
    assert OFFICE_CONTENT_BOX_COPY in out["human_copy"]
    assert "LibreOffice" not in out["human_copy"]
    assert out["observation"]["saw_screen"] is False
    raw = store.blobs["art-1"]
    assert raw[:2] == b"PK"
    assert b"%PDF" not in raw


@pytest.mark.asyncio
async def test_document_open_calc_writes_xlsx_with_known_cell(monkeypatch):
    async def fake_sidecar(method, path, **kwargs):
        raise AssertionError(f"office content-box must not call sidecar {method} {path}")

    monkeypatch.setattr("pico_orchestrator.tools_builtin.sidecar_json", fake_sidecar)
    store = MemoryArtifactStore()
    gw = build_default_gateway(store)
    owner = P(school_id="sch", membership_id="mem")
    out = await gw.invoke(
        owner,
        "sandbox_document_open",
        {"kind": "calc", "filename": "课堂成绩.xlsx", "body": "NIGHT-P4-CELL-ALPHA"},
    )
    assert out["view"] == "content-box"
    assert out["kind"] == "calc"
    assert "session_id" not in out
    raw = store.blobs[out["artifact_id"]]
    assert raw[:2] == b"PK"
    with zipfile.ZipFile(io.BytesIO(raw)) as zf:
        blob = b"".join(zf.read(n) for n in zf.namelist())
        assert b"NIGHT-P4-CELL-ALPHA" in blob
    assert b"%PDF" not in raw


@pytest.mark.asyncio
async def test_document_open_existing_artifact_skips_rewrite(monkeypatch):
    async def fake_sidecar(method, path, **kwargs):
        raise AssertionError(f"office content-box must not call sidecar {method} {path}")

    monkeypatch.setattr("pico_orchestrator.tools_builtin.sidecar_json", fake_sidecar)
    store = MemoryArtifactStore()
    raw = build_docx_document(title="报告.docx", marker="EXISTING", body="已有正文")
    rec = await store.write(P("sch", "mem"), title="报告.docx", content=raw, kind="docx")
    gw = build_default_gateway(store)
    out = await gw.invoke(
        P("sch", "mem"),
        "sandbox_document_open",
        {"artifact_id": rec["artifact_id"]},
    )
    assert out["artifact_id"] == rec["artifact_id"]
    assert out["view"] == "content-box"
    assert len(store.rows) == 1


@pytest.mark.asyncio
async def test_document_open_reads_teacher_disk(monkeypatch, tmp_path):
    monkeypatch.setenv("PICO_SANDBOX_DISK", str(tmp_path / "disks"))

    async def fake_sidecar(method, path, **kwargs):
        raise AssertionError(f"office content-box must not call sidecar {method} {path}")

    monkeypatch.setattr("pico_orchestrator.tools_builtin.sidecar_json", fake_sidecar)
    raw = build_docx_document(title="disk.docx", marker="FROM-DISK", body="老师盘上的 Word")
    write_owner_disk_file("sch", "mem", "disk.docx", raw)
    store = MemoryArtifactStore()
    gw = build_default_gateway(store)
    out = await gw.invoke(
        P("sch", "mem"),
        "sandbox_document_open",
        {"filename": "disk.docx"},
    )
    assert out["view"] == "content-box"
    raw = store.blobs[out["artifact_id"]]
    assert raw[:2] == b"PK"
    with zipfile.ZipFile(io.BytesIO(raw)) as zf:
        xml = zf.read("word/document.xml")
    assert b"FROM-DISK" in xml
