"""T-ASK-USER · park until the teacher picks."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "orchestrator"))

from pico_orchestrator.ask_user import answer, cancel, park, pending
from pico_orchestrator.capability_loading import CORE_VISIBLE_TOOLS
from pico_orchestrator.true_pi.config import ALLOWED_GATEWAY_TOOLS


def test_ask_user_is_core_visible() -> None:
    assert "ask_user" in CORE_VISIBLE_TOOLS
    assert "ask_user" in ALLOWED_GATEWAY_TOOLS


async def test_park_resolves_on_answer() -> None:
    events: list[tuple[str, dict]] = []

    async def emit(kind: str, payload: dict) -> None:
        events.append((kind, payload))

    async def picker() -> None:
        for _ in range(50):
            if pending("run-ask"):
                assert answer("run-ask", "解释一下")
                return
            await asyncio.sleep(0.01)
        raise AssertionError("never parked")

    parked, _ = await asyncio.gather(
        park("run-ask", "你想做什么？", ["解释一下", "改文件"], emit, timeout=2),
        picker(),
    )
    assert parked == {"ok": True, "answer": "解释一下", "question": "你想做什么？"}
    kinds = [item[0] for item in events]
    assert kinds == ["ui.prompt.begin", "ui.prompt.end"]
    assert events[0][1]["options"] == ["解释一下", "改文件"]
    assert pending("run-ask") is None


async def test_park_timeout_is_error_not_answer() -> None:
    events: list[tuple[str, dict]] = []

    async def emit(kind: str, payload: dict) -> None:
        events.append((kind, payload))

    out = await park(
        "run-to",
        "计划好了，下一步？",
        ["确认执行", "先不执行"],
        emit,
        timeout=0.05,
    )
    assert out["ok"] is False
    assert out["error"] == "timeout"
    kinds = [item[0] for item in events]
    assert "ui.prompt.begin" in kinds
    assert events[-1][0] == "ui.prompt.end"
    assert events[-1][1]["text"] == "超时未选"
    assert pending("run-to") is None


async def test_park_rejects_one_option() -> None:
    out = await park("run-bad", "?", ["only"], None)
    assert out["ok"] is False
    assert pending("run-bad") is None


async def test_cancel_drops_pending() -> None:
    async def emit(_kind: str, _payload: dict) -> None:
        return

    task = asyncio.create_task(
        park("run-cancel", "还做吗？", ["继续", "停下"], emit, timeout=2)
    )
    for _ in range(50):
        if pending("run-cancel"):
            break
        await asyncio.sleep(0.01)
    cancel("run-cancel")
    try:
        await task
    except asyncio.CancelledError:
        pass
    assert pending("run-cancel") is None
