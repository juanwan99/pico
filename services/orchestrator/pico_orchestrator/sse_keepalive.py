"""SSE comment frames so Cloudflare / nginx do not idle-drop long runs.

Not a second stream protocol. Callers already speak text/event-stream.
A ``:`` comment is ignored by EventSource clients and does not enter the bubble.
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import AsyncIterator
from contextlib import suppress
from typing import Any

SSE_COMMENT_KEEPALIVE = b": keepalive\n\n"
SSE_KEEPALIVE_SECONDS = 15.0
SSE_IDLE_POLL_SECONDS = 1.0

SSE_STREAM_HEADERS = {
    "Cache-Control": "no-cache, no-transform",
    "X-Accel-Buffering": "no",
    "Connection": "keep-alive",
}


def is_proxy_first_byte_timeout(exc: BaseException) -> bool:
    """Cloudflare/AIProxy 524: origin did not flush the first HTTP byte in time."""
    code = getattr(exc, "status_code", None)
    if code == 524:
        return True
    msg = str(exc).lower()
    return "524" in msg or "aiproxy service is temporarily unavailable" in msg


async def iter_with_idle_ticks(
    agen: AsyncIterator[Any],
    *,
    poll_s: float = SSE_IDLE_POLL_SECONDS,
    idle_s: float = SSE_KEEPALIVE_SECONDS,
) -> AsyncIterator[Any | None]:
    """Yield ``None`` when the inner iterator is silent for ``idle_s`` seconds.

    Does not cancel the in-flight ``__anext__`` on an idle tick (that would
    abort the upstream model stream).
    """
    it = agen.__aiter__()
    nxt: asyncio.Task[Any] = asyncio.create_task(it.__anext__())
    last = time.monotonic()
    try:
        while True:
            done, _pending = await asyncio.wait({nxt}, timeout=max(0.05, float(poll_s)))
            if not done:
                if time.monotonic() - last >= float(idle_s):
                    last = time.monotonic()
                    yield None
                continue
            try:
                item = nxt.result()
            except StopAsyncIteration:
                return
            last = time.monotonic()
            yield item
            nxt = asyncio.create_task(it.__anext__())
    finally:
        if not nxt.done():
            nxt.cancel()
            with suppress(BaseException):
                await nxt
