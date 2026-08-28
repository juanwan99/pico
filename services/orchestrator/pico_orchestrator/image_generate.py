"""Thin image HTTPS adapter. No local diffusion / no SiliconFlow.

Owner 2026-08-27: SiliconFlow images REJECTED.
Owner 2026-08-28: Gemini official API or owner New API gateway first
(#752). Zhipu glm-image stays as leftover when those keys are absent.
No cookie/session Gemini web farm. No in-process multi-key rotator.
"""

from __future__ import annotations

import asyncio
import base64
import ipaddress
import json
import logging
import os
import time
from datetime import UTC
from email.utils import parsedate_to_datetime
from io import BytesIO
from typing import Any
from urllib.parse import urlparse

import httpx

from pico_orchestrator.gateway import ToolError

logger = logging.getLogger(__name__)

# China leftover (ZHIPU_*). Override with ZHIPU_IMAGES_URL for api.z.ai.
DEFAULT_IMAGES_URL = "https://open.bigmodel.cn/api/paas/v4/images/generations"
DEFAULT_MODEL = "glm-image"
DEFAULT_SIZE = "1280x1280"
DEFAULT_QUALITY = "standard"
DEFAULT_GEMINI_MODEL = "gemini-2.5-flash-image"
DEFAULT_GEMINI_ROOT = "https://generativelanguage.googleapis.com/v1beta"
PROVIDER_GATEWAY = "gateway"
PROVIDER_GEMINI = "gemini"
PROVIDER_ZHIPU = "zhipu"
IMAGE_TIMEOUT_S = 90.0
# Live F5 (#752) this-round glm-image 429: Retry-After header absent,
# body error.code=1113 「余额不足或无可用资源包,请充值。」. F4 single-flight +
# 2/4/8/16/30 then rate-gate ~28s still consecutive-flew and 429'd.
# Honor Retry-After (HTTP-date or seconds), cap = image timeout window.
# Missing header → rest that window before the next POST, not 28s.
# 1113 is not a rate limit — do not retry. Exhausted still
# image.provider — never invent pixels.
_429_MAX_TRIES = 6
_429_RETRY_AFTER_CAP_S = IMAGE_TIMEOUT_S
_429_NON_RETRYABLE_CODES = frozenset({"1113"})
_flight_lock = asyncio.Lock()
_glm_lock = asyncio.Lock()
_inflight: dict[str, asyncio.Future[tuple[bytes, str]]] = {}
_next_post_mono = 0.0
_MAX_PROMPT = 2000
_MAX_IMAGE_BYTES = 8 * 1024 * 1024
PNG_MAGIC = b"\x89PNG\r\n\x1a\n"
JPEG_MAGIC = b"\xff\xd8\xff"

NO_KEY_MESSAGE = (
    "出图尚未接通。请管理员在主机写入 GEMINI_API_KEY"
    "（或 PICO_IMAGE_GATEWAY_URL + PICO_IMAGE_GATEWAY_KEY）后重试，不能编造图片。"
)
REJECTED_PROVIDER_MESSAGE = (
    "出图提供商硅基流动已否决，不再调用。请使用 Gemini 或智谱出图，不能编造图片。"
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


def gemini_api_key() -> str:
    return (
        os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY") or ""
    ).strip()


def gemini_image_model() -> str:
    raw = (os.environ.get("GEMINI_IMAGE_MODEL") or DEFAULT_GEMINI_MODEL).strip()
    return raw or DEFAULT_GEMINI_MODEL


def gemini_generate_url() -> str:
    raw = (os.environ.get("GEMINI_IMAGES_URL") or "").strip()
    if raw:
        return raw
    return f"{DEFAULT_GEMINI_ROOT}/models/{gemini_image_model()}:generateContent"


def gateway_key() -> str:
    return (os.environ.get("PICO_IMAGE_GATEWAY_KEY") or "").strip()


def gateway_images_url() -> str:
    raw = (os.environ.get("PICO_IMAGE_GATEWAY_URL") or "").strip()
    if not raw:
        return ""
    text = raw.rstrip("/")
    if text.endswith("/images/generations"):
        return text
    return f"{text}/v1/images/generations"


def gateway_model() -> str:
    raw = (os.environ.get("PICO_IMAGE_GATEWAY_MODEL") or "").strip()
    return raw or gemini_image_model()


def allowed_image_key() -> bool:
    return bool(
        zhipu_api_key()
        or gemini_api_key()
        or (gateway_images_url() and gateway_key())
    )


def selected_image_provider() -> str | None:
    """Owner 2026-08-28: gateway / Gemini first; Zhipu leftover."""
    if gateway_images_url() and gateway_key():
        return PROVIDER_GATEWAY
    if gemini_api_key():
        return PROVIDER_GEMINI
    if zhipu_api_key():
        return PROVIDER_ZHIPU
    return None


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
    text = str(raw).strip()
    if not text:
        return None
    try:
        n = float(text)
    except ValueError:
        n = None
    if n is not None:
        if n <= 0:
            return None
        return min(n, _429_RETRY_AFTER_CAP_S)
    try:
        dt = parsedate_to_datetime(text)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=UTC)
        delay = dt.timestamp() - time.time()
    except (TypeError, ValueError, OverflowError, OSError):
        return None
    if delay <= 0:
        return None
    return min(delay, _429_RETRY_AFTER_CAP_S)


