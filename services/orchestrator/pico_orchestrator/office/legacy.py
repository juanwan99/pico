"""Honest fail for old binary Office formats. No conversion."""

from __future__ import annotations

LEGACY_OFFICE_EXTS = frozenset({".doc", ".ppt", ".xls"})
LEGACY_OFFICE_ERROR = "旧版 .doc/.ppt/.xls 打不开也转不了。请另存为 .docx/.pptx/.xlsx 再试。"
SUPPORTED_OFFICE_EXTS = frozenset({".docx", ".pptx", ".xlsx"})


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


def guess_office_ext(*, kind: str = "", title: str = "") -> str:
    name = (title or "").strip().lower()
    token = (kind or "").strip().lower()
    if token in {"xlsx", "xls"} or name.endswith((".xlsx", ".xls")):
        if token == "xls" or name.endswith(".xls"):
            raise ValueError(LEGACY_OFFICE_ERROR)
        return ".xlsx"
    if token in {"pptx", "ppt"} or name.endswith((".pptx", ".ppt")):
        if token == "ppt" or name.endswith(".ppt"):
            raise ValueError(LEGACY_OFFICE_ERROR)
        return ".pptx"
    if token in {"docx", "doc"} or name.endswith((".docx", ".doc")):
        if token == "doc" or name.endswith(".doc"):
            raise ValueError(LEGACY_OFFICE_ERROR)
        return ".docx"
    if name.endswith((".odt", ".ods", ".odp")):
        raise ValueError("不支持 OpenDocument（.odt/.ods/.odp）。请另存为 .docx/.xlsx/.pptx 再试。")
    return ".docx"
