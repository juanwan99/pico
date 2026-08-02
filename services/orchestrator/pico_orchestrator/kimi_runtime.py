"""Feature-flagged Kimi Agent Session runtime.

This module is reachable only when the runtime gate is on and the principal is allowlisted.
The production default remains the transitional ``run_agent_loop``.
"""

from __future__ import annotations

import asyncio
import os
import shutil
import tempfile
import time
from collections.abc import Awaitable, Callable
from contextlib import suppress
from pathlib import Path
from typing import Any

from kaos.path import KaosPath
from kimi_agent_sdk import (
    ApprovalRequest,
    Config,
    LLMNotSet,
    MaxStepsReached,
    RunCancelled,
    Session,
    StatusUpdate,
    StepBegin,
    TextPart,
    TurnEnd,
)

from pico_orchestrator.gateway import ArtifactStore, Principal
from pico_orchestrator.kimi_adapter import KimiEventContractError, KimiWireEventAdapter
from pico_orchestrator.kimi_tools import GatewayToolContext, bind_gateway_tools
from pico_orchestrator.provider import resolve_provider
from pico_orchestrator.runner import EventEmitter, RunCaps, RunResult
from pico_orchestrator.tools_builtin import build_default_gateway
from pico_orchestrator.user_errors import enrich_fail_payload


def _agent_bundle_dir() -> Path:
    """Prefer package data (wheel/image), fall back to repo agents/."""
    packaged = Path(__file__).resolve().parent / "agent_assets"
    if (packaged / "pico-kimi-runtime.yaml").is_file() and (packaged / "system.md").is_file():
        return packaged
    repo = Path(__file__).resolve().parents[1] / "agents"
    return repo


_AGENT_DIR = _agent_bundle_dir()
_AGENT_FILE = _AGENT_DIR / "pico-kimi-runtime.yaml"
_SYSTEM_PROMPT_FILE = _AGENT_DIR / "system.md"
_CANCEL_POLL_SECONDS = 0.05
_USAGE_FIELDS = (
    "input_tokens",
    "output_tokens",
    "total_tokens",
    "input_cache_read",
    "input_cache_creation",
)


