"""Thin image HTTPS adapter. New API gateway only.

Owner 2026-08-27: SiliconFlow images REJECTED.
Owner 2026-08-28: New API reverse-proxies many Gemini API keys (#752).
Pico talks only to PICO_IMAGE_GATEWAY_*. No direct Zhipu / Gemini /
SiliconFlow. No cookie farm. No Pico multi-key rotator.
"""

from __future__ import annotations

import asyncio
import base64
import ipaddress
import json
import logging
import os
import time
from collections import OrderedDict
from datetime import UTC
from email.utils import parsedate_to_datetime
from io import BytesIO
from typing import Any
from urllib.parse import urlparse

import httpx

from pico_orchestrator import upstream
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
IMAGE_TIMEOUT_S = 90.0
# Live F5 (#752) this-round glm-image 429: Retry-After header absent,
# body error.code=1113 「余额不足或无可用资源包,请充值。」. F4 single-flight +
# 2/4/8/16/30 then rate-gate ~28s still consecutive-flew and 429'd.
# Honor Retry-After (HTTP-date or seconds), cap = image timeout window.
# Missing header → rest that window before the next POST, not 28s.
# 1113 is not a rate limit — do not retry. Exhausted still
# image.provider — never invent pixels.
# 429 waits come out of the same three-request budget as everything else (pico#1271).
_429_MAX_TRIES = upstream.CALL_BUDGET
_429_RETRY_AFTER_CAP_S = IMAGE_TIMEOUT_S
_429_NON_RETRYABLE_CODES = frozenset({"1113"})
# New API answers these itself, before or instead of reaching the model: the
# same request fails the same way however often it is sent or reworded
# (relaykit/types/error.go). pico#1301: "only imagen models are supported"
# came back as HTTP 500 convert_request_failed and was sent 8× in one run.
_GATEWAY_FIXED_CODES = frozenset(
    {
        "invalid_request",
        "count_token_failed",
        "model_price_error",
        "invalid_api_type",
        "json_marshal_failed",
        "convert_request_failed",
        "access_denied",
        "bad_request_body",
        "channel:model_mapped_error",
        "channel:param_override_invalid",
        "channel:header_override_invalid",
        "channel:invalid_key",
    }
)
_GATEWAY_QUOTA_CODES = frozenset({"insufficient_user_quota", "pre_consume_token_quota_failed"})
# A run's image door shuts after this many failed requests in a row (5xx,
# transport, timeout), or at once on a fixed/quota answer. Later
# generate_image calls in the run answer at once, New API is not reached.
_RUN_FAILS_TO_SHUT = 2
_RUN_FAILS: OrderedDict[str, int] = OrderedDict()
_SHUT_RUNS: OrderedDict[str, ToolError] = OrderedDict()
_RUNS_KEPT = 512
_flight_lock = asyncio.Lock()
_glm_lock = asyncio.Lock()
_inflight: dict[str, asyncio.Future[tuple[bytes, str, dict[str, int] | None]]] = {}
_next_post_mono = 0.0
_MAX_PROMPT = 2000
_MAX_IMAGE_BYTES = 8 * 1024 * 1024
PNG_MAGIC = b"\x89PNG\r\n\x1a\n"
JPEG_MAGIC = b"\xff\xd8\xff"

# Teachers read these (the model relays them): no vendor, key or env names.
NO_KEY_MESSAGE = "出图尚未接通，请告诉学校管理员。不能编造图片。"
REJECTED_PROVIDER_MESSAGE = "这次没能出图。请稍后重试，不能编造图片。"
TIMEOUT_MESSAGE = "出图超时（90 秒）。请稍后重试，不能编造图片。"
REJECT_MESSAGE = "出图服务拒绝了这次请求。请稍后重试或换一句描述，不能编造图片。"
# 5xx / 429 / transport: the description is not the problem, rewording only resends.
BUSY_MESSAGE = "出图服务这会儿出错了，和描述怎么写无关。请稍后重试，不能编造图片。"
UNAVAILABLE_MESSAGE = (
    "出图通道这会儿接不通，和描述怎么写无关；这一轮别再调用出图，"
    "如实告诉老师稍后再试。不能编造图片。"
)
QUOTA_MESSAGE = "出图额度用完了；这一轮别再调用出图，请老师告诉学校管理员充值。不能编造图片。"
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


def gateway_root_url() -> str:
    raw = (os.environ.get("PICO_IMAGE_GATEWAY_URL") or "").strip()
    if not raw:
        return ""
    text = raw.rstrip("/")
    if text.endswith("/v1/images/generations"):
        return text[: -len("/v1/images/generations")]
    if text.endswith("/images/generations"):
        return text[: -len("/images/generations")]
    if text.endswith("/v1"):
        return text[:-3]
    return text


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


