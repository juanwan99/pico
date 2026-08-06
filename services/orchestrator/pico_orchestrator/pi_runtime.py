"""Pi Agent harness — default multi-step orchestration kernel (HANDOFF-WB-PI).

Minimal tool loop (Pi philosophy): model + allowlisted tools, no self-built OS.
Model = DeepSeek (primary) via OpenAI-compatible HTTPS. Events enter Pico ledger.
"""

from __future__ import annotations

import asyncio
import json
import uuid
from collections.abc import Awaitable, Callable
from contextlib import suppress
from pathlib import Path
from string import Template
from typing import Any

from openai import AsyncOpenAI

from pico_orchestrator.gateway import ArtifactStore, Principal, ToolError
from pico_orchestrator.provider import resolve_provider
from pico_orchestrator.run_types import EventEmitter, RunCaps, RunResult
from pico_orchestrator.tools_builtin import build_default_gateway, openai_tool_schemas
from pico_orchestrator.user_errors import enrich_fail_payload

RUNTIME_LABEL = "pi-agent"
_CANCEL_POLL_SECONDS = 0.05
_HEARTBEAT_SECONDS = 30.0

_DEFAULT_SYSTEM = """# Pico · Pi harness

You are **Pico**, a task-oriented AI workbench agent (Pi-style minimal harness).

## Rules
- Use tools when they help deliver real work (files, documents, lists).
- Prefer structured, professional Chinese or English matching the user.
- Tenant identity comes from the verified token — never invent school_id / membership_id.
- No host shell, no unrestricted web, no MCP unless the control plane allows it.
- When creating files/documents, call the generate_* or workspace_write tools.
- Short answers: do not force a file. Delivery tasks: produce a real artifact.
- On failure, say so honestly. Never claim success without tool evidence.

## Skill instruction (if any)
$skill_block
"""


