"""Thin chat failover: same New API, next model if the current one is down.

Not a second router. Gemini Vertex is primary; Grok / GPT-5.6-sol are backups.
Teacher is told when a backup is used. Tests inject transport and skip this loop.
"""

from __future__ import annotations

import os
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


def configured_fallbacks() -> list[str]:
    raw = (os.environ.get("PICO_BRAIN_FALLBACKS") or "grok-4.6,gpt-5.6-sol").strip()
    out: list[str] = []
    for part in raw.split(","):
        mid = part.strip()
        if mid and mid not in out:
            out.append(mid)
    return out


def brain_candidates(primary: str | None) -> list[str]:
    head = (primary or "").strip()
    out: list[str] = []
    if head:
        out.append(head)
    for mid in configured_fallbacks():
        if mid not in out:
            out.append(mid)
    return out or [head] if head else []


def is_channel_dead(error: str) -> bool:
    low = (error or "").lower()
    return any(m in low for m in _CHANNEL_DEAD_MARKERS)


def is_upstream_overloaded(error: str) -> bool:
    """New API load shedding / rate limit: the same wait hits every model."""
    low = (error or "").lower()
    return "overloaded" in low or "429" in low or "rate limit" in low


def is_failover_error(error: str, *, first: bool = False) -> bool:
    low = (error or "").lower()
    if any(m in low for m in _FAILOVER_MARKERS):
        return True
    return first and any(m in low for m in _FIRST_HOP_MARKERS)


def should_failover(result: Any, *, first: bool = False) -> bool:
    if str(getattr(result, "status", "") or "") != "failed":
        return False
    err = str(getattr(result, "error", "") or "")
    code = str(getattr(result, "code", "") or "")
    return is_failover_error(f"{code} {err}", first=first)


def fallback_teacher_note(from_model: str, to_model: str) -> str:
    return (
        f"主渠道（{from_model}）暂时不可用，已改用备用模型 {to_model} 继续。"
        "不是你的问题写错。"
    )
