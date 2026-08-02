"""Pure Kimi Wire-to-Pico ledger event mapping."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from kimi_agent_sdk import (
    ApprovalRequest,
    ApprovalResponse,
    CompactionBegin,
    CompactionEnd,
    StatusUpdate,
    StepBegin,
    StepInterrupted,
    SubagentEvent,
    TextPart,
    ThinkPart,
    ToolCall,
    ToolCallPart,
    ToolResult,
    TurnBegin,
    TurnEnd,
    WireMessage,
)


@dataclass(frozen=True, slots=True)
class LedgerEvent:
    """One event ready for Pico's ordered ``append_event`` emitter."""

    type: str
    payload: dict[str, Any]


class KimiEventContractError(RuntimeError):
    """The Wire stream cannot be represented safely by the KA-1 contract."""


class KimiWireEventAdapter:
    """Map one merged Kimi ``Session.prompt`` Wire stream to ledger events.

    The caller requests ``merge_wire_messages=True``, but provider streams can
    still expose a trailing ``ToolCallPart``.  Incomplete tool calls therefore
    remain buffered until their arguments are complete and safe to persist.
    """

    def __init__(self) -> None:
        self._started = False
        self._ended = False
        self._tool_names: dict[str, str] = {}
        self._pending_calls: dict[str, ToolCall] = {}
        self._seen_call_ids: set[str] = set()
        self._last_call_id: str | None = None

    def feed(self, message: WireMessage) -> list[LedgerEvent]:
        """Convert a Wire message without performing I/O or running a tool."""

        if self._ended:
            raise KimiEventContractError("message received after terminal TurnEnd")

        match message:
            case TurnBegin():
                if self._started:
                    raise KimiEventContractError("duplicate TurnBegin")
                self._started = True
                return [
                    LedgerEvent(
                        "run.status",
                        {"status": "running", "runtime": "kimi-agent"},
                    )
                ]
            case StepBegin(n=step):
                self._require_started(message)
                return [LedgerEvent("agent.step", {"step": step, "phase": "model"})]
            case TextPart(text=text):
                self._require_started(message)
                return [LedgerEvent("message.delta", {"text": text})] if text else []
            case ThinkPart():
                self._require_started(message)
                # Do not persist private reasoning / chain-of-thought.
                return []
            case StatusUpdate() as update:
                self._require_started(message)
                payload = self._usage_payload(update)
                return [LedgerEvent("run.usage", payload)] if payload else []
            case ToolCall() as call:
                self._require_started(message)
                if call.id in self._seen_call_ids:
                    raise KimiEventContractError(f"duplicate tool call id: {call.id}")
                self._seen_call_ids.add(call.id)
                self._last_call_id = call.id
                if not call.function.arguments:
                    self._pending_calls[call.id] = call.model_copy(deep=True)
                    return []
                try:
                    arguments = self._parse_arguments(
                        call.function.arguments, call.id
                    )
                except KimiEventContractError:
                    self._pending_calls[call.id] = call.model_copy(deep=True)
                    return []
                self._tool_names[call.id] = call.function.name
                return [self._tool_call_event(call, arguments)]
            case ToolCallPart() as part:
                self._require_started(message)
                call_id = self._last_call_id
                if call_id is None or call_id not in self._pending_calls:
                    # Kimi's own message aggregator drops an orphan part: it
                    # has no call id and cannot be attached safely.
                    return []
                call = self._pending_calls[call_id]
                call.merge_in_place(part)
                try:
                    arguments = self._parse_arguments(call.function.arguments, call_id)
                except KimiEventContractError:
                    return []
                self._pending_calls.pop(call_id)
                self._tool_names[call_id] = call.function.name
                return [self._tool_call_event(call, arguments)]
            case ToolResult() as result:
                self._require_started(message)
                call_events: list[LedgerEvent] = []
                tool_name = self._tool_names.pop(result.tool_call_id, None)
                if tool_name is None and result.tool_call_id in self._pending_calls:
                    call = self._pending_calls.pop(result.tool_call_id)
                    arguments = self._parse_arguments(
                        call.function.arguments, result.tool_call_id
                    )
                    tool_name = call.function.name
                    call_events.append(self._tool_call_event(call, arguments))
                if tool_name is None:
                    raise KimiEventContractError(
                        f"tool result without preceding call: {result.tool_call_id}"
                    )
                value = result.return_value.model_dump(mode="json")
                return call_events + [
                    LedgerEvent(
                        "tool.result",
                        {
                            "tool": tool_name,
                            "ok": not result.return_value.is_error,
                            "result": value["output"],
                            "message": value["message"],
                            "call_id": result.tool_call_id,
                        },
                    )
                ]
            case ApprovalRequest() as request:
                self._require_started(message)
                return [
                    LedgerEvent(
                        "tool.approval_required",
                        {
                            "request_id": request.id,
                            "call_id": request.tool_call_id,
                            "sender": request.sender,
                            "action": request.action,
                            "description": request.description,
                        },
                    )
                ]
            case ApprovalResponse() as response:
                self._require_started(message)
                return [
                    LedgerEvent(
                        "tool.approval_resolved",
                        {"request_id": response.request_id, "response": response.response},
                    )
                ]
            case CompactionBegin():
                self._require_started(message)
                return [LedgerEvent("agent.step", {"phase": "compaction.begin"})]
            case CompactionEnd():
                self._require_started(message)
                return [LedgerEvent("agent.step", {"phase": "compaction.end"})]
            case StepInterrupted():
                self._require_started(message)
                return [LedgerEvent("agent.step", {"phase": "interrupted"})]
            case TurnEnd():
                self._require_started(message)
                if self._tool_names or self._pending_calls:
                    raise KimiEventContractError("TurnEnd received with unfinished tool calls")
                self._ended = True
                return [
                    LedgerEvent(
                        "run.status",
                        {"status": "succeeded", "runtime": "kimi-agent"},
                    )
                ]
            case SubagentEvent():
                raise KimiEventContractError("subagent events are disabled by the Pico agent spec")
            case _:
                raise KimiEventContractError(
                    f"unsupported Kimi Wire message: {type(message).__name__}"
                )

    def _require_started(self, message: WireMessage) -> None:
        if not self._started:
            raise KimiEventContractError(
                f"{type(message).__name__} received before TurnBegin"
            )

    @staticmethod
    def _tool_call_event(
        call: ToolCall, arguments: dict[str, Any]
    ) -> LedgerEvent:
        return LedgerEvent(
            "tool.call",
            {
                "tool": call.function.name,
                "arguments": arguments,
                "call_id": call.id,
            },
        )

    @staticmethod
    def _parse_arguments(raw: str | None, call_id: str) -> dict[str, Any]:
        try:
            value = json.loads(raw or "{}")
        except json.JSONDecodeError as exc:
            raise KimiEventContractError(f"invalid tool arguments for {call_id}") from exc
        if not isinstance(value, dict):
            raise KimiEventContractError(f"tool arguments for {call_id} must be an object")
        return value

    @staticmethod
    def _usage_payload(update: StatusUpdate) -> dict[str, Any]:
        payload: dict[str, Any] = {}
        if update.context_usage is not None:
            payload["context_usage"] = update.context_usage
        if update.message_id is not None:
            payload["message_id"] = update.message_id
        if update.token_usage is not None:
            usage = update.token_usage
            input_tokens = usage.input_other + usage.input_cache_read + usage.input_cache_creation
            payload.update(
                {
                    "scope": "step",
                    "input_tokens": input_tokens,
                    "output_tokens": usage.output,
                    "total_tokens": input_tokens + usage.output,
                    "input_cache_read": usage.input_cache_read,
                    "input_cache_creation": usage.input_cache_creation,
                }
            )
        return payload