async def run_pi_agent(
    *,
    prompt: str,
    principal: Principal,
    emit: EventEmitter,
    is_cancelled: Callable[[], Awaitable[bool]],
    caps: RunCaps | None = None,
    history: list[dict[str, Any]] | None = None,
    artifact_store: ArtifactStore | None = None,
) -> RunResult:
    """Run one multi-step Pi turn; map tool loop to Pico ledger events."""

    caps = caps or RunCaps()
    if await is_cancelled():
        await emit("run.status", {"status": "cancelled", "runtime": RUNTIME_LABEL})
        return RunResult(status="cancelled", final_text="")

    provider = resolve_provider()
    if provider is None:
        return await _failed_result(
            emit,
            code="model.unconfigured",
            reason="Pi runtime requires DEEPSEEK_API_KEY (preferred) or KIMI_API_KEY",
        )

    gateway = build_default_gateway(artifact_store).restricted_to(caps.allowed_tools)
    tool_schemas = openai_tool_schemas(gateway, allowed_tools=caps.allowed_tools)
    client = AsyncOpenAI(api_key=provider.api_key, base_url=provider.base_url)

    skill_block = caps.skill_instruction.strip() if caps.skill_instruction else "(none)"
    system = _load_system_prompt(skill_block)
    messages: list[dict[str, Any]] = [{"role": "system", "content": system}]
    for item in (history or [])[-20:]:
        role = item.get("role")
        content = item.get("content")
        if role in {"user", "assistant"} and content:
            messages.append({"role": role, "content": str(content)[:4000]})
    messages.append({"role": "user", "content": prompt})

    await emit("run.status", {"status": "running", "runtime": RUNTIME_LABEL})

    final_parts: list[str] = []
    tool_context_results: list[tuple[str, dict[str, Any]]] = []
    token_usage: dict[str, int] = {
        "input_tokens": 0,
        "output_tokens": 0,
        "total_tokens": 0,
    }
    stop = asyncio.Event()
    timed_out = asyncio.Event()
    loop = asyncio.get_running_loop()
    started = loop.time()
    deadline = started + max(1, caps.max_seconds)
    last_heartbeat = started

    watcher = asyncio.create_task(
        _watch_cancel(is_cancelled, stop, timed_out, deadline, started, emit)
    )
    try:
        for step in range(1, max(1, caps.max_steps) + 1):
            if stop.is_set() or await is_cancelled():
                await emit("run.status", {"status": "cancelled", "runtime": RUNTIME_LABEL})
                return _result(
                    "cancelled",
                    final_parts,
                    token_usage=token_usage,
                    tool_results=tool_context_results,
                    principal=principal,
                )
            if timed_out.is_set() or loop.time() >= deadline:
                return await _failed_result(
                    emit,
                    code="timeout",
                    reason=f"Pi agent timeout after {caps.max_seconds}s",
                    final_parts=final_parts,
                    token_usage=token_usage,
                    tool_results=tool_context_results,
                    principal=principal,
                )
            if token_usage["total_tokens"] > caps.max_tokens:
                return await _failed_result(
                    emit,
                    code="token_cap",
                    reason=f"Pi agent token cap exceeded: {caps.max_tokens}",
                    final_parts=final_parts,
                    token_usage=token_usage,
                    tool_results=tool_context_results,
                    principal=principal,
                )

            now = loop.time()
            if now - last_heartbeat >= _HEARTBEAT_SECONDS:
                await emit(
                    "run.heartbeat",
                    {
                        "elapsed_seconds": int(now - started),
                        "remaining_seconds": max(0, int(deadline - now)),
                        "max_seconds": caps.max_seconds,
                        "runtime": RUNTIME_LABEL,
                    },
                )
                last_heartbeat = now

            await emit("agent.step", {"step": step, "phase": "model"})

            create_kwargs: dict[str, Any] = {
                "model": provider.model,
                "messages": messages,
                "max_tokens": min(4096, max(256, caps.max_tokens - token_usage["total_tokens"])),
            }
            if tool_schemas:
                create_kwargs["tools"] = tool_schemas
                create_kwargs["tool_choice"] = "auto"

            remaining = max(1.0, deadline - loop.time())
            try:
                response = await asyncio.wait_for(
                    client.chat.completions.create(**create_kwargs),
                    timeout=remaining,
                )
            except TimeoutError:
                timed_out.set()
                return await _failed_result(
                    emit,
                    code="timeout",
                    reason=f"Pi agent timeout after {caps.max_seconds}s",
                    final_parts=final_parts,
                    token_usage=token_usage,
                    tool_results=tool_context_results,
                    principal=principal,
                )
            except Exception as exc:  # noqa: BLE001
                return await _failed_result(
                    emit,
                    code="pi.runtime_error",
                    reason=f"Pi agent model error ({type(exc).__name__})",
                    final_parts=final_parts,
                    token_usage=token_usage,
                    tool_results=tool_context_results,
                    principal=principal,
                )

            usage = getattr(response, "usage", None)
            if usage is not None:
                inp = int(getattr(usage, "prompt_tokens", 0) or 0)
                out = int(getattr(usage, "completion_tokens", 0) or 0)
                token_usage["input_tokens"] += inp
                token_usage["output_tokens"] += out
                token_usage["total_tokens"] += inp + out
                await emit(
                    "run.usage",
                    {
                        "scope": "step",
                        "input_tokens": inp,
                        "output_tokens": out,
                        "total_tokens": inp + out,
                        "cumulative_total_tokens": token_usage["total_tokens"],
                    },
                )

            choice = response.choices[0] if response.choices else None
            if choice is None:
                return await _failed_result(
                    emit,
                    code="pi.empty_response",
                    reason="Pi agent received empty model response",
                    final_parts=final_parts,
                    token_usage=token_usage,
                    tool_results=tool_context_results,
                    principal=principal,
                )

            msg = choice.message
            content = (msg.content or "").strip()
            tool_calls = list(msg.tool_calls or [])

            assistant_msg: dict[str, Any] = {"role": "assistant", "content": msg.content or ""}
            if tool_calls:
                assistant_msg["tool_calls"] = [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments or "{}",
                        },
                    }
                    for tc in tool_calls
                ]
            messages.append(assistant_msg)

            if content:
                final_parts.append(content)
                await emit("message.delta", {"text": content})

            if not tool_calls:
                await emit(
                    "run.status",
                    {"status": "succeeded", "runtime": RUNTIME_LABEL},
                )
                return _result(
                    "succeeded",
                    final_parts,
                    token_usage=token_usage,
                    tool_results=tool_context_results,
                    principal=principal,
                )

            await emit("agent.step", {"step": step, "phase": "tools"})
            for tc in tool_calls:
                if stop.is_set() or await is_cancelled():
                    await emit(
                        "run.status",
                        {"status": "cancelled", "runtime": RUNTIME_LABEL},
                    )
                    return _result(
                        "cancelled",
                        final_parts,
                        token_usage=token_usage,
                        tool_results=tool_context_results,
                        principal=principal,
                    )
                call_id = tc.id or f"call-{uuid.uuid4().hex[:12]}"
                name = tc.function.name
                try:
                    arguments = json.loads(tc.function.arguments or "{}")
                    if not isinstance(arguments, dict):
                        raise json.JSONDecodeError("not object", "", 0)
                except json.JSONDecodeError:
                    arguments = {}
                    err_payload = {
                        "error": "invalid tool arguments JSON",
                        "raw": (tc.function.arguments or "")[:500],
                    }
                    await emit(
                        "tool.call",
                        {"tool": name, "arguments": {}, "call_id": call_id},
                    )
                    await emit(
                        "tool.result",
                        {
                            "tool": name,
                            "ok": False,
                            "result": json.dumps(err_payload, ensure_ascii=False),
                            "message": "invalid arguments",
                            "call_id": call_id,
                        },
                    )
                    messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": call_id,
                            "content": json.dumps(err_payload, ensure_ascii=False),
                        }
                    )
                    continue

                await emit(
                    "tool.call",
                    {"tool": name, "arguments": arguments, "call_id": call_id},
                )
                try:
                    result = await gateway.invoke(principal, name, arguments)
                    tool_context_results.append((name, result))
                    out_text = json.dumps(result, ensure_ascii=False)
                    await emit(
                        "tool.result",
                        {
                            "tool": name,
                            "ok": True,
                            "result": out_text,
                            "message": f"{name} completed through Pico allowlist gateway",
                            "call_id": call_id,
                        },
                    )
                    messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": call_id,
                            "content": out_text,
                        }
                    )
                except ToolError as exc:
                    if exc.code == "tenant.cross_school":
                        await emit(
                            "auth.deny",
                            {
                                "code": exc.code,
                                "message": "跨校访问已被拒绝（租户隔离）。",
                                "tool": name,
                            },
                        )
                    err_body = {"code": exc.code, "error": exc.message}
                    out_text = json.dumps(err_body, ensure_ascii=False)
                    await emit(
                        "tool.result",
                        {
                            "tool": name,
                            "ok": False,
                            "result": out_text,
                            "message": exc.message,
                            "call_id": call_id,
                        },
                    )
                    messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": call_id,
                            "content": out_text,
                        }
                    )

        return await _failed_result(
            emit,
            code="pi.max_steps",
            reason="Pi agent reached the step limit",
            final_parts=final_parts,
            token_usage=token_usage,
            tool_results=tool_context_results,
            principal=principal,
        )
    finally:
        stop.set()
        watcher.cancel()
        with suppress(asyncio.CancelledError):
            await watcher


