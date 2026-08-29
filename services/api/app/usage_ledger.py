"""Product usage ledger — statistics/management only. Never billing.

Write path is retryable and must not break the main Run path.
See docs/USAGE-LEDGER.md.
"""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from pico_orchestrator.usage_parse import (
    billed_model_id,
    is_ui_lane,
    parse_usage_blob,
    usage_extra_bits,
)
from sqlalchemy import and_, func, or_, select
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import Principal
from app.db import TaskRow, UsageEventRow, new_id, session_factory

logger = logging.getLogger(__name__)

USAGE_KINDS = frozenset({"llm", "search", "sandbox", "image", "api", "other"})
USAGE_EXPORT_SCHEMA = "pico.usage.v1"
BILLING_COLUMN_NAMES = frozenset(
    {
        "price",
        "currency",
        "cost",
        "charge",
        "amount",
        "billing",
        "payment",
        "package",
        "debit",
        "invoice",
    }
)
_FORBIDDEN_EXTRA_KEYS = BILLING_COLUMN_NAMES


@dataclass(frozen=True)
class TokenFields:
    prompt_tokens: int | None
    completion_tokens: int | None
    total_tokens: int | None
    tokens_unknown: bool
    estimated: bool

    @classmethod
    def unknown(cls) -> TokenFields:
        return cls(None, None, None, True, False)


def _int_or_none(value: Any) -> int | None:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    if isinstance(value, str) and value.strip().lstrip("-").isdigit():
        return int(value.strip())
    return None


def extract_token_fields(usage: dict[str, Any] | None) -> TokenFields:
    """Map provider/run usage dicts onto ledger token columns.

    Honest unknown: missing keys or uninitialized all-zero counters without
    an explicit estimated flag. Never invent a billing-grade zero.
    """
    parsed = parse_usage_blob(usage) if isinstance(usage, dict) else None
    if not parsed:
        return TokenFields.unknown()
    return TokenFields(
        prompt_tokens=_int_or_none(parsed.get("prompt_tokens")),
        completion_tokens=_int_or_none(parsed.get("completion_tokens")),
        total_tokens=_int_or_none(parsed.get("total_tokens")),
        tokens_unknown=False,
        estimated=bool(parsed.get("estimated")),
    )


