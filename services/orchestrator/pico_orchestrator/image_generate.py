"""Thin SiliconFlow HTTPS image adapter. No local diffusion / no copied vendor kernels.

Tiers (ADR-CAPABILITY-LOADING): one verb, 档 is a parameter.
cheap = FLUX.1-schnell unlettered raster. high = Kolors (or env pin).
"""

from __future__ import annotations

import base64
import logging
import os
from io import BytesIO
from typing import Any
from urllib.parse import urlparse

import httpx

from pico_orchestrator.gateway import ToolError

logger = logging.getLogger(__name__)

SILICONFLOW_IMAGES_URL = "https://api.siliconflow.cn/v1/images/generations"
CHEAP_MODEL = "black-forest-labs/FLUX.1-schnell"
HIGH_MODEL = "Kwai-Kolors/Kolors"
# Kept for ops that still set the old single-model env (maps to high).
DEFAULT_MODEL = HIGH_MODEL
IMAGE_TIMEOUT_S = 45.0
_MAX_PROMPT = 2000
_MAX_IMAGE_BYTES = 8 * 1024 * 1024
PNG_MAGIC = b"\x89PNG\r\n\x1a\n"
JPEG_MAGIC = b"\xff\xd8\xff"

NO_KEY_MESSAGE = "出图服务未配置。请管理员在主机写入 SILICONFLOW_API_KEY 后重试，不能编造图片。"
TIMEOUT_MESSAGE = "出图超时（45 秒）。请稍后重试，不能编造图片。"
REJECT_MESSAGE = "出图服务拒绝了这次请求。请稍后重试或换一句描述，不能编造图片。"
INVALID_MESSAGE = "出图结果不是可打开的 png/jpg，未保存，不能编造图片。"
TIER_MESSAGE = "出图只有 cheap / high 两档。不能编造图片。"
NO_TEXT_SUFFIX = (
    " No text, letters, numbers, captions, labels, or watermarks in the image."
)

_TIER_ALIASES = {
    "cheap": "cheap",
    "fast": "cheap",
    "low": "cheap",
    "sketch": "cheap",
    "high": "high",
    "quality": "high",
    "photo": "high",
    "best": "high",
}
DEFAULT_TIER = "cheap"


def siliconflow_api_key() -> str:
    return (os.environ.get("SILICONFLOW_API_KEY") or "").strip()


def normalize_image_tier(raw: str | None) -> str:
    if raw is None:
        return DEFAULT_TIER
    text = str(raw).strip().lower()
    if not text:
        return DEFAULT_TIER
    mapped = _TIER_ALIASES.get(text)
    if mapped is None:
        raise ToolError("image.unsupported_tier", TIER_MESSAGE)
    return mapped


def image_model_for(tier: str) -> str:
    resolved = normalize_image_tier(tier)
    if resolved == "cheap":
        return (
            (os.environ.get("SILICONFLOW_IMAGE_MODEL_CHEAP") or "").strip()
            or CHEAP_MODEL
        )
    return (
        (os.environ.get("SILICONFLOW_IMAGE_MODEL_HIGH") or "").strip()
        or (os.environ.get("SILICONFLOW_IMAGE_MODEL") or "").strip()
        or HIGH_MODEL
    )


def image_model() -> str:
    """High-tier model (legacy env SILICONFLOW_IMAGE_MODEL)."""
    return image_model_for("high")


def _as_png_or_jpeg(raw: bytes) -> tuple[bytes, str]:
    if not raw or len(raw) > _MAX_IMAGE_BYTES:
        raise ToolError("image.invalid", INVALID_MESSAGE)
    if raw.startswith(PNG_MAGIC):
        return raw, "png"
    if raw[:3] == JPEG_MAGIC:
        return raw, "jpg"
    if raw[:4] == b"RIFF" and raw[8:12] == b"WEBP":
        from PIL import Image

        image = Image.open(BytesIO(raw))
        out = BytesIO()
        image.save(out, format="PNG")
        data = out.getvalue()
        if not data.startswith(PNG_MAGIC):
            raise ToolError("image.invalid", INVALID_MESSAGE)
        return data, "png"
    raise ToolError("image.invalid", INVALID_MESSAGE)


