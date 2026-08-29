"""Fail-closed: Pi/OpenAI turn errors and empty answers must not succeed blank.

Live 2026-08-29 session 1758d5df…: first turn stopReason=error
「The usage limit has been reached」 with content=[] was painted succeeded
+ empty bubble. Second turn had text but only at settle (● while waiting).
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "api"))
sys.path.insert(0, str(ROOT / "services" / "orchestrator"))

from pico_orchestrator.run_types import RunCaps
from pico_orchestrator.true_pi.client import FakeTransport, RpcEvent
from pico_orchestrator.true_pi.events import (
    EventMapState,
    assistant_turn_error,
    map_event,
)
from pico_orchestrator.true_pi.runtime import run_true_pi_agent
from pico_orchestrator.user_errors import user_message_for_error

_USAGE_LIMIT = "The usage limit has been reached"


class Principal:
    def __init__(self, school_id: str = "school-a", membership_id: str = "member-a") -> None:
        self.school_id = school_id
        self.membership_id = membership_id
        self.scopes = ["ai:run"]


async def _not_cancelled() -> bool:
    return False


def _usage_limit_assistant() -> dict[str, Any]:
    return {
        "role": "assistant",
        "content": [],
        "api": "openai-responses",
        "provider": "openai",
        "model": "gpt-5.6-sol",
        "usage": {
            "input": 0,
            "output": 0,
            "cacheRead": 0,
            "cacheWrite": 0,
            "totalTokens": 0,
        },
        "stopReason": "error",
        "errorMessage": _USAGE_LIMIT,
    }


def test_assistant_turn_error_reads_live_usage_limit_shape() -> None:
    err = assistant_turn_error(_usage_limit_assistant())
    assert "usage limit" in err.lower()
    assert assistant_turn_error({"role": "assistant", "content": [], "stopReason": "stop"}) == ""
    nested = assistant_turn_error({"type": "message", "message": _usage_limit_assistant()})
    assert "usage limit" in nested.lower()


def test_usage_limit_and_empty_response_are_human_chinese() -> None:
    limit = user_message_for_error(_USAGE_LIMIT, code="model.usage_limit")
    assert "用量" in limit
    assert "usage limit" not in limit.lower()
    empty = user_message_for_error(
        "Pi agent received empty model response", code="pi.empty_response"
    )
    assert "可见回复" in empty or "再试" in empty
    assert "empty model" not in empty.lower()


@pytest.mark.asyncio
async def test_map_event_usage_limit_sets_provider_error() -> None:
    state = EventMapState()
    events: list[tuple[str, dict[str, Any]]] = []

    async def emit(k: str, p: dict[str, Any]) -> None:
        events.append((k, p))

    await map_event(
        RpcEvent({"type": "message_end", "message": _usage_limit_assistant()}),
        emit=emit,
        state=state,
    )
    assert state.provider_error is not None
    assert "usage limit" in state.provider_error.lower()
    assert state.final_parts == []


@pytest.mark.asyncio
async def test_map_event_session_message_type_also_captures_error() -> None:
    state = EventMapState()

    async def emit(k: str, p: dict[str, Any]) -> None:
        del k, p

    await map_event(
        RpcEvent({"type": "message", "message": _usage_limit_assistant()}),
        emit=emit,
        state=state,
    )
    assert state.provider_error is not None


@pytest.mark.asyncio
async def test_usage_limit_run_fails_with_human_copy_not_blank_success() -> None:
    events: list[tuple[str, dict[str, Any]]] = []

    async def emit(k: str, p: dict[str, Any]) -> None:
        events.append((k, p))

    transport = FakeTransport(
        scripted=[
            {"type": "agent_start"},
            {"type": "turn_start"},
            {"type": "message_end", "message": _usage_limit_assistant()},
            {
                "type": "turn_end",
                "message": _usage_limit_assistant(),
            },
            {"type": "agent_end", "willRetry": False},
        ],
        assistant_text="",
    )
    result = await run_true_pi_agent(
        prompt="帮我做一个展示页  你知道什么是展示页吗",
        principal=Principal(),
        emit=emit,
        is_cancelled=_not_cancelled,
        caps=RunCaps(min_artifacts=0, max_seconds=8),
        transport=transport,
    )
    assert result.status == "failed"
    assert result.final_text == ""
    assert "usage limit" in (result.error or "").lower()
    statuses = [p.get("status") for k, p in events if k == "run.status"]
    assert "succeeded" not in statuses
    assert "failed" in statuses
    human = user_message_for_error(result.error, code="model.usage_limit")
    assert "用量" in human
    deltas = [p.get("text") for k, p in events if k == "message.delta"]
    assert deltas == []


@pytest.mark.asyncio
async def test_empty_stop_without_error_is_empty_response_not_success() -> None:
    events: list[tuple[str, dict[str, Any]]] = []

    async def emit(k: str, p: dict[str, Any]) -> None:
        events.append((k, p))

    transport = FakeTransport(
        scripted=[
            {"type": "agent_start"},
            {"type": "turn_start"},
            {
                "type": "message_end",
                "message": {
                    "role": "assistant",
                    "content": [],
                    "stopReason": "stop",
                },
            },
            {"type": "agent_end", "willRetry": False},
        ],
        assistant_text="",
    )
    result = await run_true_pi_agent(
        prompt="？",
        principal=Principal(),
        emit=emit,
        is_cancelled=_not_cancelled,
        caps=RunCaps(min_artifacts=0, max_seconds=8),
        transport=transport,
    )
    assert result.status == "failed"
    assert "empty" in (result.error or "").lower()
    assert "succeeded" not in [p.get("status") for k, p in events if k == "run.status"]
