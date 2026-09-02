"""Thin extract of official Pi thinking blocks. Not a second kernel."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

_MAX_DELTA = 4000


def thinking_delta_from_rpc(obj: Mapping[str, Any] | None) -> str:
    """Return the official ``thinking_delta`` chunk, or empty.

    Full ``message_update`` payloads stay dropped (OOM). Only this small
    delta is allowed back onto the RPC queue.
    """
    if not isinstance(obj, Mapping):
        return ""
    ame = obj.get("assistantMessageEvent")
    if not isinstance(ame, dict):
        return ""
    if str(ame.get("type") or "") != "thinking_delta":
        return ""
    return str(ame.get("delta") or "")[:_MAX_DELTA]


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
