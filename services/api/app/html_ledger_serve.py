"""Serve-time: resolve pico-artifact: ids to data: URLs.

Write path keeps ids on the ledger (small). Open/download/public GET inlines
bytes. Not a second HTML kernel.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.artifact_store import decode_artifact_payload
from app.db import ArtifactRow, TaskRow


async def inline_html_ledger_images(
    html: str,
    session: AsyncSession,
    *,
    school_id: str,
    membership_id: str,
) -> str:
    from pico_orchestrator.html_ledger_images import (
        collect_pico_artifact_refs,
        image_data_url,
        rewrite_pico_artifact_srcs,
    )

    text = html or ""
    ids = collect_pico_artifact_refs(text, [])
    if not ids:
        return text
    resolved: dict[str, str] = {}
    for aid in ids:
        row = (
            await session.execute(
                select(ArtifactRow)
                .join(TaskRow, ArtifactRow.task_id == TaskRow.id)
                .where(
                    ArtifactRow.id == aid,
                    TaskRow.school_id == school_id,
                    TaskRow.membership_id == membership_id,
                )
            )
        ).scalar_one_or_none()
        if row is None:
            continue
        try:
            raw = decode_artifact_payload(
                row.inline, getattr(row, "content_encoding", None)
            )
        except Exception:  # noqa: BLE001,S112 — skip a missing picture, keep the page
            continue
        url = image_data_url(raw)
        if url:
            resolved[aid] = url
    out, _meta = rewrite_pico_artifact_srcs(text, resolved=resolved, index_ids=[])
    return out