def estimated_char_tokens(prompt: str, completion: str) -> dict[str, int | bool]:
    """Rough char/4 estimate — marked estimated, never a price."""
    prompt_tokens = max(1, (len(prompt or "") + 3) // 4)
    completion_tokens = max(1, (len(completion or "") + 3) // 4)
    return {
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": prompt_tokens + completion_tokens,
        "estimated": True,
    }


def _strip_money_keys(extra: dict[str, Any] | None) -> dict[str, Any]:
    if not extra:
        return {}
    return {k: v for k, v in extra.items() if str(k).lower() not in _FORBIDDEN_EXTRA_KEYS}


def usage_event_dict(row: UsageEventRow) -> dict[str, Any]:
    try:
        extra = json.loads(row.extra_json or "{}")
    except json.JSONDecodeError:
        extra = {}
    if not isinstance(extra, dict):
        extra = {}
    extra = _strip_money_keys(extra)
    return {
        "id": row.id,
        "school_id": row.school_id,
        "membership_id": row.membership_id,
        "kind": row.kind,
        "model": row.model,
        "prompt_tokens": row.prompt_tokens,
        "completion_tokens": row.completion_tokens,
        "total_tokens": row.total_tokens,
        "tokens_unknown": bool(row.tokens_unknown),
        "estimated": bool(row.estimated),
        "task_id": row.task_id,
        "run_id": row.run_id,
        "source": row.source,
        "extra": extra,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "billing": False,
        "schema": USAGE_EXPORT_SCHEMA,
    }


def schema_has_billing_columns() -> bool:
    cols = {c.name.lower() for c in UsageEventRow.__table__.columns}
    return bool(cols & BILLING_COLUMN_NAMES)


async def record_usage_event(
    *,
    school_id: str,
    membership_id: str,
    kind: str,
    model: str | None = None,
    prompt_tokens: int | None = None,
    completion_tokens: int | None = None,
    total_tokens: int | None = None,
    tokens_unknown: bool = False,
    estimated: bool = False,
    task_id: str | None = None,
    run_id: str | None = None,
    source: str = "",
    extra: dict[str, Any] | None = None,
    idempotency_key: str | None = None,
) -> UsageEventRow | None:
    """Persist one usage row. Never raises to the caller (Run path stays up)."""
    try:
        return await _record_usage_event_inner(
            school_id=school_id,
            membership_id=membership_id,
            kind=kind,
            model=model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            tokens_unknown=tokens_unknown,
            estimated=estimated,
            task_id=task_id,
            run_id=run_id,
            source=source,
            extra=extra,
            idempotency_key=idempotency_key,
        )
    except Exception:
        logger.exception("usage_events write failed; run path continues")
        return None


async def _record_usage_event_inner(
    *,
    school_id: str,
    membership_id: str,
    kind: str,
    model: str | None,
    prompt_tokens: int | None,
    completion_tokens: int | None,
    total_tokens: int | None,
    tokens_unknown: bool,
    estimated: bool,
    task_id: str | None,
    run_id: str | None,
    source: str,
    extra: dict[str, Any] | None,
    idempotency_key: str | None,
) -> UsageEventRow | None:
    kind_n = (kind or "").strip().lower()
    if kind_n not in USAGE_KINDS:
        logger.warning("usage_events rejected unknown kind=%r", kind)
        return None
    school = (school_id or "").strip()
    member = (membership_id or "").strip()
    if not school or not member:
        logger.warning("usage_events missing tenant identity")
        return None
    key = (idempotency_key or "").strip() or f"{kind_n}:{new_id()}"
    extra_clean = _strip_money_keys(extra if isinstance(extra, dict) else None)
    factory = session_factory()
    last_err: Exception | None = None
    for attempt in range(5):
        try:
            async with factory() as session:
                row = UsageEventRow(
                    id=new_id(),
                    school_id=school,
                    membership_id=member,
                    kind=kind_n,
                    model=(model or "").strip() or None,
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                    total_tokens=total_tokens,
                    tokens_unknown=1 if tokens_unknown else 0,
                    estimated=1 if estimated else 0,
                    task_id=task_id,
                    run_id=run_id,
                    source=(source or "")[:64],
                    extra_json=json.dumps(extra_clean, ensure_ascii=False),
                    idempotency_key=key[:160],
                )
                session.add(row)
                await session.commit()
                await session.refresh(row)
                return row
        except IntegrityError:
            # Retry of the same idempotency key — already recorded.
            async with factory() as session:
                existing = await session.execute(
                    select(UsageEventRow).where(UsageEventRow.idempotency_key == key[:160])
                )
                found = existing.scalar_one_or_none()
                if found is not None:
                    return found
            return None
        except OperationalError as exc:
            last_err = exc
            if attempt >= 4:
                raise
            await asyncio.sleep(0.05 * (attempt + 1))
        except RuntimeError:
            # DB not initialized — still must not break Run.
            logger.exception("usage_events write skipped (db not ready)")
            return None
    raise RuntimeError(f"usage_events write exhausted: {last_err!r}")


async def _backend_model_from_events(session: AsyncSession, run_id: str) -> str | None:
    from sqlalchemy import select

    from app.db import EventRow

    result = await session.execute(
        select(EventRow.payload_json)
        .where(EventRow.run_id == run_id, EventRow.type == "run.model")
        .order_by(EventRow.seq.desc())
        .limit(1)
    )
    raw = result.scalar_one_or_none()
    if not raw:
        return None
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return None
    if not isinstance(payload, dict):
        return None
    backend = str(payload.get("backend_model") or "").strip()
    return backend or None


async def emit_llm_usage_after_run(
    run_id: str,
    *,
    token_usage: dict[str, Any] | None = None,
    prompt: str | None = None,
    completion: str | None = None,
    source: str = "",
    school_id: str | None = None,
    membership_id: str | None = None,
    model: str | None = None,
    task_id: str | None = None,
    estimate_if_missing: bool = False,
) -> None:
    """Best-effort llm event for a finished Run. Safe to call after commit.

    Default is honest unknown when the provider did not return usage.
    Char/4 estimates are opt-in (``estimate_if_missing``) and never the
    agent path — those numbers are not billable.
    """
    from app.db import RunRow

    rid = (run_id or "").strip()
    if not rid:
        return
    school = school_id
    member = membership_id
    model_id = model
    ui_model: str | None = None
    tid = task_id
    usage = token_usage
    backend_from_event: str | None = None
    try:
        factory = session_factory()
        async with factory() as session:
            run = await session.get(RunRow, rid)
            if run is None and (school is None or member is None):
                return
            if run is not None:
                tid = tid or run.task_id
                ui_model = (run.model or "").strip() or None
                model_id = model_id or ui_model
                backend_from_event = await _backend_model_from_events(session, rid)
                if usage is None:
                    try:
                        parsed = json.loads(run.token_usage_json or "{}")
                        usage = parsed if isinstance(parsed, dict) else None
                    except json.JSONDecodeError:
                        usage = None
                if school is None or member is None:
                    task = await session.get(TaskRow, run.task_id)
                    if task is None:
                        return
                    school = school or task.school_id
                    member = member or task.membership_id
    except Exception:
        logger.exception("usage_events could not load run %s", rid)
        return

    if not school or not member:
        return
    usage_dict = usage if isinstance(usage, dict) else None
    fields = extract_token_fields(usage_dict)
    if fields.tokens_unknown and estimate_if_missing and prompt is not None and completion is not None:
        fields = extract_token_fields(estimated_char_tokens(prompt, completion))
    billed = billed_model_id(model_id, backend_from_event)
    extra = usage_extra_bits(usage_dict)
    if ui_model and is_ui_lane(ui_model):
        extra.setdefault("ui_model", ui_model)
    await record_usage_event(
        school_id=school,
        membership_id=member,
        kind="llm",
        model=billed,
        prompt_tokens=fields.prompt_tokens,
        completion_tokens=fields.completion_tokens,
        total_tokens=fields.total_tokens,
        tokens_unknown=fields.tokens_unknown,
        estimated=fields.estimated,
        task_id=tid,
        run_id=rid,
        source=source or "llm",
        extra=extra or None,
        idempotency_key=f"llm:{rid}",
    )


def _tenant_filter(principal: Principal, membership_id: str | None) -> tuple[str, str]:
    """Return (school_id, membership_id) the caller is allowed to read."""
    school = principal.school_id
    want = (membership_id or "").strip() or principal.membership_id
    if want != principal.membership_id and "ai:admin" not in principal.scopes:
        from fastapi import HTTPException, status

        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "usage.forbidden", "message": "cannot read another account"},
        )
    return school, want


