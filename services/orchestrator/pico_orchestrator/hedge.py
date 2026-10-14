"""Hedged first-token race for model calls (pico#1257).

The relay's time to first token is heavy-tailed and independent per request
(gpt-5.6-sol, 3 days of New API ``frt``: p50 6 s, p90 34 s, 1 in 3 over 12 s;
the same tiny prompt took 3 s or 67 s). Waiting on one request until it errors
is what made Pico unusable. Instead: if no first token after ``delays[0]`` s,
fire a second request; after ``delays[1]`` a third; the first one to produce a
token wins and the rest are cancelled. A failed attempt is replaced at once.

New API only sends response headers with the first token, so "opened" and
"first token" are the same moment for both the SDK path and the raw proxy.
"""

from __future__ import annotations

import asyncio
import os
from collections.abc import Awaitable, Callable, Sequence
from contextlib import suppress

HEDGE_FAST_ENV = "PICO_HEDGE_FAST_S"
HEDGE_DEEP_ENV = "PICO_HEDGE_DEEP_S"
# Fast lane: live A/B 10-14 (20 alternating calls): 1.5/4/8 s → first-token
# p90 7.6 s vs 21 s unhedged. Cancelled losers bill 0 in New API.
_FAST_DEFAULT = (1.5, 4.0, 8.0)
# Deep thinking legitimately holds the first token for tens of seconds.
_DEEP_DEFAULT = (25.0, 50.0)


def _parse(raw: str | None, default: Sequence[float]) -> list[float]:
    if raw is None or not raw.strip():
        return list(default)
    if raw.strip().lower() in {"0", "off", "none"}:
        return []
    out: list[float] = []
    for part in raw.split(","):
        with suppress(ValueError):
            v = float(part.strip())
            if v >= 0:
                out.append(v)
    return sorted(out)


def hedge_delays(*, deep: bool) -> list[float]:
    """Seconds after start at which the 2nd, 3rd, … attempt fires."""
    if deep:
        return _parse(os.environ.get(HEDGE_DEEP_ENV), _DEEP_DEFAULT)
    return _parse(os.environ.get(HEDGE_FAST_ENV), _FAST_DEFAULT)


async def race_first[T](
    start: Callable[[int], Awaitable[T] | None],
    delays: Sequence[float],
    *,
    relaunch: Callable[[BaseException], bool],
    discard: Callable[[T], Awaitable[None]],
) -> tuple[T, int]:
    """First attempt to succeed wins: ``(result, attempt_index)``.

    ``start(k)`` opens attempt ``k`` (returns None when there is no attempt k).
    It must clean up after itself when cancelled. Attempt k>0 starts at
    ``delays[k-1]`` s, or at once when an attempt fails and ``relaunch(exc)``.
    Extra winners are passed to ``discard``. If every attempt fails, the last
    error is raised.
    """
    loop = asyncio.get_running_loop()
    t0 = loop.time()
    pending: dict[asyncio.Future, int] = {}
    launched = 0
    exhausted = False
    last_exc: BaseException | None = None
    winner: asyncio.Future | None = None

    def launch() -> None:
        nonlocal launched, exhausted
        if exhausted:
            return
        aw = start(launched)
        if aw is None:
            exhausted = True
            return
        pending[asyncio.ensure_future(aw)] = launched
        launched += 1

    launch()
    try:
        while pending:
            timeout = None
            if not exhausted and launched - 1 < len(delays):
                timeout = max(0.0, t0 + delays[launched - 1] - loop.time())
            done, _ = await asyncio.wait(
                pending, timeout=timeout, return_when=asyncio.FIRST_COMPLETED
            )
            if not done:
                launch()
                continue
            failed_retry = False
            for fut in sorted(done, key=lambda f: pending[f]):
                idx = pending.pop(fut)
                exc = fut.exception()
                if exc is None:
                    if winner is None:
                        winner = fut
                        winner_idx = idx
                    else:
                        with suppress(Exception):
                            await discard(fut.result())
                    continue
                last_exc = exc
                failed_retry = failed_retry or relaunch(exc)
            if winner is not None:
                return winner.result(), winner_idx
            if failed_retry:
                launch()
        if last_exc is not None:
            raise last_exc
        raise RuntimeError("no model attempt was started")
    finally:
        for fut in pending:
            fut.cancel()
        for fut in list(pending):
            with suppress(BaseException):
                res = await fut
                if fut is not winner:
                    with suppress(Exception):
                        await discard(res)
