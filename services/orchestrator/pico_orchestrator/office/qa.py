"""Package legality. LibreOffice sandbox_document_open is preview only — not used here."""

from __future__ import annotations

import io
from typing import Any

from pico_orchestrator.artifact_types import is_valid_ooxml_package


def verify_bytes(raw: bytes, ext: str) -> dict[str, Any]:
    """Fail closed: bad ZIP / missing OOXML parts / library cannot open."""
    suffix = (ext or "").lower()
    if suffix and not suffix.startswith("."):
        suffix = f".{suffix}"
    if suffix not in {".docx", ".pptx"}:
        return {
            "ok": False,
            "kind": suffix.lstrip(".") or None,
            "ooxml": False,
            "can_open": False,
            "error": "只核对 Word/PPT。Excel 是卡 2。",
        }
    kind = suffix.lstrip(".")
    if not raw or raw[:2] != b"PK":
        return {
            "ok": False,
            "kind": kind,
            "ooxml": False,
            "can_open": False,
            "error": "不是 OOXML 压缩包（缺少 PK 头）。",
        }
    if not is_valid_ooxml_package(raw, suffix):
        return {
            "ok": False,
            "kind": kind,
            "ooxml": False,
            "can_open": False,
            "error": "OOXML 零件不完整，不能当真文件。",
        }
    try:
        if suffix == ".docx":
            from docx import Document

            Document(io.BytesIO(raw))
        else:
            from pptx import Presentation

            Presentation(io.BytesIO(raw))
    except (ValueError, KeyError, OSError, TypeError) as exc:
        return {
            "ok": False,
            "kind": kind,
            "ooxml": True,
            "can_open": False,
            "error": f"库打不开这份文件：{exc.__class__.__name__}",
        }
    return {
        "ok": True,
        "kind": kind,
        "ooxml": True,
        "can_open": True,
        "error": None,
    }
