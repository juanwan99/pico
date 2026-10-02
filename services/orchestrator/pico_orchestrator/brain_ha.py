"""Thin chat failover: same New API, next model if the current one has no channel.

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
)


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


# Mid-run (the model already worked): Pi's retries on the same model this many
# times in a row before the session switches to the next backup (#1160).
SWITCH_AFTER_RETRIES = 3


def should_switch_mid_run(attempt: int, error: str) -> bool:
    """Pi's consecutive retry ``attempt`` failed with ``error``: try a backup now?

    An overload is New API shedding load and hits every model the same, so it
    keeps Pi's own backoff. A broken stream or 5xx on one channel does not.
    """
    return int(attempt or 0) >= SWITCH_AFTER_RETRIES and not is_upstream_overloaded(error)


def should_failover(result: Any) -> bool:
    if str(getattr(result, "status", "") or "") != "failed":
        return False
    err = str(getattr(result, "error", "") or "").lower()
    code = str(getattr(result, "code", "") or "").lower()
    blob = f"{code} {err}"
    return any(m in blob for m in _FAILOVER_MARKERS)


def fallback_teacher_note(from_model: str, to_model: str) -> str:
    return (
        f"主渠道（{from_model}）暂时不可用，已改用备用模型 {to_model} 继续。"
        "不是你的问题写错。"
    )


def switch_teacher_note(to_model: str) -> str:
    return f"（主模型连续几次没有回应，已换备用模型 {to_model} 接着做，前面的进度都在）\n"