async def run_kimi_agent(
    *,
    prompt: str,
    principal: Principal,
    emit: EventEmitter,
    is_cancelled: Callable[[], Awaitable[bool]],
    caps: RunCaps | None = None,
    history: list[dict[str, Any]] | None = None,
    artifact_store: ArtifactStore | None = None,
) -> RunResult:
    """Run one Kimi Session turn and map its merged Wire stream to Pico events."""

    caps = caps or RunCaps()
    if await is_cancelled():
        await emit("run.status", {"status": "cancelled", "runtime": "kimi-agent"})
        return RunResult(status="cancelled", final_text="")

    provider = resolve_provider()
    if provider is None or provider.name != "kimi":
        return await _failed_result(
            emit,
            code="model.unconfigured",
            reason="Kimi Agent runtime requires server-side KIMI_API_KEY",
        )

    config = Config.model_validate(
        {
            "default_model": "pico-runtime",
            "models": {
                "pico-runtime": {
                    "provider": "pico-kimi",
                    "model": provider.model,
                    "max_context_size": 128_000,
                }
            },
            "providers": {
                "pico-kimi": {
                    "type": "kimi",
                    "base_url": provider.base_url,
                    "api_key": provider.api_key,
                }
            },
        }
    )
    gateway = build_default_gateway(artifact_store).restricted_to(caps.allowed_tools)
    adapter = KimiWireEventAdapter()
    final_parts: list[str] = []
    token_usage: dict[str, int] | None = None
    terminal_status: str | None = None
    current_step: int | None = None
    usage_by_step: dict[int | str, dict[str, int]] = {}
    unscoped_usage_updates = 0

    work_base = _kimi_work_base()
    _sweep_old_kimi_runs(work_base)
    # Session-owned sandbox (may be reset by the SDK). Agent bundle lives outside it.
    work_dir = Path(tempfile.mkdtemp(prefix="run-", dir=str(work_base)))
    skills_dir = work_dir / "skills"
    skills_dir.mkdir(parents=True, exist_ok=True)
    work_agent_file = _stage_shared_agent_bundle(work_base)
    try:
        with bind_gateway_tools(gateway, principal, emit=emit) as tool_context:
            stop_watcher = asyncio.Event()
            timed_out = asyncio.Event()
            token_cap_exceeded = asyncio.Event()
            contract_failure: list[str] = []
            try:
                session = await Session.create(
                    work_dir=KaosPath(work_dir),
                    config=config,
                    model="pico-runtime",
                    yolo=False,
                    agent_file=work_agent_file,
                    mcp_configs=[],
                    skills_dir=KaosPath(skills_dir),
                    max_steps_per_turn=caps.max_steps,
                    max_retries_per_step=max(1, caps.max_retries),
                    max_ralph_iterations=0,
                )
                async with session:
                    watcher = asyncio.create_task(
                        _watch_cancel(
                            session,
                            is_cancelled,
                            stop_watcher,
                            timed_out,
                            caps.max_seconds,
                        )
                    )
                    try:
                        async for message in session.prompt(
                            _user_input(prompt, history, caps.skill_instruction),
                            merge_wire_messages=True,
                        ):
                            if isinstance(message, TurnEnd) and await is_cancelled():
                                session.cancel()
                                await emit(
                                    "run.status",
                                    {"status": "cancelled", "runtime": "kimi-agent"},
                                )
                                return _result(
                                    "cancelled",
                                    final_parts,
                                    token_usage=token_usage,
                                    tool_context=tool_context,
                                )
                            if contract_failure:
                                session.cancel()
                                continue
                            if token_cap_exceeded.is_set():
                                session.cancel()
                                continue
                            if isinstance(message, StepBegin):
                                current_step = message.n
                            try:
                                for event in adapter.feed(message):
                                    payload = event.payload
                                    if event.type == "run.usage":
                                        step_total = payload.get("total_tokens")
                                        if isinstance(step_total, int):
                                            if current_step is None:
                                                unscoped_usage_updates += 1
                                                usage_key: int | str = (
                                                    f"update:{unscoped_usage_updates}"
                                                )
                                            else:
                                                usage_key = current_step
                                            usage_by_step[usage_key] = {
                                                field: int(payload.get(field) or 0)
                                                for field in _USAGE_FIELDS
                                            }
                                            cumulative = {
                                                field: sum(
                                                    usage[field]
                                                    for usage in usage_by_step.values()
                                                )
                                                for field in _USAGE_FIELDS
                                            }
                                            payload = {
                                                **payload,
                                                **{
                                                    f"cumulative_{field}": value
                                                    for field, value in cumulative.items()
                                                },
                                            }
                                            token_usage = {
                                                "total_tokens": cumulative["total_tokens"]
                                            }
                                    await emit(event.type, payload)
                                    if event.type == "run.status":
                                        terminal_status = str(payload.get("status") or "")
                            except KimiEventContractError as exc:
                                contract_failure.append(str(exc))
                                session.cancel()
                                continue
                            if isinstance(message, TextPart):
                                final_parts.append(message.text)
                            elif (
                                isinstance(message, StatusUpdate)
                                and token_usage is not None
                                and token_usage["total_tokens"] > caps.max_tokens
                            ):
                                token_cap_exceeded.set()
                                session.cancel()
                            elif isinstance(message, ApprovalRequest):
                                # No Pico approval control plane exists in KA-2.
                                message.resolve("reject")
                    finally:
                        stop_watcher.set()
                        watcher.cancel()
                        with suppress(asyncio.CancelledError):
                            await watcher
            except RunCancelled:
                if timed_out.is_set():
                    return await _failed_result(
                        emit,
                        code="timeout",
                        reason=f"Kimi Agent timeout after {caps.max_seconds}s",
                        final_parts=final_parts,
                        token_usage=token_usage,
                        tool_context=tool_context,
                    )
                if token_cap_exceeded.is_set():
                    return await _failed_result(
                        emit,
                        code="token_cap",
                        reason=f"Kimi Agent token cap exceeded: {caps.max_tokens}",
                        final_parts=final_parts,
                        token_usage=token_usage,
                        tool_context=tool_context,
                    )
                if contract_failure:
                    return await _failed_result(
                        emit,
                        code="kimi.event_contract",
                        reason=contract_failure[0],
                        final_parts=final_parts,
                        token_usage=token_usage,
                        tool_context=tool_context,
                    )
                await emit("run.status", {"status": "cancelled", "runtime": "kimi-agent"})
                return _result(
                    "cancelled",
                    final_parts,
                    token_usage=token_usage,
                    tool_context=tool_context,
                )
            except LLMNotSet:
                return await _failed_result(
                    emit,
                    code="model.unconfigured",
                    reason="Kimi Agent LLM is not configured",
                    final_parts=final_parts,
                    tool_context=tool_context,
                )
            except MaxStepsReached:
                return await _failed_result(
                    emit,
                    code="kimi.max_steps",
                    reason="Kimi Agent reached the step limit",
                    final_parts=final_parts,
                    token_usage=token_usage,
                    tool_context=tool_context,
                )
            except KimiEventContractError as exc:
                return await _failed_result(
                    emit,
                    code="kimi.event_contract",
                    reason=str(exc),
                    final_parts=final_parts,
                    token_usage=token_usage,
                    tool_context=tool_context,
                )
            except asyncio.CancelledError:
                if "session" in locals():
                    session.cancel()
                raise
            except Exception as exc:  # noqa: BLE001 - sanitize provider/runtime failures
                missing = isinstance(exc, (FileNotFoundError, OSError)) or (
                    "No such file" in str(exc)
                )
                path_hint = str(exc)
                # If Session wiped its sandbox after tools already ran, prefer ledger truth
                # over a hard fail when we already have assistant text or tool results.
                if missing and (
                    final_parts
                    or (tool_context is not None and tool_context.results)
                ):
                    await emit(
                        "run.error",
                        enrich_fail_payload(
                            {
                                "code": "kimi.workdir_race",
                                "error": path_hint,
                                "recovered": True,
                            }
                        ),
                    )
                    if terminal_status != "succeeded":
                        await emit(
                            "run.status",
                            {"status": "succeeded", "runtime": "kimi-agent", "recovered": True},
                        )
                    return _result(
                        "succeeded",
                        final_parts,
                        token_usage=token_usage,
                        tool_context=tool_context,
                    )
                return await _failed_result(
                    emit,
                    code="kimi.runtime_error",
                    reason=(
                        f"Kimi Agent runtime error ({type(exc).__name__}: {exc})"
                        if missing
                        else f"Kimi Agent runtime error ({type(exc).__name__})"
                    ),
                    final_parts=final_parts,
                    token_usage=token_usage,
                    tool_context=tool_context,
                )

    finally:
        # Only the per-run sandbox. Agent bundle is shared and must survive.
        # Defer slightly so Session teardown cannot race the rmtree.
        try:
            await asyncio.sleep(0)
        except Exception:  # noqa: BLE001
            pass
        if work_dir.is_dir():
            shutil.rmtree(work_dir, ignore_errors=True)

    if timed_out.is_set():
        return await _failed_result(
            emit,
            code="timeout",
            reason=f"Kimi Agent timeout after {caps.max_seconds}s",
            final_parts=final_parts,
            token_usage=token_usage,
            tool_context=tool_context,
        )
    if token_cap_exceeded.is_set():
        return await _failed_result(
            emit,
            code="token_cap",
            reason=f"Kimi Agent token cap exceeded: {caps.max_tokens}",
            final_parts=final_parts,
            token_usage=token_usage,
            tool_context=tool_context,
        )
    if contract_failure:
        return await _failed_result(
            emit,
            code="kimi.event_contract",
            reason=contract_failure[0],
            final_parts=final_parts,
            token_usage=token_usage,
            tool_context=tool_context,
        )
    if terminal_status != "succeeded":
        return await _failed_result(
            emit,
            code="kimi.missing_terminal",
            reason="Kimi Agent stream ended without TurnEnd",
            final_parts=final_parts,
            token_usage=token_usage,
        )
    return _result(
        "succeeded",
        final_parts,
        token_usage=token_usage,
        tool_context=tool_context,
    )



