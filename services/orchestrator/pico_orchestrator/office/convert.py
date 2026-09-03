"""Thin adapter: sandbox soffice OLE → OOXML. Not a Pico reader."""

from __future__ import annotations

import base64
import logging

from pico_orchestrator.gateway import ToolError
from pico_orchestrator.office.legacy import convert_target_from_name, looks_ooxml

logger = logging.getLogger(__name__)


async def convert_legacy_office_bytes(filename: str, data: bytes) -> bytes:
    """Return OOXML bytes, or original data when conversion is not needed / unavailable."""
    if not data:
        return data
    if looks_ooxml(data):
        return data
    if convert_target_from_name(filename) is None:
        return data
    try:
        from pico_orchestrator.sandbox_sidecar import sidecar_json

        out = await sidecar_json(
            "POST",
            "/v1/internal/office/convert",
            json_body={
                "filename": filename,
                "document_base64": base64.b64encode(data).decode("ascii"),
            },
        )
    except ToolError as exc:
        logger.info(
            "legacy office convert skipped name=%s code=%s",
            filename,
            getattr(exc, "code", type(exc).__name__),
        )
        return data
    except Exception as exc:  # noqa: BLE001 — ingest must not 500 on sidecar gaps
        logger.info("legacy office convert skipped name=%s err=%s", filename, type(exc).__name__)
        return data
    if not isinstance(out, dict):
        return data
    raw_b64 = str(out.get("document_base64") or "").strip()
    if not raw_b64:
        return data
    try:
        converted = base64.b64decode(raw_b64, validate=False)
    except (ValueError, TypeError):
        return data
    if looks_ooxml(converted):
        return converted
    return data
