"""Bypass runtime: true Pi RPC + gateway tool bridge + landing gate.

Never changes production default_runtime. Call only when:
  - tests inject a FakeTransport, or
  - PICO_TRUE_PI_BYPASS / shadow path explicitly requests it.
"""

from __future__ import annotations

import asyncio
import logging
import os
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
    RUNTIME_LABEL,
    memory_extension_path,
    persist_memory_dir,
    persist_session_dir,
    persist_session_file,
    plan_mode_extension_path,
    session_root,
)
from pico_orchestrator.true_pi.events import EventMapState, map_event
from pico_orchestrator.true_pi.tool_server import ToolServer
from pico_orchestrator.true_pi.workenv_attach import AttachTransport
from pico_orchestrator.user_errors import enrich_fail_payload
from pico_orchestrator.workbench_progress import failed_write_user_message

logger = logging.getLogger(__name__)

_CANCEL_POLL = 0.05
# First plan-turn select arrives on the same stdout pipe; 1s is enough.
_PLAN_FIRST_END_GRACE = 1.0


def _hitl_ask_timed_out(transport: Any) -> bool:
    return bool(
        getattr(transport, "plan_ask_timed_out", False)
        or getattr(transport, "ask_timed_out", False)
    )


def want_plan_mode_extension(*, plan_on: bool) -> bool:
    """Load vendor plan-mode only when this spawn's plan_on is true.

    The extension's session_start restores persisted ``plan-mode`` enabled
    even without ``--plan``. Attaching it on every tree session made a
    leftover HITL after a plain greeting.
    """
    return bool(plan_on)


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


