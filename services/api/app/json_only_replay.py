"""Replay an identical edu json_only answer for 10 minutes (#1204).

Edu's steward re-sends the very same JSON envelope (72% of its calls, half
within 96 s). Same tenant + member + same model input → hand back the last
successful answer: no model call, no run, no usage row. Process-local only;
a restart just empties it. Not a general cache: callers decide what is
replayable, a miss is the normal path.
"""

from __future__ import annotations

import hashlib
import json
import time
from collections import OrderedDict
from typing import Any

TTL_S = 600.0
MAX_ENTRIES = 512

_entries: OrderedDict[str, tuple[float, dict[str, Any]]] = OrderedDict()


def replay_key(*, school_id: str, membership_id: str, **model_input: Any) -> str:
    raw = json.dumps(
        {"school": school_id, "member": membership_id, **model_input},
        ensure_ascii=False,
        sort_keys=True,
        default=str,
    )
    return hashlib.sha256(raw.encode()).hexdigest()


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


def clear() -> None:
    _entries.clear()
