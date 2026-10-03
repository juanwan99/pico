"""#1175 PR-3: a finished run lands its page / material artifacts as grey
drafts in the school field the conversation is bound to.

Thin adapter over the existing ``membership/land`` call (app.edu_school):

* The only switch is ``edu_named_bind.field_id`` — the teacher picked the
  field in the workbench materials bar, or edu's 「去办」 handed it over.
  No bound field → nothing happens; Pico never guesses a destination.
* Copy mode: the Pico artifact stays in 「我的文件」; edu gets a grey draft.
  Publishing (green / public) stays in edu — edu refuses silent green.
* Landing never flips the run. Each outcome is one ledger event
  (``artifact.landed`` / ``artifact.land_failed``) so the person can see
  what reached the school field; the reply body has already streamed.
"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import Principal
from app.db import ArtifactRow, RunRow, TaskRow, append_event

logger = logging.getLogger(__name__)

LANDED_EVENT = "artifact.landed"
FAILED_EVENT = "artifact.land_failed"
AUTO_LAND_ISS = "pico-auto-land"
# The same person's write ticket is minted from school_id + membership_id;
# scopes here only shape the local Principal, not the edu ticket.
AUTO_LAND_SCOPES = ["ai:read", "ai:run"]
MAX_ARTIFACTS_PER_RUN = 20


def _is_page(title: str, kind: str) -> bool:
    return kind in {"html", "htm", "page"} or title.lower().endswith((".html", ".htm"))


async def auto_land_run_artifacts(session: AsyncSession, run_id: str) -> list[dict[str, Any]]:
    """Land this run's page / material artifacts into the bound field.

    Returns one result dict per attempted artifact. Must be called after the
    run's terminal status is committed; it opens its own transactions so the
    edu round-trip never holds a write lock (#1135).
    """
    from app.artifact_store import decode_artifact_payload
    from app.edu_school import (
        _BOOKKEEPING,
        classify_land_kind,
        land_generated_artifact,
        load_named_field_id,
    )

    run = await session.get(RunRow, run_id)
    if run is None or run.status != "succeeded":
        return []
    task = await session.get(TaskRow, run.task_id)
    if task is None:
        return []
    convo = str(task.conversation_id or "").strip()
    if not convo:
        return []
    field_id = await load_named_field_id(session, task.school_id, task.membership_id, convo)
    if not field_id:
        return []
    rows = (
        (
            await session.execute(
                select(ArtifactRow)
                .where(ArtifactRow.run_id == run.id)
                .order_by(ArtifactRow.created_at, ArtifactRow.id)
            )
        )
        .scalars()
        .all()
    )
    candidates = [
        row
        for row in rows
        if str(row.title or "").strip()
        and str(row.title or "").strip() not in _BOOKKEEPING
        and classify_land_kind(str(row.title or "")) in {"page", "material"}
    ]
    if not candidates:
        return []
    principal = Principal(
        school_id=task.school_id,
        membership_id=task.membership_id,
        scopes=list(AUTO_LAND_SCOPES),
        iss=AUTO_LAND_ISS,
        aud="pico-api",
        exp=0,
        raw={},
    )
    results: list[dict[str, Any]] = []
    for artifact in candidates[:MAX_ARTIFACTS_PER_RUN]:
        title = str(artifact.title or "").strip()
        kind = str(artifact.kind or "").strip().lower()
        payload: dict[str, Any] = {
            "artifact_id": artifact.id,
            "title": title,
            "field_id": field_id,
            "mode": "copy",
        }
        try:
            raw = decode_artifact_payload(artifact.inline, artifact.content_encoding)
            content: str | bytes = raw.decode("utf-8") if _is_page(title, kind) else raw
            outcome = await land_generated_artifact(
                principal,
                title=title,
                content=content,
                field_id=field_id,
                conversation_id=convo,
                artifact_id=artifact.id,
                task_id=str(task.id),
                session=session,
            )
        except Exception as exc:  # one bad artifact must not stop the rest
            logger.exception("auto land failed for artifact %s", artifact.id)
            outcome = {
                "ok": False,
                "landed": False,
                "code": "auto_land.error",
                "error": str(exc)[:200],
            }
        landed = outcome.get("landed") is True
        payload["landed"] = landed
        payload["code"] = str(outcome.get("code") or ("landed" if landed else "edu.land_failed"))
        if landed:
            payload["edu_id"] = outcome.get("id")
            payload["kind"] = outcome.get("kind") or ""
            payload["zone"] = outcome.get("zone") or "draft"
        else:
            payload["error"] = str(outcome.get("error") or outcome.get("user_message") or "")[:300]
        await append_event(session, run.id, LANDED_EVENT if landed else FAILED_EVENT, payload)
        results.append(payload)
    return results


async def auto_land_after_run(session: AsyncSession, run_id: str) -> None:
    """Best-effort hook for the run finalizers. Never raises."""
    try:
        await auto_land_run_artifacts(session, run_id)
    except Exception:
        logger.exception("auto land skipped for run %s", run_id)
        try:
            await session.rollback()
        except Exception:
            logger.exception("auto land rollback failed for run %s", run_id)