def _kimi_work_base() -> Path:
    """Prefer durable app data over ephemeral /tmp (survives scrubbers + volume)."""
    env = os.environ.get("PICO_KIMI_WORKDIR_BASE", "").strip()
    candidates: list[Path] = []
    if env:
        candidates.append(Path(env))
    candidates.append(Path("/app/data/kimi-work"))
    candidates.append(Path(tempfile.gettempdir()) / "pico-kimi-work")
    for base in candidates:
        try:
            base.mkdir(parents=True, exist_ok=True)
            probe = base / ".pico-write-probe"
            probe.write_text("ok", encoding="utf-8")
            probe.unlink(missing_ok=True)
            return base
        except OSError:
            continue
    # Last resort: relative local dir
    fallback = Path("data/kimi-work").resolve()
    fallback.mkdir(parents=True, exist_ok=True)
    return fallback


def _sweep_old_kimi_runs(work_base: Path, *, max_age_sec: int = 3600) -> None:
    """Best-effort cleanup of prior run dirs. Never delete the active run dir here."""
    now = time.time()
    try:
        children = list(work_base.iterdir())
    except OSError:
        return
    for child in children:
        if not child.is_dir() or not child.name.startswith("run-"):
            continue
        try:
            age = now - child.stat().st_mtime
            if age >= max_age_sec:
                shutil.rmtree(child, ignore_errors=True)
        except OSError:
            continue


