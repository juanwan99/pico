"""Official Pi thinking_delta is a thin extract — never full message_update."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "orchestrator"))

from pico_orchestrator.true_pi.client import RpcEvent
from pico_orchestrator.true_pi.events import EventMapState, map_event
from pico_orchestrator.true_pi.thinking import (
    incremental_text_from_update,
    incremental_thinking_from_update,
    text_delta_from_rpc,
    thinking_delta_from_rpc,
    thinking_from_message,
)


def test_thinking_delta_from_rpc_keeps_only_the_chunk() -> None:
    flood = {
        "type": "message_update",
        "message": {
            "role": "assistant",
            "content": [{"type": "text", "text": "x" * 8000}],
        },
        "assistantMessageEvent": {
            "type": "thinking_delta",
            "delta": "先看题目",
            "contentIndex": 0,
        },
    }
    assert thinking_delta_from_rpc(flood) == "先看题目"


def test_text_delta_from_rpc_keeps_only_the_chunk() -> None:
    flood = {
        "type": "message_update",
        "message": {
            "role": "assistant",
            "content": [{"type": "text", "text": "x" * 8000}],
            "usage": {"input": 9, "output": 9, "totalTokens": 18},
        },
        "assistantMessageEvent": {
            "type": "text_delta",
            "delta": "培训在",
            "contentIndex": 0,
        },
    }
    assert text_delta_from_rpc(flood) == "培训在"
    assert thinking_delta_from_rpc(flood) == ""


def test_incremental_text_uses_snapshot_suffix_when_no_official_delta() -> None:
    first = {
        "type": "message_update",
        "message": {"role": "assistant", "content": [{"type": "text", "text": "培训"}]},
    }
    piece, seen = incremental_text_from_update(first, 0)
    assert piece == "培训"
    assert seen == 2
    second = {
        "type": "message_update",
        "message": {"role": "assistant", "content": [{"type": "text", "text": "培训在哪"}]},
    }
    piece, seen = incremental_text_from_update(second, seen)
    assert piece == "在哪"
    assert seen == 4
    # Growing 8k body still only yields the new tail, never the whole blob.
    flood = {
        "type": "message_update",
        "message": {"role": "assistant", "content": [{"type": "text", "text": "培训在哪" + ("。") * 100}]},
    }
    piece, seen = incremental_text_from_update(flood, seen)
    assert piece.startswith("。")
    assert len(piece) == 100


def test_thinking_delta_from_rpc_ignores_text_and_tool_deltas() -> None:
    assert (
        thinking_delta_from_rpc(
            {
                "type": "message_update",
                "assistantMessageEvent": {"type": "text_delta", "delta": "成品句"},
            }
        )
        == ""
    )
    assert thinking_delta_from_rpc({"type": "message_update"}) == ""


def test_incremental_thinking_uses_snapshot_suffix_when_no_official_delta() -> None:
    first = {
        "type": "message_update",
        "message": {
            "role": "assistant",
            "content": [{"type": "thinking", "thinking": "先看"}],
        },
    }
    piece, seen = incremental_thinking_from_update(first, 0)
    assert piece == "先看"
    assert seen == 2
    second = {
        "type": "message_update",
        "message": {
            "role": "assistant",
            "content": [{"type": "thinking", "thinking": "先看题目"}],
        },
    }
    piece, seen = incremental_thinking_from_update(second, seen)
    assert piece == "题目"
    flood = {
        "type": "message_update",
        "message": {
            "role": "assistant",
            "content": [{"type": "thinking", "thinking": "先看题目" + ("。") * 80}],
        },
    }
    piece, seen = incremental_thinking_from_update(flood, seen)
    assert piece.startswith("。")
    assert len(piece) == 80


def test_incremental_thinking_prefers_official_delta() -> None:
    flood = {
        "type": "message_update",
        "message": {
            "role": "assistant",
            "content": [{"type": "thinking", "thinking": "x" * 8000}],
        },
        "assistantMessageEvent": {"type": "thinking_delta", "delta": "先看题目"},
    }
    piece, seen = incremental_thinking_from_update(flood, 0)
    assert piece == "先看题目"
    assert seen == 8000


def test_thinking_from_message_skips_product_text() -> None:
    msg = {
        "role": "assistant",
        "content": [
            {"type": "thinking", "thinking": "内部推理"},
            {"type": "text", "text": "给老师的答案"},
        ],
    }
    assert thinking_from_message(msg) == "内部推理"


@pytest.mark.asyncio
async def test_map_event_emits_thinking_delta_not_message_delta() -> None:
    events: list[tuple[str, dict[str, Any]]] = []

    async def emit(kind: str, payload: dict[str, Any]) -> None:
        events.append((kind, payload))

    state = EventMapState()
    await map_event(
        RpcEvent({"type": "thinking_delta", "delta": "先列步骤"}),
        emit=emit,
        state=state,
    )
    assert [k for k, _ in events] == ["thinking.delta"]
    assert events[0][1]["text"] == "先列步骤"
    assert "message.delta" not in [k for k, _ in events]
    assert "message.stream" not in [k for k, _ in events]
    assert state.thinking_emitted is True


@pytest.mark.asyncio
async def test_map_event_emits_text_delta_as_stream_not_ledger_kind() -> None:
    events: list[tuple[str, dict[str, Any]]] = []

    async def emit(kind: str, payload: dict[str, Any]) -> None:
        events.append((kind, payload))

    state = EventMapState()
    await map_event(
        RpcEvent({"type": "text_delta", "delta": "培训在"}),
        emit=emit,
        state=state,
    )
    assert [k for k, _ in events] == ["message.stream"]
    assert events[0][1]["text"] == "培训在"
    assert state.text_streamed is True
    assert state.final_parts == []
    assert state.token_usage is None


@pytest.mark.asyncio
async def test_message_end_emits_thinking_once_if_no_stream() -> None:
    events: list[tuple[str, dict[str, Any]]] = []

    async def emit(kind: str, payload: dict[str, Any]) -> None:
        events.append((kind, payload))

    state = EventMapState()
    await map_event(
        RpcEvent(
            {
                "type": "message_end",
                "message": {
                    "role": "assistant",
                    "content": [
                        {"type": "thinking", "thinking": "收尾思考"},
                        {"type": "text", "text": "答案"},
                    ],
                },
            }
        ),
        emit=emit,
        state=state,
    )
    kinds = [k for k, _ in events]
    assert kinds.count("thinking.delta") == 1
    assert events[0][1]["text"] == "收尾思考"
    assert state.final_parts == ["答案"]


def test_compat_streams_reasoning_content_not_product_bubble() -> None:
    src = (
        Path(__file__).resolve().parents[2] / "services/api/app/openai_compat.py"
    ).read_text()
    assert '"reasoning_content": str(payload)' in src
    assert '"reasoning": str(payload)' in src
    assert 'if event_type == "thinking.delta"' in src
    assert 'await q.put(("think", text))' in src
    assert 'if event_type == "message.stream"' in src
    assert "ledger_only" in src
