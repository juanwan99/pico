"""Task/Run lifecycle + background agent execution."""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.artifact_store import LedgerArtifactStore
from app.auth import Principal
from app.db import (
    ArtifactRow,
    AuditRow,
    ChangeProposalRow,
    EventRow,
    RunRow,
    TaskRow,
    append_event,
    new_id,
    session_factory,
)
from app.settings import get_settings


def _utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


@dataclass(frozen=True)
class CancelResult:
    run: RunRow
    request_recorded: bool
    status_changed: bool


def _json_dict(raw: str | None) -> dict[str, Any]:
    try:
        data = json.loads(raw or "{}")
        return data if isinstance(data, dict) else {}
    except json.JSONDecodeError:
        return {}


def _merge_token_usage(
    existing: str | None,
    usage: dict[str, Any] | None,
    skill_snapshot: dict[str, Any] | None,
) -> str:
    merged = _json_dict(existing)
    merged.update(usage or {})
    if skill_snapshot:
        merged["skill_snapshot"] = skill_snapshot
    return json.dumps(merged, ensure_ascii=False)


def _run_skill_snapshot(run: RunRow | None) -> dict[str, Any] | None:
    if run is None:
        return None
    snapshot = _json_dict(run.token_usage_json).get("skill_snapshot")
    return snapshot if isinstance(snapshot, dict) else None


def _skill_s7_payload(
    *,
    prompt: str,
    final_text: str | None,
    snapshot: dict[str, Any],
) -> dict[str, Any]:
    return {
        "title": "S7 变更提案（skill.write_s7）",
        "summary": (final_text or "skill.write_s7 requested a controlled change proposal.")[:1000],
        "payload": {
            "skill_snapshot": snapshot,
            "prompt": prompt[:2000],
            "final_text": (final_text or "")[:4000],
        },
    }


async def create_task(
    session: AsyncSession,
    principal: Principal,
    title: str,
    prompt: str,
    skill_id: str | None = None,
) -> tuple[TaskRow, RunRow]:
    from pico_orchestrator.skill_policy import snapshot_for_skill

    skill_snapshot = snapshot_for_skill(skill_id)
    task = TaskRow(
        id=new_id(),
        school_id=principal.school_id,
        membership_id=principal.membership_id,
        title=title or (prompt[:80] if prompt else "untitled"),
    )
    session.add(task)
    await session.flush()
    run = RunRow(
        id=new_id(),
        task_id=task.id,
        status="queued",
        prompt=prompt,
        model="",
        token_usage_json=_merge_token_usage(None, None, skill_snapshot),
    )
    session.add(run)
    await session.commit()
    await session.refresh(task)
    await session.refresh(run)
    return task, run


async def get_task_for_principal(
    session: AsyncSession, task_id: str, principal: Principal
) -> TaskRow | None:
    row = await session.get(TaskRow, task_id)
    if row is None:
        return None
    if row.school_id != principal.school_id:
        return None
    # Personal workspace: same school is not enough — owner membership must match.
    if row.membership_id != principal.membership_id:
        return None
    return row


async def get_run_for_principal(
    session: AsyncSession, run_id: str, principal: Principal
) -> RunRow | None:
    run = await session.get(RunRow, run_id)
    if run is None:
        return None
    task = await session.get(TaskRow, run.task_id)
    if task is None:
        return None
    if task.school_id != principal.school_id:
        return None
    if task.membership_id != principal.membership_id:
        return None
    return run


async def list_tasks(
    session: AsyncSession,
    principal: Principal,
    *,
    conversation_id: str | None = None,
) -> list[TaskRow]:
    query = select(TaskRow).where(
        TaskRow.school_id == principal.school_id,
        TaskRow.membership_id == principal.membership_id,
    )
    if conversation_id:
        query = query.where(TaskRow.conversation_id == conversation_id)
    result = await session.execute(query.order_by(TaskRow.created_at.desc()).limit(50))
    return list(result.scalars().all())


async def list_events(session: AsyncSession, run_id: str) -> list[EventRow]:
    result = await session.execute(
        select(EventRow).where(EventRow.run_id == run_id).order_by(EventRow.seq.asc())
    )
    return list(result.scalars().all())


async def list_runs_for_task(session: AsyncSession, task_id: str) -> list[RunRow]:
    result = await session.execute(
        select(RunRow)
        .where(RunRow.task_id == task_id)
        .order_by(RunRow.created_at.desc())
    )
    return list(result.scalars().all())


