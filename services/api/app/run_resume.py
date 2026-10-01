"""Restart resume for workspace runs (#1133).

Thin adapter. The Pi session (``.pico/session/pico.jsonl`` in the workspace)
already holds the whole turn; a pico-api restart only loses the in-process
owner. So the stream path stores what the owner was started with, and on
startup pico-api calls the same runtime again — same run_id, same Pi
session — asking Pi to carry on. No second runner, no state machine.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import time
from dataclasses import fields, replace
from typing import Any

from sqlalchemy import select

from app.auth import Principal, payer_for
from app.db import EventRow, RunRow, append_event, session_factory
from app.run_service import _json_dict, _track_inflight
from app.settings import get_settings, millipoints_for_usage

logger = logging.getLogger(__name__)

SPEC_KEY = "resume_spec"
REASON = "api.restart"
RESTART_PROMPT = (
    "服务刚才重启，打断了这个任务。请从中断处继续完成原任务："
    "先看工作区里已经写好的文件，不要重做，只补齐剩下的部分，然后照常交付。"
)
TEACHER_NOTE = "服务刚才重启，任务正在从断处接着跑。"
RUNNER_WAIT_S = 120.0
# Rebuilt per resume, or too big / not JSON: never stored.
_CAPS_SKIP = frozenset({"images", "millipoints_for_usage", "outputs_since"})
_ACTIVE = ("queued", "preparing", "running")

_shutting_down = False


def mark_shutting_down() -> None:
    global _shutting_down
    _shutting_down = True


def shutting_down() -> bool:
    return _shutting_down


def build_spec(
    *,
    caps: Any,
    principal: Principal,
    conversation_id: str | None,
    task_id: str,
) -> dict[str, Any] | None:
    """What ``resume_run`` needs. None when the run has no workspace session."""
    from pico_orchestrator.true_pi.runner import runner_enabled

    if not conversation_id or not runner_enabled(principal.membership_id):
        return None
    spec = {
        "v": 1,
        "caps": {f.name: getattr(caps, f.name) for f in fields(caps) if f.name not in _CAPS_SKIP},
        "principal": {
            "school_id": principal.school_id,
            "membership_id": principal.membership_id,
            "scopes": list(principal.scopes),
            "iss": principal.iss,
            "aud": principal.aud,
            "exp": principal.exp,
            "raw": dict(principal.raw or {}),
        },
        "conversation_id": conversation_id,
        "task_id": task_id,
        "started": time.time(),
    }
    try:
        json.dumps(spec, ensure_ascii=False)
    except (TypeError, ValueError):
        return None
    return spec


async def save_spec(run_id: str, spec: dict[str, Any] | None) -> None:
    if spec is None:
        return
    try:
        async with session_factory()() as session:
            run = await session.get(RunRow, run_id)
            if run is None or run.status not in _ACTIVE:
                return
            blob = _json_dict(run.token_usage_json)
            blob[SPEC_KEY] = spec
            run.token_usage_json = json.dumps(blob, ensure_ascii=False)
            await session.commit()
    except Exception as exc:  # noqa: BLE001 — resume is best-effort, the run is not
        logger.warning("resume spec not saved run=%s: %s", run_id, type(exc).__name__)


def spec_of(run: RunRow) -> dict[str, Any] | None:
    spec = _json_dict(run.token_usage_json).get(SPEC_KEY)
    return spec if isinstance(spec, dict) and spec.get("v") == 1 else None


async def _restart_resumes(session: Any, run_id: str) -> int:
    rows = (
        await session.execute(
            select(EventRow.payload_json).where(EventRow.run_id == run_id, EventRow.type == "run.resume")
        )
    ).scalars()
    return sum(1 for raw in rows if _json_dict(raw).get("reason") == REASON)


async def resumable(session: Any, run: RunRow) -> bool:
    """Left ``running`` across a restart: workspace run, not stopped, not too old,
    restart resumes left."""
    settings = get_settings()
    limit = int(settings.pico_run_restart_resume_max)
    spec = spec_of(run)
    if limit <= 0 or spec is None or run.cancel_requested or run.status not in _ACTIVE:
        return False
    wall = int(settings.pico_run_durable_max_seconds)
    if wall > 0 and time.time() - float(spec.get("started") or 0) > wall:
        return False
    return await _restart_resumes(session, run.id) < limit


async def keep_for_resume(run_id: str) -> bool:
    """Shutdown cancelled this run's owner: leave it ``running`` for the next process."""
    try:
        async with session_factory()() as session:
            run = await session.get(RunRow, run_id)
            if run is None or not await resumable(session, run):
                return False
            await append_event(session, run_id, "run.interrupted", {"reason": REASON})
            return True
    except Exception as exc:  # noqa: BLE001
        logger.warning("resume keep failed run=%s: %s", run_id, type(exc).__name__)
        return False


