"""Thin Zhipu glm-image HTTPS adapter. No local diffusion / no SiliconFlow.

Owner 2026-08-27: SiliconFlow images REJECTED.
Owner 2026-08-27: 「1 开工」= wire glm-image (#729).
Upstream: Zhipu / Z.AI POST …/paas/v4/images/generations model=glm-image.
"""

from __future__ import annotations

import asyncio
import base64
import ipaddress
import logging
import os
import time
from io import BytesIO
from typing import Any
from urllib.parse import urlparse

import httpx

from pico_orchestrator.gateway import ToolError

logger = logging.getLogger(__name__)

# China default (ZHIPU_* keys). Override with ZHIPU_IMAGES_URL for api.z.ai.
DEFAULT_IMAGES_URL = "https://open.bigmodel.cn/api/paas/v4/images/generations"
DEFAULT_MODEL = "glm-image"
DEFAULT_SIZE = "1280x1280"
DEFAULT_QUALITY = "standard"
IMAGE_TIMEOUT_S = 90.0
# Live F4 (#752): Pi fired generate_image 2–3 times; each exhausted 6 POSTs
# (27s) on 429. One in-process flight + longer backoff (60s sleep, still
# inside 90s). Exhausted still image.provider — never invent pixels.
_429_MAX_TRIES = 6
_429_BACKOFF_S = (2.0, 4.0, 8.0, 16.0, 30.0)
_429_RETRY_AFTER_CAP_S = 30.0
_flight_lock = asyncio.Lock()
_glm_lock = asyncio.Lock()
_inflight: dict[str, asyncio.Future[tuple[bytes, str]]] = {}
_next_post_mono = 0.0
_MAX_PROMPT = 2000
_MAX_IMAGE_BYTES = 8 * 1024 * 1024
PNG_MAGIC = b"\x89PNG\r\n\x1a\n"
JPEG_MAGIC = b"\xff\xd8\xff"

NO_KEY_MESSAGE = "出图尚未接通。请管理员在主机写入 ZHIPU_API_KEY 后重试，不能编造图片。"
REJECTED_PROVIDER_MESSAGE = (
    "出图提供商硅基流动已否决，不再调用。请使用智谱 glm-image，不能编造图片。"
)
TIMEOUT_MESSAGE = "出图超时（90 秒）。请稍后重试，不能编造图片。"
REJECT_MESSAGE = "出图服务拒绝了这次请求。请稍后重试或换一句描述，不能编造图片。"
INVALID_MESSAGE = "出图结果不是可打开的 png/jpg，未保存，不能编造图片。"


def siliconflow_api_key() -> str:
    """Legacy env peek — presence must reject, not enable."""
    return (os.environ.get("SILICONFLOW_API_KEY") or "").strip()


def zhipu_api_key() -> str:
    return (os.environ.get("ZHIPU_API_KEY") or "").strip()


def images_url() -> str:
    raw = (os.environ.get("ZHIPU_IMAGES_URL") or "").strip()
    return raw or DEFAULT_IMAGES_URL


def image_model() -> str:
    return (os.environ.get("ZHIPU_IMAGE_MODEL") or DEFAULT_MODEL).strip() or DEFAULT_MODEL


def image_size() -> str:
    return (os.environ.get("ZHIPU_IMAGE_SIZE") or DEFAULT_SIZE).strip() or DEFAULT_SIZE


def image_quality() -> str:
    raw = (os.environ.get("ZHIPU_IMAGE_QUALITY") or DEFAULT_QUALITY).strip().lower()
    return raw if raw in {"hd", "standard"} else DEFAULT_QUALITY


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
        image.convert("RGB").save(out, format="PNG")
        return out.getvalue(), "png"
    raise ToolError("image.invalid", INVALID_MESSAGE)


def _public_https_url(url: str) -> str:
    parsed = urlparse(url.strip())
    if parsed.scheme != "https" or not parsed.hostname:
        raise ToolError("image.invalid", INVALID_MESSAGE)
    host = parsed.hostname
    try:
        addr = ipaddress.ip_address(host)
        if (
            addr.is_private
            or addr.is_loopback
            or addr.is_link_local
            or addr.is_reserved
            or addr.is_multicast
        ):
            raise ToolError("image.invalid", INVALID_MESSAGE)
    except ValueError:
        # hostname, not literal IP — ok
        low = host.lower()
        if low == "localhost" or low.endswith((".local", ".internal")):
            raise ToolError("image.invalid", INVALID_MESSAGE) from None
    return url.strip()


def _http_status(response: Any) -> int:
    try:
        return int(getattr(response, "status_code", 0) or 0)
    except (TypeError, ValueError):
        return 0


def _retry_after_header(response: Any) -> str | None:
    headers = getattr(response, "headers", None)
    if headers is None:
        return None
    get = getattr(headers, "get", None)
    if not callable(get):
        return None
    raw = get("Retry-After")
    if raw is None:
        raw = get("retry-after")
    if raw is None:
        return None
    text = str(raw).strip()
    return text or None


def _parse_retry_after_s(raw: str | None) -> float | None:
    if not raw:
        return None
    try:
        n = float(raw)
    except ValueError:
        return None
    if n <= 0:
        return None
    return min(n, _429_RETRY_AFTER_CAP_S)