async def latest_runs_for_tasks(
    session: AsyncSession, task_ids: list[str]
) -> dict[str, RunRow]:
    """Map task_id -> newest RunRow (one query; pick max created_at per task)."""
    if not task_ids:
        return {}
    result = await session.execute(
        select(RunRow)
        .where(RunRow.task_id.in_(task_ids))
        .order_by(RunRow.created_at.desc())
    )
    out: dict[str, RunRow] = {}
    for row in result.scalars().all():
        if row.task_id not in out:
            out[row.task_id] = row
    return out


async def request_cancel(session: AsyncSession, run: RunRow) -> CancelResult:
    if run.status == "cancelled":
        return CancelResult(run=run, request_recorded=False, status_changed=False)
    if run.status not in ("queued", "preparing", "running"):
        raise ValueError("run is already terminal")

    request_was_pending = bool(run.cancel_requested)
    result = await session.execute(
        update(RunRow)
        .where(
            RunRow.id == run.id,
            RunRow.status.in_(("queued", "preparing", "running")),
        )
        .values(
            cancel_requested=1,
            status="cancelled",
            ended_at=_utcnow(),
            error=None,
        )
        .execution_options(synchronize_session=False)
    )
    await session.commit()
    await session.refresh(run)
    if result.rowcount == 1:
        return CancelResult(
            run=run,
            request_recorded=not request_was_pending,
            status_changed=True,
        )
    if run.status == "cancelled":
        return CancelResult(run=run, request_recorded=False, status_changed=False)
    raise ValueError("run is already terminal")


async def cancel_active_runs_for_task(
    session: AsyncSession, task_id: str
) -> list[CancelResult]:
    """Cancel every non-terminal run on a task (chat UI stop by task)."""
    rows = (
        await session.execute(
            select(RunRow).where(
                RunRow.task_id == task_id,
                RunRow.status.in_(("queued", "preparing", "running")),
            )
        )
    ).scalars().all()
    out: list[CancelResult] = []
    for run in rows:
        out.append(await request_cancel(session, run))
    return out


async def reconcile_orphaned_runs(session: AsyncSession) -> dict[str, int]:
    """Finalize non-terminal runs whose in-process owner was lost on restart."""
    active = (
        await session.execute(
            select(RunRow).where(
                RunRow.status.in_(("queued", "preparing", "running"))
            )
        )
    ).scalars().all()
    counts = {"cancelled": 0, "failed": 0}
    for run in active:
        if run.cancel_requested:
            run.status = "cancelled"
            run.error = None
        else:
            run.status = "failed"
            run.error = "run owner was lost during API restart"
        run.ended_at = _utcnow()
        counts[run.status] += 1
        await append_event(
            session,
            run.id,
            "run.status",
            {
                "status": run.status,
                "reason": "api_restart_reconciliation",
            },
            commit=False,
        )
    await session.commit()
    return counts


async def retry_failed_run(session: AsyncSession, source_run: RunRow) -> RunRow:
    """Create a distinct ledger Run from a failed Run's immutable context."""
    if source_run.status != "failed":
        raise ValueError("only failed runs can be retried")

    active = await session.execute(
        select(RunRow.id).where(
            RunRow.task_id == source_run.task_id,
            RunRow.status.in_(("queued", "preparing", "running")),
        ).limit(1)
    )
    if active.scalar_one_or_none() is not None:
        raise RuntimeError("task already has an active run")

    retry_run = RunRow(
        id=new_id(),
        task_id=source_run.task_id,
        status="queued",
        prompt=source_run.prompt,
        model="",
        token_usage_json=_merge_token_usage(
            None,
            None,
            _run_skill_snapshot(source_run),
        ),
    )
    session.add(retry_run)
    await session.flush()
    await append_event(
        session,
        source_run.id,
        "run.retry_requested",
        {"retry_run_id": retry_run.id},
        commit=False,
    )
    await append_event(
        session,
        retry_run.id,
        "run.retry_created",
        {"source_run_id": source_run.id},
        commit=False,
    )
    await session.commit()
    await session.refresh(retry_run)
    return retry_run


async def start_run_background(run_id: str, principal: Principal) -> None:
    """Schedule agent loop in-process (Phase 1 single-node)."""
    asyncio.create_task(_execute_run(run_id, principal))


