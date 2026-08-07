from __future__ import annotations

import pytest

pytest.importorskip("kimi_agent_sdk")


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


@pytest.mark.parametrize(
    ("initial_arguments", "arguments_part"),
    [
        ('{"expression":"6 *', ' 7"}'),
        (None, '{"expression":"6 * 7"}'),
    ],
)
def test_buffers_partial_tool_call_until_result(
    initial_arguments: str | None, arguments_part: str
) -> None:
    adapter = KimiWireEventAdapter()
    adapter.feed(TurnBegin(user_input="hello"))

    call = ToolCall(
        id="split-call",
        function=ToolCall.FunctionBody(
            name="calculator", arguments=initial_arguments
        ),
    )
    assert adapter.feed(call) == []
    call_events = adapter.feed(ToolCallPart(arguments_part=arguments_part))
    result_events = adapter.feed(
        ToolResult(tool_call_id="split-call", return_value=ToolOk(output="42"))
    )
    events = call_events + result_events

    assert [(event.type, event.payload) for event in events] == [
        (
            "tool.call",
            {
                "tool": "calculator",
                "arguments": {"expression": "6 * 7"},
                "call_id": "split-call",
            },
        ),
        (
            "tool.result",
            {
                "tool": "calculator",
                "ok": True,
                "result": "42",
                "message": "",
                "call_id": "split-call",
            },
        ),
    ]


def test_ignores_orphan_tool_call_part_and_rejects_invalid_arguments() -> None:
    adapter = KimiWireEventAdapter()
    adapter.feed(TurnBegin(user_input="hello"))

    assert adapter.feed(ToolCallPart(arguments_part='{"orphan":true}')) == []

    invalid = ToolCall(
        id="bad-call",
        function=ToolCall.FunctionBody(name="calculator", arguments="not-json"),
    )
    assert adapter.feed(invalid) == []
    with pytest.raises(KimiEventContractError, match="invalid tool arguments"):
        adapter.feed(
            ToolResult(tool_call_id="bad-call", return_value=ToolOk(output="unused"))
        )


def test_requires_call_before_result_and_no_unfinished_call_at_turn_end() -> None:
    adapter = KimiWireEventAdapter()
    adapter.feed(TurnBegin(user_input="hello"))
    result = ToolResult(tool_call_id="missing", return_value=ToolOk(output="42"))

    with pytest.raises(KimiEventContractError, match="without preceding call"):
        adapter.feed(result)

    adapter.feed(_tool_call())
    with pytest.raises(KimiEventContractError, match="unfinished tool calls"):
        adapter.feed(TurnEnd())
