"""Rebuild Meili projection from the artifact ledger (source of truth)."""

from __future__ import annotations

import asyncio
import os
import time
from typing import Any

from pico_orchestrator.meili_kb import (
    indexed_artifact_ids,
    is_lab_school,
    is_material,
    material_chunk_docs,
    upsert_documents,
)
from sqlalchemy import select

from app.artifact_store import decode_artifact_payload
from app.auth import Principal
from app.db import ArtifactRow, TaskRow, session_factory

_FLUSH = 80
_PER_MIN = 600


def rebuild_per_min() -> int:
    try:
        return max(60, int(os.environ.get("PICO_KB_REBUILD_PER_MIN") or _PER_MIN))
    except ValueError:
        return _PER_MIN


class _Pace:
    """Chunks written per minute (pico#1271). Each chunk is one embedding request
    Meili makes to New API; 09-16's full ingest hit ch5 with ~2,100 a minute. The
    first minute's worth goes at once, so a deploy's small incremental pass
    never waits; a full rebuild (~72k chunks) takes about two hours."""

    def __init__(self, per_min: int) -> None:
        self.per_min = per_min
        self.sent = 0
        self.t0 = time.monotonic()

    async def after(self, n: int) -> None:
        self.sent += n
        wait = (self.sent - self.per_min) * 60.0 / self.per_min - (time.monotonic() - self.t0)
        if wait > 0:
            await asyncio.sleep(wait)


async def rebuild_materials(
    principal: Principal | None = None,
    *,
    force: bool = False,
) -> dict[str, Any]:
    """Project ledger materials into Meili.

    Incremental by default: artifacts whose chunks are already in the index are
    left alone (``unchanged``), so a deploy only chunks what is new. ``force``
    re-chunks everything (needed after chunker/schema changes). If the set of
    indexed ids cannot be read, fall back to a full pass rather than skip.
    """
    factory = session_factory()
    indexed = 0
    skipped = 0
    unchanged = 0
    pending: list[dict[str, Any]] = []
    pending_arts = 0
    known: set[str] | None = None if force else indexed_artifact_ids()
    mode = "incremental" if known is not None else "full"
    async with factory() as session:
        stmt = select(ArtifactRow, TaskRow).join(TaskRow, ArtifactRow.task_id == TaskRow.id)
        if principal is not None:
            stmt = stmt.where(
                TaskRow.school_id == principal.school_id,
                TaskRow.membership_id == principal.membership_id,
            )
        rows = (await session.execute(stmt)).all()

    stored_by_task_title: dict[tuple[str, str], str] = {}
    for artifact, task in rows:
        if str(artifact.kind or "") != "kb_text":
            continue
        if (artifact.content_encoding or "utf8") != "utf8":
            continue
        body = str(artifact.inline or "").strip()
        if not body:
            continue
        stored_by_task_title[(str(task.id), str(artifact.title or ""))] = body

    pace = _Pace(rebuild_per_min())

    def _flush() -> int:
        nonlocal pending, pending_arts, indexed, skipped
        if not pending:
            return 0
        flushed = len(pending)
        if upsert_documents(pending, replace_artifact=False):
            indexed += pending_arts
        else:
            skipped += pending_arts
        pending = []
        pending_arts = 0
        return flushed

    for artifact, task in rows:
        if is_lab_school(str(task.school_id or "")):
            skipped += 1
            continue
        if not is_material(kind=artifact.kind, title=artifact.title):
            skipped += 1
            continue
        if known is not None and str(artifact.id) in known:
            unchanged += 1
            continue
        encoding = artifact.content_encoding or "utf8"
        content: str | bytes | None
        if encoding == "base64":
            try:
                content = decode_artifact_payload(artifact.inline, encoding)
            except Exception:  # noqa: BLE001
                content = None
        else:
            content = artifact.inline or ""

        class _P:
            school_id = task.school_id
            membership_id = task.membership_id

        created = artifact.created_at.isoformat() if artifact.created_at else None
        docs = material_chunk_docs(
            _P(),
            artifact_id=artifact.id,
            title=artifact.title,
            kind=artifact.kind,
            content=content,
            created_at=created,
            stored_text=stored_by_task_title.get((str(task.id), str(artifact.title or ""))),
        )
        if not docs:
            skipped += 1
            continue
        pending.extend(docs)
        pending_arts += 1
        if len(pending) >= _FLUSH:
            await pace.after(_flush())
    _flush()
    return {
        "ok": True,
        "mode": mode,
        "indexed": indexed,
        "unchanged": unchanged,
        "skipped": skipped,
        "total": indexed + unchanged + skipped,
    }
