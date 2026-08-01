"""Pure Kimi Wire-to-Pico ledger event mapping.

KA-1 defines the adapter contract only.  Nothing in the production API imports
or calls this module yet; ``run_agent_loop`` remains the active runtime.
"""

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

    The caller must request ``merge_wire_messages=True``.  In particular, this
    ensures a ``ToolCall`` contains its complete JSON arguments before it is
    made durable.  Runtime execution, cancellation, and gateway dispatch are
    deliberately outside this KA-1 mapping skeleton.
    """

    def __init__(self) -> None:
        self._started = False
        self._ended = False
        self._tool_names: dict[str, str] = {}

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
                if call.id in self._tool_names:
                    raise KimiEventContractError(f"duplicate tool call id: {call.id}")
                arguments = self._parse_arguments(call.function.arguments, call.id)
                self._tool_names[call.id] = call.function.name
                return [
                    LedgerEvent(
                        "tool.call",
                        {
                            "tool": call.function.name,
                            "arguments": arguments,
                            "call_id": call.id,
                        },
                    )
                ]
            case ToolCallPart():
                raise KimiEventContractError(
                    "partial ToolCall received; use Session.prompt(merge_wire_messages=True)"
                )
            case ToolResult() as result:
                self._require_started(message)
                tool_name = self._tool_names.pop(result.tool_call_id, None)
                if tool_name is None:
                    raise KimiEventContractError(
                        f"tool result without preceding call: {result.tool_call_id}"
                    )
                value = result.return_value.model_dump(mode="json")
                return [
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
                if self._tool_names:
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
