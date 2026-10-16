"""Teacher speaks while a turn still runs (pico#1318).

Thin: one in-process map from a teacher's conversation to the live Pi client
of its running turn. A new message goes into Pi's own steer queue — Pi
delivers it after the running tools, before its next model call, so the turn
changes course without throwing away what it already did.

Not live in this process (other runtime, turn settled, API restarted) → the
caller falls back to the #1250 takeover. Never a second queue or ledger.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

Key = tuple[str, str, str]


@dataclass
class LiveTurn:
    client: Any
    # Open only while a prompt drives Pi and it has not settled: a steer
    # queued on an idle Pi would wait silently for a prompt that never comes.
    open: bool = False
    # Accepted by Pi but not yet seen injected (message_start role=user).
    pending: list[str] = field(default_factory=list)
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)

    def seen(self, text: str) -> bool:
        if text in self.pending:
            self.pending.remove(text)
            return True
        return False

    def take_pending(self) -> list[str]:
        out, self.pending = self.pending, []
        return out


_LIVE: dict[Key, LiveTurn] = {}


def turn_key(school_id: Any, membership_id: Any, conversation_id: Any) -> Key | None:
    parts = (str(school_id or ""), str(membership_id or ""), str(conversation_id or ""))
    return parts if all(parts) else None


def register(key: Key | None, client: Any) -> LiveTurn | None:
    if key is None:
        return None
    live = LiveTurn(client=client)
    _LIVE[key] = live
    return live


def unregister(key: Key | None, live: LiveTurn | None) -> None:
    if key is not None and live is not None and _LIVE.get(key) is live:
        del _LIVE[key]


async def steer(key: Key | None, text: str) -> bool:
    """Hand ``text`` to the live turn of this conversation. False → take over instead."""
    live = _LIVE.get(key) if key is not None else None
    text = (text or "").strip()
    if live is None or not text:
        return False
    async with live.lock:
        if not live.open:
            return False
        # Pending before the RPC: Pi may inject it (message_start role=user)
        # before its steer ack reaches us. Recorded only after the ack, it would
        # stay pending and be said again as a late prompt — run twice.
        live.pending.append(text)
        try:
            await live.client.steer(text)
        except Exception as exc:  # noqa: BLE001 — a refused steer falls back to takeover
            logger.warning("true_pi teacher steer failed: %s", type(exc).__name__)
            if text in live.pending:
                live.pending.remove(text)
            return False
    return True
