"""Thin chat failover: same New API, next model if the current one is down.

Not a second router. Gemini Vertex is primary; DeepSeek, then Grok / GPT-5.6-sol
are backups (edu-core#3509).
The switch is invisible to the teacher. Tests inject transport and skip this loop.
"""

from __future__ import annotations

import os
import re
import time
from typing import Any

from pico_orchestrator.upstream import DEAD_STATUS

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
# Only the relay's own words count: a bare 401 / 403 is also what our run
# proxy answers (proxy.no_run, auth.denied) and says nothing about the model.
_KEY_DEAD_MARKERS = (
    "permission_error",
    "已被暂停",
    "密钥无效",
    "suspended",
    "unauthorized",
    "invalid api key",
    "invalid_api_key",
    "insufficient_quota",
    "quota",
    "额度",
    "余额",
)
# Pi run codes that mean the model call itself failed (not the runner / tools).
_MODEL_FAIL_CODES = ("true_pi.assistant_error", "model.usage_limit", "model.unconfigured")
DOWN_ENV = "PICO_BRAIN_DOWN_S"
_DOWN_DEFAULT_S = 300.0
_down_until: dict[str, float] = {}
# A whole channel can stall for minutes (10-15 09:30: four gemini hedges of one
# Pi step all waited 134 s for the first token). Same-model hedges cannot get
# out of that; the next model can. Fast lane only: deep thinking is slow on purpose.
PI_STALL_ENV = "PICO_PI_STALL_SWITCH_S"
_PI_STALL_DEFAULT_S = 25.0
FIRST_TOKEN_STALL = "first token stall"
STALL_DOWN_S = 120.0


# Models behind AIProxy, a coding subscription: it only takes what a coding
# client does — one session, many rounds, context carried on (owner 10-18
# 07:3x PDT「根本不是速率问题 是使用方式问题」, pico#1344). Only a Pi run (one
# conversation, many steps) may use them; one-shot calls (direct answers,
# grading, JSON, titles) never do. Unset = the AIProxy model; "" = no limit.
LONG_SESSION_ENV = "PICO_LONG_SESSION_MODELS"
_LONG_SESSION_DEFAULT = "gpt-5.6-sol"


def long_session_models() -> set[str]:
    raw = os.environ.get(LONG_SESSION_ENV)
    if raw is None:
        raw = _LONG_SESSION_DEFAULT
    return {m.strip() for m in raw.split(",") if m.strip()}


# DeepSeek official (New API channel 8) first: its own quota, reads images (edu-core#3509).
DEFAULT_FALLBACKS = "deepseek-flash,grok-4.6,gpt-5.6-sol"


def configured_fallbacks() -> list[str]:
    raw = (os.environ.get("PICO_BRAIN_FALLBACKS") or DEFAULT_FALLBACKS).strip()
    out: list[str] = []
    for part in raw.split(","):
        mid = part.strip()
        if mid and mid not in out:
            out.append(mid)
    return out


def brain_candidates(primary: str | None, *, long_session: bool = False) -> list[str]:
    """Primary then fallbacks; a model marked down goes last (still a last resort).

    Without ``long_session`` the AIProxy models are left out, the primary too:
    the list can come back empty, and the caller says so instead of using them.
    """
    head = (primary or "").strip()
    out: list[str] = []
    if head:
        out.append(head)
    for mid in configured_fallbacks():
        if mid not in out:
            out.append(mid)
    if not long_session:
        only_long = long_session_models()
        out = [m for m in out if m not in only_long]
    up = [m for m in out if not is_down(m)]
    return up + [m for m in out if m not in up]


def one_shot_model(model: str | None) -> str | None:
    """The model a one-shot call (web search, query expansion) may use: ``model``
    unless it is AIProxy-only, else the first fallback that is not; None if none."""
    models = brain_candidates(model)
    return models[0] if models else None


def mark_down(model: str, seconds: float | None = None) -> None:
    """Skip a dead channel / key for a while instead of hitting it on every call."""
    span = seconds
    if span is None:
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
    return any(m in low for m in _KEY_DEAD_MARKERS)


def is_relay_key_dead(error: str) -> bool:
    """The relay itself answered 401 / 402 / 403 (noted by the run proxy, pico#1271).

    Our own proxy's 403 (``proxy.no_run``, ``auth.denied``) never gets an
    ``upstream <status>`` note, so a bare relay 403 still counts (#1263).
    """
    m = re.search(r"\bupstream (\d{3})\b", error or "")
    return bool(m) and int(m.group(1)) in DEAD_STATUS


def is_model_dead(error: str) -> bool:
    """This model cannot answer any call now: no channel, or its key is dead."""
    return is_channel_dead(error) or is_key_dead(error) or is_relay_key_dead(error)


def pi_stall_switch_s() -> float:
    """Seconds without a first token before a Pi fast-lane run moves on (0 = off)."""
    try:
        return max(0.0, float(os.environ.get(PI_STALL_ENV) or _PI_STALL_DEFAULT_S))
    except ValueError:
        return _PI_STALL_DEFAULT_S


def is_stall(error: str) -> bool:
    return FIRST_TOKEN_STALL in (error or "")


def is_upstream_overloaded(error: str) -> bool:
    """New API load shedding / rate limit: the same wait hits every model."""
    low = (error or "").lower()
    return "overloaded" in low or "429" in low or "rate limit" in low


def is_failover_error(error: str, *, first: bool = False) -> bool:
    low = (error or "").lower()
    if any(m in low for m in _FAILOVER_MARKERS) or is_key_dead(low) or is_relay_key_dead(low):
        return True
    return first and any(m in low for m in _FIRST_HOP_MARKERS)


def should_failover(result: Any, *, first: bool = False, relay: str = "") -> bool:
    """``relay``: what the relay itself last answered this run (``upstream <status> …``)."""
    if str(getattr(result, "status", "") or "") != "failed":
        return False
    err = str(getattr(result, "error", "") or "")
    code = str(getattr(result, "code", "") or "")
    # The primary's model call failed before any output: whatever the relay
    # said (formats change), the next model gets one try.
    if first and code in _MODEL_FAIL_CODES:
        return True
    return is_failover_error(f"{code} {err} {relay}", first=first)
