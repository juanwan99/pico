"""Thin SiliconFlow HTTPS image adapter. No local diffusion / no copied vendor kernels."""

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
DEFAULT_MODEL = "Kwai-Kolors/Kolors"
IMAGE_TIMEOUT_S = 45.0
_MAX_PROMPT = 2000
_MAX_IMAGE_BYTES = 8 * 1024 * 1024
PNG_MAGIC = b"\x89PNG\r\n\x1a\n"
JPEG_MAGIC = b"\xff\xd8\xff"

NO_KEY_MESSAGE = (
    "出图服务未配置：主机还没有写入 SILICONFLOW_API_KEY。"
    "Pico 已接通出图接口，配置密钥后即可生成真实图片，不能编造图片。"
)


def image_generate_configured() -> bool:
    return bool(siliconflow_api_key())


TIMEOUT_MESSAGE = "出图超时（45 秒）。请稍后重试，不能编造图片。"
REJECT_MESSAGE = "出图服务拒绝了这次请求。请稍后重试或换一句描述，不能编造图片。"
INVALID_MESSAGE = "出图结果不是可打开的 png/jpg，未保存，不能编造图片。"


def siliconflow_api_key() -> str:
    return (os.environ.get("SILICONFLOW_API_KEY") or "").strip()


def image_model() -> str:
    return (os.environ.get("SILICONFLOW_IMAGE_MODEL") or DEFAULT_MODEL).strip() or DEFAULT_MODEL


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


async def generate_image_bytes(prompt: str) -> tuple[bytes, str]:
    """Return (image_bytes, png|jpg). Never invent pixels on failure."""
    text = (prompt or "").strip()
    if not text:
        raise ToolError("tool.invalid_arguments", "请写要画的内容。")
    if len(text) > _MAX_PROMPT:
        raise ToolError("tool.invalid_arguments", f"出图描述不能超过 {_MAX_PROMPT} 字。")
    api_key = siliconflow_api_key()
    if not api_key:
        raise ToolError("image.unconfigured", NO_KEY_MESSAGE)
    payload = {
        "model": image_model(),
        "prompt": text,
        "image_size": "1024x1024",
        "batch_size": 1,
        "num_inference_steps": 20,
    }
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
    return _as_png_or_jpeg(raw)