def _429_delay_s(retry_after: str | None) -> float:
    """Seconds to rest before the next glm-image POST.

    This round's live 429 had Retry-After absent — rest the timeout
    window rather than 2/4/8/16/30 then ~28s consecutive fly.
    """
    parsed = _parse_retry_after_s(retry_after)
    if parsed is None:
        return _429_RETRY_AFTER_CAP_S
    return max(parsed, 1.0)


def _zhipu_error_code(response: Any) -> str | None:
    json_fn = getattr(response, "json", None)
    body: Any = None
    if callable(json_fn):
        try:
            body = json_fn()
        except (TypeError, ValueError, json.JSONDecodeError, AttributeError):
            body = None
    elif isinstance(getattr(response, "text", None), str):
        try:
            body = json.loads(response.text)
        except (TypeError, ValueError, json.JSONDecodeError):
            body = None
    if not isinstance(body, dict):
        return None
    err = body.get("error")
    code = err.get("code") if isinstance(err, dict) else body.get("code")
    if code is None:
        return None
    text = str(code).strip()
    return text or None


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
    err.zhipu_error_code = _zhipu_error_code(response)
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


async def _post_gateway(
    payload: dict[str, Any], *, api_key: str, timeout: float
) -> httpx.Response:
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    async with httpx.AsyncClient(timeout=timeout) as client:
        return await client.post(gateway_images_url(), json=payload, headers=headers)


async def _post_gemini(
    payload: dict[str, Any], *, api_key: str, timeout: float
) -> httpx.Response:
    headers = {
        "x-goog-api-key": api_key,
        "Content-Type": "application/json",
    }
    async with httpx.AsyncClient(timeout=timeout) as client:
        return await client.post(gemini_generate_url(), json=payload, headers=headers)


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


def _gemini_inline_b64(body: Any) -> str | None:
    if not isinstance(body, dict):
        return None
    cands = body.get("candidates")
    if not isinstance(cands, list):
        return None
    for cand in cands:
        if not isinstance(cand, dict):
            continue
        content = cand.get("content")
        if not isinstance(content, dict):
            continue
        parts = content.get("parts")
        if not isinstance(parts, list):
            continue
        for part in parts:
            if not isinstance(part, dict):
                continue
            inline = part.get("inlineData") or part.get("inline_data")
            if not isinstance(inline, dict):
                continue
            data = inline.get("data")
            if isinstance(data, str) and data.strip():
                return data.strip()
    return None


async def generate_image_bytes(prompt: str) -> tuple[bytes, str]:
    """Return (image_bytes, png|jpg). Never invent pixels on failure."""
    text = (prompt or "").strip()
    if not text:
        raise ToolError("tool.invalid_arguments", "请写要画的内容。")
    if len(text) > _MAX_PROMPT:
        raise ToolError("tool.invalid_arguments", f"出图描述不能超过 {_MAX_PROMPT} 字。")
    if siliconflow_api_key() and not allowed_image_key():
        logger.warning("generate_image refused: SiliconFlow-only key; provider rejected")
        raise ToolError("image.provider_rejected", REJECTED_PROVIDER_MESSAGE)
    if selected_image_provider() is None:
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
            result = await _generate_image_campaign(text)
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