def _stage_shared_agent_bundle(work_base: Path) -> Path:
    """Stage yaml+system.md under work_base/agent-bundle (NOT under Session work_dir).

    Kimi Session may reset/clear ``work_dir`` during a turn. Keeping the agent
    spec outside that directory prevents mid-run FileNotFoundError on the bundle.
    """
    bundle = work_base / "agent-bundle"
    bundle.mkdir(parents=True, exist_ok=True)
    return _stage_agent_bundle(bundle)

def _stage_agent_bundle(work_dir: Path) -> Path:
    """Stage agent yaml + system.md where Session resolves paths.

    Kimi Session treats ``work_dir`` as the resolution root for relative
    ``system_prompt_path: ./system.md``. Staging only under ``work_dir/agent/``
    causes intermittent FileNotFoundError. Copy to **work_dir root** and keep a
    duplicate under ``agent/`` for debugging.
    """

    work_dir.mkdir(parents=True, exist_ok=True)
    agent_dir = work_dir / "agent"
    agent_dir.mkdir(parents=True, exist_ok=True)

    resolved: list[Path] = []
    for candidate in (_AGENT_FILE, _SYSTEM_PROMPT_FILE):
        if candidate.is_file():
            resolved.append(candidate)
            continue
        alt = Path(__file__).resolve().parents[1] / "agents" / candidate.name
        if alt.is_file():
            resolved.append(alt)
            continue
        raise FileNotFoundError(
            f"Kimi agent asset missing: {candidate} (also tried {alt})"
        )

    for source in resolved:
        shutil.copy2(source, work_dir / source.name)
        shutil.copy2(source, agent_dir / source.name)

    staged = (work_dir / "pico-kimi-runtime.yaml").resolve()
    system_staged = (work_dir / "system.md").resolve()
    if not staged.is_file() or not system_staged.is_file():
        raise FileNotFoundError(
            f"staged agent assets incomplete under {work_dir}: "
            f"yaml={staged.is_file()} system={system_staged.is_file()}"
        )

    # Force relative prompt path next to the yaml (SDK-safe).
    text = staged.read_text(encoding="utf-8")
    lines: list[str] = []
    for line in text.splitlines(keepends=True):
        if "system_prompt_path:" in line:
            indent = line.split("system_prompt_path:")[0]
            nl = "\n" if line.endswith("\n") else ""
            lines.append(f"{indent}system_prompt_path: ./system.md{nl}")
        else:
            lines.append(line)
    staged.write_text("".join(lines), encoding="utf-8")

    # Preflight open — surface the real path if anything is wrong.
    with staged.open("rb") as handle:
        handle.read(64)
    with system_staged.open("rb") as handle:
        handle.read(64)
    return staged


