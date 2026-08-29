"""Map true-Pi RPC events → Pico ledger event kinds.

Honest mapping only — never invent success from silence.
"""

from __future__ import annotations

import json
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

from pico_orchestrator.sandbox_session_event import (
    SANDBOX_BROWSER_TOOLS,
    public_tool_result,
    sandbox_session_payload,
)
from pico_orchestrator.true_pi.client import RpcEvent
from pico_orchestrator.true_pi.config import RUNTIME_LABEL
from pico_orchestrator.user_errors import user_message_for_error
from pico_orchestrator.workbench_progress import (
    tool_result_failed,
    workbench_tool_step_line,
)

EventEmitter = Callable[[str, dict[str, Any]], Awaitable[None]]

COMPACTION_HUMAN = "在整理上文"
_PLAN_INTERNAL_CUSTOM = frozenset(
    {"plan-todo-list", "plan-complete", "plan-mode-execute", "plan-execution-context"}
)


@dataclass
class EventMapState:
    step: int = 0
    tool_results: list[tuple[str, dict[str, Any]]] = field(default_factory=list)
    final_parts: list[str] = field(default_factory=list)
    event_kinds: list[str] = field(default_factory=list)
    settled: bool = False
    started: bool = False
    tool_calls: int = 0
    tool_oks: int = 0
    token_usage: dict[str, Any] | None = None
    # Upstream Pi/OpenAI turn failure (stopReason=error / errorMessage).
    # Must not be painted as succeeded + empty bubble.
    provider_error: str | None = None


def assistant_turn_error(blob: Any) -> str:
    """Return the upstream turn error, or empty if this blob is not a failed turn.

    Live 2026-08-29: gpt-5.6-sol + openai-responses landed
    ``stopReason=error`` / ``errorMessage=The usage limit has been reached``
    with ``content=[]``. Mapping that to succeeded+blank is fake green.
    """
    if not isinstance(blob, dict):
        return ""
    pieces: list[dict[str, Any]] = [blob]
    nested = blob.get("message")
    if isinstance(nested, dict):
        pieces.append(nested)
    for item in pieces:
        stop = str(item.get("stopReason") or "").strip().lower()
        raw_err = item.get("errorMessage")
        if raw_err is None:
            raw_err = item.get("error")
        if isinstance(raw_err, dict):
            err = str(raw_err.get("message") or raw_err.get("code") or "").strip()
        else:
            err = str(raw_err or "").strip()
        if stop in {"error", "aborted", "cancelled"}:
            return err or stop
        if err and stop not in {"stop", "end_turn", "tool_calls", "length"}:
            return err
    return ""


def _record_assistant_turn(state: EventMapState, *, msg: Any, raw: dict[str, Any]) -> None:
    """Capture provider errors and product text. Plan chrome stays out of final_parts."""
    if not isinstance(msg, dict):
        msg = {}
    role = str(msg.get("role") or raw.get("role") or "assistant")
    if role != "assistant":
        return
    err = assistant_turn_error(msg) or assistant_turn_error(raw)
    if err:
        state.provider_error = err
    custom = str(msg.get("customType") or raw.get("customType") or "")
    text = _text_from_message(msg)
    if text and custom not in _PLAN_INTERNAL_CUSTOM:
        from pico_orchestrator.human_package import is_plan_passphrase, strip_ansi

        cleaned = strip_ansi(text).strip()
        if cleaned and not is_plan_passphrase(cleaned):
            state.final_parts.append(cleaned)


def _text_from_message(message: Any) -> str:
    if not isinstance(message, dict):
        return ""
    content = message.get("content")
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        parts: list[str] = []
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                parts.append(str(block.get("text") or ""))
        return "".join(parts).strip()
    return ""


def _result_dict(raw: Any) -> dict[str, Any]:
    if isinstance(raw, dict):
        # Extension may nest {"content":[{"type":"text","text":"{...json...}"}]}
        content = raw.get("content")
        if isinstance(content, list):
            for block in content:
                if isinstance(block, dict) and block.get("type") == "text":
                    text = str(block.get("text") or "")
                    try:
                        parsed = json.loads(text)
                        if isinstance(parsed, dict):
                            return parsed
                    except json.JSONDecodeError:
                        return {"text": text}
        if "result" in raw and isinstance(raw["result"], dict):
            return raw["result"]
        return raw
    if isinstance(raw, str):
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            return {"text": raw}
    return {"value": raw}


