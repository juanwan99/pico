"""Thin extract of official Pi thinking blocks. Not a second kernel."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

_MAX_DELTA = 4000


def _ame_delta(obj: Mapping[str, Any] | None, want: str) -> str:
    if not isinstance(obj, Mapping):
        return ""
    ame = obj.get("assistantMessageEvent")
    if not isinstance(ame, dict):
        return ""
    if str(ame.get("type") or "") != want:
        return ""
    return str(ame.get("delta") or "")[:_MAX_DELTA]


def thinking_delta_from_rpc(obj: Mapping[str, Any] | None) -> str:
    """Return the official ``thinking_delta`` chunk, or empty.

    Full ``message_update`` payloads stay dropped (OOM). Only this small
    delta is allowed back onto the RPC queue.
    """
    return _ame_delta(obj, "thinking_delta")


def text_delta_from_rpc(obj: Mapping[str, Any] | None) -> str:
    """Return the official ``text_delta`` chunk, or empty.

    Same flood rule as thinking: never enqueue the accumulated message body.
    """
    return _ame_delta(obj, "text_delta")


def product_text_snapshot(obj: Mapping[str, Any] | None) -> str:
    """Visible assistant text on a ``message_update``. Not thinking, not tools."""
    if not isinstance(obj, Mapping):
        return ""
    msg = obj.get("message")
    if not isinstance(msg, dict):
        return ""
    content = msg.get("content")
    if isinstance(content, str):
        return content
    if not isinstance(content, list):
        return ""
    parts: list[str] = []
    for block in content:
        if not isinstance(block, dict):
            continue
        if str(block.get("type") or "") != "text":
            continue
        parts.append(str(block.get("text") or ""))
    return "".join(parts)


def incremental_text_from_update(obj: Mapping[str, Any] | None, seen: int) -> tuple[str, int]:
    """Small new product slice. Prefer official text_delta; else snapshot suffix."""
    have = max(0, int(seen))
    official = text_delta_from_rpc(obj)
    snap = product_text_snapshot(obj)
    if snap and len(snap) < have:
        have = 0
    if official:
        return official, max(have + len(official), len(snap))
    if len(snap) <= have:
        return "", have
    piece = snap[have:][:_MAX_DELTA]
    return piece, have + len(piece)


def thinking_from_message(msg: Mapping[str, Any] | None) -> str:
    """Join official ``{type: thinking}`` content blocks. Never product text."""
    if not isinstance(msg, Mapping):
        return ""
    content = msg.get("content")
    if not isinstance(content, list):
        return ""
    parts: list[str] = []
    for block in content:
        if not isinstance(block, dict):
            continue
        if str(block.get("type") or "") != "thinking":
            continue
        parts.append(str(block.get("thinking") or block.get("text") or ""))
    return "".join(parts).strip()