async def _watch_cancel(
    session: Session,
    is_cancelled: Callable[[], Awaitable[bool]],
    stop: asyncio.Event,
    timed_out: asyncio.Event,
    max_seconds: int,
) -> None:
    loop = asyncio.get_running_loop()
    deadline = loop.time() + max_seconds
    while not stop.is_set():
        if await is_cancelled():
            session.cancel()
            return
        remaining = deadline - loop.time()
        if remaining <= 0:
            timed_out.set()
            session.cancel()
            return
        try:
            await asyncio.wait_for(
                stop.wait(), timeout=min(_CANCEL_POLL_SECONDS, remaining)
            )
        except TimeoutError:
            pass


def _user_input(
    prompt: str,
    history: list[dict[str, Any]] | None,
    skill_instruction: str,
) -> str:
    parts: list[str] = []
    if skill_instruction:
        parts.append(f"<pico_skill_instruction>\n{skill_instruction}\n</pico_skill_instruction>")
    transcript: list[str] = []
    for item in (history or [])[-20:]:
        role = item.get("role")
        content = item.get("content")
        if role in {"user", "assistant"} and content:
            transcript.append(f"{role}: {str(content)[:4000]}")
    if transcript:
        parts.append("<conversation_history>\n" + "\n".join(transcript) + "\n</conversation_history>")
    parts.append(prompt)
    return "\n\n".join(parts)


async def _failed_result(
    emit: EventEmitter,
    *,
    code: str,
    reason: str,
    final_parts: list[str] | None = None,
    token_usage: dict[str, int] | None = None,
    tool_context: GatewayToolContext | None = None,
) -> RunResult:
    await emit(
        "run.error",
        enrich_fail_payload({"code": code, "error": reason}),
    )
    await emit(
        "run.status",
        enrich_fail_payload(
            {
                "status": "failed",
                "reason": reason,
                "code": code,
                "runtime": "kimi-agent",
            }
        ),
    )
    result = _result(
        "failed",
        final_parts or [],
        error=reason,
        token_usage=token_usage,
        tool_context=tool_context,
    )
    return result


def _result(
    status: str,
    final_parts: list[str],
    *,
    error: str | None = None,
    token_usage: dict[str, int] | None = None,
    tool_context: GatewayToolContext | None = None,
) -> RunResult:
    artifact_markdown: str | None = None
    change_proposal: dict[str, Any] | None = None
    for name, value in tool_context.results if tool_context else []:
        if name == "fake_edu_list_classes":
            artifact_markdown = _classes_artifact(value)
        elif name == "pico_propose_change":
            change_proposal = value
    return RunResult(
        status=status,
        final_text="".join(final_parts).strip(),
        error=error,
        token_usage=token_usage,
        artifact_markdown=artifact_markdown,
        change_proposal=change_proposal,
    )


def _classes_artifact(result: dict[str, Any]) -> str:
    lines = [
        f"# 班级列表（{result.get('school_id', '')}）",
        "",
        "| ID | 名称 |",
        "|----|------|",
    ]
    for item in result.get("classes") or []:
        lines.append(f"| {item.get('id', '')} | {item.get('name', '')} |")
    return "\n".join(lines)
