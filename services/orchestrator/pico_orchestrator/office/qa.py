"""Fail-closed OOXML check. LibreOffice preview is not a layout engine."""

from __future__ import annotations

from pico_orchestrator.artifact_types import is_valid_ooxml_package


def verify_office_bytes(raw: bytes, ext: str) -> dict[str, object]:
    suffix = ext if ext.startswith(".") else f".{ext}"
    ok = is_valid_ooxml_package(raw, suffix)
    if not ok:
        return {
            "ok": False,
            "valid_ooxml": False,
            "error": f"不是合法 {suffix}（OOXML）。未保存为成功文件。",
        }
    return {"ok": True, "valid_ooxml": True, "ext": suffix}