def billed_image_model() -> str:
    return gateway_model()


def gateway_uses_gemini_native() -> bool:
    """New API /v1/images/generations only maps imagen-*.

    Live QuantumNous new-api (2026-08-28): any other model on that
    path → "only imagen models are supported". Every Gemini image
    model is generateContent, whatever its name says (nano-banana has
    no "image" in it, pico#1301). Pico still talks only to New API
    (Bearer gateway token), never Google directly.
    """
    return gateway_model().lower().startswith("gemini-")


def gateway_generate_content_url() -> str:
    root = gateway_root_url()
    if not root:
        return ""
    return f"{root}/v1beta/models/{gateway_model()}:generateContent"


def allowed_image_key() -> bool:
    return bool(gateway_images_url() and gateway_key())


def selected_image_provider() -> str | None:
    """New API gateway only. Direct Zhipu/Gemini are deleted product paths."""
    if gateway_images_url() and gateway_key():
        return PROVIDER_GATEWAY
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
    _SHUT_RUNS.clear()
    _RUN_FAILS.clear()
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
    status = _http_status(response)
    rejected = isinstance(status, int) and 400 <= status < 500 and status != 429
    err = ToolError("image.provider", REJECT_MESSAGE if rejected else BUSY_MESSAGE)
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
    payload: dict[str, Any],
    *,
    api_key: str,
    timeout: float,
    url: str | None = None,
) -> httpx.Response:
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    target = (url or gateway_images_url()).strip()
    release = await upstream.acquire(api_key, "image")
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            return await client.post(target, json=payload, headers=headers)
    finally:
        release()


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
        raise ToolError("image.provider", BUSY_MESSAGE)
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


def usage_from_gemini_body(body: Any) -> dict[str, int] | None:
    if not isinstance(body, dict):
        return None
    meta = body.get("usageMetadata") or body.get("usage_metadata")
    if not isinstance(meta, dict):
        usage = body.get("usage")
        if isinstance(usage, dict):
            meta = usage
        else:
            return None
    def _n(*keys: str) -> int | None:
        for key in keys:
            raw = meta.get(key)
            if isinstance(raw, bool):
                continue
            if isinstance(raw, int) and raw >= 0:
                return raw
            if isinstance(raw, float) and raw.is_integer() and raw >= 0:
                return int(raw)
        return None

    prompt = _n("promptTokenCount", "prompt_token_count", "prompt_tokens", "input_tokens")
    completion = _n(
        "candidatesTokenCount",
        "candidates_token_count",
        "completion_tokens",
        "output_tokens",
    )
    total = _n("totalTokenCount", "total_token_count", "total_tokens")
    if prompt is None and completion is None and total is None:
        return None
    out: dict[str, int] = {}
    if prompt is not None:
        out["prompt_tokens"] = prompt
    if completion is not None:
        out["completion_tokens"] = completion
    if total is not None:
        out["total_tokens"] = total
    return out


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
    raw, ext, _usage = await generate_image_with_usage(prompt)
    return raw, ext


def _shut_error(run_id: str | None) -> ToolError | None:
    return _SHUT_RUNS.get(run_id) if run_id else None


def _keep(table: OrderedDict[str, Any], run_id: str, value: Any) -> None:
    table[run_id] = value
    table.move_to_end(run_id)
    while len(table) > _RUNS_KEPT:
        table.popitem(last=False)


def _shut_run(run_id: str | None, err: ToolError) -> ToolError:
    if run_id:
        _keep(_SHUT_RUNS, run_id, err)
    return err


def _door_failed(exc: ToolError) -> bool:
    """The request reached for the door and the door failed: 5xx, transport, timeout."""
    if exc.code == "image.timeout":
        return True
    if exc.code != "image.provider":
        return False
    status = getattr(exc, "http_status", None)
    return not isinstance(status, int) or status >= 500


def _note_door_failure(run_id: str | None) -> bool:
    """Count one failed request in the run; True once the run's door should shut."""
    if not run_id:
        return False
    n = _RUN_FAILS.get(run_id, 0) + 1
    _keep(_RUN_FAILS, run_id, n)
    return n >= _RUN_FAILS_TO_SHUT