async def resume_orphaned_runs() -> int:
    """Startup: hand every resumable orphan back to the runtime."""
    limit = int(get_settings().pico_run_restart_resume_max)
    if limit <= 0:
        return 0
    picked: list[str] = []
    async with session_factory()() as session:
        runs = (await session.execute(select(RunRow).where(RunRow.status.in_(_ACTIVE)))).scalars().all()
        for run in runs:
            if not await resumable(session, run):
                continue
            attempt = await _restart_resumes(session, run.id) + 1
            await append_event(
                session,
                run.id,
                "run.resume",
                {"reason": REASON, "attempt": attempt, "max": limit, "user_message": TEACHER_NOTE},
                commit=False,
            )
            picked.append(run.id)
        await session.commit()
    for run_id in picked:
        _track_inflight(asyncio.create_task(resume_run(run_id)))
    return len(picked)


async def _wait_runner() -> None:
    """A deploy may restart pi-runner too; do not race its boot."""
    import httpx
    from pico_orchestrator.true_pi.runner import runner_url

    deadline = time.monotonic() + RUNNER_WAIT_S
    async with httpx.AsyncClient(timeout=5.0) as client:
        while time.monotonic() < deadline:
            with contextlib.suppress(Exception):
                if (await client.get(f"{runner_url()}/health")).status_code == 200:
                    return
            await asyncio.sleep(2.0)


async def resume_run(run_id: str) -> None:
    from pico_orchestrator.run_types import RunCaps
    from pico_orchestrator.runtime import run_agent_runtime

    from app.artifact_store import LedgerArtifactStore
    from app.openai_compat import _finalize_run

    settings = get_settings()
    factory = session_factory()
    async with factory() as session:
        run = await session.get(RunRow, run_id)
        spec = spec_of(run) if run is not None else None
        if run is None or spec is None:
            return
        user_prompt = run.prompt
    task_id = str(spec["task_id"])
    conversation_id = str(spec["conversation_id"])
    principal = Principal(**spec["principal"])
    known = {f.name for f in fields(RunCaps)}
    caps = RunCaps(**{k: v for k, v in dict(spec["caps"]).items() if k in known})
    caps = replace(
        caps,
        millipoints_for_usage=millipoints_for_usage,
        outputs_since=float(spec.get("started") or 0),
    )

    async def emit(event_type: str, payload: dict[str, Any]) -> None:
        # Token-level stream has no subscriber after a restart.
        if event_type in {"thinking.delta", "message.stream"}:
            return
        async with factory() as session:
            await append_event(session, run_id, event_type, payload)

    async def is_cancelled() -> bool:
        async with factory() as session:
            row = await session.get(RunRow, run_id)
            return bool(row and (row.cancel_requested or row.status == "cancelled"))

    try:
        await _wait_runner()
        result = await run_agent_runtime(
            use_pi_agent=settings.pico_pi_agent_runtime,
            pi_agent_canary_principals=settings.pi_agent_canary_principal_set,
            pi_agent_allow_all=settings.pi_agent_default_all,
            use_kimi_agent=settings.legacy_kimi_enabled,
            kimi_agent_canary_principals=settings.kimi_agent_canary_principal_set,
            kimi_agent_allow_all=settings.kimi_agent_default_all,
            legacy_agent_loop_emergency=settings.pico_legacy_agent_loop_emergency,
            prompt=RESTART_PROMPT,
            principal=principal,
            emit=emit,
            is_cancelled=is_cancelled,
            caps=caps,
            history=None,
            artifact_store=LedgerArtifactStore(
                factory, task_id=task_id, run_id=run_id, conversation_id=conversation_id
            ),
            conversation_id=conversation_id,
            persist_pi_session=True,
            run_id=run_id,
        )
        await _finalize_run(
            run_id,
            status=result.status,
            error=result.error,
            final_text=result.final_text,
            task_id=task_id,
            user_prompt=user_prompt,
            change_proposal=getattr(result, "change_proposal", None),
            token_usage=getattr(result, "token_usage", None),
            bill_to=payer_for(principal),
        )
    except asyncio.CancelledError:
        if not (shutting_down() and await keep_for_resume(run_id)):
            await asyncio.shield(
                _finalize_run(run_id, status="cancelled", error="run cancelled", task_id=task_id)
            )
        raise
    except Exception as exc:
        logger.exception("restart resume failed run=%s", run_id)
        await _finalize_run(
            run_id, status="failed", error=str(exc), task_id=task_id, bill_to=payer_for(principal)
        )
