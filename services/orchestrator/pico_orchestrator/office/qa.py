"""Fail-closed OOXML check. LibreOffice preview is not a layout engine."""

from __future__ import annotations

from pico_orchestrator.artifact_types import is_valid_ooxml_package
from pico_orchestrator.office.legacy import (
    LEGACY_OFFICE_ERROR,
    LEGACY_OFFICE_EXTS,
    looks_ooxml,
    normalize_office_ext,
    office_ext_for_bytes,
    require_supported_office_ext,
)


def verify_office_bytes(raw: bytes, ext: str) -> dict[str, object]:
    suffix = normalize_office_ext(ext)
    if suffix in LEGACY_OFFICE_EXTS:
        if looks_ooxml(raw):
            suffix = office_ext_for_bytes(suffix, raw)
        else:
            return {
                "ok": False,
                "valid_ooxml": False,
                "error": LEGACY_OFFICE_ERROR,
            }
    try:
        suffix = require_supported_office_ext(suffix)
    except ValueError as exc:
        return {"ok": False, "valid_ooxml": False, "error": str(exc)}
    ok = is_valid_ooxml_package(raw, suffix)
    if not ok:
        return {
            "ok": False,
            "valid_ooxml": False,
            "error": f"不是合法 {suffix}（OOXML）。未保存为成功文件。",
        }
    return {"ok": True, "valid_ooxml": True, "ext": suffix}