async def map_event(
    event: RpcEvent,
    *,
    emit: EventEmitter,
    state: EventMapState,
    shadow: bool = False,
) -> None:
    """Emit Pico ledger events for one Pi RPC event."""
    kind = event.type
    raw = event.raw
    tag = {"runtime": RUNTIME_LABEL}
    if shadow:
        tag["shadow"] = True

    from pico_orchestrator.usage_parse import add_usage, parse_usage_blob

    nested = raw.get("usage") if isinstance(raw, dict) else None
    piece = parse_usage_blob(raw) or parse_usage_blob(nested)
    if piece:
        state.token_usage = add_usage(state.token_usage, piece)

    if kind == "agent_start":
        state.started = True
        state.event_kinds.append("run.status")
        await emit("run.status", {"status": "running", **tag})
        return

    if kind == "turn_start":
        state.step += 1
        state.event_kinds.append("agent.step")
        await emit("agent.step", {"step": state.step, "phase": "model", **tag})
        return

    if kind == "tool_execution_start":
        state.tool_calls += 1
        name = str(raw.get("toolName") or raw.get("tool") or "unknown")
        call_id = str(raw.get("toolCallId") or raw.get("callId") or f"tp-{state.tool_calls}")
        args = raw.get("args") or raw.get("arguments") or {}
        if not isinstance(args, dict):
            args = {}
        state.event_kinds.append("tool.call")
        step = workbench_tool_step_line(name)
        await emit(
            "tool.call",
            {
                "tool": name,
                "arguments": args,
                "call_id": call_id,
                "step_line": step,
                **tag,
            },
        )
        return

    if kind == "tool_execution_end":
        name = str(raw.get("toolName") or raw.get("tool") or "unknown")
        call_id = str(raw.get("toolCallId") or raw.get("callId") or "")
        is_error = bool(raw.get("isError") or raw.get("error"))
        result = _result_dict(raw.get("result") if "result" in raw else raw.get("details"))
        if name in SANDBOX_BROWSER_TOOLS:
            result = public_tool_result(result)
        if is_error and "error" not in result:
            result = {**result, "error": str(raw.get("error") or "tool error")}
        failed = is_error or tool_result_failed(result)
        if not failed:
            state.tool_oks += 1
        else:
            result = dict(result)
            result.setdefault(
                "error",
                str(raw.get("error") or result.get("message") or "tool failed"),
            )
            if raw.get("code") and "code" not in result:
                result["code"] = raw.get("code")
        state.tool_results.append((name, result))
        state.event_kinds.append("tool.result")
        err_text = str(result.get("error") or "") if failed else ""
        err_code = result.get("code") if isinstance(result.get("code"), str) else None
        user_message = user_message_for_error(err_text, code=err_code) if failed else None
        payload = {
            "tool": name,
            "ok": not failed,
            "result": json.dumps(result, ensure_ascii=False),
            "message": user_message or ("" if failed else "ok"),
            "call_id": call_id,
            **tag,
        }
        if failed:
            payload["user_message"] = user_message
            if err_code:
                payload["code"] = err_code
        await emit("tool.result", payload)
        if name in {"web_search", "web_fetch", "kb_search"}:
            sources = result.get("sources") if isinstance(result, dict) else None
            state.event_kinds.append("search.sources")
            await emit(
                "search.sources",
                {
                    "tool": name,
                    "retrieved": bool(isinstance(result, dict) and result.get("retrieved")),
                    "honest_miss": bool(
                        isinstance(result, dict) and result.get("honest_miss")
                    )
                    or (not sources),
                    "sources": sources if isinstance(sources, list) else [],
                    "message": (
                        str(result.get("message") or "")
                        if isinstance(result, dict)
                        else ""
                    ),
                    **tag,
                },
            )
        if name in SANDBOX_BROWSER_TOOLS:
            session_ev = sandbox_session_payload(result)
            if session_ev:
                state.event_kinds.append("sandbox.session")
                await emit(
                    "sandbox.session",
                    {**session_ev, "tool": name, **tag},
                )
        return

    if kind in {"message_end", "message"}:
        msg = raw.get("message") if isinstance(raw.get("message"), dict) else raw
        custom = ""
        if isinstance(msg, dict):
            custom = str(msg.get("customType") or raw.get("customType") or "")
            text = _text_from_message(msg)
            if custom in {"plan-todo-list", "plan-complete", "plan-mode-execute"} and text:
                state.event_kinds.append("plan.progress")
                await emit("plan.progress", {"text": text, "customType": custom, **tag})
        _record_assistant_turn(
            state, msg=msg if isinstance(msg, dict) else {}, raw=raw
        )
        return

    if kind == "message_update":
        # Streaming deltas — do not accumulate monologue into final_parts.
        return

    if kind in {"compaction_start", "compaction_end"}:
        phase = "begin" if kind.endswith("start") else "end"
        state.event_kinds.append(f"compaction.{phase}")
        payload = {**tag, "source": "true-pi", "text": COMPACTION_HUMAN}
        if raw.get("reason"):
            payload["reason"] = raw.get("reason")
        result = raw.get("result") if isinstance(raw.get("result"), dict) else {}
        details = result.get("details") if isinstance(result.get("details"), dict) else {}
        # Official Pi CompactionDetails (read/modified files). Pass through only.
        for key in ("readFiles", "modifiedFiles"):
            files = details.get(key)
            if isinstance(files, list):
                payload[key] = [str(item) for item in files[:40]]
        kept = result.get("firstKeptEntryId")
        if kept:
            payload["firstKeptEntryId"] = str(kept)
        if "willRetry" in raw:
            payload["will_retry"] = bool(raw.get("willRetry"))
        await emit(f"compaction.{phase}", payload)
        # Process strip / timeline already show 在整理上文. Do not write it into
        # message.delta — that becomes the product bubble and looks like amnesia.
        return

    if kind == "extension_ui_request":
        method = str(raw.get("method") or "")
        text = ""
        if method == "notify":
            text = str(raw.get("message") or "")[:400]
        elif method == "setStatus":
            text = str(raw.get("statusText") or "")[:200]
        elif method == "setWidget":
            lines = raw.get("widgetLines") or []
            if isinstance(lines, list):
                text = "\n".join(str(x) for x in lines[:8])[:400]
        if text.strip():
            from pico_orchestrator.human_package import strip_ansi

            state.event_kinds.append("plan.progress")
            await emit(
                "plan.progress",
                {"text": strip_ansi(text.strip()), "method": method, **tag},
            )
        return

    if kind == "agent_end":
        # pi 0.73.x emits agent_end when one low-level run completes.
        # willRetry=true means auto-retry follows — do not settle yet.
        will_retry = bool(raw.get("willRetry"))
        packed = raw.get("messages")
        if isinstance(packed, list):
            for item in packed:
                if isinstance(item, dict):
                    _record_assistant_turn(state, msg=item, raw=item)
        err = assistant_turn_error(raw)
        if err:
            state.provider_error = err
        state.event_kinds.append("agent.end")
        await emit("agent.end", {"will_retry": will_retry, **tag})
        if not will_retry:
            state.settled = True
            state.event_kinds.append("agent.settled")
            await emit("agent.settled", {"source": "agent_end", **tag})
        return

    if kind == "agent_settled":
        # Newer pi versions may emit agent_settled after retries/compactions.
        state.settled = True
        state.event_kinds.append("agent.settled")
        await emit("agent.settled", {"source": "agent_settled", **tag})
        return

    if kind == "turn_end":
        # Not terminal alone (multi-turn tools), but useful progress.
        state.event_kinds.append("turn.end")
        await emit("agent.step", {"phase": "turn_end", "step": state.step, **tag})
        msg = raw.get("message") or {}
        _record_assistant_turn(
            state, msg=msg if isinstance(msg, dict) else {}, raw=raw
        )
        return

    if kind == "extension_error":
        state.event_kinds.append("run.error")
        raw_err = str(raw.get("error") or raw.get("message") or "extension error")
        await emit(
            "run.error",
            {
                "code": "true_pi.extension_error",
                "error": raw_err,
                "user_message": user_message_for_error(
                    raw_err, code="true_pi.extension_error"
                ),
                **tag,
            },
        )
        return

    # Unknown event types: ignore (do not invent status).
