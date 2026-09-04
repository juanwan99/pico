"""Thin adapter: sandbox soffice OLE → OOXML. Not a Pico reader."""

from __future__ import annotations

import base64
import logging

from pico_orchestrator.gateway import ToolError
from pico_orchestrator.office.legacy import convert_target_from_name, looks_ooxml

logger = logging.getLogger(__name__)


class LegacyOfficeConvertError(Exception):
    """OLE did not become OOXML. Caller must not pretend the model has the file."""

    def __init__(self, message: str = "旧版文档转不开") -> None:
        super().__init__(message)
        self.message = message


async def convert_legacy_office_bytes(filename: str, data: bytes) -> bytes:
    """Return OOXML bytes. Raise when a legacy name is still OLE after soffice."""
    if not data:
        if convert_target_from_name(filename):
            raise LegacyOfficeConvertError("文档内容为空")
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
    except ToolError as err:
        logger.info(
            "legacy office convert failed name=%s code=%s",
            filename,
            getattr(err, "code", type(err).__name__),
        )
        raise LegacyOfficeConvertError(str(getattr(err, "message", None) or err)) from err
    except Exception as err:
        logger.info("legacy office convert failed name=%s err=%s", filename, type(err).__name__)
        raise LegacyOfficeConvertError("旧版文档转不开") from err
    if not isinstance(out, dict):
        raise LegacyOfficeConvertError("旧版文档转不开")
    raw_b64 = str(out.get("document_base64") or "").strip()
    if not raw_b64:
        raise LegacyOfficeConvertError("旧版文档转不开")
    try:
        converted = base64.b64decode(raw_b64, validate=False)
    except (ValueError, TypeError) as err:
        raise LegacyOfficeConvertError("旧版文档转不开") from err
    if looks_ooxml(converted):
        return converted
    raise LegacyOfficeConvertError("旧版文档转不开")
