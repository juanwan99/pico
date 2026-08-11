"""Bypass runtime: true Pi RPC + gateway tool bridge + landing gate.

Never changes production default_runtime. Call only when:
  - tests inject a FakeTransport, or
  - PICO_TRUE_PI_BYPASS / shadow path explicitly requests it.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from collections.abc import Awaitable, Callable
from contextlib import suppress
from pathlib import Path
from typing import Any

from pico_orchestrator.gateway import ArtifactStore, Principal
from pico_orchestrator.pi_runtime import count_write_tool_successes
from pico_orchestrator.provider import resolve_provider
from pico_orchestrator.run_types import EventEmitter, RunCaps, RunResult
from pico_orchestrator.tools_builtin import build_default_gateway
from pico_orchestrator.true_pi.client import (
    FakeTransport,
    SubprocessTransport,
    TruePiClientError,
    TruePiRpcClient,
    TruePiTransport,
)
from pico_orchestrator.true_pi.config import (
    ALLOWED_GATEWAY_TOOLS,
    RUNTIME_LABEL,
    history_n,
    session_root,
)
from pico_orchestrator.true_pi.events import EventMapState, map_event
from pico_orchestrator.true_pi.tool_server import ToolServer
from pico_orchestrator.user_errors import enrich_fail_payload

logger = logging.getLogger(__name__)

_CANCEL_POLL = 0.05


async def run_true_pi_agent(
    *,
    prompt: str,
    principal: Principal,
    emit: EventEmitter,
    is_cancelled: Callable[[], Awaitable[bool]],
    caps: RunCaps | None = None,
    history: list[dict[str, Any]] | None = None,
    artifact_store: ArtifactStore | None = None,
    transport: TruePiTransport | None = None,
    shadow: bool = False,
    run_id: str | None = None,
    session_dir: Path | None = None,
) -> RunResult:
    """Run one multi-step turn on true Pi (or fake transport)."""
    caps = caps or RunCaps()
    rid = run_id or f"tp-{uuid.uuid4().hex[:12]}"
    min_arts = max(0, int(getattr(caps, "min_artifacts", 0) or 0))
    tag = {"runtime": RUNTIME_LABEL, **({"shadow": True} if shadow else {})}

    if await is_cancelled():
        await emit("run.status", {"status": "cancelled", **tag})
        return RunResult(status="cancelled", final_text="")

    # Restrict tools to the thin-bridge allowlist, further intersect caps.
    gateway = build_default_gateway(artifact_store)
    allowed = list(ALLOWED_GATEWAY_TOOLS)
    if caps.allowed_tools is not None:
        allowed = [t for t in allowed if t in set(caps.allowed_tools)]
    gateway = gateway.restricted_to(allowed)

    tool_server: ToolServer | None = None
    client: TruePiRpcClient | None = None
    state = EventMapState()
    stop = asyncio.Event()
    timed_out = asyncio.Event()
    loop = asyncio.get_running_loop()
    started = loop.time()
    deadline = started + max(1, caps.max_seconds)

    async def _watcher() -> None:
        while not stop.is_set():
            if await is_cancelled():
                return
            if loop.time() >= deadline:
                timed_out.set()
                return
            try:
                await asyncio.wait_for(stop.wait(), timeout=_CANCEL_POLL)
            except TimeoutError:
                pass

    watcher = asyncio.create_task(_watcher())
    try:
        if transport is None:
            provider = resolve_provider()
            if provider is None:
                return await _failed(
                    emit,
                    code="model.unconfigured",
                    reason="True Pi requires DEEPSEEK_API_KEY (preferred) or KIMI_API_KEY",
                    tag=tag,
                )
            tool_server = ToolServer(principal=principal, gateway=gateway, run_id=rid)
            tool_url = await tool_server.start()
            sess = session_dir or (session_root() / rid)
            transport = SubprocessTransport(
                session_dir=sess,
                tool_url=tool_url,
                tool_token=tool_server.token,
                run_id=rid,
                provider="deepseek" if provider.name == "deepseek" else "openai",
                model=provider.model,
                env={
                    "DEEPSEEK_API_KEY": provider.api_key
                    if provider.name == "deepseek"
                    else "",
                    "OPENAI_API_KEY": provider.api_key
                    if provider.name != "deepseek"
                    else "",
                },
            )

        # Fake transport still needs a tool server if it will not invoke tools
        # via HTTP — matrix tests inject tool_results via scripted events.
        if isinstance(transport, FakeTransport) and tool_server is None:
            # No HTTP server for pure scripted runs.
            pass

        client = TruePiRpcClient(transport)
        await client.start()

        skill = (caps.skill_instruction or "").strip()
        full_prompt = _compose_prompt(
            prompt=prompt,
            skill=skill,
            min_arts=min_arts,
            history=history,
            allowed_tools=allowed,
        )

        await client.prompt(full_prompt)

        async def _consume() -> None:
            async for event in client.events():
                # Responses are handled by wait_response on SubprocessTransport;
                # ignore type=response in the event stream if any leak through.
                if event.type == "response":
                    continue
                # Streaming deltas (message_update) carry the FULL accumulated
                # text and can arrive at hundreds/thousands per second while the
                # model streams (O(n^2) over tokens). map_event drops them, so
                # drop them HERE before the per-event cancellation DB check —
                # otherwise a fast model stream backlogs the event queue with
                # RpcEvents (each holding the growing text) and balloons memory.
                # Cancellation is already enforced by the main loop + _watcher.
                if event.type == "message_update":
                    continue
                if stop.is_set() or timed_out.is_set() or await is_cancelled():
                    break
                await map_event(event, emit=emit, state=state, shadow=shadow)
                if state.settled:
                    break

        consumer = asyncio.create_task(_consume())
        try:
            while not state.settled and not stop.is_set():
                if await is_cancelled():
                    await client.abort()
                    await emit("run.status", {"status": "cancelled", **tag})
                    return _result("cancelled", state, principal=principal)
                if timed_out.is_set() or loop.time() >= deadline:
                    await client.abort()
                    return await _failed(
                        emit,
                        code="timeout",
                        reason=f"True Pi timeout after {caps.max_seconds}s",
                        state=state,
                        principal=principal,
                        tag=tag,
                    )
                if consumer.done():
                    break
                await asyncio.sleep(0.05)
        finally:
            if not consumer.done():
                consumer.cancel()
                with suppress(asyncio.CancelledError):
                    await consumer
            else:
                with suppress(Exception):
                    consumer.result()

        if await is_cancelled():
            await client.abort()
            await emit("run.status", {"status": "cancelled", **tag})
            return _result("cancelled", state, principal=principal)

        if timed_out.is_set() or loop.time() >= deadline:
            await client.abort()
            return await _failed(
                emit,
                code="timeout",
                reason=f"True Pi timeout after {caps.max_seconds}s",
                state=state,
                principal=principal,
                tag=tag,
            )

        if not state.settled and not state.started:
            # Stream ended with no agent_start (e.g. process died).
            return await _failed(
                emit,
                code="true_pi.no_events",
                reason="True Pi produced no agent events",
                state=state,
                principal=principal,
                tag=tag,
            )

        if not state.settled:
            # Stream ended without agent_settled — treat as incomplete / timeout-class.
            return await _failed(
                emit,
                code="timeout",
                reason=f"True Pi did not settle within {caps.max_seconds}s",
                state=state,
                principal=principal,
                tag=tag,
            )

        # Pull assistant text if event map did not capture it.
        if not state.final_parts and not isinstance(transport, FakeTransport):
            with suppress(TruePiClientError):
                text = await client.get_last_assistant_text()
                if text:
                    state.final_parts.append(text)
        elif (
            not state.final_parts
            and isinstance(transport, FakeTransport)
            and transport.assistant_text
        ):
            state.final_parts.append(transport.assistant_text)

        writes = count_write_tool_successes(state.tool_results)
        landing_ok = min_arts <= 0 or writes >= min_arts
        if not landing_ok:
            return await _failed(
                emit,
                code="delivery.missing_artifact",
                reason=(
                    "交付意图下未写入可下载文件（聊天复述不能当作交件）。"
                    "请再跑一次或明确要求用工具落盘。"
                ),
                state=state,
                principal=principal,
                tag=tag,
            )

        # Human package
        from pico_orchestrator.human_package import (
            sanitize_user_facing_text,
            titles_from_tool_results,
        )
        from pico_orchestrator.redact import redact_tenant_text

        titles = titles_from_tool_results(state.tool_results)
        base = (state.final_parts[-1] if state.final_parts else "") or ""
        human = sanitize_user_facing_text(base, artifact_titles=titles)
        final_text = redact_tenant_text(
            human,
            school_id=getattr(principal, "school_id", None),
            membership_id=getattr(principal, "membership_id", None),
        )
        if final_text:
            await emit("message.delta", {"text": final_text, **tag})
        await emit("run.status", {"status": "succeeded", **tag})
        return RunResult(status="succeeded", final_text=final_text)

    except TruePiClientError as exc:
        return await _failed(
            emit,
            code="true_pi.rpc_error",
            reason=str(exc)[:500],
            state=state,
            principal=principal,
            tag=tag,
        )
    except Exception as exc:
        logger.exception("true_pi runtime error run_id=%s", rid)
        return await _failed(
            emit,
            code="true_pi.runtime_error",
            reason=f"True Pi error ({type(exc).__name__})",
            state=state,
            principal=principal,
            tag=tag,
        )
    finally:
        stop.set()
        watcher.cancel()
        with suppress(asyncio.CancelledError):
            await watcher
        if client is not None:
            with suppress(Exception):
                await client.close(kill=True)
        if tool_server is not None:
            with suppress(Exception):
                await tool_server.stop()


def _compose_prompt(
    *,
    prompt: str,
    skill: str,
    min_arts: int,
    history: list[dict[str, Any]] | None,
    allowed_tools: list[str],
) -> str:
    """Build single prompt for true Pi: tools + skill + minimal history + user."""
    parts: list[str] = []
    parts.append(
        "# Pico true-Pi harness\n"
        "You are Pico. Use only the registered tools listed below. "
        "No host shell. Deliver real files via write/generate tools when asked.\n"
        f"Allowed tools: {', '.join(allowed_tools)}"
    )
    if skill:
        parts.append(f"## Skill instruction\n{skill}")
    n = history_n()
    if history and n > 0:
        # Minimal history: last N user/assistant text turns (not full session tree).
        hist_lines: list[str] = []
        selected = [
            item
            for item in history
            if isinstance(item, dict)
            and item.get("role") in {"user", "assistant"}
            and item.get("content")
        ][-n:]
        for item in selected:
            role = str(item.get("role"))
            content = str(item.get("content"))[:2000]
            hist_lines.append(f"{role}: {content}")
        if hist_lines:
            parts.append("## Recent conversation\n" + "\n".join(hist_lines))
    parts.append(f"## User request\n{prompt}")
    if min_arts > 0:
        parts.append(
            f"## Landing requirement\n"
            f"Write at least {min_arts} downloadable file(s) using "
            "workspace_write_file or generate_*_document. "
            "Chat-only claims are not delivery.\n"
            "Keep HTML/DOCX/PPTX source compact (target under 10KB per file): "
            "streaming a huge body token-by-token over the RPC pipe is slow and "
            "memory-heavy. A focused, well-crafted page beats a bloated one.\n"
            "Your FINAL reply is shown directly to the user in the chat. Output "
            "it in the user's language (Chinese for zh requests) and ONLY a "
            "clean delivery summary — no internal reasoning, no narration of "
            "tool calls, no schema/argument/verify-process talk."
        )
    return "\n\n".join(parts)


async def _failed(
    emit: EventEmitter,
    *,
    code: str,
    reason: str,
    state: EventMapState | None = None,
    principal: Principal | None = None,
    tag: dict[str, Any] | None = None,
) -> RunResult:
    tag = tag or {"runtime": RUNTIME_LABEL}
    await emit("run.error", enrich_fail_payload({"code": code, "error": reason, **tag}))
    await emit(
        "run.status",
        enrich_fail_payload(
            {"status": "failed", "reason": reason, "code": code, **tag}
        ),
    )
    return _result("failed", state or EventMapState(), error=reason, principal=principal)


def _result(
    status: str,
    state: EventMapState,
    *,
    error: str | None = None,
    principal: Principal | None = None,
) -> RunResult:
    from pico_orchestrator.human_package import (
        sanitize_user_facing_text,
        titles_from_tool_results,
    )
    from pico_orchestrator.redact import redact_tenant_text

    titles = titles_from_tool_results(state.tool_results)
    base = (state.final_parts[-1] if state.final_parts else "") or ""
    human = sanitize_user_facing_text(base, artifact_titles=titles)
    final_text = redact_tenant_text(
        human,
        school_id=getattr(principal, "school_id", None) if principal else None,
        membership_id=getattr(principal, "membership_id", None) if principal else None,
    )
    return RunResult(status=status, final_text=final_text, error=error)
