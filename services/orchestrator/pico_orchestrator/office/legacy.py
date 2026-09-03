"""OLE vs OOXML. Conversion is soffice in the sandbox, not a Pico kernel."""

from __future__ import annotations

LEGACY_OFFICE_EXTS = frozenset({".doc", ".ppt", ".xls"})
LEGACY_OFFICE_ERROR = "这份还是旧版 .doc/.ppt/.xls（OLE），没有可用的 OOXML。"
SUPPORTED_OFFICE_EXTS = frozenset({".docx", ".pptx", ".xlsx"})
LEGACY_TO_OOXML = {".doc": ".docx", ".ppt": ".pptx", ".xls": ".xlsx"}


def normalize_office_ext(ext: str) -> str:
    suffix = (ext or "").strip().lower()
    if suffix and not suffix.startswith("."):
        suffix = f".{suffix}"
    return suffix


def reject_legacy_office(ext: str) -> None:
    suffix = normalize_office_ext(ext)
    if suffix in LEGACY_OFFICE_EXTS:
        raise ValueError(LEGACY_OFFICE_ERROR)


def require_supported_office_ext(ext: str) -> str:
    suffix = normalize_office_ext(ext)
    reject_legacy_office(suffix)
    if suffix not in SUPPORTED_OFFICE_EXTS:
        raise ValueError(f"只支持 .docx / .pptx / .xlsx，不支持 {suffix or '空'}。")
    return suffix


def ooxml_ext_for_legacy(ext: str) -> str | None:
    return LEGACY_TO_OOXML.get(normalize_office_ext(ext))


def looks_ooxml(raw: bytes) -> bool:
    return bool(raw) and raw[:2] == b"PK"


def office_ext_for_bytes(ext: str, raw: bytes) -> str:
    """Teacher name may stay .doc after soffice conversion; bytes decide."""
    suffix = normalize_office_ext(ext)
    mapped = ooxml_ext_for_legacy(suffix)
    if mapped and looks_ooxml(raw):
        return mapped
    return require_supported_office_ext(suffix)


def guess_office_ext(*, kind: str = "", title: str = "") -> str:
    name = (title or "").strip().lower()
    token = (kind or "").strip().lower()
    if token in {"xlsx", "xls"} or name.endswith((".xlsx", ".xls")):
        return ".xlsx"
    if token in {"pptx", "ppt"} or name.endswith((".pptx", ".ppt")):
        return ".pptx"
    if token in {"docx", "doc"} or name.endswith((".docx", ".doc")):
        return ".docx"
    if name.endswith((".odt", ".ods", ".odp")):
        raise ValueError("不支持 OpenDocument（.odt/.ods/.odp）。")
    return ".docx"


def convert_target_from_name(filename: str) -> str | None:
    name = (filename or "").strip().lower()
    if name.endswith((".docx", ".pptx", ".xlsx")):
        return None
    if name.endswith(".doc"):
        return ".docx"
    if name.endswith(".ppt"):
        return ".pptx"
    if name.endswith(".xls"):
        return ".xlsx"
    return None