async def _execute_run(run_id: str, principal: Principal) -> None:
    from pico_orchestrator.runner import RunCaps, provider_label
    from pico_orchestrator.runtime import run_agent_runtime
    from pico_orchestrator.user_errors import enrich_fail_payload, user_message_for_error

    settings = get_settings()
    factory = session_factory()

    try:
        async with factory() as session:
            run = await session.get(RunRow, run_id)
            if run is None:
                return
            if run.status == "cancelled":
                await append_event(session, run_id, "run.status", {"status": "cancelled"})
                return
            run.status = "running"
            run.started_at = _utcnow()
            run.model = provider_label()
            await session.commit()

        async def emit(event_type: str, payload: dict[str, Any]) -> None:
            async with factory() as session:
                await append_event(session, run_id, event_type, payload)

        async def is_cancelled() -> bool:
            async with factory() as session:
                run = await session.get(RunRow, run_id)
                return bool(run and (run.cancel_requested or run.status == "cancelled"))

        caps = RunCaps(
            max_seconds=settings.pico_run_max_seconds,
            max_tokens=settings.pico_run_max_tokens,
            max_retries=settings.pico_run_max_retries,
        )

        async with factory() as session:
            run = await session.get(RunRow, run_id)
            assert run is not None
            prompt = run.prompt
            skill_snapshot = _run_skill_snapshot(run)

        if skill_snapshot:
            await emit("skill.snapshot", skill_snapshot)
            from pico_orchestrator.skill_policy import instruction_for_snapshot

            caps.allowed_tools = list(skill_snapshot.get("tools") or [])
            caps.skill_instruction = instruction_for_snapshot(skill_snapshot)

        result = await run_agent_runtime(
            use_kimi_agent=settings.pico_kimi_agent_runtime,
            kimi_agent_canary_principals=(
                settings.kimi_agent_canary_principal_set
            ),
            prompt=prompt,
            principal=principal,
            emit=emit,
            is_cancelled=is_cancelled,
            caps=caps,
            artifact_store=LedgerArtifactStore(
                factory,
                task_id=run.task_id,
                run_id=run_id,
            ),
        )
    except Exception as exc:  # noqa: BLE001 — persist failure on any crash
        async with factory() as session:
            run = await session.get(RunRow, run_id)
            if run is None:
                return
            if run.status in ("succeeded", "failed", "cancelled"):
                return
            # Prefer honest cancel over masking a late cancel with sqlite/other crash.
            if run.cancel_requested:
                run.status = "cancelled"
                run.ended_at = _utcnow()
                run.error = None
                await session.commit()
                await append_event(
                    session,
                    run_id,
                    "run.status",
                    {"status": "cancelled"},
                )
                return
            run.status = "failed"
            run.ended_at = _utcnow()
            run.error = str(exc)
            await session.commit()
            await append_event(
                session,
                run_id,
                "run.status",
                enrich_fail_payload({"status": "failed", "reason": str(exc)}),
            )
            await append_event(
                session,
                run_id,
                "message.final",
                {
                    "text": user_message_for_error(str(exc)),
                    "role": "assistant",
                    "kind": "error",
                },
            )
        return

    async with factory() as session:
        run = await session.get(RunRow, run_id)
        if run is None:
            return
        if run.status in ("succeeded", "failed", "cancelled"):
            return
        run.status = result.status
        run.ended_at = _utcnow()
        run.error = result.error
        skill_snapshot = _run_skill_snapshot(run)
        run.token_usage_json = _merge_token_usage(
            run.token_usage_json,
            result.token_usage,
            skill_snapshot,
        )
        if result.status == "failed" and not result.final_text:
            await append_event(
                session,
                run_id,
                "message.final",
                {
                    "text": user_message_for_error(result.error),
                    "role": "assistant",
                    "kind": "error",
                },
            )
        if result.final_text:
            # final assistant message event if not already
            await append_event(
                session,
                run_id,
                "message.final",
                {"text": result.final_text},
            )
        if result.artifact_markdown:
            art = ArtifactRow(
                id=new_id(),
                task_id=run.task_id,
                run_id=run.id,
                kind="table",
                title="工具产物",
                inline=result.artifact_markdown,
            )
            session.add(art)
            await append_event(
                session,
                run_id,
                "artifact.created",
                {"title": art.title, "kind": art.kind, "artifact_id": art.id},
            )
        change_proposal = result.change_proposal
        if not change_proposal and skill_snapshot and skill_snapshot.get("requires_s7"):
            change_proposal = {
                "proposal": _skill_s7_payload(
                    prompt=run.prompt,
                    final_text=result.final_text,
                    snapshot=skill_snapshot,
                )
            }
        if change_proposal:
            prop = change_proposal.get("proposal") or change_proposal
            ch = ChangeProposalRow(
                id=new_id(),
                school_id=principal.school_id,
                membership_id=principal.membership_id,
                task_id=run.task_id,
                run_id=run.id,
                title=str(prop.get("title") or "变更提案"),
                summary=str(prop.get("summary") or ""),
                payload_json=json.dumps(prop.get("payload") or {}, ensure_ascii=False),
                status="proposed",
            )
            session.add(ch)
            await append_event(
                session,
                run_id,
                "change.proposed",
                {"change_id": ch.id, "title": ch.title},
            )
        await session.commit()