def _public_https(url: str) -> str:
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    if parsed.scheme != "https" or not host:
        raise ToolError("image.invalid", INVALID_MESSAGE)
    if host in {"localhost", "127.0.0.1", "::1"} or host.endswith(".local"):
        raise ToolError("image.invalid", INVALID_MESSAGE)
    if host.startswith(("10.", "192.168.", "169.254.")):
        raise ToolError("image.invalid", INVALID_MESSAGE)
    return url


async def _post_images(
    payload: dict[str, Any],
    *,
    api_key: str,
    timeout: float,
) -> httpx.Response:
    async with httpx.AsyncClient(timeout=timeout) as client:
        return await client.post(
            SILICONFLOW_IMAGES_URL,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
        )


async def _fetch_url(url: str, *, timeout: float) -> bytes:
    safe = _public_https(url)
    async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
        response = await client.get(safe)
    if response.status_code >= 400:
        raise ToolError("image.provider", REJECT_MESSAGE)
    return bytes(response.content or b"")


def _first_image_payload(body: Any) -> tuple[str | None, str | None]:
    if not isinstance(body, dict):
        return None, None
    rows = body.get("images")
    if not isinstance(rows, list):
        rows = body.get("data")
    if not isinstance(rows, list) or not rows:
        return None, None
    first = rows[0]
    if not isinstance(first, dict):
        return None, None
    url = first.get("url") or first.get("image")
    b64 = first.get("b64_json") or first.get("b64")
    url_s = str(url).strip() if isinstance(url, str) else None
    b64_s = str(b64).strip() if isinstance(b64, str) else None
    return url_s or None, b64_s or None


def _payload_for(tier: str, model: str, prompt: str) -> dict[str, Any]:
    body: dict[str, Any] = {
        "model": model,
        "prompt": prompt,
        "image_size": "1024x1024",
        "batch_size": 1,
    }
    if tier == "high":
        body["num_inference_steps"] = 20
    return body


async def generate_image_bytes(
    prompt: str,
    *,
    tier: str | None = None,
) -> tuple[bytes, str, dict[str, Any]]:
    """Return (image_bytes, png|jpg, meta). Never invent pixels on failure."""
    text = (prompt or "").strip()
    if not text:
        raise ToolError("tool.invalid_arguments", "请写要画的内容。")
    if len(text) > _MAX_PROMPT:
        raise ToolError("tool.invalid_arguments", f"出图描述不能超过 {_MAX_PROMPT} 字。")
    resolved = normalize_image_tier(tier)
    model = image_model_for(resolved)
    send = text + NO_TEXT_SUFFIX if resolved == "cheap" else text
    if len(send) > _MAX_PROMPT:
        send = send[:_MAX_PROMPT]
    api_key = siliconflow_api_key()
    if not api_key:
        raise ToolError("image.unconfigured", NO_KEY_MESSAGE)
    payload = _payload_for(resolved, model, send)
    try:
        response = await _post_images(payload, api_key=api_key, timeout=IMAGE_TIMEOUT_S)
    except httpx.TimeoutException as exc:
        raise ToolError("image.timeout", TIMEOUT_MESSAGE) from exc
    except httpx.HTTPError as exc:
        logger.warning("siliconflow images transport failed: %s", type(exc).__name__)
        raise ToolError("image.provider", REJECT_MESSAGE) from exc
    if response.status_code in {401, 403}:
        raise ToolError("image.unconfigured", NO_KEY_MESSAGE)
    if response.status_code >= 400:
        raise ToolError("image.provider", REJECT_MESSAGE)
    try:
        body = response.json()
    except Exception as exc:
        raise ToolError("image.invalid", INVALID_MESSAGE) from exc
    url, b64 = _first_image_payload(body)
    raw = b""
    if b64:
        try:
            raw = base64.b64decode(b64, validate=False)
        except Exception as exc:
            raise ToolError("image.invalid", INVALID_MESSAGE) from exc
    elif url:
        try:
            raw = await _fetch_url(url, timeout=IMAGE_TIMEOUT_S)
        except ToolError:
            raise
        except httpx.TimeoutException as exc:
            raise ToolError("image.timeout", TIMEOUT_MESSAGE) from exc
        except httpx.HTTPError as exc:
            raise ToolError("image.provider", REJECT_MESSAGE) from exc
    else:
        raise ToolError("image.invalid", INVALID_MESSAGE)
    png, ext = _as_png_or_jpeg(raw)
    return png, ext, {"tier": resolved, "model": model, "unlettered": resolved == "cheap"}