def should_trip_true_pi_idle_breaker(
    *,
    thinking_on: bool,
    openai_responses_brain: bool,
    tool_oks: int,
    tool_gap: float,
    progress_gap: float,
    breaker_seconds: float,
) -> bool:
    """Deep-lane empty-loop fuse. GPT Responses thinking is not an empty loop.

    DeepSeek 深度 can spin with zero tools. Codex-class GPT often thinks
    several minutes before the first token or tool; a 180s fuse falsely
    kills long office HTML/PPT. Wall budget remains ``caps.max_seconds``.
    """
    if openai_responses_brain:
        return False
    if not thinking_on or tool_oks > 0:
        return False
    limit = max(1.0, float(breaker_seconds))
    return tool_gap >= limit or progress_gap >= limit


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

    # Visible = CORE, or a hung skill's snapshot (⊆ gateway). Not the full 26.
    from pico_orchestrator.capability_loading import (
        resolve_visible_tools,
        visible_tools_env,
    )

    gateway = build_default_gateway(artifact_store)
    allowed = resolve_visible_tools(caps.allowed_tools)
    gateway = gateway.restricted_to(allowed)
    system_text = pico_system_text(
        skill=str(getattr(caps, "skill_instruction", "") or ""),
        system_override=str(getattr(caps, "system_prompt", "") or ""),
        day_use=str(getattr(caps, "day_use", "") or ""),
    )

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
    plan_on = bool(getattr(caps, "plan_on", False))
    openai_responses_brain = False
    breaker_seconds = max(1, int(getattr(caps, "no_progress_seconds", 180) or 180))
    last_tool_ok_wall: float | None = None
    last_progress_wall = started
    workenv_mode = (os.environ.get("PICO_WORKENV") or "off").strip().lower()
    workenv_gate = None

    async def _destroy_workenv_run() -> bool:
        if workenv_gate is None:
            return True
        from pico_orchestrator.true_pi.workenv_http import WorkenvHttpError, workenv_post

        try:
            body = await workenv_post(
                "/v1/internal/workenv/destroy-run",
                {"workspace_id": rid},
                timeout=15.0,
            )
            destroyed = bool(body.get("destroyed")) and bool(body.get("ok", True))
            if not destroyed:
                workenv_gate.fail_destroy()
                return False
            if workenv_gate.status == "cancelling":
                workenv_gate.finish_cancel()
            return True
        except WorkenvHttpError:
            workenv_gate.fail_destroy()
            return False
        except Exception:  # noqa: BLE001
            workenv_gate.fail_destroy()
            return False

    async def _cancel_run() -> RunResult:
        assert client is not None
        if workenv_gate is not None:
            workenv_gate.begin_cancel()
            await emit("run.status", {"status": "cancelling", **tag})
        await client.abort()
        if workenv_gate is not None:
            destroyed = await _destroy_workenv_run()
            if not destroyed or workenv_gate.status == "failed":
                return await _failed(
                    emit,
                    code="sandbox.workenv_destroy_failed",
                    reason="隔离环境没关掉",
                    state=state,
                    principal=principal,
                    tag=tag,
                )
            await emit("sandbox.workenv.destroy", {"workspace_id": rid, **tag})
        await emit("run.status", {"status": "cancelled", **tag})
        return _result("cancelled", state, principal=principal)

    async def _watcher() -> None:
        while not stop.is_set():
            if await is_cancelled():
                if workenv_gate is not None:
                    workenv_gate.begin_cancel()
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
        if transport is None and workenv_mode == "pi":
            from pico_orchestrator.true_pi.workenv_http import workenv_post
            from pico_orchestrator.true_pi.workenv_ledger import WorkenvCancelGate

            created = await workenv_post(
                "/v1/internal/workenv/create",
                {
                    "run_id": rid,
                    "workspace_id": rid,
                    "conversation_id": conversation_id or rid,
                    "school_id": str(getattr(principal, "school_id", "") or ""),
                    "membership_id": str(getattr(principal, "membership_id", "") or ""),
                    "mode": "pi",
                },
            )
            transport = AttachTransport(
                run_id=rid,
                box_id=str(created.get("box_id") or "box-1"),
            )
            workenv_gate = WorkenvCancelGate()
            await _attach_workenv_fixtures(
                rid,
                principal=principal,
                artifact_store=artifact_store,
            )
        elif transport is None and workenv_mode == "exec":
            from pico_orchestrator.true_pi.workenv_ledger import WorkenvCancelGate
            from pico_orchestrator.true_pi.workenv_remote import ensure_overlay_run

            await ensure_overlay_run(
                rid,
                principal=principal,
                conversation_id=conversation_id or rid,
            )
            workenv_gate = WorkenvCancelGate()
            await _attach_workenv_fixtures(
                rid,
                principal=principal,
                artifact_store=artifact_store,
            )
        elif isinstance(transport, AttachTransport):
            from pico_orchestrator.true_pi.workenv_ledger import WorkenvCancelGate

            workenv_gate = WorkenvCancelGate()
        if transport is None:
            provider = resolve_provider()
            if provider is None:
                return await _failed(
                    emit,
                    code="model.unconfigured",
                    reason="True Pi requires DEEPSEEK_API_KEY (preferred) or KIMI_API_KEY",
                    tag=tag,
                )
            # Dual-mode (F1/F3): lane policy flows into the true_pi kernel —
            # pico-fast → deepseek-v4-flash; pico-deep → deepseek-reasoner.
            # thinking flag follows caps.thinking_on. Never a global hardcoded off.
            from pico_orchestrator.provider import (
                runtime_policy_for_model,
                uses_openai_responses_brain,
            )

            ui_model = str(getattr(caps, "ui_model", "") or "")
            policy = runtime_policy_for_model(ui_model or None)
            backend_model = str(getattr(caps, "backend_model", "") or "") or str(
                policy.get("backend_model") or provider.model
            )
            images = list(getattr(caps, "images", None) or [])
            if images:
                from pico_orchestrator.vision import vision_model_for_images

                backend_model = vision_model_for_images(backend_model)
            thinking_on = bool(getattr(caps, "thinking_on", False))
            max_context, max_out = true_pi_windows_from_caps(caps)
            openai_brain = uses_openai_responses_brain(provider)
            openai_responses_brain = openai_brain
            pi_provider = "openai" if openai_brain or provider.name != "deepseek" else "deepseek"
            pi_base = provider.base_url if openai_brain else ""
            pi_api = "openai-responses" if openai_brain else ""
            if openai_brain and rid:
                from pico_orchestrator.llm_file_pass import has_turn_files, pass_base_url

                if has_turn_files(rid):
                    pi_base = pass_base_url(rid)
                    logger.info("true_pi llm-pass baseUrl run_id=%s", rid)
            # Workbench GPT: medium. Caps thinking_on=False (edu sidebar) must
            # spawn --thinking off so content, not reasoning, hits the rail.
            pi_thinking_level = (
                ("medium" if thinking_on else "off") if openai_brain else ""
            )
            tool_server = ToolServer(
                principal=principal,
                gateway=gateway,
                run_id=rid,
                conversation_id=conversation_id,
                emit=emit,
            )
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
            session_file = (
                persist_session_file(
                    school_id=str(getattr(principal, "school_id", "") or ""),
                    conversation_id=conversation_id,
                )
                if use_tree
                else None
            )
            extra_ext: list[Path] = []
            mem_dir = persist_memory_dir(
                school_id=str(getattr(principal, "school_id", "") or ""),
                membership_id=str(getattr(principal, "membership_id", "") or ""),
            )
            mem_path = memory_extension_path()
            if mem_dir is not None and mem_path.is_file():
                extra_ext.append(mem_path)
            plan_path = plan_mode_extension_path()
            if plan_path.is_file() and want_plan_mode_extension(plan_on=plan_on):
                extra_ext.append(plan_path)
            transport = SubprocessTransport(
                session_dir=sess,
                tool_url=tool_url,
                tool_token=tool_server.token,
                run_id=rid,
                provider=pi_provider,
                model=backend_model,
                thinking=thinking_on,
                max_context=max_context,
                max_tokens=max_out,
                extra_extensions=extra_ext,
                continue_session=use_tree and session_file is None,
                session_file=session_file,
                # --plan only when the teacher toggled 先计划 this turn.
                plan_flag=plan_on,
                plan_hitl=plan_on,
                spawn_cwd=sess,
                system_prompt_text=system_text,
                accept_image=bool(images),
                base_url=pi_base,
                api=pi_api,
                thinking_level=pi_thinking_level,
                env={
                    "DEEPSEEK_API_KEY": provider.api_key
                    if pi_provider == "deepseek"
                    else "",
                    "OPENAI_API_KEY": provider.api_key
                    if pi_provider != "deepseek"
                    else "",
                    "PICO_TRUE_PI_VISIBLE_TOOLS": visible_tools_env(allowed),
                    **(
                        {
                            "PI_MEMORY_DIR": str(mem_dir),
                            "PI_AUTOCOMMIT": "0",
                        }
                        if mem_dir is not None
                        else {}
                    ),
                },
            )

        if tool_server is not None:

            def _mark_ask_timeout() -> None:
                transport.ask_timed_out = True

            tool_server.ask_timeout_hook = _mark_ask_timeout

        # Fake transport still needs a tool server if it will not invoke tools
        # via HTTP — matrix tests inject tool_results via scripted events.
        if isinstance(transport, FakeTransport) and tool_server is None:
            # No HTTP server for pure scripted runs.
            pass

        client = TruePiRpcClient(transport)
        if plan_on:
            from pico_orchestrator.ask_user import park as park_ask
            from pico_orchestrator.true_pi.client import PLAN_NEXT_QUESTION

            async def _plan_select(question: str, options: list[Any]) -> str:
                labels = [str(item).strip() for item in options if str(item).strip()]
                parked = await park_ask(
                    rid,
                    question or PLAN_NEXT_QUESTION,
                    labels,
                    emit,
                )
                if parked.get("ok"):
                    return str(parked.get("answer") or "").strip()
                from pico_orchestrator.ask_user import AskTimedOut

                if str(parked.get("error") or "") == "timeout":
                    raise AskTimedOut(str(parked.get("question") or ""))
                return ""

            transport.ui_select = _plan_select
            if hasattr(transport, "plan_hitl"):
                transport.plan_hitl = True
        await client.start()
        await emit(
            "run.model",
            {
                "ui_model": str(getattr(caps, "ui_model", "") or "") or None,
                "backend_model": str(getattr(caps, "backend_model", "") or "")
                or str(getattr(transport, "model", "") or "")
                or None,
                **tag,
            },
        )

        skill = (caps.skill_instruction or "").strip()
        # Workbench Pi session tree holds history. Do not paste N turns as text.
        # T-GROK-PATH: prompt() is the teacher original only. System lives in SYSTEM.md.
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

        await client.prompt(full_prompt, images=list(getattr(caps, "images", None) or []))

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
                await map_event(
                    event,
                    emit=emit,
                    state=state,
                    shadow=shadow,
                    artifact_store=artifact_store,
                    principal=principal,
                )
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
                if _hitl_ask_timed_out(transport):
                    await client.abort()
                    return await _failed(
                        emit,
                        code="ask.timeout",
                        reason="超时未选，没有继续。请再发一次。",
                        state=state,
                        principal=principal,
                        tag=tag,
                    )
                if await is_cancelled():
                    return await _cancel_run()
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
                # Dual-mode deep-lane circuit breaker (F2): DeepSeek 深度 empty
                # loop fuse. GPT Responses thinking is skipped (see helper).
                if thinking_on and not state.settled:
                    now = loop.time()
                    tool_gap = (
                        now - last_tool_ok_wall
                        if last_tool_ok_wall is not None
                        else now - started
                    )
                    progress_gap = now - last_progress_wall
                    if should_trip_true_pi_idle_breaker(
                        thinking_on=thinking_on,
                        openai_responses_brain=openai_responses_brain,
                        tool_oks=state.tool_oks,
                        tool_gap=tool_gap,
                        progress_gap=progress_gap,
                        breaker_seconds=breaker_seconds,
                    ):
                        await client.abort()
                        await emit(
                            "circuit.breaker",
                            {
                                "tool_exec_count": state.tool_oks,
                                "wall_seconds": int(now - started),
                                "stalled_seconds": int(progress_gap),
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

        if _hitl_ask_timed_out(transport):
            await client.abort()
            return await _failed(
                emit,
                code="ask.timeout",
                reason="超时未选，没有继续。请再发一次。",
                state=state,
                principal=principal,
                tag=tag,
            )

        if await is_cancelled():
            return await _cancel_run()

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
        collected_n = 0
        if await is_cancelled() or (
            workenv_gate is not None and not workenv_gate.collect_allowed()
        ):
            return await _cancel_run()
        if workenv_gate is not None and artifact_store is not None:
            collected_n = await _collect_workenv_into_store(
                workspace_id=rid,
                principal=principal,
                store=artifact_store,
                gate=workenv_gate,
            )
            writes = max(writes, collected_n)

        # Quota / stream errors fail the run. collected_n must not wipe that.
        if provider_error_blocks_success(state.provider_error, collected_n=collected_n):
            return await _failed(
                emit,
                code=_provider_fail_code(state.provider_error),
                reason=state.provider_error,
                state=state,
                principal=principal,
                tag=tag,
            )
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
        if not (final_text or "").strip() and writes <= 0:
            return await _failed(
                emit,
                code="pi.empty_response",
                reason="Pi agent received empty model response",
                state=state,
                principal=principal,
                tag=tag,
            )
        if final_text:
            await emit("message.delta", {"text": final_text, **tag})
        if workenv_gate is not None:
            destroyed = await _destroy_workenv_run()
            if not destroyed:
                return await _failed(
                    emit,
                    code="sandbox.workenv_destroy_failed",
                    reason="隔离环境没关掉",
                    state=state,
                    principal=principal,
                    tag=tag,
                )
            await emit("sandbox.workenv.destroy", {"workspace_id": rid, **tag})
        await emit("run.status", {"status": "succeeded", **tag})
        return RunResult(status="succeeded", final_text=final_text, token_usage=state.token_usage)

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
        from pico_orchestrator.llm_file_pass import forget_turn_files

        forget_turn_files(rid)
        stop.set()
        watcher.cancel()
        with suppress(asyncio.CancelledError):
            await watcher
        if client is not None:
            with suppress(Exception):
                # Let Pi flush the session jsonl before SIGTERM (T-LONG-HOLD).
                await client.close(kill=True)
        if tool_server is not None:
            with suppress(Exception):
                await tool_server.stop()
        if workenv_gate is not None:
            with suppress(Exception):
                await _destroy_workenv_run()


def _provider_fail_code(reason: str) -> str:
    low = (reason or "").lower()
    if "usage limit" in low or "quota" in low or "insufficient_quota" in low:
        return "model.usage_limit"
    return "true_pi.assistant_error"


def provider_error_blocks_success(reason: str | None, *, collected_n: int) -> bool:
    """True when an upstream turn error must fail the run.

    collected_n is ignored. Files already on disk stay in ArtifactStore, but
    a provider/assistant error must not stamp the run succeeded.
    """
    del collected_n
    return bool((reason or "").strip())


def pico_system_text(*, skill: str = "", system_override: str = "", day_use: str = "") -> str:
    """Pi SYSTEM.md body. Never the teacher turn; never a Landing-requirement weld."""
    override = str(system_override or "").strip()
    skill_block = str(skill or "").strip() or "(none)"
    day = str(day_use or "").strip()
    if override:
        if skill_block and skill_block != "(none)":
            body = f"{override}\n\n{skill_block}"
        else:
            body = override
    else:
        from pico_orchestrator.pi_runtime import _load_system_prompt

        body = _load_system_prompt(skill_block)
    if day:
        return f"{body}\n\n{day}"
    return body


def _bytes_from_store_row(row: dict[str, Any]) -> bytes | None:
    blob = row.get("content")
    if isinstance(blob, (bytes, bytearray)):
        return bytes(blob)
    b64 = row.get("content_base64")
    if isinstance(b64, str) and b64:
        import base64

        try:
            return base64.b64decode(b64)
        except Exception:  # noqa: BLE001
            return None
    text = row.get("content")
    if isinstance(text, str) and text:
        return text.encode("utf-8")
    return None


async def _prior_workenv_files(
    *,
    principal: Principal,
    artifact_store: ArtifactStore | None,
) -> list[dict[str, Any]]:
    """T1 round 2: previous collect bytes, newest title wins."""
    import base64

    if artifact_store is None:
        return []
    try:
        rows = await artifact_store.list(principal, limit=50)
    except Exception as _exc:  # noqa: BLE001
        del _exc
        return []
    files: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in rows:
        name = Path(str(row.get("title") or "")).name
        if not name or name in seen:
            continue
        art_id = str(row.get("artifact_id") or row.get("id") or "") or None
        try:
            full = await artifact_store.read(
                principal, artifact_id=art_id, title=name if not art_id else None
            )
        except Exception as _exc:  # noqa: BLE001
            del _exc
            continue
        if not isinstance(full, dict):
            continue
        raw = _bytes_from_store_row(full)
        if not raw:
            continue
        seen.add(name)
        files.append({"name": name, "bytes_b64": base64.b64encode(raw).decode("ascii")})
    return files


async def _attach_workenv_fixtures(
    workspace_id: str,
    *,
    principal: Principal | None = None,
    artifact_store: ArtifactStore | None = None,
) -> None:
    """Copy frozen PoC files + prior collect into /work/{run}."""
    import base64

    from pico_orchestrator.true_pi.workenv_http import workenv_post

    files: list[dict[str, Any]] = []
    prior_names: set[str] = set()
    if principal is not None:
        prior = await _prior_workenv_files(
            principal=principal, artifact_store=artifact_store
        )
        for item in prior:
            files.append(item)
            prior_names.add(str(item.get("name") or ""))
    root = Path(os.environ.get("PICO_WORKENV_FIXTURE_DIR") or "")
    if root.is_dir():
        for path in sorted(root.iterdir()):
            if not path.is_file():
                continue
            if path.suffix.lower() not in {".xlsx", ".csv", ".docx", ".pptx", ".html", ".txt"}:
                continue
            if path.name in prior_names:
                continue
            raw = path.read_bytes()
            files.append(
                {
                    "name": path.name,
                    "bytes_b64": base64.b64encode(raw).decode("ascii"),
                }
            )
    if not files:
        return
    await workenv_post(
        "/v1/internal/workenv/attach",
        {"workspace_id": workspace_id, "files": files},
    )


async def _collect_workenv_into_store(
    *,
    workspace_id: str,
    principal: Principal,
    store: ArtifactStore,
    gate: Any,
) -> int:
    """Host-side collect → ArtifactStore. Unchanged fixture bytes are not new artifacts."""
    import hashlib

    from pico_orchestrator.true_pi.workenv_http import decode_collect_files, workenv_post
    from pico_orchestrator.true_pi.workenv_ledger import WorkenvCollectRejected

    body = await workenv_post(
        "/v1/internal/workenv/collect",
        {
            "workspace_id": workspace_id,
            "glob": ["*.xlsx", "*.docx", "*.pptx", "*.html", "*.png"],
        },
    )
    files = decode_collect_files(body)
    skip_sha: dict[str, str] = {}
    root = Path(os.environ.get("PICO_WORKENV_FIXTURE_DIR") or "")
    if root.is_dir():
        for path in root.iterdir():
            if path.is_file():
                skip_sha[path.name] = hashlib.sha256(path.read_bytes()).hexdigest()
    from pico_orchestrator.artifact_types import is_valid_ooxml_package, title_protected_extension

    kept: list[dict[str, Any]] = []
    for item in files:
        name = str(item.get("name") or "")
        blob = item.get("bytes") or b""
        if not isinstance(blob, (bytes, bytearray)) or not blob:
            continue
        digest = hashlib.sha256(blob).hexdigest()
        if skip_sha.get(name) == digest:
            continue
        ext = title_protected_extension(name)
        if ext in {".docx", ".pptx", ".xlsx"} and not is_valid_ooxml_package(blob, ext):
            continue
        kept.append(item)
    if not kept:
        return 0
    try:
        rows = await gate.ingest_collect(principal, store, kept)
    except WorkenvCollectRejected:
        return 0
    return len(rows)


def _compose_prompt(
    *,
    prompt: str,
    skill: str,
    min_arts: int,
    history: list[dict[str, Any]] | None,
    allowed_tools: list[str],
    system_prompt: str = "",
) -> str:
    """User message for true Pi ``prompt()``: teacher original only.

    Skill / landing / history / tool lists are system or session-tree, not user.
    Signature kept so existing callers/tests still pass kwargs.
    """
    del skill, min_arts, history, allowed_tools, system_prompt
    return str(prompt or "")


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
    return RunResult(
        status=status,
        final_text=final_text,
        error=error,
        token_usage=state.token_usage,
    )