async def create_change(
    session: AsyncSession,
    principal: Principal,
    *,
    title: str,
    summary: str,
    payload: dict[str, Any],
    task_id: str | None = None,
    run_id: str | None = None,
) -> ChangeProposalRow:
    if task_id and await get_task_for_principal(session, task_id, principal) is None:
        raise KeyError("task not found")
    if run_id:
        run = await get_run_for_principal(session, run_id, principal)
        if run is None:
            raise KeyError("run not found")
        if task_id and run.task_id != task_id:
            raise ValueError("run does not belong to task")
        task_id = task_id or run.task_id

    row = ChangeProposalRow(
        id=new_id(),
        school_id=principal.school_id,
        membership_id=principal.membership_id,
        task_id=task_id,
        run_id=run_id,
        title=title,
        summary=summary,
        payload_json=json.dumps(payload, ensure_ascii=False),
        status="proposed",
    )
    session.add(row)
    audit = AuditRow(
        id=new_id(),
        school_id=principal.school_id,
        membership_id=principal.membership_id,
        action="change.proposed",
        subject_type="change_proposal",
        subject_id=row.id,
        detail_json=json.dumps({"title": title}, ensure_ascii=False),
    )
    session.add(audit)
    await session.commit()
    await session.refresh(row)
    return row


async def get_change_for_principal(
    session: AsyncSession,
    principal: Principal,
    change_id: str,
) -> ChangeProposalRow | None:
    row = await session.get(ChangeProposalRow, change_id)
    if row is None:
        return None
    if row.school_id != principal.school_id:
        return None
    if row.membership_id != principal.membership_id:
        return None
    return row


async def _transition_change(
    session: AsyncSession,
    principal: Principal,
    change_id: str,
    *,
    target_status: str,
) -> ChangeProposalRow:
    transitioned_at = _utcnow()
    values: dict[str, Any] = {"status": target_status}
    if target_status == "confirmed":
        values.update(
            confirmed_at=transitioned_at,
            confirmed_by=principal.membership_id,
        )
    result = await session.execute(
        update(ChangeProposalRow)
        .where(
            ChangeProposalRow.id == change_id,
            ChangeProposalRow.school_id == principal.school_id,
            ChangeProposalRow.membership_id == principal.membership_id,
            ChangeProposalRow.status == "proposed",
        )
        .values(**values)
        .execution_options(synchronize_session=False)
    )
    if result.rowcount != 1:
        await session.rollback()
        existing = await get_change_for_principal(session, principal, change_id)
        if existing is None:
            raise KeyError("not found")
        raise ValueError(
            f"cannot transition to {target_status} from status={existing.status}"
        )

    row = await session.get(ChangeProposalRow, change_id)
    if row is None:
        await session.rollback()
        raise KeyError("not found")
    action = "confirmed" if target_status == "confirmed" else "rejected"
    history = json.loads(row.audit_json or "[]")
    history.append(
        {
            "action": action,
            "by": principal.membership_id,
            "at": transitioned_at.isoformat(),
        }
    )
    row.audit_json = json.dumps(history, ensure_ascii=False)
    session.add(
        AuditRow(
            id=new_id(),
            school_id=principal.school_id,
            membership_id=principal.membership_id,
            action=f"change.{action}",
            subject_type="change_proposal",
            subject_id=row.id,
            detail_json=json.dumps({"title": row.title}, ensure_ascii=False),
        )
    )
    await session.commit()
    await session.refresh(row)
    return row


