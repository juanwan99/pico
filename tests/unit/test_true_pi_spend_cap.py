"""Per-run spend cap (#1104 IN3): a pause like the wall clock, priced by pico-api."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "api"))
sys.path.insert(0, str(ROOT / "services" / "orchestrator"))

from pico_orchestrator.run_caps import caps_for_tier
from pico_orchestrator.run_types import RunCaps
from pico_orchestrator.true_pi.client import FakeTransport, RpcEvent
from pico_orchestrator.true_pi.events import EventMapState, map_event
from pico_orchestrator.true_pi.runtime import run_true_pi_agent
from pico_orchestrator.user_errors import spend_stop_teacher_text


class Principal:
    def __init__(self) -> None:
        self.school_id = "school-a"
        self.membership_id = "member-a"
        self.scopes = ["ai:run"]


async def _not_cancelled() -> bool:
    return False


def _usage(inp: int, out: int) -> dict[str, Any]:
    return {"input": inp, "output": out, "cacheRead": 0, "cacheWrite": 0, "totalTokens": inp + out}


def _turn(inp: int, out: int) -> list[dict[str, Any]]:
    msg = {
        "role": "assistant",
        "content": [{"type": "text", "text": "…"}],
        "usage": _usage(inp, out),
    }
    return [
        {"type": "turn_start"},
        {"type": "message_end", "message": msg},
        {"type": "turn_end", "message": msg},
    ]


def _one_milli_per_token(usage: dict[str, Any], model: str) -> int | None:
    assert model
    return int(usage.get("total_tokens") or 0)


@pytest.mark.asyncio
async def test_assistant_message_end_usage_accumulates_spend_separately_from_ledger() -> None:
    state = EventMapState()

    async def emit(k: str, p: dict[str, Any]) -> None:
        del k, p

    for ev in [*_turn(100, 20), *_turn(300, 50)]:
        await map_event(RpcEvent(ev), emit=emit, state=state)
    assert state.spent_calls == 2
    assert state.spent_usage["total_tokens"] == 470
    assert state.token_usage is None  # ledger usage still only from agent_end


@pytest.mark.asyncio
async def test_only_assistant_message_end_counts_as_a_call() -> None:
    """User / tool-result message_end and the turn_end echo add nothing."""
    state = EventMapState()

    async def emit(k: str, p: dict[str, Any]) -> None:
        del k, p

    call = {"role": "assistant", "content": [], "usage": _usage(100, 20)}
    for ev in [
        {"type": "message_end", "message": {"role": "user", "content": "hi"}},
        {"type": "message_end", "message": call},
        {"type": "message_end", "message": {"role": "toolResult", "content": [], "usage": _usage(9, 9)}},
        {"type": "turn_end", "message": call},
    ]:
        await map_event(RpcEvent(ev), emit=emit, state=state)
    assert state.spent_calls == 1
    assert state.spent_usage["total_tokens"] == 120


@pytest.mark.asyncio
async def test_spend_cap_pauses_run_with_teacher_copy() -> None:
    events: list[tuple[str, dict[str, Any]]] = []

    async def emit(k: str, p: dict[str, Any]) -> None:
        events.append((k, p))

    # No agent_end: Pi keeps going; the cap must stop it.
    transport = FakeTransport(
        scripted=[{"type": "agent_start"}, *_turn(600, 100), *_turn(600, 100)],
        assistant_text="",
    )
    result = await run_true_pi_agent(
        prompt="做一份长报告",
        principal=Principal(),
        emit=emit,
        is_cancelled=_not_cancelled,
        caps=RunCaps(
            min_artifacts=0,
            max_seconds=10,
            backend_model="gemini-3.8-flash",
            max_millipoints=1_000,
            millipoints_for_usage=_one_milli_per_token,
        ),
        transport=transport,
        run_id="spend-t1",
    )
    assert result.status == "succeeded"
    status = [p for k, p in events if k == "run.status"][-1]
    assert status["code"] == "spend.stop"
    spend = [p for k, p in events if k == "run.spend"]
    assert spend and spend[0]["millipoints"] == 1_400 and spend[0]["cap_millipoints"] == 1_000
    assert any("单次上限" in str(p.get("text")) for k, p in events if k == "message.delta")
    assert any(c.get("type") == "abort" for c in transport.sent)
    assert not any(k == "run.error" for k, _ in events)


@pytest.mark.asyncio
async def test_no_cap_or_no_pricer_never_stops(monkeypatch: pytest.MonkeyPatch) -> None:
    events: list[tuple[str, dict[str, Any]]] = []

    async def emit(k: str, p: dict[str, Any]) -> None:
        events.append((k, p))

    for caps in (
        RunCaps(
            min_artifacts=0,
            max_seconds=1,
            max_millipoints=0,
            millipoints_for_usage=_one_milli_per_token,
        ),
        RunCaps(min_artifacts=0, max_seconds=1, max_millipoints=10, millipoints_for_usage=None),
    ):
        transport = FakeTransport(
            scripted=[{"type": "agent_start"}, *_turn(600, 100)], assistant_text=""
        )
        result = await run_true_pi_agent(
            prompt="x",
            principal=Principal(),
            emit=emit,
            is_cancelled=_not_cancelled,
            caps=caps,
            transport=transport,
            run_id="spend-t2",
        )
        # Only the 1s wall ends it — as a wall pause, never spend.stop.
        assert result.status == "succeeded"
        assert [p for k, p in events if k == "run.status"][-1]["code"] == "wall.stop"
        assert not any(k == "run.spend" for k, _ in events)


def test_caps_for_tier_carries_spend_cap() -> None:
    caps = caps_for_tier(
        "durable", max_millipoints=5_000, millipoints_for_usage=_one_milli_per_token
    )
    assert caps.max_millipoints == 5_000 and caps.millipoints_for_usage is _one_milli_per_token
    assert caps_for_tier("delivery").max_millipoints == 0


def test_settings_pricer_uses_rate_card() -> None:
    from app.settings import millipoints_for_usage

    priced = millipoints_for_usage(
        {"prompt_tokens": 100_000, "completion_tokens": 20_000, "total_tokens": 120_000},
        "gemini-3.8-flash",
    )
    assert priced is not None and priced > 0
    assert millipoints_for_usage({"total_tokens": 10}, "no-such-model-xyz") is None


def test_spend_stop_copy_is_teacher_words() -> None:
    text = spend_stop_teacher_text(millipoints=12_345, cap_millipoints=10_000, has_deliverable=True)
    assert "12.3 点" in text and "10 点" in text and "不是系统报错" in text and "产物" in text
    assert "millipoint" not in text.lower()


@pytest.mark.asyncio
async def test_failed_event_write_is_reported_not_called_a_wall_clock() -> None:
    """#1135 32-box load: a ledger write that fails mid-stream ended the consumer;
    the run said "did not settle within 21600s" after 30 seconds."""
    events: list[tuple[str, dict[str, Any]]] = []
    raised: list[str] = []

    class LedgerBusy(Exception):
        pass

    async def emit(k: str, p: dict[str, Any]) -> None:
        if k == "agent.step" and not raised:
            raised.append(k)
            raise LedgerBusy("database is locked")
        events.append((k, p))

    transport = FakeTransport(
        scripted=[{"type": "agent_start"}, *_turn(10, 5), *_turn(10, 5)],
        assistant_text="",
    )
    result = await run_true_pi_agent(
        prompt="写一个脚本",
        principal=Principal(),
        emit=emit,
        is_cancelled=_not_cancelled,
        caps=RunCaps(min_artifacts=0, max_seconds=600),
        transport=transport,
        run_id="ledger-busy-t1",
    )
    assert raised
    assert result.status == "failed"
    status = [p for k, p in events if k == "run.status"][-1]
    assert "LedgerBusy" in status["reason"]
    assert "did not settle" not in status["reason"]
