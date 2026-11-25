"""Rebuild Meili projection from the artifact ledger (source of truth)."""

from __future__ import annotations

import asyncio
import logging
import os
import time
from datetime import datetime
from typing import Any

from pico_orchestrator.meili_kb import MeiliIndex, is_lab_school, is_material, material_chunk_docs
from sqlalchemy import select
from sqlalchemy.orm import load_only

from app.artifact_store import decode_artifact_payload
from app.auth import Principal
from app.db import UPLOAD_TASK_PREFIX, ArtifactRow, TaskRow, is_teacher_material, session_factory

logger = logging.getLogger(__name__)
_BATCH_SIZE = 20
_PER_MIN = 600
_rebuild_lock = asyncio.Lock()


def rebuild_per_min() -> int:
    try:
        return max(60, int(os.environ.get("PICO_KB_REBUILD_PER_MIN") or _PER_MIN))
    except ValueError:
        return _PER_MIN


class _Pace:
    """Leave Meili idle for at least the previous batch's write time."""

    def __init__(self, per_min: int) -> None:
        self.per_min = per_min
        self.next_push_at = time.monotonic()

    async def push(self, index: MeiliIndex, docs: list[dict[str, Any]]) -> None:
        wait = self.next_push_at - time.monotonic()
        if wait > 0:
            await asyncio.sleep(wait)
        started_at = time.monotonic()
        await index.upsert_rebuild_batch(docs)
        completed_at = time.monotonic()
        self.next_push_at = completed_at + max(
            len(docs) * 60.0 / self.per_min, completed_at - started_at
        )


def _chunk_artifact(
    artifact: ArtifactRow,
    task: TaskRow,
    *,
    inline: str | None,
    content_encoding: str | None,
    created_at: datetime | None,
    stored_text: str | None,
) -> list[dict[str, Any]]:
    content = (
        decode_artifact_payload(inline, content_encoding)
        if content_encoding == "base64"
        else inline or ""
    )
    return material_chunk_docs(
        task,
        artifact_id=artifact.id,
        title=artifact.title,
        kind=artifact.kind,
        content=content,
        created_at=created_at.isoformat() if created_at else None,
        stored_text=stored_text,
    )


async def rebuild_materials(
    principal: Principal | None = None,
    *,
    force: bool = False,
) -> dict[str, Any]:
    """Project ledger materials into Meili, one completed batch at a time."""
    async with _rebuild_lock:
        return await _rebuild_materials(principal, force=force)


async def _rebuild_materials(principal: Principal | None, *, force: bool) -> dict[str, Any]:
    idx = MeiliIndex()
    await idx.wait_until_idle()
    known = set() if force else await asyncio.to_thread(idx.artifact_ids)

    factory = session_factory()
    # In SQLite, reading even one column after inline can traverse its overflow pages.
    stmt = (
        select(ArtifactRow, TaskRow)
        .join(TaskRow, ArtifactRow.task_id == TaskRow.id)
        .options(
            load_only(
                ArtifactRow.id,
                ArtifactRow.task_id,
                ArtifactRow.run_id,
                ArtifactRow.kind,
                ArtifactRow.title,
                raiseload=True,
            ),
            load_only(TaskRow.id, TaskRow.title, TaskRow.school_id, TaskRow.membership_id),
        )
    )
    if principal is not None:
        stmt = stmt.where(
            TaskRow.school_id == principal.school_id,
            TaskRow.membership_id == principal.membership_id,
        )
    async with factory() as session:
        rows = (await session.execute(stmt)).all()

    stored_by_task_title: dict[tuple[str, str], list[str]] = {}
    for artifact, task in rows:
        if artifact.kind == "kb_text" and artifact.run_id is None:
            stored_by_task_title.setdefault((task.id, artifact.title), []).append(artifact.id)

    pace = _Pace(rebuild_per_min())
    indexed = 0
    unchanged = 0
    skipped = 0
    pending: list[dict[str, Any]] = []
    for artifact, task in rows:
        if (
            artifact.run_id is not None
            or not (task.title or "").startswith(UPLOAD_TASK_PREFIX)
            or is_lab_school(str(task.school_id or ""))
            or not is_material(kind=artifact.kind, title=artifact.title)
            or artifact.kind == "edu_excerpt"
        ):
            skipped += 1
            continue
        if artifact.id in known:
            unchanged += 1
            continue

        # Read bodies only for materials being rebuilt. Release SQLite before embedding.
        stored_ids = stored_by_task_title.get((task.id, artifact.title), [])
        async with factory() as session:
            origin_row = (
                await session.execute(
                    select(ArtifactRow.origin).where(ArtifactRow.id == artifact.id)
                )
            ).one_or_none()
            if origin_row is None or not is_teacher_material(origin_row.origin, task.title):
                skipped += 1
                continue
            result = await session.execute(
                select(
                    ArtifactRow.id,
                    ArtifactRow.content_encoding,
                    ArtifactRow.created_at,
                    ArtifactRow.inline,
                ).where(ArtifactRow.id.in_([artifact.id, *stored_ids]))
            )
            payloads = {row.id: row for row in result.all()}
        payload = payloads.get(artifact.id)
        if payload is None:
            skipped += 1
            continue
        stored_text = None
        for aid in stored_ids:
            stored = payloads.get(aid)
            if (
                stored is not None
                and (stored.content_encoding or "utf8") == "utf8"
                and (body := (stored.inline or "").strip())
            ):
                stored_text = body
        docs = await asyncio.to_thread(
            _chunk_artifact,
            artifact,
            task,
            inline=payload.inline,
            content_encoding=payload.content_encoding,
            created_at=payload.created_at,
            stored_text=stored_text,
        )
        if not docs:
            skipped += 1
            continue
        indexed += 1

        # Write chunk 0 last so an interrupted multi-batch artifact stays eligible on retry.
        for doc in reversed(docs):
            pending.append(doc)
            if len(pending) == _BATCH_SIZE:
                await pace.push(idx, pending)
                pending = []
    if pending:
        await pace.push(idx, pending)

    return {
        "ok": True,
        "mode": "full" if force else "incremental",
        "indexed": indexed,
        "unchanged": unchanged,
        "skipped": skipped,
        "total": indexed + unchanged + skipped,
    }


def log_rebuild_result(task: asyncio.Task[dict[str, Any]]) -> None:
    if task.cancelled():
        logger.warning("kb reindex cancelled")
        return
    try:
        result = task.result()
    except Exception:
        logger.exception("kb reindex failed")
    else:
        logger.info("kb reindex completed %s", result)