async def confirm_change(
    session: AsyncSession,
    principal: Principal,
    change_id: str,
) -> ChangeProposalRow:
    row = await _transition_change(
        session,
        principal,
        change_id,
        target_status="confirmed",
    )

    # Phase 3 optional push to edu Review queue — edu owns business write
    try:
        from pico_orchestrator.edu_adapter import (
            EduAdapterError,
            build_change_handoff,
            push_change_proposal,
        )

        handoff_body = build_change_handoff(
            pico_change_id=row.id,
            school_id=row.school_id,
            membership_id=row.membership_id,
            title=row.title,
            summary=row.summary,
            payload=json.loads(row.payload_json or "{}"),
            confirmed_at=row.confirmed_at or _utcnow(),
            confirmed_by=row.confirmed_by or "",
        )
        result = await push_change_proposal(handoff_body)
        if result is not None:
            history = json.loads(row.audit_json or "[]")
            history.append(
                {
                    "action": "handoff_pushed",
                    "edu_response": result,
                    "at": _utcnow().isoformat(),
                }
            )
            row.audit_json = json.dumps(history, ensure_ascii=False)
            session.add(
                AuditRow(
                    id=new_id(),
                    school_id=principal.school_id,
                    membership_id=principal.membership_id,
                    action="change.handoff_pushed",
                    subject_type="change_proposal",
                    subject_id=row.id,
                    detail_json=json.dumps(result, ensure_ascii=False),
                )
            )
            await session.commit()
            await session.refresh(row)
    except EduAdapterError as e:
        history = json.loads(row.audit_json or "[]")
        history.append(
            {
                "action": "handoff_failed",
                "code": e.code,
                "message": e.message,
                "at": _utcnow().isoformat(),
            }
        )
        row.audit_json = json.dumps(history, ensure_ascii=False)
        await session.commit()
        await session.refresh(row)
    return row


async def reject_change(
    session: AsyncSession,
    principal: Principal,
    change_id: str,
) -> ChangeProposalRow:
    return await _transition_change(
        session,
        principal,
        change_id,
        target_status="rejected",
    )


async def list_changes(
    session: AsyncSession,
    principal: Principal,
    *,
    task_id: str | None = None,
    status: str | None = None,
) -> list[ChangeProposalRow]:
    query = select(ChangeProposalRow).where(
        ChangeProposalRow.school_id == principal.school_id,
        ChangeProposalRow.membership_id == principal.membership_id,
    )
    if task_id:
        query = query.where(ChangeProposalRow.task_id == task_id)
    if status:
        query = query.where(ChangeProposalRow.status == status)
    result = await session.execute(
        query.order_by(ChangeProposalRow.created_at.desc()).limit(50)
    )
    return list(result.scalars().all())


async def list_artifacts_for_task(
    session: AsyncSession, task_id: str
) -> list[ArtifactRow]:
    result = await session.execute(
        select(ArtifactRow)
        .where(ArtifactRow.task_id == task_id)
        .order_by(ArtifactRow.created_at.desc())
    )
    return list(result.scalars().all())


async def get_artifact_for_principal(
    session: AsyncSession,
    artifact_id: str,
    principal: Principal,
) -> ArtifactRow | None:
    result = await session.execute(
        select(ArtifactRow)
        .join(TaskRow, ArtifactRow.task_id == TaskRow.id)
        .where(
            ArtifactRow.id == artifact_id,
            TaskRow.school_id == principal.school_id,
            TaskRow.membership_id == principal.membership_id,
        )
    )
    return result.scalar_one_or_none()


async def demo_cross_school_deny(
    session: AsyncSession, principal: Principal
) -> dict[str, Any]:
    """Record cross-school tool deny as Event on a short run (S6)."""
    from pico_orchestrator.gateway import ToolError
    from pico_orchestrator.tools_builtin import build_default_gateway

    task, run = await create_task(
        session,
        principal,
        title="跨校拒绝演示",
        prompt="cross-school deny probe",
    )
    run.status = "running"
    run.started_at = _utcnow()
    await session.commit()

    await append_event(session, run.id, "run.status", {"status": "running", "demo": "cross_school"})
    await append_event(
        session,
        run.id,
        "tool.call",
        {
            "tool": "fake_edu_list_classes",
            "arguments": {"school_id": "school-b"},
        },
    )
    gw = build_default_gateway()
    try:
        await gw.invoke(principal, "fake_edu_list_classes", {"school_id": "school-b"})
        ok = True
        detail: dict[str, Any] = {}
    except ToolError as e:
        ok = False
        detail = {"code": e.code, "message": e.message}
        await append_event(
            session,
            run.id,
            "auth.deny",
            {
                "code": e.code,
                "message": e.message,
                "token_school_id": principal.school_id,
                "requested_school_id": "school-b",
            },
        )
        await append_event(
            session,
            run.id,
            "tool.result",
            {"tool": "fake_edu_list_classes", "ok": False, **detail},
        )

    run = await session.get(RunRow, run.id)
    assert run is not None
    run.status = "succeeded" if not ok else "failed"
    run.ended_at = _utcnow()
    await session.commit()
    await append_event(session, run.id, "run.status", {"status": run.status})

    events = await list_events(session, run.id)
    return {
        "task_id": task.id,
        "run_id": run.id,
        "denied": not ok,
        "events": [
            {"seq": e.seq, "type": e.type, "payload": e.payload} for e in events
        ],
    }
