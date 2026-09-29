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


@pytest.mark.asyncio
async def test_upstream_error_still_delivers_saved_workspace_files(monkeypatch) -> None:
    """Live LT3 2026-09-29: 20-slide pptx saved, then the stream died → 0 files."""
    from types import SimpleNamespace

    from pico_orchestrator.true_pi import runner

    events: list[tuple[str, dict[str, Any]]] = []

    async def emit(k: str, p: dict[str, Any]) -> None:
        events.append((k, p))

    async def fake_list(_key: Any) -> dict[str, Any]:
        return {}

    landed_calls: list[Any] = []

    async def fake_land(**kw: Any) -> list[tuple[str, dict[str, Any]]]:
        landed_calls.append(kw)
        return [("workspace_output", {"artifact_id": "a1", "title": "家长说明会.pptx"})]

    monkeypatch.setattr(runner, "list_outputs", fake_list)
    monkeypatch.setattr(runner, "land_outputs", fake_land)
    transport = FakeTransport(
        scripted=[
            {"type": "agent_start"},
            {"type": "turn_start"},
            {"type": "message_end", "message": _usage_limit_assistant()},
            {"type": "turn_end", "message": _usage_limit_assistant()},
            {"type": "agent_end", "willRetry": False},
        ],
        assistant_text="",
    )
    transport.runner = SimpleNamespace(key="ws-key")
    result = await run_true_pi_agent(
        prompt="做 20 页 PPT",
        principal=Principal(),
        emit=emit,
        is_cancelled=_not_cancelled,
        caps=RunCaps(min_artifacts=0, max_seconds=8),
        transport=transport,
    )
    assert result.status == "failed"
    assert len(landed_calls) == 1
    kinds = [k for k, _ in events]
    assert kinds.index("tool.result") < kinds.index("run.status", kinds.index("tool.result"))
    landed = [p for k, p in events if k == "tool.result" and p.get("tool") == "workspace_output"]
    assert landed and landed[0]["ok"] is True


def _stream_cut_assistant() -> dict[str, Any]:
    return {**_usage_limit_assistant(), "errorMessage": "Stream ended without finish_reason"}


def _answer_assistant(text: str) -> dict[str, Any]:
    return {
        "role": "assistant",
        "content": [{"type": "text", "text": text}],
        "stopReason": "stop",
    }


async def _run_scripted(scripted: list[dict[str, Any]]):
    events: list[tuple[str, dict[str, Any]]] = []

    async def emit(k: str, p: dict[str, Any]) -> None:
        events.append((k, p))

    result = await run_true_pi_agent(
        prompt="做 20 页 PPT",
        principal=Principal(),
        emit=emit,
        is_cancelled=_not_cancelled,
        caps=RunCaps(min_artifacts=0, max_seconds=8),
        transport=FakeTransport(scripted=scripted, assistant_text=""),
    )
    return result, events


@pytest.mark.asyncio
async def test_error_pi_retried_successfully_is_not_a_failure() -> None:
    """Live LT3/LT6/LT8 2026-09-29: Pi auto-retried a cut stream and finished;
    Pico still failed the run with the first error."""
    cut = _stream_cut_assistant()
    done = _answer_assistant("PPT 已做好。")
    result, events = await _run_scripted(
        [
            {"type": "agent_start"},
            {"type": "message_end", "message": cut},
            {"type": "turn_end", "message": cut},
            {"type": "agent_end", "willRetry": True, "messages": [cut]},
            {"type": "message_end", "message": done},
            {"type": "turn_end", "message": done},
            {"type": "agent_end", "willRetry": False, "messages": [done]},
        ]
    )
    assert result.status == "succeeded", result.error
    assert "failed" not in [p.get("status") for k, p in events if k == "run.status"]


@pytest.mark.asyncio
async def test_error_still_failing_after_retry_fails_the_run() -> None:
    cut = _stream_cut_assistant()
    result, _ = await _run_scripted(
        [
            {"type": "agent_start"},
            {"type": "message_end", "message": cut},
            {"type": "agent_end", "willRetry": True, "messages": [cut]},
            {"type": "message_end", "message": cut},
            {"type": "agent_end", "willRetry": False, "messages": [cut]},
        ]
    )
    assert result.status == "failed"
    assert "finish_reason" in (result.error or "")
