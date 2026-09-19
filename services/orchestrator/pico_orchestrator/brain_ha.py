"""Thin chat failover: same New API, next model if the current one has no channel.

Not a second router. Gemini Vertex is primary; Grok / GPT-5.6-sol are backups.
Teacher is told when a backup is used. Tests inject transport and skip this loop.
"""

from __future__ import annotations

import os
from typing import Any

_FAILOVER_MARKERS = (
    "no available channel",
    "failed to get available channel",
    "model_not_found",
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