async def _generate_image_campaign(text: str) -> tuple[bytes, str]:
    await _respect_rate_gate()
    rate_tries = 0
    provider_retried = False
    while True:
        try:
            return await _generate_image_call(text)
        except ToolError as exc:
            if exc.code != "image.provider":
                raise
            status = getattr(exc, "http_status", None)
            if status == 429:
                retry_after = getattr(exc, "retry_after", None)
                error_code = str(getattr(exc, "zhipu_error_code", None) or "").strip()
                delay = _429_delay_s(retry_after)
                if error_code in _429_NON_RETRYABLE_CODES:
                    delay = _429_RETRY_AFTER_CAP_S
                _arm_rate_gate(delay)
                no_retry = (
                    error_code in _429_NON_RETRYABLE_CODES
                    or rate_tries >= _429_MAX_TRIES - 1
                    or delay >= _429_RETRY_AFTER_CAP_S
                )
                if no_retry:
                    logger.warning(
                        "images HTTP 429 retry-after=%r error_code=%s; "
                        "gate %.1fs, no in-campaign fly",
                        retry_after,
                        error_code or None,
                        delay,
                    )
                    raise
                logger.warning(
                    "images HTTP 429 retry-after=%r error_code=%s; "
                    "retry %s/%s after %.1fs",
                    retry_after,
                    error_code or None,
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
            logger.warning("images provider failed; retrying once")
            provider_retried = True


async def _generate_image_call(text: str) -> tuple[bytes, str]:
    kind = selected_image_provider()
    if kind == PROVIDER_GEMINI:
        return await _generate_gemini_call(text)
    if kind == PROVIDER_GATEWAY:
        return await _generate_gateway_call(text)
    if kind == PROVIDER_ZHIPU:
        return await _generate_zhipu_call(text)
    raise ToolError("image.unconfigured", NO_KEY_MESSAGE)


async def _raise_http_response(response: Any, *, log_name: str) -> None:
    if response.status_code in {401, 403}:
        raise ToolError("image.unconfigured", NO_KEY_MESSAGE)
    if response.status_code >= 400:
        logger.warning(
            "%s HTTP %s retry-after=%r error_code=%s",
            log_name,
            response.status_code,
            _retry_after_header(response),
            _zhipu_error_code(response),
        )
        raise _http_provider_error(response)


async def _bytes_from_openai_image_body(body: Any) -> tuple[bytes, str]:
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


async def _generate_zhipu_call(text: str) -> tuple[bytes, str]:
    payload = {
        "model": image_model(),
        "prompt": text,
        "size": image_size(),
        "quality": image_quality(),
    }
    try:
        response = await _post_images(
            payload, api_key=zhipu_api_key(), timeout=IMAGE_TIMEOUT_S
        )
    except httpx.TimeoutException as exc:
        raise ToolError("image.timeout", TIMEOUT_MESSAGE) from exc
    except httpx.HTTPError as exc:
        logger.warning("zhipu images transport failed: %s", type(exc).__name__)
        raise ToolError("image.provider", REJECT_MESSAGE) from exc
    await _raise_http_response(response, log_name="zhipu images")
    try:
        body = response.json()
    except Exception as exc:
        raise ToolError("image.invalid", INVALID_MESSAGE) from exc
    return await _bytes_from_openai_image_body(body)


async def _generate_gateway_call(text: str) -> tuple[bytes, str]:
    payload = {
        "model": gateway_model(),
        "prompt": text,
        "size": image_size(),
        "n": 1,
    }
    try:
        response = await _post_gateway(
            payload, api_key=gateway_key(), timeout=IMAGE_TIMEOUT_S
        )
    except httpx.TimeoutException as exc:
        raise ToolError("image.timeout", TIMEOUT_MESSAGE) from exc
    except httpx.HTTPError as exc:
        logger.warning("gateway images transport failed: %s", type(exc).__name__)
        raise ToolError("image.provider", REJECT_MESSAGE) from exc
    await _raise_http_response(response, log_name="gateway images")
    try:
        body = response.json()
    except Exception as exc:
        raise ToolError("image.invalid", INVALID_MESSAGE) from exc
    return await _bytes_from_openai_image_body(body)


async def _generate_gemini_call(text: str) -> tuple[bytes, str]:
    payload = {
        "contents": [{"role": "user", "parts": [{"text": text}]}],
        "generationConfig": {"responseModalities": ["TEXT", "IMAGE"]},
    }
    try:
        response = await _post_gemini(
            payload, api_key=gemini_api_key(), timeout=IMAGE_TIMEOUT_S
        )
    except httpx.TimeoutException as exc:
        raise ToolError("image.timeout", TIMEOUT_MESSAGE) from exc
    except httpx.HTTPError as exc:
        logger.warning("gemini images transport failed: %s", type(exc).__name__)
        raise ToolError("image.provider", REJECT_MESSAGE) from exc
    await _raise_http_response(response, log_name="gemini images")
    try:
        body = response.json()
    except Exception as exc:
        raise ToolError("image.invalid", INVALID_MESSAGE) from exc
    b64 = _gemini_inline_b64(body)
    if not b64:
        raise ToolError("image.invalid", INVALID_MESSAGE)
    try:
        raw = base64.b64decode(b64, validate=False)
    except Exception as exc:
        raise ToolError("image.invalid", INVALID_MESSAGE) from exc
    return _as_png_or_jpeg(raw)