def _day_bounds(day: str) -> tuple[datetime, datetime]:
    try:
        # Naive UTC calendar day — matches db._utcnow() (tzinfo stripped).
        y, m, d = (int(p) for p in day.strip().split("-"))
        start = datetime(y, m, d, tzinfo=UTC).replace(tzinfo=None)
    except ValueError as exc:
        from fastapi import HTTPException, status

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "usage.bad_day", "message": "day must be YYYY-MM-DD"},
        ) from exc
    return start, start + timedelta(days=1)


async def list_usage_events(
    session: AsyncSession,
    principal: Principal,
    *,
    kind: str | None = None,
    day: str | None = None,
    membership_id: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[UsageEventRow]:
    school, member = _tenant_filter(principal, membership_id)
    q = select(UsageEventRow).where(
        UsageEventRow.school_id == school,
        UsageEventRow.membership_id == member,
    )
    if kind:
        kind_n = kind.strip().lower()
        if kind_n not in USAGE_KINDS:
            from fastapi import HTTPException, status

            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"code": "usage.bad_kind", "message": f"kind must be one of {sorted(USAGE_KINDS)}"},
            )
        q = q.where(UsageEventRow.kind == kind_n)
    if day:
        start, end = _day_bounds(day)
        q = q.where(UsageEventRow.created_at >= start, UsageEventRow.created_at < end)
    cap = max(1, min(int(limit or 50), 200))
    off = max(0, int(offset or 0))
    q = q.order_by(UsageEventRow.created_at.desc()).offset(off).limit(cap)
    result = await session.execute(q)
    return list(result.scalars().all())


async def get_usage_event_for_principal(
    session: AsyncSession,
    event_id: str,
    principal: Principal,
) -> UsageEventRow | None:
    row = await session.get(UsageEventRow, event_id)
    if row is None:
        return None
    if row.school_id != principal.school_id:
        return None
    if row.membership_id != principal.membership_id and "ai:admin" not in principal.scopes:
        return None
    return row


