"""Bypass runtime: true Pi RPC + gateway tool bridge + landing gate.

Never changes production default_runtime. Call only when:
  - tests inject a FakeTransport, or
  - PICO_TRUE_PI_BYPASS / shadow path explicitly requests it.
"""

from __future__ import annotations

import asyncio
import logging
import time
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
    """Run one turn. Fake transport skips HA. Live: Gemini → Grok → GPT on channel death."""
    kwargs = {
        "prompt": prompt,
        "principal": principal,
        "is_cancelled": is_cancelled,
        "caps": caps,
        "history": history,
        "artifact_store": artifact_store,
        "transport": transport,
        "shadow": shadow,
        "run_id": run_id,
        "session_dir": session_dir,
        "conversation_id": conversation_id,
        "persist_pi_session": persist_pi_session,
    }
    if transport is not None:
        return await _run_true_pi_once(emit=emit, **kwargs)
    from dataclasses import replace

    from pico_orchestrator.brain_ha import (
        brain_candidates,
        fallback_teacher_note,
        should_failover,
    )
    from pico_orchestrator.provider import runtime_policy_for_model

    caps = caps or RunCaps()
    ui = str(getattr(caps, "ui_model", "") or "")
    primary = str(getattr(caps, "backend_model", "") or "") or str(
        runtime_policy_for_model(ui or None).get("backend_model") or ""
    )
    models = [m for m in brain_candidates(primary) if m] or [primary]
    last: RunResult | None = None
    gate: _FailoverGate | None = None
    for i, mid in enumerate(models):
        note = fallback_teacher_note(models[0], mid) + "\n" if i > 0 else ""
        gate = _FailoverGate(emit, note)
        last = await _run_true_pi_once(
            emit=gate.emit,
            **{**kwargs, "caps": replace(caps, backend_model=mid)},
        )
        # Once the model has produced output the teacher saw it live; a
        # restart on another model would redo the task from scratch.
        if gate.live or last.status in {"succeeded", "cancelled"} or not should_failover(last):
            await gate.flush()
            return last
    if gate is not None:
        await gate.flush()
    return last or await _run_true_pi_once(emit=emit, **kwargs)


# First sign the model channel works; before it a failed attempt is dropped.
_LIVE_KINDS = frozenset({"tool.call", "message.stream", "thinking.delta", "message.delta"})


class _FailoverGate:
    """Hold one attempt's events until the model answers, then stream live."""

    def __init__(self, emit: EventEmitter, note: str) -> None:
        self._emit = emit
        self._note = note
        self._held: list[tuple[str, dict[str, Any]]] = []
        self.live = False

    async def emit(self, kind: str, payload: dict[str, Any]) -> None:
        if self.live:
            await self._emit(kind, payload)
            return
        self._held.append((kind, payload))
        if kind in _LIVE_KINDS:
            await self.flush()

    async def flush(self) -> None:
        if not self.live and self._note:
            await self._emit("message.delta", {"text": self._note})
        self.live = True
        held, self._held = self._held, []
        for kind, payload in held:
            await self._emit(kind, payload)


