"""Rebuild Meili projection from the artifact ledger (source of truth)."""

from __future__ import annotations

from typing import Any

from pico_orchestrator.meili_kb import (
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


async def rebuild_materials(principal: Principal | None = None) -> dict[str, Any]:
    factory = session_factory()
    indexed = 0
    skipped = 0
    pending: list[dict[str, Any]] = []
    pending_arts = 0
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

    def _flush() -> None:
        nonlocal pending, pending_arts, indexed, skipped
        if not pending:
            return
        if upsert_documents(pending, replace_artifact=False):
            indexed += pending_arts
        else:
            skipped += pending_arts
        pending = []
        pending_arts = 0

    for artifact, task in rows:
        if is_lab_school(str(task.school_id or "")):
            skipped += 1
            continue
        if not is_material(kind=artifact.kind, title=artifact.title):
            skipped += 1
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
            _flush()
    _flush()
    return {"ok": True, "indexed": indexed, "skipped": skipped, "total": indexed + skipped}
