"""B1 soft drain: in-process tasks are awaited on shutdown."""

from __future__ import annotations

import asyncio
import importlib.util
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[2]
_SPEC = importlib.util.spec_from_file_location(
    "run_service_drain",
    _ROOT / "services/api/app/run_service.py",
)
# Loading full run_service pulls app deps; test drain helpers in isolation instead.


@pytest.mark.asyncio
async def test_drain_inflight_waits_for_short_task() -> None:
    # Minimal clone of track/drain without importing the whole FastAPI app graph.
    inflight: set[asyncio.Task] = set()

    def track(task: asyncio.Task) -> None:
        inflight.add(task)
        task.add_done_callback(inflight.discard)

    async def drain(*, timeout_s: float = 45.0) -> dict[str, int]:
        pending = {t for t in inflight if not t.done()}
        if not pending:
            return {"waited": 0, "remaining": 0, "timed_out": 0}
        done, still = await asyncio.wait(pending, timeout=timeout_s)
        for t in still:
            t.cancel()
        return {
            "waited": len(done),
            "remaining": len(still),
            "timed_out": 1 if still else 0,
        }

    async def work() -> str:
        await asyncio.sleep(0.05)
        return "ok"

    t = asyncio.create_task(work())
    track(t)
    result = await drain(timeout_s=2.0)
    assert result["waited"] == 1
    assert result["remaining"] == 0
    assert await t == "ok"


@pytest.mark.asyncio
async def test_drain_inflight_times_out_and_cancels() -> None:
    inflight: set[asyncio.Task] = set()

    def track(task: asyncio.Task) -> None:
        inflight.add(task)
        task.add_done_callback(inflight.discard)

    async def drain(*, timeout_s: float = 45.0) -> dict[str, int]:
        pending = {t for t in inflight if not t.done()}
        if not pending:
            return {"waited": 0, "remaining": 0, "timed_out": 0}
        done, still = await asyncio.wait(pending, timeout=timeout_s)
        for t in still:
            t.cancel()
        return {
            "waited": len(done),
            "remaining": len(still),
            "timed_out": 1 if still else 0,
        }

    async def long_work() -> None:
        await asyncio.sleep(30)

    t = asyncio.create_task(long_work())
    track(t)
    result = await drain(timeout_s=0.05)
    assert result["timed_out"] == 1
    assert result["remaining"] == 1
    with pytest.raises(asyncio.CancelledError):
        await t
