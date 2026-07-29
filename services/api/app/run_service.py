"""Task/Run lifecycle + background agent execution."""

from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

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


async def create_task(
    session: AsyncSession,
    principal: Principal,
    title: str,
    prompt: str,
) -> tuple[TaskRow, RunRow]:
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
    if row is None or row.school_id != principal.school_id:
        return None
    return row


async def get_run_for_principal(
    session: AsyncSession, run_id: str, principal: Principal
) -> RunRow | None:
    run = await session.get(RunRow, run_id)
    if run is None:
        return None
    task = await session.get(TaskRow, run.task_id)
    if task is None or task.school_id != principal.school_id:
        return None
    return run


async def list_tasks(session: AsyncSession, principal: Principal) -> list[TaskRow]:
    result = await session.execute(
        select(TaskRow)
        .where(TaskRow.school_id == principal.school_id)
        .order_by(TaskRow.created_at.desc())
        .limit(50)
    )
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


async def request_cancel(session: AsyncSession, run: RunRow) -> RunRow:
    run.cancel_requested = 1
    # Immediate terminal cancel if still queued; running worker polls cancel_requested.
    if run.status == "queued":
        run.status = "cancelled"
        run.ended_at = _utcnow()
    await session.commit()
    await session.refresh(run)
    return run


async def start_run_background(run_id: str, principal: Principal) -> None:
    """Schedule agent loop in-process (Phase 1 single-node)."""
    asyncio.create_task(_execute_run(run_id, principal))


async def _execute_run(run_id: str, principal: Principal) -> None:
    from pico_orchestrator.runner import RunCaps, provider_label, run_agent_loop

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
                return bool(run and run.cancel_requested)

        caps = RunCaps(
            max_seconds=settings.pico_run_max_seconds,
            max_tokens=settings.pico_run_max_tokens,
            max_retries=settings.pico_run_max_retries,
        )

        async with factory() as session:
            run = await session.get(RunRow, run_id)
            assert run is not None
            prompt = run.prompt

        result = await run_agent_loop(
            prompt=prompt,
            principal=principal,
            emit=emit,
            is_cancelled=is_cancelled,
            caps=caps,
        )
    except Exception as exc:  # noqa: BLE001 — persist failure on any crash
        async with factory() as session:
            run = await session.get(RunRow, run_id)
            if run is None:
                return
            run.status = "failed"
            run.ended_at = _utcnow()
            run.error = str(exc)
            await session.commit()
            await append_event(
                session, run_id, "run.status", {"status": "failed", "reason": str(exc)}
            )
        return

    async with factory() as session:
        run = await session.get(RunRow, run_id)
        if run is None:
            return
        run.status = result.status
        run.ended_at = _utcnow()
        run.error = result.error
        run.token_usage_json = json.dumps(result.token_usage or {})
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
        if result.change_proposal:
            prop = result.change_proposal.get("proposal") or result.change_proposal
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


async def confirm_change(
    session: AsyncSession,
    principal: Principal,
    change_id: str,
) -> ChangeProposalRow:
    row = await session.get(ChangeProposalRow, change_id)
    if row is None or row.school_id != principal.school_id:
        raise KeyError("not found")
    if row.status != "proposed":
        raise ValueError(f"cannot confirm status={row.status}")
    row.status = "confirmed"
    row.confirmed_at = _utcnow()
    row.confirmed_by = principal.membership_id
    history = json.loads(row.audit_json or "[]")
    history.append(
        {
            "action": "confirmed",
            "by": principal.membership_id,
            "at": row.confirmed_at.isoformat(),
        }
    )
    row.audit_json = json.dumps(history, ensure_ascii=False)
    audit = AuditRow(
        id=new_id(),
        school_id=principal.school_id,
        membership_id=principal.membership_id,
        action="change.confirmed",
        subject_type="change_proposal",
        subject_id=row.id,
        detail_json=json.dumps({"title": row.title}, ensure_ascii=False),
    )
    session.add(audit)
    await session.commit()
    await session.refresh(row)

    # Phase 3 optional push to edu Review queue — edu owns business write
    try:
        from pico_orchestrator.edu_adapter import EduAdapterError, push_change_proposal

        handoff_body = {
            "pico_change_id": row.id,
            "school_id": row.school_id,
            "membership_id": row.membership_id,
            "title": row.title,
            "summary": row.summary,
            "payload": json.loads(row.payload_json or "{}"),
            "confirmed_at": row.confirmed_at.isoformat() if row.confirmed_at else None,
            "confirmed_by": row.confirmed_by,
        }
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


async def list_changes(session: AsyncSession, principal: Principal) -> list[ChangeProposalRow]:
    result = await session.execute(
        select(ChangeProposalRow)
        .where(ChangeProposalRow.school_id == principal.school_id)
        .order_by(ChangeProposalRow.created_at.desc())
        .limit(50)
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
