"""Thin chat failover: same New API, next model if the current one is down.

Not a second router. Gemini Vertex is primary; Grok / GPT-5.6-sol are backups.
The switch is invisible to the teacher. Tests inject transport and skip this loop.
"""

from __future__ import annotations

import os
import re
import time
from typing import Any

# New API has no channel for this model: retrying the same model cannot help.
_CHANNEL_DEAD_MARKERS = (
    "no available channel",
    "failed to get available channel",
    "model_not_found",
    "无可用渠道",
)
_FAILOVER_MARKERS = (
    *_CHANNEL_DEAD_MARKERS,
    "http 503",
    "http 502",
    "temporarily unavailable",
    "connection",
    "upstream",
    "model.unconfigured",
    # AIProxy relay (gpt-5.6-sol) answered every image call with 400 "try again
    # later" for hours (#1248); the next model on the same New API was fine.
    "aiproxy_api_error",
    "try again later",
)
# A 400 the primary rejects may be its relay, not the request: one hop only.
# The next model rejecting it too means the request itself is bad.
_FIRST_HOP_MARKERS = ("invalid_request", "invalid request")
# The key behind this model's channel is suspended / unauthorised / out of
# quota (10-15: sol's upstream answered every call 403 "API密钥已被暂停" for
# 23 minutes while flash was fine). Other models ride other channels' keys.
_KEY_DEAD_MARKERS = (
    "permission_error",
    "已被暂停",
    "密钥无效",
    "未授权",
    "suspended",
    "unauthorized",
    "forbidden",
    "invalid api key",
    "invalid_api_key",
    "insufficient_quota",
    "quota",
    "额度",
    "余额",
)
_KEY_DEAD_STATUS = re.compile(r"(?<!\d)(401|402|403)(?!\d)")
# Pi run codes that mean the model call itself failed (not the runner / tools).
_MODEL_FAIL_CODES = ("true_pi.assistant_error", "model.usage_limit", "model.unconfigured")
DOWN_ENV = "PICO_BRAIN_DOWN_S"
_DOWN_DEFAULT_S = 300.0
_down_until: dict[str, float] = {}


def configured_fallbacks() -> list[str]:
    raw = (os.environ.get("PICO_BRAIN_FALLBACKS") or "grok-4.6,gpt-5.6-sol").strip()
    out: list[str] = []
    for part in raw.split(","):
        mid = part.strip()
        if mid and mid not in out:
            out.append(mid)
    return out


def brain_candidates(primary: str | None) -> list[str]:
    """Primary then fallbacks; a model marked down goes last (still a last resort)."""
    head = (primary or "").strip()
    out: list[str] = []
    if head:
        out.append(head)
    for mid in configured_fallbacks():
        if mid not in out:
            out.append(mid)
    up = [m for m in out if not is_down(m)]
    return up + [m for m in out if m not in up]


def mark_down(model: str) -> None:
    """Skip a dead channel / key for a while instead of hitting it on every call."""
    try:
        span = float(os.environ.get(DOWN_ENV) or _DOWN_DEFAULT_S)
    except ValueError:
        span = _DOWN_DEFAULT_S
    if model and span > 0:
        _down_until[model] = time.monotonic() + span


def is_down(model: str) -> bool:
    until = _down_until.get(model)
    if until is None:
        return False
    if time.monotonic() >= until:
        _down_until.pop(model, None)
        return False
    return True


def is_channel_dead(error: str) -> bool:
    low = (error or "").lower()
    return any(m in low for m in _CHANNEL_DEAD_MARKERS)


def is_key_dead(error: str) -> bool:
    low = (error or "").lower()
    return any(m in low for m in _KEY_DEAD_MARKERS) or bool(_KEY_DEAD_STATUS.search(low))


def is_model_dead(error: str) -> bool:
    """This model cannot answer any call now: no channel, or its key is dead."""
    return is_channel_dead(error) or is_key_dead(error)


def is_upstream_overloaded(error: str) -> bool:
    """New API load shedding / rate limit: the same wait hits every model."""
    low = (error or "").lower()
    return "overloaded" in low or "429" in low or "rate limit" in low


def is_failover_error(error: str, *, first: bool = False) -> bool:
    low = (error or "").lower()
    if any(m in low for m in _FAILOVER_MARKERS) or is_key_dead(low):
        return True
    return first and any(m in low for m in _FIRST_HOP_MARKERS)


def should_failover(result: Any, *, first: bool = False) -> bool:
    if str(getattr(result, "status", "") or "") != "failed":
        return False
    err = str(getattr(result, "error", "") or "")
    code = str(getattr(result, "code", "") or "")
    # The primary's model call failed before any output: whatever the relay
    # said (formats change), the next model gets one try.
    if first and code in _MODEL_FAIL_CODES:
        return True
    return is_failover_error(f"{code} {err}", first=first)