async def _run_true_pi_once(
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

    # edu sidebar with a page that reported affordances: one extra hand that
    # only stages proposals against those ids (edu-core#604 · Pico half).
    from pico_orchestrator.page_mutations import TOOL_NAME as PAGE_TOOL
    from pico_orchestrator.page_mutations import PageMutationBook

    page_affordances = list(getattr(caps, "page_affordances", None) or [])
    page_book = (
        PageMutationBook(
            affordances=page_affordances,
            page_title=str(getattr(caps, "page_title", "") or ""),
        )
        if page_affordances
        else None
    )
    gateway = build_default_gateway(artifact_store, page_mutations=page_book)
    allowed = resolve_visible_tools(caps.allowed_tools)
    if page_book is not None and PAGE_TOOL not in allowed:
        allowed = [*allowed, PAGE_TOOL]
    from pico_orchestrator.true_pi.runner import BOX_HIDDEN_TOOLS, runner_enabled

    school_key = str(getattr(principal, "school_id", "") or "")
    member_key = str(getattr(principal, "membership_id", "") or "")
    # Tenant fail-closed: no box without both ids (legacy spawn keeps builtins off).
    box_mode = (
        transport is None and bool(school_key and member_key) and runner_enabled(member_key)
    )
    if box_mode:
        allowed = [name for name in allowed if name not in BOX_HIDDEN_TOOLS]
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
    from pico_orchestrator.run_caps import wall_deadline, wall_expired

    deadline = wall_deadline(started, int(getattr(caps, "max_seconds", 0) or 0))
    # Dual-mode deep-lane circuit breaker (F2): true_pi must not run away on an
    # empty/no-tool-progress loop any more than the hosted kernel. Only the
    # thinking-on lane (Pico 深度) arms it; fast lane never trips.
    thinking_on = bool(getattr(caps, "thinking_on", False))
    plan_on = bool(getattr(caps, "plan_on", False))
    openai_responses_brain = False
    breaker_seconds = max(1, int(getattr(caps, "no_progress_seconds", 180) or 180))
    last_tool_ok_wall: float | None = None
    last_progress_wall = started

    async def _watcher() -> None:
        while not stop.is_set():
            if await is_cancelled():
                return
            if wall_expired(loop.time(), deadline):
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
            # Dual-mode (F1/F3): lane policy flows into the true_pi kernel —
            # pico-fast → deepseek-v4-flash; pico-deep → deepseek-reasoner.
            # thinking flag follows caps.thinking_on. Never a global hardcoded off.
            from pico_orchestrator.provider import (
                is_gemini_model,
                runtime_policy_for_model,
                uses_new_api_openai_overlay,
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
            openai_overlay = uses_new_api_openai_overlay(provider) or openai_brain
            openai_responses_brain = openai_brain
            pi_provider = "openai" if openai_overlay or provider.name != "deepseek" else "deepseek"
            pi_base = provider.base_url if openai_overlay else ""
            if openai_brain:
                pi_api = "openai-responses"
            elif openai_overlay and is_gemini_model(backend_model):
                pi_api = "openai-completions"
            else:
                pi_api = ""
            if openai_overlay and rid:
                from pico_orchestrator.llm_file_pass import has_turn_files, pass_base_url

                if has_turn_files(rid):
                    pi_base = pass_base_url(rid)
                    logger.info("true_pi llm-pass baseUrl run_id=%s", rid)
            # Workbench GPT: medium. Caps thinking_on=False (edu sidebar / pico-fast)
            # must spawn --thinking off so the first visible character is not
            # waiting on Gemini/GPT reasoning (#1005 首字).
            pi_thinking_level = (
                ("medium" if thinking_on else "off")
                if (openai_brain or is_gemini_model(backend_model))
                else ""
            )
            tool_server = ToolServer(
                principal=principal,
                gateway=gateway,
                run_id=rid,
                conversation_id=conversation_id,
                emit=emit,
            )
            persist_dir = (
                persist_session_dir(
                    school_id=school_key,
                    membership_id=member_key,
                    conversation_id=conversation_id,
                )
                if persist_pi_session
                else None
            )
            sess = session_dir or persist_dir or (session_root() / rid)
            use_tree = persist_dir is not None and session_dir is None
            session_file = (
                persist_session_file(
                    school_id=school_key,
                    membership_id=member_key,
                    conversation_id=conversation_id,
                )
                if use_tree
                else None
            )
            extra_ext: list[Path] = []
            mem_dir = persist_memory_dir(
                school_id=school_key,
                membership_id=member_key,
            )
            mem_path = memory_extension_path()
            if mem_dir is not None and mem_path.is_file():
                extra_ext.append(mem_path)
            plan_path = plan_mode_extension_path()
            if plan_path.is_file() and want_plan_mode_extension(plan_on=plan_on):
                extra_ext.append(plan_path)
            from pico_orchestrator.true_pi.runner import (
                WORKSPACE_SYSTEM,
                RunnerSpec,
                RunnerTransport,
                WorkspaceKey,
                take_conversation_files,
            )

            transport_cls: Any = SubprocessTransport
            runner_kwargs: dict[str, Any] = {}
            if box_mode:
                from pico_orchestrator.llm_file_pass import turn_files

                # Box always speaks OpenAI-compatible to the runner proxy; the
                # real upstream (+ key) stays in pico-api.
                llm_upstream = pi_base or provider.base_url
                if pi_provider == "deepseek" or not pi_api:
                    pi_provider = "openai"
                    pi_api = pi_api or "openai-completions"
                ws_key = WorkspaceKey.for_run(
                    school_id=school_key,
                    membership_id=member_key,
                    conversation_id=conversation_id,
                    run_id=rid,
                )
                runner_kwargs["runner"] = RunnerSpec(
                    key=ws_key,
                    llm_upstream=llm_upstream,
                    llm_key=provider.api_key,
                    with_memory=mem_dir is not None and mem_path in extra_ext,
                    attachments=_box_attachments(
                        take_conversation_files(member_key, conversation_id),
                        [(f.filename, f.data) for f in turn_files(rid)],
                    ),
                )
                system_text = f"{system_text}\n\n{WORKSPACE_SYSTEM}".strip()
                transport_cls = RunnerTransport
            transport = transport_cls(
                **runner_kwargs,
                session_dir=sess,
                tool_url="",
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
            # Bind the tool port while writing models.json so spawn is not
            # waiting on both serially (#1005 首字).
            url_task = asyncio.create_task(tool_server.start())
            transport.prepare_agent_home()
            transport.tool_url = await url_task

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
        ws_on = getattr(transport, "runner", None) is not None
        ws_before: dict[str, Any] | None = None
        ws_since = time.time()
        if ws_on:
            # Snapshot before the box exists (the runner refuses file access
            # while one runs). On failure landing falls back to mtime >= since.
            from pico_orchestrator.true_pi.runner import list_outputs

            try:
                ws_before = await list_outputs(transport.runner.key)
            except Exception as exc:  # noqa: BLE001
                logger.warning("true_pi runner outputs snapshot failed: %s", type(exc).__name__)
        await client.start()
        await emit(
            "run.model",
            {
                "ui_model": str(getattr(caps, "ui_model", "") or "") or None,
                "backend_model": str(getattr(caps, "backend_model", "") or "")
                or str(getattr(transport, "model", "") or "")
                or None,
                # Which hands this run could actually call (receipt, not a schema).
                "visible_tools": list(allowed),
                **tag,
            },
        )

        skill = (caps.skill_instruction or "").strip()
        # Workbench Pi session tree holds history. Do not paste N turns as text.
        # T-GROK-PATH: prompt() is the teacher original only. System lives in SYSTEM.md.
        tree_history = history
        if persist_pi_session and persist_session_dir(
            school_id=str(getattr(principal, "school_id", "") or ""),
            membership_id=str(getattr(principal, "membership_id", "") or ""),
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

        async def _drive(prompt_text: str, images: list[dict[str, Any]]) -> RunResult | None:
            """One prompt on the live Pi session. Returns a RunResult only on an early stop."""
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
                # Consume must run while wait_response sits on prompt ack.
                # Live Pi can stream text_delta before the prompt response;
                # starting after prompt() made TTFB == generation wall time.
                await client.prompt(prompt_text, images=images)
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
                        await client.abort()
                        await emit("run.status", {"status": "cancelled", **tag})
                        return _result("cancelled", state, principal=principal)
                    if timed_out.is_set() or wall_expired(loop.time(), deadline):
                        await client.abort()
                        return await _wall_stop(
                            emit,
                            caps=caps,
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
            return None

        early = await _drive(full_prompt, list(getattr(caps, "images", None) or []))
        if early is not None:
            return early
        # Same-session resume (#1104): one upstream error after the model already
        # did work must not throw the whole long task away. Pi keeps the turn in
        # its session; ask it to carry on from where it stopped. Before any
        # output brain-HA still fails over to the next model instead.
        from pico_orchestrator.true_pi.config import resume_max

        budget = resume_max()
        while (
            state.settled
            and state.provider_error
            and state.has_output
            and not state.no_resume
            and state.resumes < budget
            and _provider_fail_code(state.provider_error) != "model.usage_limit"
        ):
            state.resumes += 1
            reason = str(state.provider_error)[:200]
            logger.info("true_pi resume run_id=%s n=%s/%s reason=%s", rid, state.resumes, budget, reason)
            state.provider_error = None
            state.settled = False
            state.event_kinds.append("run.resume")
            await emit(
                "run.resume",
                {"attempt": state.resumes, "max": budget, "reason": reason, **tag},
            )
            await emit("message.delta", {"text": resume_teacher_note(state.resumes), **tag})
            early = await _drive(resume_prompt(reason), [])
            if early is not None:
                return early
        if state.event_kinds:
            logger.info(
                "true_pi mapped_kinds run_id=%s n=%s kinds=%s",
                rid,
                len(state.event_kinds),
                ",".join(state.event_kinds[:120]),
            )

        async def salvage_outputs() -> None:
            # A turn that stops early still delivers what it already saved.
            if ws_on:
                await _land_workspace_outputs(
                    transport=transport,
                    before=ws_before,
                    since=ws_since,
                    artifact_store=artifact_store,
                    principal=principal,
                    state=state,
                    emit=emit,
                    tag=tag,
                )

        if _hitl_ask_timed_out(transport):
            await client.abort()
            await salvage_outputs()
            return await _failed(
                emit,
                code="ask.timeout",
                reason="超时未选，没有继续。请再发一次。",
                state=state,
                principal=principal,
                tag=tag,
            )

        if await is_cancelled():
            await client.abort()
            await salvage_outputs()
            await emit("run.status", {"status": "cancelled", **tag})
            return _result("cancelled", state, principal=principal)

        if timed_out.is_set() or wall_expired(loop.time(), deadline):
            await client.abort()
            await salvage_outputs()
            return await _wall_stop(
                emit,
                caps=caps,
                state=state,
                principal=principal,
                tag=tag,
            )

        if not state.settled and not state.started:
            # Stream ended with no agent_start (e.g. process died).
            await salvage_outputs()
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
                await salvage_outputs()
                return await _failed(
                    emit,
                    code="timeout",
                    reason=f"True Pi did not settle within {caps.max_seconds}s",
                    state=state,
                    principal=principal,
                    tag=tag,
                )

        # Upstream said this turn failed (quota / provider). Do not succeed blank.
        if state.provider_error:
            await salvage_outputs()
            return await _failed(
                emit,
                code=_provider_fail_code(state.provider_error),
                reason=state.provider_error,
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

        ws_landed: list[tuple[str, dict[str, Any]]] = []
        if ws_on:
            ws_landed = await _land_workspace_outputs(
                transport=transport,
                before=ws_before,
                since=ws_since,
                artifact_store=artifact_store,
                principal=principal,
                state=state,
                emit=emit,
                tag=tag,
            )

        write_basis = state.tool_results
        if ws_on and tool_server is not None:
            # Box can forge Pi RPC tool events; count only what Pico itself saw.
            write_basis = [*tool_server.trusted_results, *ws_landed]
        writes = count_write_tool_successes(write_basis)
        write_fail = failed_write_user_message(write_basis)
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
            payload = {"text": final_text, **tag}
            if state.text_streamed:
                # Live SSE already got token deltas. Ledger the cleaned
                # answer once; do not dump the whole bubble again.
                payload["ledger_only"] = True
            await emit("message.delta", payload)
        if page_book is not None and page_book.mutations:
            await emit(
                "page.mutations",
                {"count": len(page_book.mutations), "page_title": page_book.page_title, **tag},
            )
        await emit("run.status", {"status": "succeeded", **tag})
        return RunResult(
            status="succeeded",
            final_text=final_text,
            token_usage=state.token_usage,
            change_proposal=page_book.change_proposal() if page_book else None,
            page_mutations=list(page_book.mutations) if page_book else None,
        )

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


def _box_attachments(
    conversation: list[tuple[str, bytes]], turn: list[tuple[str, bytes]]
) -> list[tuple[str, bytes]]:
    """All conversation uploads (any type) plus this turn's native files, by name."""
    out: dict[str, bytes] = {}
    for name, data in [*conversation, *turn]:
        if name and data:
            out[str(name)] = bytes(data)
    return list(out.items())


async def _land_workspace_outputs(
    *,
    transport: Any,
    before: dict[str, Any] | None,
    since: float,
    artifact_store: ArtifactStore | None,
    principal: Principal,
    state: EventMapState,
    emit: EventEmitter,
    tag: dict[str, Any],
) -> list[tuple[str, dict[str, Any]]]:
    """Workspace ``outputs/`` → Pico ledger, shown like any write tool.

    Returns what landed: the only workspace delivery evidence that counts
    (a ``workspace_output`` event from the box's RPC stream can be forged).
    """
    import json as _json

    from pico_orchestrator.true_pi.runner import land_outputs

    # Stop the box first: files are only read once nothing can race them.
    with suppress(Exception):
        await transport.close(kill=True)
    try:
        landed = await land_outputs(
            key=transport.runner.key,
            before=before,
            since=since,
            artifact_store=artifact_store,
            principal=principal,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("true_pi runner land outputs failed: %s", type(exc).__name__)
        landed = [("workspace_output", {"error": "工作区文件没能取回，请再跑一次。"})]
    for name, result in landed:
        state.tool_results.append((name, result))
        failed = bool(result.get("error"))
        payload = {
            "tool": name,
            "ok": not failed,
            "result": _json.dumps(result, ensure_ascii=False),
            "message": str(result.get("error") or "ok"),
            "call_id": f"ws-{len(state.tool_results)}",
            **tag,
        }
        if failed:
            payload["user_message"] = str(result.get("error"))
        state.event_kinds.append("tool.result")
        await emit("tool.result", payload)
    return landed


def _provider_fail_code(reason: str) -> str:
    low = (reason or "").lower()
    if "usage limit" in low or "quota" in low or "insufficient_quota" in low:
        return "model.usage_limit"
    return "true_pi.assistant_error"


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


def resume_teacher_note(attempt: int) -> str:
    return f"（模型渠道中断了一次，已自动从断处续跑，第 {attempt} 次）\n"


def resume_prompt(reason: str) -> str:
    """User turn Pi gets after an upstream error: carry on, do not redo saved work."""
    why = (reason or "").strip().replace("\n", " ")[:200]
    return (
        f"上游模型刚才中断了一次（{why}）。请从中断处继续完成原任务："
        "先看工作区里已经写好的文件，不要重做，只补齐剩下的部分，然后照常交付。"
    )


async def _wall_stop(
    emit: EventEmitter,
    *,
    caps: RunCaps,
    state: EventMapState,
    principal: Principal | None,
    tag: dict[str, Any],
) -> RunResult:
    """Hit Pico wall: teacher-facing pause, not a failed error bubble."""
    from pico_orchestrator.user_errors import wall_stop_teacher_text

    writes = count_write_tool_successes(state.tool_results)
    text = wall_stop_teacher_text(
        max_seconds=int(getattr(caps, "max_seconds", 0) or 0),
        has_deliverable=writes > 0,
    )
    state.final_parts.append(text)
    await emit("message.delta", {"text": text, **tag})
    await emit("run.status", {"status": "succeeded", "code": "wall.stop", **tag})
    return _result("succeeded", state, principal=principal)


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