def _429_delay_s(retry_index: int, retry_after: str | None) -> float:
    idx = min(max(retry_index, 0), len(_429_BACKOFF_S) - 1)
    scheduled = _429_BACKOFF_S[idx]
    parsed = _parse_retry_after_s(retry_after)
    delay = scheduled if parsed is None else max(scheduled, parsed)
    return max(delay, 1.0)


def reset_image_generate_runtime() -> None:
    """Tests only: drop in-flight joiners and the process 429 gate."""
    global _next_post_mono, _flight_lock, _glm_lock
    _next_post_mono = 0.0
    _inflight.clear()
    _flight_lock = asyncio.Lock()
    _glm_lock = asyncio.Lock()


def _prompt_key(text: str) -> str:
    return " ".join((text or "").split())


async def _respect_rate_gate() -> None:
    delay = _next_post_mono - time.monotonic()
    if delay <= 0:
        return
    logger.warning("zhipu images rate gate wait %.1fs", delay)
    await asyncio.sleep(delay)


def _arm_rate_gate(delay: float) -> None:
    global _next_post_mono
    wait = max(float(delay), 1.0)
    _next_post_mono = max(_next_post_mono, time.monotonic() + wait)


def _http_provider_error(response: Any) -> ToolError:
    err = ToolError("image.provider", REJECT_MESSAGE)
    err.http_status = _http_status(response)
    err.retry_after = _retry_after_header(response)
    return err


async def _post_images(
    payload: dict[str, Any], *, api_key: str, timeout: float
) -> httpx.Response:
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    async with httpx.AsyncClient(timeout=timeout) as client:
        return await client.post(images_url(), json=payload, headers=headers)


async def _fetch_url(url: str, *, timeout: float) -> bytes:
    safe = _public_https_url(url)
    async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
        response = await client.get(safe)
    if response.status_code >= 400:
        raise ToolError("image.provider", REJECT_MESSAGE)
    return response.content


def _first_image_payload(body: Any) -> tuple[str | None, str | None]:
    if not isinstance(body, dict):
        return None, None
    rows = body.get("data")
    if not isinstance(rows, list):
        rows = body.get("images")
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
    if siliconflow_api_key() and not zhipu_api_key():
        logger.warning("generate_image refused: SiliconFlow-only key; provider rejected")
        raise ToolError("image.provider_rejected", REJECTED_PROVIDER_MESSAGE)
    api_key = zhipu_api_key()
    if not api_key:
        raise ToolError("image.unconfigured", NO_KEY_MESSAGE)
    key = _prompt_key(text)
    async with _flight_lock:
        existing = _inflight.get(key)
        if existing is not None:
            fut: asyncio.Future[tuple[bytes, str]] = existing
            created = False
        else:
            fut = asyncio.get_running_loop().create_future()
            _inflight[key] = fut
            created = True
    if not created:
        return await asyncio.shield(fut)
    try:
        async with _glm_lock:
            result = await _generate_image_campaign(text, api_key)
        if not fut.done():
            fut.set_result(result)
        return result
    except BaseException as exc:
        if not fut.done():
            fut.set_exception(exc)
            fut.exception()
        raise
    finally:
        async with _flight_lock:
            if _inflight.get(key) is fut:
                _inflight.pop(key, None)


async def _generate_image_campaign(text: str, api_key: str) -> tuple[bytes, str]:
    await _respect_rate_gate()
    rate_tries = 0
    provider_retried = False
    while True:
        try:
            return await _generate_image_call(text, api_key)
        except ToolError as exc:
            if exc.code != "image.provider":
                raise
            status = getattr(exc, "http_status", None)
            if status == 429:
                if rate_tries >= _429_MAX_TRIES - 1:
                    _arm_rate_gate(_429_RETRY_AFTER_CAP_S)
                    raise
                delay = _429_delay_s(rate_tries, getattr(exc, "retry_after", None))
                logger.warning(
                    "zhipu images HTTP 429; retry %s/%s after %.1fs",
                    rate_tries + 1,
                    _429_MAX_TRIES - 1,
                    delay,
                )
                await asyncio.sleep(delay)
                rate_tries += 1
                continue
            if isinstance(status, int) and 400 <= status < 500:
                raise
            if provider_retried:
                raise
            logger.warning("zhipu images provider failed; retrying once")
            provider_retried = True


async def _generate_image_call(text: str, api_key: str) -> tuple[bytes, str]:
    payload = {
        "model": image_model(),
        "prompt": text,
        "size": image_size(),
        "quality": image_quality(),
    }
    try:
        response = await _post_images(payload, api_key=api_key, timeout=IMAGE_TIMEOUT_S)
    except httpx.TimeoutException as exc:
        raise ToolError("image.timeout", TIMEOUT_MESSAGE) from exc
    except httpx.HTTPError as exc:
        logger.warning("zhipu images transport failed: %s", type(exc).__name__)
        raise ToolError("image.provider", REJECT_MESSAGE) from exc
    if response.status_code in {401, 403}:
        raise ToolError("image.unconfigured", NO_KEY_MESSAGE)
    if response.status_code >= 400:
        logger.warning("zhipu images HTTP %s", response.status_code)
        raise _http_provider_error(response)
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
