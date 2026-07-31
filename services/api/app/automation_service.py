"""Server-side automation scheduler (browser product — not desktop keep-alive)."""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select

from app import run_service
from app.auth import Principal
from app.db import AutomationRow, RunRow, TaskRow, _utcnow, new_id, session_factory

log = logging.getLogger("pico.automation")

_scheduler_task: asyncio.Task | None = None
_stop = asyncio.Event()


def _parse_next_run(kind: str, schedule: dict[str, Any], from_dt: datetime | None = None) -> datetime | None:
    now = from_dt or datetime.now(UTC).replace(tzinfo=None)
    kind = (kind or "periodic").lower()
    if kind == "once":
        # ISO at schedule.at
        at = schedule.get("at")
        if not at:
            return now + timedelta(minutes=1)
        try:
            return datetime.fromisoformat(str(at).replace("Z", ""))
        except ValueError:
            return now + timedelta(minutes=1)
    if kind == "interval":
        minutes = int(schedule.get("minutes") or 60)
        minutes = max(1, min(minutes, 60 * 24 * 7))
        return now + timedelta(minutes=minutes)
    # periodic: daily at HH:MM
    hhmm = str(schedule.get("time") or "09:00")
    try:
        h, m = hhmm.split(":")
        hour, minute = int(h), int(m)
    except (ValueError, TypeError):
        hour, minute = 9, 0
    candidate = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if candidate <= now:
        candidate = candidate + timedelta(days=1)
    return candidate


async def create_automation(
    session,
    principal: Principal,
    *,
    name: str,
    prompt: str,
    schedule_kind: str,
    schedule: dict[str, Any],
    workspace_id: str | None = None,
) -> AutomationRow:
    sk = schedule_kind if schedule_kind in {"periodic", "interval", "once"} else "periodic"
    next_run = _parse_next_run(sk, schedule)
    row = AutomationRow(
        id=new_id(),
        school_id=principal.school_id,
        membership_id=principal.membership_id,
        name=name[:256],
        prompt=prompt,
        schedule_kind=sk,
        schedule_json=json.dumps(schedule or {}, ensure_ascii=False),
        workspace_id=workspace_id,
        enabled=1,
        next_run_at=next_run,
    )
    session.add(row)
    await session.commit()
    await session.refresh(row)
    return row


async def list_automations(session, principal: Principal) -> list[AutomationRow]:
    q = await session.execute(
        select(AutomationRow)
        .where(
            AutomationRow.school_id == principal.school_id,
            AutomationRow.membership_id == principal.membership_id,
        )
        .order_by(AutomationRow.created_at.desc())
    )
    return list(q.scalars().all())


async def set_enabled(session, principal: Principal, auto_id: str, enabled: bool) -> AutomationRow | None:
    row = await session.get(AutomationRow, auto_id)
    if not row or row.school_id != principal.school_id or row.membership_id != principal.membership_id:
        return None
    row.enabled = 1 if enabled else 0
    if enabled and not row.next_run_at:
        sched = json.loads(row.schedule_json or "{}")
        row.next_run_at = _parse_next_run(row.schedule_kind, sched)
    await session.commit()
    await session.refresh(row)
    return row


async def delete_automation(session, principal: Principal, auto_id: str) -> bool:
    row = await session.get(AutomationRow, auto_id)
    if not row or row.school_id != principal.school_id or row.membership_id != principal.membership_id:
        return False
    await session.delete(row)
    await session.commit()
    return True


async def run_once(
    session,
    principal: Principal,
    auto_id: str,
) -> tuple[AutomationRow, TaskRow, RunRow] | None:
    """Create and start one real run without changing the saved schedule."""
    auto = await session.get(AutomationRow, auto_id)
    if (
        not auto
        or auto.school_id != principal.school_id
        or auto.membership_id != principal.membership_id
    ):
        return None

    task, run = await run_service.create_task(
        session,
        principal,
        f"[自动] {auto.name}"[:80],
        auto.prompt.strip() or auto.name,
    )
    if auto.workspace_id and hasattr(task, "workspace_id"):
        task.workspace_id = auto.workspace_id
    auto.last_run_at = _utcnow()
    await session.commit()
    await session.refresh(auto)
    await session.refresh(task)
    await run_service.start_run_background(run.id, principal)
    return auto, task, run


async def _fire_due() -> int:
    """Create Task/Run for due automations. Returns count fired."""
    factory = session_factory()
    now = _utcnow()
    fired = 0
    async with factory() as session:
        q = await session.execute(
            select(AutomationRow).where(
                AutomationRow.enabled == 1,
                AutomationRow.next_run_at.is_not(None),
                AutomationRow.next_run_at <= now,
            )
        )
        due = list(q.scalars().all())
        for auto in due:
            principal = Principal(
                school_id=auto.school_id,
                membership_id=auto.membership_id,
                scopes=["ai:run", "ai:read"],
                iss="pico-automation",
                aud="pico",
                exp=0,
                raw={"automation_id": auto.id},
            )
            title = f"[自动] {auto.name}"[:80]
            try:
                task, run = await run_service.create_task(
                    session, principal, title, auto.prompt.strip() or auto.name
                )
                # attach workspace if column exists on task
                if auto.workspace_id and hasattr(task, "workspace_id"):
                    task.workspace_id = auto.workspace_id
                    await session.commit()
                await run_service.start_run_background(run.id, principal)
                auto.last_run_at = now
                sched = json.loads(auto.schedule_json or "{}")
                if auto.schedule_kind == "once":
                    auto.enabled = 0
                    auto.next_run_at = None
                else:
                    auto.next_run_at = _parse_next_run(auto.schedule_kind, sched, from_dt=now)
                await session.commit()
                fired += 1
                log.info("automation fired id=%s run=%s", auto.id, run.id)
            except Exception:
                log.exception("automation fire failed id=%s", auto.id)
                # backoff 5 min
                auto.next_run_at = now + timedelta(minutes=5)
                await session.commit()
    return fired


async def _loop() -> None:
    log.info("automation scheduler started")
    while not _stop.is_set():
        try:
            await _fire_due()
        except Exception:
            log.exception("scheduler tick failed")
        try:
            await asyncio.wait_for(_stop.wait(), timeout=20.0)
        except TimeoutError:
            continue
    log.info("automation scheduler stopped")


def start_scheduler() -> None:
    global _scheduler_task
    if _scheduler_task and not _scheduler_task.done():
        return
    _stop.clear()
    _scheduler_task = asyncio.create_task(_loop())


async def stop_scheduler() -> None:
    global _scheduler_task
    _stop.set()
    if _scheduler_task:
        try:
            await asyncio.wait_for(_scheduler_task, timeout=3)
        except Exception:  # noqa: BLE001
            _scheduler_task.cancel()
        _scheduler_task = None