def _load_system_prompt(skill_block: str) -> str:
    packaged = Path(__file__).resolve().parent / "agent_assets" / "system.md"
    if packaged.is_file():
        raw = packaged.read_text(encoding="utf-8")
    else:
        raw = _DEFAULT_SYSTEM
    # Support $skill_block (Template) and plain {skill_block}; leave other braces alone.
    if "$skill_block" in raw:
        return Template(raw).safe_substitute(skill_block=skill_block, ROLE_ADDITIONAL="")
    if "{skill_block}" in raw:
        return raw.replace("{skill_block}", skill_block).replace("${ROLE_ADDITIONAL}", "").replace(
            "{ROLE_ADDITIONAL}", ""
        )
    return raw + f"\n\n## Skill instruction\n{skill_block}\n"


async def _watch_cancel(
    is_cancelled: Callable[[], Awaitable[bool]],
    stop: asyncio.Event,
    timed_out: asyncio.Event,
    deadline: float,
    started: float,
    emit: EventEmitter,
) -> None:
    loop = asyncio.get_running_loop()
    last_heartbeat = started
    while not stop.is_set():
        if await is_cancelled():
            return
        now = loop.time()
        if now >= deadline:
            timed_out.set()
            return
        if now - last_heartbeat >= _HEARTBEAT_SECONDS:
            try:
                await emit(
                    "run.heartbeat",
                    {
                        "elapsed_seconds": int(now - started),
                        "remaining_seconds": max(0, int(deadline - now)),
                        "runtime": RUNTIME_LABEL,
                    },
                )
            except Exception:  # noqa: BLE001
                pass
            last_heartbeat = now
        try:
            await asyncio.wait_for(stop.wait(), timeout=_CANCEL_POLL_SECONDS)
        except TimeoutError:
            pass


