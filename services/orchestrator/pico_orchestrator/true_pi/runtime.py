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
    true_pi_windows_from_caps,
)
from pico_orchestrator.true_pi.config import (
    ALLOWED_GATEWAY_TOOLS,
    RUNTIME_LABEL,
    history_n,
    persist_session_dir,
    plan_mode_extension_path,
    session_root,
)
from pico_orchestrator.true_pi.events import EventMapState, map_event
from pico_orchestrator.true_pi.tool_server import ToolServer
from pico_orchestrator.user_errors import enrich_fail_payload
from pico_orchestrator.workbench_progress import failed_write_user_message

logger = logging.getLogger(__name__)

_CANCEL_POLL = 0.05
# First plan-turn select arrives on the same stdout pipe; 1s is enough.
_PLAN_FIRST_END_GRACE = 1.0


def plan_settle_hold(
    *,
    event_type: str,
    plan_flag: bool,
    plan_agent_ends: int,
    plan_execute_pending: bool,
) -> tuple[bool, int, bool]:
    """Whether to un-settle this event.

    Returns (hold, new_ends, pending). Hold only while Execute is pending and
    we have not seen the execute-turn ``agent_end``. Empty-plan / no Execute
    does not hold. A 2nd end always lands (never wait for a 3rd).
    """
    if not plan_flag or event_type not in {"agent_end", "agent_settled"}:
        return False, plan_agent_ends, plan_execute_pending
    ends = plan_agent_ends + (1 if event_type == "agent_end" else 0)
    if ends < 2:
        # First plan-turn. Execute UI may still be in the pipe — hold.
        # Main loop grace / stream-end lands if Execute never starts.
        return True, ends, plan_execute_pending
    return False, ends, plan_execute_pending


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
    conversation_id: str | None = None,
    persist_pi_session: bool = False,
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
    # Dual-mode deep-lane circuit breaker (F2): true_pi must not run away on an
    # empty/no-tool-progress loop any more than the hosted kernel. Only the
    # thinking-on lane (Pico 深度) arms it; fast lane never trips.
    thinking_on = bool(getattr(caps, "thinking_on", False))
    breaker_seconds = max(1, int(getattr(caps, "no_progress_seconds", 180) or 180))
    last_tool_ok_wall: float | None = None
    last_progress_wall = started

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
            # Dual-mode (F1/F3): lane policy flows into the true_pi kernel — the
            # backend model is pinned to deepseek-v4-flash and the thinking flag
            # follows caps.thinking_on (Pico 快速=off / Pico 深度=on). Never a
            # global hardcoded off.
            from pico_orchestrator.provider import runtime_policy_for_model

            policy = runtime_policy_for_model(None)
            backend_model = str(policy.get("backend_model") or provider.model)
            thinking_on = bool(getattr(caps, "thinking_on", False))
            max_context, max_out = true_pi_windows_from_caps(caps)
            tool_server = ToolServer(principal=principal, gateway=gateway, run_id=rid)
            tool_url = await tool_server.start()
            persist_dir = (
                persist_session_dir(
                    school_id=str(getattr(principal, "school_id", "") or ""),
                    conversation_id=conversation_id,
                )
                if persist_pi_session
                else None
            )
            sess = session_dir or persist_dir or (session_root() / rid)
            use_tree = persist_dir is not None and session_dir is None
            extra_ext: list[Path] = []
            plan_path = plan_mode_extension_path()
            if use_tree and plan_path.is_file():
                extra_ext.append(plan_path)
            transport = SubprocessTransport(
                session_dir=sess,
                tool_url=tool_url,
                tool_token=tool_server.token,
                run_id=rid,
                provider="deepseek" if provider.name == "deepseek" else "openai",
                model=backend_model,
                thinking=thinking_on,
                max_context=max_context,
                max_tokens=max_out,
                extra_extensions=extra_ext,
                continue_session=use_tree,
                # Official plan-mode stays loaded. Do not force --plan on every
                # workbench turn: that waits a second agent_end that may never
                # land (T-AGENT-PLAIN-V1 live hang).
                plan_flag=False,
                spawn_cwd=sess,
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
        # Workbench Pi session tree holds history. Do not paste N turns as text.
        tree_history = history
        if persist_pi_session and persist_session_dir(
            school_id=str(getattr(principal, "school_id", "") or ""),
            conversation_id=conversation_id,
        ):
            tree_history = None
        full_prompt = _compose_prompt(
            prompt=prompt,
            skill=skill,
            min_arts=min_arts,
            history=tree_history,
            allowed_tools=allowed,
            system_prompt=str(getattr(caps, "system_prompt", "") or ""),
        )

        await client.prompt(full_prompt)

        async def _consume() -> None:
            nonlocal last_progress_wall, last_tool_ok_wall
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
                prev_tool_oks = state.tool_oks
                await map_event(event, emit=emit, state=state, shadow=shadow)
                # Official plan-mode: hold the first end only while auto-Execute
                # actually started a second turn. Never wait for a 3rd end
                # (live hang: pending stayed True and unset the 2nd settle).
                hold, ends, pending = plan_settle_hold(
                    event_type=event.type,
                    plan_flag=bool(getattr(transport, "plan_flag", False)),
                    plan_agent_ends=int(getattr(transport, "plan_agent_ends", 0) or 0),
                    plan_execute_pending=bool(
                        getattr(transport, "plan_execute_pending", False)
                    ),
                )
                transport.plan_agent_ends = ends
                if hold:
                    state.settled = False
                elif pending and ends >= 2:
                    transport.plan_execute_pending = False
                # Circuit-breaker progress bookkeeping (F2): any event that maps
                # is real forward motion; a newly successful tool execution
                # resets the no-tool-progress timer used by the deep-lane
                # bailout.
                last_progress_wall = loop.time()
                if state.tool_oks > prev_tool_oks:
                    last_tool_ok_wall = loop.time()
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
                # Dual-mode deep-lane circuit breaker (F2): the true_pi kernel
                # must not run away on an empty / no-tool-progress loop. Only
                # the thinking-on lane (Pico 深度) arms it; fast lane never
                # trips. Two triggers: no tool success for ≥180s, or the event
                # stream stalls ≥180s with zero tool success.
                if thinking_on and not state.settled:
                    now = loop.time()
                    tool_gap = (
                        now - last_tool_ok_wall
                        if last_tool_ok_wall is not None
                        else now - started
                    )
                    if tool_gap >= breaker_seconds and state.tool_oks == 0:
                        await client.abort()
                        await emit(
                            "circuit.breaker",
                            {
                                "tool_exec_count": state.tool_oks,
                                "wall_seconds": int(now - started),
                                "runtime": RUNTIME_LABEL,
                            },
                        )
                        return await _failed(
                            emit,
                            code="pi.no_progress",
                            reason=(
                                "深度模式长时间无有效进展，已触发熔断以避免空转/OOM。"
                                "可点「再跑一次」或将任务拆短后重试。"
                            ),
                            state=state,
                            principal=principal,
                            tag=tag,
                        )
                    if now - last_progress_wall >= breaker_seconds and state.tool_oks == 0:
                        await client.abort()
                        await emit(
                            "circuit.breaker",
                            {
                                "tool_exec_count": state.tool_oks,
                                "stalled_seconds": int(now - last_progress_wall),
                                "runtime": RUNTIME_LABEL,
                            },
                        )
                        return await _failed(
                            emit,
                            code="pi.no_progress",
                            reason=(
                                "深度模式长时间无有效进展，已触发熔断以避免空转。"
                                "可点「再跑一次」，或改用 Pico 快速档重试。"
                            ),
                            state=state,
                            principal=principal,
                            tag=tag,
                        )
                if consumer.done():
                    break
                # Empty-plan Stay / no UI: first end already happened, Execute
                # never started, Pi is idle. Land instead of waiting 3600s.
                if (
                    not state.settled
                    and int(getattr(transport, "plan_agent_ends", 0) or 0) >= 1
                    and not bool(getattr(transport, "plan_execute_pending", False))
                ):
                    held_at = getattr(transport, "plan_first_held_at", None)
                    if held_at is None:
                        transport.plan_first_held_at = loop.time()
                    elif loop.time() - float(transport.plan_first_held_at) >= _PLAN_FIRST_END_GRACE:
                        state.settled = True
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
            # Stream ended. If the first plan-turn already finished and Execute
            # never started, the first answer is the product — land it.
            if (
                int(getattr(transport, "plan_agent_ends", 0) or 0) >= 1
                and not bool(getattr(transport, "plan_execute_pending", False))
            ):
                state.settled = True
            else:
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
        write_fail = failed_write_user_message(state.tool_results)
        if write_fail:
            return await _failed(
                emit,
                code="tool.write_failed",
                reason=write_fail,
                state=state,
                principal=principal,
                tag=tag,
            )
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
        from pico_orchestrator.web_tools import attach_teacher_sources

        human = attach_teacher_sources(human, state.tool_results)
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
    system_prompt: str = "",
) -> str:
    """Build single prompt for true Pi: tools + skill + minimal history + user."""
    parts: list[str] = []
    override = str(system_prompt or "").strip()
    if override:
        parts.append(override)
        parts.append(
            "Use only the registered tools listed below. "
            "This chat's files belong to this conversation, not a long-term cabinet.\n"
            f"Allowed tools: {', '.join(allowed_tools)}"
        )
    else:
        parts.append(
            "# Pico true-Pi harness\n"
            "You are Pico. Use only the registered tools listed below. "
            "No host shell. Deliver real files via write/generate tools when asked.\n"
            f"Allowed tools: {', '.join(allowed_tools)}\n"
            "When the question needs current/public facts, call web_search and "
            "put clickable markdown sources in the final reply. "
            "When the user pastes a specific http(s) URL, call web_fetch. "
            "If retrieval returns honest_miss / 未检索, say so — never invent citations. "
            "Do not fetch intranet, localhost, or cloud metadata."
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
    from pico_orchestrator.web_tools import attach_teacher_sources

    human = attach_teacher_sources(human, state.tool_results)
    final_text = redact_tenant_text(
        human,
        school_id=getattr(principal, "school_id", None) if principal else None,
        membership_id=getattr(principal, "membership_id", None) if principal else None,
    )
    return RunResult(status=status, final_text=final_text, error=error)
