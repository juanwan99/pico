"""Replay an identical edu json_only answer for 10 minutes (#1204).

Edu's steward re-sends the very same JSON envelope (72% of its calls, half
within 96 s). Same tenant + member + same model input → hand back the last
successful answer: no model call, no run, no usage row. A caller that hung
up (steward's 15 s budget) still gets its answer stored here (pico#1257).
Process-local only; a restart just empties it. Not a general cache: callers decide what is
replayable, a miss is the normal path.

A re-send that arrives while the first is still being answered joins that
answer (pico#1271 / #1259): one model call, not one per re-send.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import re
import time
from collections import OrderedDict
from typing import Any

TTL_S = 600.0
MAX_ENTRIES = 512

_entries: OrderedDict[str, tuple[float, dict[str, Any]]] = OrderedDict()
_inflight: dict[str, asyncio.Task] = {}


def replay_key(*, school_id: str, membership_id: str, **model_input: Any) -> str:
    raw = json.dumps(
        {"school": school_id, "member": membership_id, **model_input},
        ensure_ascii=False,
        sort_keys=True,
        default=str,
    )
    return hashlib.sha256(raw.encode()).hexdigest()


_FENCE = re.compile(r"```(?:json)?\s*([\s\S]*?)```", re.IGNORECASE)


def holds_json(text: str) -> bool:
    """The answer carries a parseable JSON object / array (fenced or bare).

    A model that slips a stray token into its JSON (edu-core#5619: ``… prisoners]}``)
    still finishes with "stop"; keeping that answer would hand the same broken
    reply to every re-send for 10 minutes instead of asking again.
    """
    raw = str(text or "").strip()
    fence = _FENCE.search(raw)
    blob = fence.group(1) if fence else raw
    starts = [i for i in (blob.find("{"), blob.find("[")) if i >= 0]
    if not starts:
        return False
    start = min(starts)
    end = blob.rfind("}" if blob[start] == "{" else "]")
    if end <= start:
        return False
    try:
        json.loads(blob[start : end + 1])
    except ValueError:  # swallow-ok: 解析不出就是不可回放，照常不存
        return False
    return True


def get(key: str) -> dict[str, Any] | None:
    hit = _entries.get(key)
    if hit is None:
        return None
    stored_at, payload = hit
    if time.monotonic() - stored_at > TTL_S:
        _entries.pop(key, None)
        return None
    return payload


def put(key: str, payload: dict[str, Any]) -> None:
    _entries[key] = (time.monotonic(), payload)
    _entries.move_to_end(key)
    while len(_entries) > MAX_ENTRIES:
        _entries.popitem(last=False)


def running(key: str) -> asyncio.Task | None:
    """The answer for this key still being computed, if any."""
    task = _inflight.get(key)
    return task if task is not None and not task.done() else None


def track(key: str, task: asyncio.Task) -> None:
    _inflight[key] = task

    def _drop(done: asyncio.Task) -> None:
        if _inflight.get(key) is done:
            _inflight.pop(key, None)

    task.add_done_callback(_drop)


def clear() -> None:
    _entries.clear()
    _inflight.clear()