async def _failed_result(
    emit: EventEmitter,
    *,
    code: str,
    reason: str,
    final_parts: list[str] | None = None,
    token_usage: dict[str, int] | None = None,
    tool_results: list[tuple[str, dict[str, Any]]] | None = None,
    principal: Principal | None = None,
) -> RunResult:
    await emit("run.error", enrich_fail_payload({"code": code, "error": reason}))
    await emit(
        "run.status",
        enrich_fail_payload(
            {
                "status": "failed",
                "reason": reason,
                "code": code,
                "runtime": RUNTIME_LABEL,
            }
        ),
    )
    return _result(
        "failed",
        final_parts or [],
        error=reason,
        token_usage=token_usage,
        tool_results=tool_results,
        principal=principal,
    )


def _result(
    status: str,
    final_parts: list[str],
    *,
    error: str | None = None,
    token_usage: dict[str, int] | None = None,
    tool_results: list[tuple[str, dict[str, Any]]] | None = None,
    principal: Principal | None = None,
) -> RunResult:
    artifact_markdown: str | None = None
    change_proposal: dict[str, Any] | None = None
    for name, value in tool_results or []:
        if name == "fake_edu_list_classes":
            artifact_markdown = _classes_artifact(value)
        elif name == "pico_propose_change":
            change_proposal = value
    from pico_orchestrator.redact import redact_tenant_text

    final_text = redact_tenant_text(
        "\n".join(p for p in final_parts if p).strip(),
        school_id=getattr(principal, "school_id", None),
        membership_id=getattr(principal, "membership_id", None),
    )
    usage_out = dict(token_usage) if token_usage else None
    if usage_out is not None:
        usage_out["estimated"] = False
    return RunResult(
        status=status,
        final_text=final_text,
        error=error,
        token_usage=usage_out,
        artifact_markdown=artifact_markdown,
        change_proposal=change_proposal,
    )


def _classes_artifact(result: dict[str, Any]) -> str:
    lines = [
        "# 班级列表（本校）",
        "",
        "| ID | 名称 |",
        "|----|------|",
    ]
    for item in result.get("classes") or []:
        lines.append(f"| {item.get('id', '')} | {item.get('name', '')} |")
    return "\n".join(lines)
