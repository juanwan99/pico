"""Thin vision adapter: keep chat image parts; never invent pixels.

LibreChat / OpenAI-style ``image_url`` parts are mapped to Pi RPC
``images[]`` (base64) or hosted ``image_url`` content. No OCR kernel.
"""

from __future__ import annotations

import base64
import binascii
import re
from typing import Any

from pico_orchestrator.run_types import RunCaps

DEFAULT_DEEPSEEK_VISION = "deepseek-v4-flash-vision-exp"
_MAX_IMAGES = 8
_MAX_IMAGE_BYTES = 8 * 1024 * 1024
_DATA_URL_RE = re.compile(
    r"^data:(image/(?:png|jpeg|jpg|gif|webp));base64,(.+)$",
    re.IGNORECASE | re.DOTALL,
)
_MIME_BY_EXT = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    ".webp": "image/webp",
}


def model_accepts_image(model: str | None) -> bool:
    mid = (model or "").strip().lower()
    return "vision" in mid or mid.endswith("-vl")


def vision_model_for_images(current: str | None = None) -> str:
    if model_accepts_image(current):
        return str(current).strip()
    return DEFAULT_DEEPSEEK_VISION


def apply_images_to_caps(caps: RunCaps, images: list[dict[str, Any]]) -> RunCaps:
    """Attach images and switch the backend to a vision model when needed."""
    from dataclasses import replace

    cleaned = [item for item in images if isinstance(item, dict)][:_MAX_IMAGES]
    if not cleaned:
        return caps
    backend = vision_model_for_images(getattr(caps, "backend_model", None))
    return replace(caps, images=cleaned, backend_model=backend)


def extract_images_from_content(content: Any) -> list[dict[str, Any]]:
    """Pull image parts from an OpenAI-style message content value."""
    if not isinstance(content, list):
        return []
    out: list[dict[str, Any]] = []
    for part in content:
        if len(out) >= _MAX_IMAGES:
            break
        parsed = _parse_part(part)
        if parsed is not None:
            out.append(parsed)
    return out


def last_user_images(messages: list[Any]) -> list[dict[str, Any]]:
    """Images on the latest user turn only (current prompt)."""
    for item in reversed(messages or []):
        role = getattr(item, "role", None)
        if role is None and isinstance(item, dict):
            role = item.get("role")
        if role != "user":
            continue
        content = getattr(item, "content", None)
        if content is None and isinstance(item, dict):
            content = item.get("content")
        return extract_images_from_content(content)
    return []


def pi_rpc_images(images: list[dict[str, Any]]) -> list[dict[str, str]]:
    """Pi RPC ``prompt.images`` payload. URL-only parts are dropped (no fetch)."""
    out: list[dict[str, str]] = []
    for item in images:
        data = str(item.get("data") or "").strip()
        mime = str(item.get("mimeType") or item.get("mime_type") or "").strip()
        if not data or not mime:
            continue
        out.append({"type": "image", "data": data, "mimeType": mime})
    return out[:_MAX_IMAGES]


def hosted_image_parts(images: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """OpenAI-compatible image_url parts for the hosted rollback loop."""
    parts: list[dict[str, Any]] = []
    for item in images:
        data = str(item.get("data") or "").strip()
        mime = str(item.get("mimeType") or item.get("mime_type") or "image/png").strip()
        url = str(item.get("url") or "").strip()
        if data and mime:
            url = f"data:{mime};base64,{data}"
        if not url:
            continue
        parts.append({"type": "image_url", "image_url": {"url": url}})
    return parts[:_MAX_IMAGES]


def hosted_user_content(prompt: str, images: list[dict[str, Any]]) -> str | list[dict[str, Any]]:
    parts = hosted_image_parts(images)
    if not parts:
        return prompt
    return [{"type": "text", "text": prompt}, *parts]


def _parse_part(part: Any) -> dict[str, Any] | None:
    if not isinstance(part, dict):
        return None
    kind = str(part.get("type") or "").strip().lower()
    if kind in {"image", "input_image"} and part.get("data"):
        mime = str(part.get("mimeType") or part.get("mime_type") or "image/png")
        data = _clean_b64(str(part.get("data") or ""))
        return _bytes_item(data, mime)
    url = _part_url(part)
    if not url:
        return None
    parsed = _from_data_url(url)
    if parsed is not None:
        return parsed
    if url.startswith(("https://", "http://")):
        return {"type": "image_url", "url": url}
    return None


def _part_url(part: dict[str, Any]) -> str:
    raw = part.get("image_url") or part.get("imageUrl") or part.get("url")
    if isinstance(raw, dict):
        return str(raw.get("url") or "").strip()
    if isinstance(raw, str):
        return raw.strip()
    return ""


def _from_data_url(url: str) -> dict[str, Any] | None:
    match = _DATA_URL_RE.match(url.strip())
    if not match:
        return None
    mime = match.group(1).lower()
    if mime == "image/jpg":
        mime = "image/jpeg"
    data = _clean_b64(match.group(2))
    return _bytes_item(data, mime)


def _clean_b64(raw: str) -> str:
    return re.sub(r"\s+", "", raw or "")


def _bytes_item(data: str, mime: str) -> dict[str, Any] | None:
    if not data:
        return None
    try:
        raw = base64.b64decode(data, validate=False)
    except (binascii.Error, ValueError):
        return None
    if not raw or len(raw) > _MAX_IMAGE_BYTES:
        return None
    mime = mime if mime.startswith("image/") else "image/png"
    return {"type": "image", "data": data, "mimeType": mime}


def image_ext_mime(ext: str) -> str | None:
    return _MIME_BY_EXT.get((ext or "").lower())