async def summarize_usage(
    session: AsyncSession,
    principal: Principal,
    *,
    kind: str | None = None,
    day: str | None = None,
    membership_id: str | None = None,
) -> dict[str, Any]:
    school, member = _tenant_filter(principal, membership_id)
    day_expr = func.strftime("%Y-%m-%d", UsageEventRow.created_at)
    q = (
        select(
            day_expr.label("day"),
            UsageEventRow.kind,
            func.count().label("event_count"),
            func.sum(UsageEventRow.prompt_tokens).label("prompt_tokens"),
            func.sum(UsageEventRow.completion_tokens).label("completion_tokens"),
            func.sum(UsageEventRow.total_tokens).label("total_tokens"),
            func.sum(UsageEventRow.tokens_unknown).label("unknown_count"),
        )
        .where(
            UsageEventRow.school_id == school,
            UsageEventRow.membership_id == member,
        )
        .group_by(day_expr, UsageEventRow.kind)
        .order_by(day_expr.desc(), UsageEventRow.kind)
    )
    if kind:
        kind_n = kind.strip().lower()
        if kind_n in USAGE_KINDS:
            q = q.where(UsageEventRow.kind == kind_n)
    if day:
        start, end = _day_bounds(day)
        q = q.where(UsageEventRow.created_at >= start, UsageEventRow.created_at < end)
    rows = (await session.execute(q)).all()
    days = [
        {
            "day": r.day,
            "kind": r.kind,
            "event_count": int(r.event_count or 0),
            "prompt_tokens": int(r.prompt_tokens) if r.prompt_tokens is not None else None,
            "completion_tokens": (
                int(r.completion_tokens) if r.completion_tokens is not None else None
            ),
            "total_tokens": int(r.total_tokens) if r.total_tokens is not None else None,
            "unknown_count": int(r.unknown_count or 0),
        }
        for r in rows
    ]
    return {
        "billing": False,
        "schema": USAGE_EXPORT_SCHEMA,
        "school_id": school,
        "membership_id": member,
        "days": days,
    }


def _parse_since(since: str | None) -> datetime | None:
    raw = (since or "").strip()
    if not raw:
        return None
    try:
        if raw.endswith("Z"):
            raw = raw[:-1] + "+00:00"
        dt = datetime.fromisoformat(raw)
        if dt.tzinfo is not None:
            dt = dt.astimezone(UTC).replace(tzinfo=None)
        return dt
    except ValueError as exc:
        from fastapi import HTTPException, status

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "usage.bad_since", "message": "since must be ISO-8601"},
        ) from exc


async def export_usage_events(
    session: AsyncSession,
    *,
    school_id: str | None = None,
    kind: str | None = None,
    since: str | None = None,
    after_id: str | None = None,
    limit: int = 200,
) -> dict[str, Any]:
    """Chronological export for edu-core. Service-token path only. No money."""
    cap = max(1, min(int(limit or 200), 1000))
    q = select(UsageEventRow)
    school = (school_id or "").strip()
    if school:
        q = q.where(UsageEventRow.school_id == school)
    if kind:
        kind_n = kind.strip().lower()
        if kind_n not in USAGE_KINDS:
            from fastapi import HTTPException, status

            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"code": "usage.bad_kind", "message": f"kind must be one of {sorted(USAGE_KINDS)}"},
            )
        q = q.where(UsageEventRow.kind == kind_n)
    since_dt = _parse_since(since)
    if since_dt is not None:
        q = q.where(UsageEventRow.created_at >= since_dt)
    after = (after_id or "").strip()
    if after:
        anchor = await session.get(UsageEventRow, after)
        if anchor is not None:
            q = q.where(
                or_(
                    UsageEventRow.created_at > anchor.created_at,
                    and_(
                        UsageEventRow.created_at == anchor.created_at,
                        UsageEventRow.id > anchor.id,
                    ),
                )
            )
    q = q.order_by(UsageEventRow.created_at.asc(), UsageEventRow.id.asc()).limit(cap + 1)
    rows = list((await session.execute(q)).scalars().all())
    has_more = len(rows) > cap
    page = rows[:cap]
    next_cursor = None
    if has_more and page:
        last = page[-1]
        next_cursor = {
            "after_id": last.id,
            "since": last.created_at.isoformat() if last.created_at else None,
        }
    return {
        "schema": USAGE_EXPORT_SCHEMA,
        "billing": False,
        "count": len(page),
        "events": [usage_event_dict(r) for r in page],
        "next": next_cursor,
    }