async def generate_image_with_usage(
    prompt: str, *, run_id: str | None = None
) -> tuple[bytes, str, dict[str, int] | None]:
    """Return bytes, format, optional provider usage tokens."""
    shut = _shut_error(run_id)
    if shut is not None:
        raise ToolError(shut.code, shut.message)
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
    try:
        from app.channel_rates import require_rate

        require_rate(kind="image", model=billed_image_model())
    except ToolError:
        raise
    except ImportError:
        pass
    key = _prompt_key(text)
    async with _flight_lock:
        existing = _inflight.get(key)
        if existing is not None:
            fut: asyncio.Future[tuple[bytes, str, dict[str, int] | None]] = existing
            created = False
        else:
            fut = asyncio.get_running_loop().create_future()
            _inflight[key] = fut
            created = True
    if not created:
        return await asyncio.shield(fut)
    try:
        async with _glm_lock:
            result = await _generate_image_campaign(text, run_id=run_id)
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


async def _generate_image_campaign(
    text: str, *, run_id: str | None = None
) -> tuple[bytes, str, dict[str, int] | None]:
    await _respect_rate_gate()
    rate_tries = 0
    provider_retried = False
    # 429 waits and the one provider retry share the door's budget (pico#1271):
    # a refused extra ends the campaign with the last answer.
    call = upstream.Call("image", run_id=run_id)
    last: ToolError | None = None
    while True:
        if not call.allow() and last is not None:
            raise last
        try:
            result = await _generate_image_call(text)
        except ToolError as exc:
            last = exc
            if exc.code == "image.unconfigured":
                raise _shut_run(run_id, exc)
            status = getattr(exc, "http_status", None)
            error_code = str(getattr(exc, "zhipu_error_code", None) or "")
            if exc.code == "image.provider" and error_code in _GATEWAY_QUOTA_CODES:
                raise _shut_run(run_id, ToolError("image.unavailable", QUOTA_MESSAGE)) from exc
            fixed = exc.code == "image.provider" and error_code in _GATEWAY_FIXED_CODES
            if fixed or (_door_failed(exc) and _note_door_failure(run_id)):
                logger.warning(
                    "images gateway %s HTTP %s error_code=%s; run image door shut",
                    exc.code,
                    status,
                    error_code or None,
                )
                shut = ToolError("image.unavailable", UNAVAILABLE_MESSAGE)
                raise _shut_run(run_id, shut) from exc
            if exc.code != "image.provider":
                raise
            if status == 429:
                retry_after = getattr(exc, "retry_after", None)
                error_code = str(getattr(exc, "zhipu_error_code", None) or "").strip()
                delay = _429_delay_s(retry_after)
                if error_code in _429_NON_RETRYABLE_CODES:
                    delay = _429_RETRY_AFTER_CAP_S
                _arm_rate_gate(delay)
                no_retry = (
                    call.sent >= call.budget
                    or error_code in _429_NON_RETRYABLE_CODES
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
            if provider_retried or call.sent >= call.budget:
                raise
            logger.warning("images provider failed; retrying once")
            provider_retried = True
            continue
        if run_id:
            _RUN_FAILS.pop(run_id, None)
        return result


async def _generate_image_call(text: str) -> tuple[bytes, str, dict[str, int] | None]:
    kind = selected_image_provider()
    if kind == PROVIDER_GATEWAY:
        return await _generate_gateway_call(text)
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
            raise ToolError("image.provider", BUSY_MESSAGE) from exc
    else:
        raise ToolError("image.invalid", INVALID_MESSAGE)
    return _as_png_or_jpeg(raw)


async def _generate_gateway_call(text: str) -> tuple[bytes, str, dict[str, int] | None]:
    if gateway_uses_gemini_native():
        payload = {
            "contents": [{"role": "user", "parts": [{"text": text}]}],
            "generationConfig": {"responseModalities": ["TEXT", "IMAGE"]},
        }
        try:
            response = await _post_gateway(
                payload,
                api_key=gateway_key(),
                timeout=IMAGE_TIMEOUT_S,
                url=gateway_generate_content_url(),
            )
        except httpx.TimeoutException as exc:
            raise ToolError("image.timeout", TIMEOUT_MESSAGE) from exc
        except httpx.HTTPError as exc:
            logger.warning("gateway generateContent transport failed: %s", type(exc).__name__)
            raise ToolError("image.provider", BUSY_MESSAGE) from exc
        await _raise_http_response(response, log_name="gateway generateContent")
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
        png, ext = _as_png_or_jpeg(raw)
        return png, ext, usage_from_gemini_body(body)

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
        raise ToolError("image.provider", BUSY_MESSAGE) from exc
    await _raise_http_response(response, log_name="gateway images")
    try:
        body = response.json()
    except Exception as exc:
        raise ToolError("image.invalid", INVALID_MESSAGE) from exc
    raw, ext = await _bytes_from_openai_image_body(body)
    return raw, ext, usage_from_gemini_body(body)
