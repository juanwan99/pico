"""Legacy OLE convert adapter: soffice in sandbox, no Pico kernel."""

from __future__ import annotations

import asyncio
import base64
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "orchestrator"))

from pico_orchestrator.document_generators import build_docx_document
from pico_orchestrator.llm_file_pass import accept_native
from pico_orchestrator.office.convert import convert_legacy_office_bytes
from pico_orchestrator.office.inspect import inspect_office_bytes
from pico_orchestrator.office.legacy import convert_target_from_name, guess_office_ext


def test_convert_target_maps_ole_not_ooxml_names() -> None:
    assert convert_target_from_name("计划.doc") == ".docx"
    assert convert_target_from_name("课.ppt") == ".pptx"
    assert convert_target_from_name("表.xls") == ".xlsx"
    assert convert_target_from_name("通知.docx") is None
    assert convert_target_from_name("a.pdf") is None


def test_guess_office_ext_maps_legacy_names_to_ooxml() -> None:
    assert guess_office_ext(title="计划.doc") == ".docx"
    assert guess_office_ext(kind="xls", title="表.xls") == ".xlsx"


def test_inspect_converted_bytes_keeps_teacher_doc_name() -> None:
    raw = build_docx_document(title="计划.docx", marker="LEGACY-CONV", body="三年级二班春游")
    outline = inspect_office_bytes(raw, ".doc")
    assert outline["kind"] == "docx"
    texts = " ".join(str(u.get("text") or "") for u in outline["units"] if isinstance(u, dict))
    assert "三年级二班春游" in texts
    item = accept_native("计划.doc", raw)
    assert item is not None
    assert item.ext == ".docx"
    assert item.filename.endswith(".docx")


def test_convert_raises_when_sidecar_unavailable(monkeypatch) -> None:
    from pico_orchestrator.gateway import ToolError
    from pico_orchestrator.office.convert import LegacyOfficeConvertError

    async def boom(*_a, **_k):
        raise ToolError("sandbox.unavailable", "no sidecar")

    monkeypatch.setattr("pico_orchestrator.sandbox_sidecar.sidecar_json", boom)
    ole = b"\xd0\xcf\x11\xe0junk"
    try:
        asyncio.run(convert_legacy_office_bytes("计划.doc", ole))
    except LegacyOfficeConvertError as err:
        assert "sidecar" in err.message or "转不开" in err.message
    else:
        raise AssertionError("expected LegacyOfficeConvertError")


def test_native_files_converts_ole_before_accept(monkeypatch) -> None:
    import asyncio

    raw = build_docx_document(title="计划.docx", marker="PASS", body="春游")

    async def fake(_method, _path, **kwargs):
        return {"ok": True, "document_base64": base64.b64encode(raw).decode("ascii")}

    monkeypatch.setattr("pico_orchestrator.sandbox_sidecar.sidecar_json", fake)
    from pico_orchestrator.llm_file_pass import accept_native
    from pico_orchestrator.office.convert import convert_legacy_office_bytes

    converted = asyncio.run(convert_legacy_office_bytes("教师教学计划.doc", b"\xd0\xcf\x11\xe0"))
    item = accept_native("教师教学计划.doc", converted)
    assert item is not None
    assert item.ext == ".docx"
    assert item.filename.endswith(".docx")


def test_convert_returns_ooxml_from_sidecar(monkeypatch) -> None:
    raw = build_docx_document(title="计划.docx", marker="CONV-OK", body="教案")

    async def fake(_method, _path, **kwargs):
        return {"ok": True, "document_base64": base64.b64encode(raw).decode("ascii")}

    monkeypatch.setattr("pico_orchestrator.sandbox_sidecar.sidecar_json", fake)
    out = asyncio.run(convert_legacy_office_bytes("计划.doc", b"OLE-bytes"))
    assert out[:2] == b"PK"
    assert accept_native("计划.doc", out) is not None


def test_sandbox_convert_uses_ascii_temp_name() -> None:
    import inspect

    from sandbox_worker.office import convert_legacy_office

    src = inspect.getsource(convert_legacy_office)
    assert "in{source_ext}" in src
    assert "safe_name" in src
    assert '"HOME": str(work)' not in src
    assert "SAL_USE_VCLPLUGIN" not in src
