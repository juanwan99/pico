"""Artifact → content-page PNGs via sandbox LibreOffice convert. No second Office OS."""

from __future__ import annotations

import base64
import binascii
import hashlib
import logging
from typing import Any

from pico_orchestrator.gateway import ToolError

logger = logging.getLogger(__name__)

_MAX_CACHED = 8
_CACHE: dict[str, list[bytes]] = {}
_ORDER: list[str] = []


def _cache_get(key: str) -> list[bytes] | None:
    pages = _CACHE.get(key)
    if pages is None:
        return None
    if key in _ORDER:
        _ORDER.remove(key)
    _ORDER.append(key)
    return pages


def _cache_put(key: str, pages: list[bytes]) -> None:
    _CACHE[key] = pages
    if key in _ORDER:
        _ORDER.remove(key)
    _ORDER.append(key)
    while len(_ORDER) > _MAX_CACHED:
        old = _ORDER.pop(0)
        _CACHE.pop(old, None)


def cache_key(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


async def pages_for_document(filename: str, raw: bytes) -> list[bytes]:
    key = cache_key(raw)
    hit = _cache_get(key)
    if hit is not None:
        return hit
    from pico_orchestrator.sandbox_sidecar import sidecar_json

    out = await sidecar_json(
        "POST",
        "/v1/internal/office/preview",
        json_body={
            "filename": filename,
            "document_base64": base64.b64encode(raw).decode("ascii"),
        },
    )
    if not isinstance(out, dict):
        raise ToolError("sandbox.raster_failed", "文档内容页转换失败")
    pages: list[bytes] = []
    rows = out.get("pages")
    if isinstance(rows, list):
        for item in rows:
            if not isinstance(item, str) or not item.strip():
                continue
            try:
                blob = base64.b64decode(item, validate=False)
            except (ValueError, TypeError, binascii.Error) as exc:
                logger.debug("skip bad office page b64: %s", type(exc).__name__)
                continue
            if blob:
                pages.append(blob)
    if not pages:
        raise ToolError("sandbox.raster_failed", "文档没有可显示的内容页")
    _cache_put(key, pages)
    return pages


def page_meta(title: str, pages: list[bytes]) -> dict[str, Any]:
    return {
        "ok": True,
        "title": title,
        "page_count": len(pages),
    }
