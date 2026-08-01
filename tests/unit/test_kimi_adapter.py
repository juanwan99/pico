from __future__ import annotations

import pytest
from kimi_agent_sdk import (
    StatusUpdate,
    StepBegin,
    TextPart,
    ThinkPart,
    TokenUsage,
    ToolCall,
    ToolCallPart,
    ToolOk,
    ToolResult,
    TurnBegin,
    TurnEnd,
)
from pico_orchestrator.kimi_adapter import KimiEventContractError, KimiWireEventAdapter


def _tool_call(call_id: str = "call-1") -> ToolCall:
    return ToolCall(
        id=call_id,
        function=ToolCall.FunctionBody(
            name="calculator",
            arguments='{"expression":"6 * 7"}',
        ),
    )


def test_maps_merged_wire_stream_to_ordered_ledger_contract() -> None:
    adapter = KimiWireEventAdapter()

    events = []
    for message in (
        TurnBegin(user_input="hello"),
        StepBegin(n=1),
        TextPart(text="先计算。"),
        _tool_call(),
        ToolResult(
            tool_call_id="call-1",
            return_value=ToolOk(output='{"value":42}', message="done", brief="42"),
        ),
        StatusUpdate(
            context_usage=0.25,
            message_id="message-1",
            token_usage=TokenUsage(
                input_other=10,
                input_cache_read=3,
                input_cache_creation=2,
                output=5,
            ),
        ),
        TextPart(text="结果是 42。"),
        TurnEnd(),
    ):
        events.extend(adapter.feed(message))

    assert [(event.type, event.payload) for event in events] == [
        ("run.status", {"status": "running", "runtime": "kimi-agent"}),
        ("agent.step", {"step": 1, "phase": "model"}),
        ("message.delta", {"text": "先计算。"}),
        (
            "tool.call",
            {
                "tool": "calculator",
                "arguments": {"expression": "6 * 7"},
                "call_id": "call-1",
            },
        ),
        (
            "tool.result",
            {
                "tool": "calculator",
                "ok": True,
                "result": '{"value":42}',
                "message": "done",
                "call_id": "call-1",
            },
        ),
        (
            "run.usage",
            {
                "context_usage": 0.25,
                "message_id": "message-1",
                "scope": "step",
                "input_tokens": 15,
                "output_tokens": 5,
                "total_tokens": 20,
                "input_cache_read": 3,
                "input_cache_creation": 2,
            },
        ),
        ("message.delta", {"text": "结果是 42。"}),
        ("run.status", {"status": "succeeded", "runtime": "kimi-agent"}),
    ]


def test_does_not_persist_thinking_content() -> None:
    adapter = KimiWireEventAdapter()
    adapter.feed(TurnBegin(user_input="hello"))

    assert adapter.feed(ThinkPart(think="private reasoning")) == []


def test_rejects_unmerged_tool_parts_and_invalid_arguments() -> None:
    adapter = KimiWireEventAdapter()
    adapter.feed(TurnBegin(user_input="hello"))

    with pytest.raises(KimiEventContractError, match="merge_wire_messages=True"):
        adapter.feed(ToolCallPart(arguments_part='{"x":'))

    invalid = ToolCall(
        id="bad-call",
        function=ToolCall.FunctionBody(name="calculator", arguments="not-json"),
    )
    with pytest.raises(KimiEventContractError, match="invalid tool arguments"):
        adapter.feed(invalid)


def test_requires_call_before_result_and_no_unfinished_call_at_turn_end() -> None:
    adapter = KimiWireEventAdapter()
    adapter.feed(TurnBegin(user_input="hello"))
    result = ToolResult(tool_call_id="missing", return_value=ToolOk(output="42"))

    with pytest.raises(KimiEventContractError, match="without preceding call"):
        adapter.feed(result)

    adapter.feed(_tool_call())
    with pytest.raises(KimiEventContractError, match="unfinished tool calls"):
        adapter.feed(TurnEnd())
