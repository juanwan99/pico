"""True-Pi RPC usage harvest: this turn only, never streaming cumulative."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "orchestrator"))

from pico_orchestrator.true_pi.client import RpcEvent
from pico_orchestrator.true_pi.events import EventMapState, map_event


def _pi_usage(*, inp: int, out: int, total: int) -> dict[str, Any]:
    return {
        "input": inp,
        "output": out,
        "cacheRead": 0,
        "cacheWrite": 0,
        "totalTokens": total,
        "cost": {"input": 0.1, "output": 0.2, "total": 0.3},
    }


@pytest.mark.asyncio
async def test_message_update_does_not_accumulate_usage() -> None:
    state = EventMapState()

    async def emit(k: str, p: dict[str, Any]) -> None:
        del k, p

    growing = _pi_usage(inp=10, out=4, total=14)
    await map_event(
        RpcEvent({"type": "message_update", "message": {"usage": growing}, "usage": growing}),
        emit=emit,
        state=state,
    )
    await map_event(
        RpcEvent(
            {
                "type": "message_update",
                "message": {"usage": _pi_usage(inp=40, out=20, total=60)},
                "usage": _pi_usage(inp=40, out=20, total=60),
            }
        ),
        emit=emit,
        state=state,
    )
    assert state.token_usage is None


@pytest.mark.asyncio
async def test_agent_end_messages_usage_lands_on_state() -> None:
    state = EventMapState()

    async def emit(k: str, p: dict[str, Any]) -> None:
        del k, p

    await map_event(
        RpcEvent(
            {
                "type": "agent_end",
                "willRetry": False,
                "messages": [
                    {"role": "user", "content": "hi"},
                    {
                        "role": "assistant",
                        "content": [{"type": "text", "text": "ok"}],
                        "usage": _pi_usage(inp=8, out=7, total=15),
                    },
                ],
            }
        ),
        emit=emit,
        state=state,
    )
    assert state.token_usage is not None
    assert state.token_usage["prompt_tokens"] == 8
    assert state.token_usage["completion_tokens"] == 7
    assert state.token_usage["total_tokens"] == 15
    assert "cost" not in state.token_usage


@pytest.mark.asyncio
async def test_compaction_end_usage_adds_to_turn() -> None:
    state = EventMapState()

    async def emit(k: str, p: dict[str, Any]) -> None:
        del k, p

    await map_event(
        RpcEvent(
            {
                "type": "agent_end",
                "willRetry": False,
                "messages": [{"role": "assistant", "usage": _pi_usage(inp=8, out=2, total=10)}],
            }
        ),
        emit=emit,
        state=state,
    )
    await map_event(
        RpcEvent(
            {
                "type": "compaction_end",
                "result": {"usage": _pi_usage(inp=20, out=5, total=25)},
            }
        ),
        emit=emit,
        state=state,
    )
    assert state.token_usage is not None
    assert state.token_usage["total_tokens"] == 35
