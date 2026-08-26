"""Public HTML page routes + publish/unpublish (thin ledger adapter)."""

from __future__ import annotations

import json
import secrets
import time
from collections import defaultdict, deque
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import Response
from pico_orchestrator.gateway import ToolError
from pico_orchestrator.html_public import (
    PUBLIC_CSP,
    assert_page_id,
    normalize_collect_payload,
    prepare_public_html,
)
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.artifact_store import decode_artifact_payload, encode_artifact_payload
from app.auth import Principal
from app.db import ArtifactRow, HtmlPageRow, PersonalFolderRow, TaskRow, new_id

router = APIRouter()

_COLLECT_RPM = 30
_collect_hits: dict[str, deque[float]] = defaultdict(deque)


def _utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _client_ip(request: Request) -> str:
    forwarded = (request.headers.get("x-forwarded-for") or "").split(",")[0].strip()
    if forwarded:
        return forwarded[:64]
    if request.client and request.client.host:
        return str(request.client.host)[:64]
    return "unknown"


def _rate_ok(page_id: str, ip: str) -> bool:
    key = f"{page_id}:{ip}"
    now = time.monotonic()
    bucket = _collect_hits[key]
    while bucket and bucket[0] <= now - 60:
        bucket.popleft()
    if len(bucket) >= _COLLECT_RPM:
        return False
    bucket.append(now)
    return True


PUBLIC_NOT_FOUND_HTML = (
    "<!doctype html><meta charset='utf-8'><title>Not found</title>"
    "<p>This public page is not available.</p>"
)


def public_url_for(page_id: str) -> str:
    return f"https://pico.aivia.asia/p/{page_id}"


def new_page_id() -> str:
    return secrets.token_hex(16)


def public_not_found() -> Response:
    return Response(
        content=PUBLIC_NOT_FOUND_HTML.encode("utf-8"),
        status_code=404,
        media_type="text/html; charset=utf-8",
        headers={"Cache-Control": "no-store"},
    )


async def _owned_html(
    session: AsyncSession, principal: Principal, artifact_id: str
) -> ArtifactRow:
    result = await session.execute(
        select(ArtifactRow)
        .join(TaskRow, ArtifactRow.task_id == TaskRow.id)
        .where(
            ArtifactRow.id == artifact_id,
            TaskRow.school_id == principal.school_id,
            TaskRow.membership_id == principal.membership_id,
        )
    )
    row = result.scalar_one_or_none()
    if row is None:
        raise ToolError("artifact.not_found", "HTML artifact not found")
    title = (row.title or "").lower()
    kind = (row.kind or "").lower()
    if kind not in {"html", "htm"} and not title.endswith((".html", ".htm")):
        raise ToolError("tool.invalid_arguments", "artifact is not HTML")
    return row


async def _folder_for_page(
    session: AsyncSession, principal: Principal, title: str
) -> str:
    name = (title or "html").strip()[:40] or "html"
    existing = await session.execute(
        select(PersonalFolderRow).where(
            PersonalFolderRow.school_id == principal.school_id,
            PersonalFolderRow.membership_id == principal.membership_id,
            PersonalFolderRow.parent_id == "",
            PersonalFolderRow.name == name,
        )
    )
    folder = existing.scalar_one_or_none()
    if folder is not None:
        return folder.id
    folder = PersonalFolderRow(
        id=new_id(),
        school_id=principal.school_id,
        membership_id=principal.membership_id,
        parent_id="",
        name=name,
    )
    session.add(folder)
    await session.flush()
    return folder.id


async def _factory() -> async_sessionmaker[AsyncSession]:
    from app.db import _Session, init_db, session_factory

    if _Session is None:
        await init_db()
    return session_factory()


async def publish_html_page(principal: Principal, *, artifact_id: str) -> dict[str, Any]:
    aid = (artifact_id or "").strip()
    if not aid:
        raise ToolError("tool.invalid_arguments", "artifact_id is required")
    factory = await _factory()
    async with factory() as session:
        artifact = await _owned_html(session, principal, aid)
        live = await session.execute(
            select(HtmlPageRow).where(
                HtmlPageRow.artifact_id == artifact.id,
                HtmlPageRow.school_id == principal.school_id,
                HtmlPageRow.membership_id == principal.membership_id,
                HtmlPageRow.status == "live",
            )
        )
        page = live.scalar_one_or_none()
        if page is None:
            folder_id = artifact.folder_id or await _folder_for_page(
                session, principal, artifact.title
            )
            if not artifact.folder_id:
                artifact.folder_id = folder_id
            page = HtmlPageRow(
                id=new_page_id(),
                artifact_id=artifact.id,
                school_id=principal.school_id,
                membership_id=principal.membership_id,
                task_id=artifact.task_id,
                folder_id=folder_id,
                status="live",
            )
            session.add(page)
            await session.commit()
        url = public_url_for(page.id)
        return {
            "page_id": page.id,
            "artifact_id": artifact.id,
            "public_url": url,
            "public_path": f"/p/{page.id}",
            "collect_path": f"/p/{page.id}/collect",
            "folder_id": page.folder_id,
            "title": artifact.title,
        }


async def unpublish_html_page(
    principal: Principal, *, page_id: str = "", artifact_id: str = ""
) -> dict[str, Any]:
    factory = await _factory()
    async with factory() as session:
        stmt = select(HtmlPageRow).where(
            HtmlPageRow.school_id == principal.school_id,
            HtmlPageRow.membership_id == principal.membership_id,
            HtmlPageRow.status == "live",
        )
        if page_id:
            stmt = stmt.where(HtmlPageRow.id == assert_page_id(page_id))
        elif artifact_id:
            stmt = stmt.where(HtmlPageRow.artifact_id == artifact_id.strip())
        else:
            raise ToolError("tool.invalid_arguments", "page_id or artifact_id is required")
        row = (await session.execute(stmt)).scalar_one_or_none()
        if row is None:
            raise ToolError("artifact.not_found", "published page not found")
        row.status = "revoked"
        row.revoked_at = _utcnow()
        await session.commit()
        return {"page_id": row.id, "revoked": True}


async def _live_page(session: AsyncSession, page_id: str) -> HtmlPageRow:
    raw = assert_page_id(page_id)
    row = await session.get(HtmlPageRow, raw)
    if row is None or row.status != "live":
        raise HTTPException(status_code=404, detail="not found")
    return row


@router.get("/p/{page_id}")
async def public_html_page(page_id: str) -> Response:
    factory = await _factory()
    try:
        async with factory() as session:
            page = await _live_page(session, page_id)
            artifact = await session.get(ArtifactRow, page.artifact_id)
            if artifact is None:
                return public_not_found()
            raw = decode_artifact_payload(
                artifact.inline, getattr(artifact, "content_encoding", None)
            )
            html = raw.decode("utf-8", errors="replace")
            body = prepare_public_html(html)
            return Response(
                content=body.encode("utf-8"),
                media_type="text/html; charset=utf-8",
                headers={
                    "Content-Security-Policy": PUBLIC_CSP,
                    "X-Content-Type-Options": "nosniff",
                    "Cache-Control": "no-store",
                },
            )
    except ToolError:
        return public_not_found()
    except HTTPException as exc:
        if exc.status_code == 404:
            return public_not_found()
        raise


@router.post("/p/{page_id}/collect")
async def public_html_collect(page_id: str, request: Request) -> dict[str, Any]:
    if not _rate_ok(page_id, _client_ip(request)):
        raise HTTPException(status_code=429, detail="too many submits")
    try:
        payload_raw: Any
        ctype = (request.headers.get("content-type") or "").lower()
        if "application/json" in ctype:
            payload_raw = await request.json()
        else:
            payload_raw = await request.body()
        fields = normalize_collect_payload(payload_raw)
    except ToolError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=400, detail="invalid collect body") from exc

    factory = await _factory()
    async with factory() as session:
        try:
            page = await _live_page(session, page_id)
        except ToolError as exc:
            raise HTTPException(status_code=404, detail="not found") from exc
        stamp = _utcnow().strftime("%Y%m%d-%H%M%S")
        title = f"entry-{stamp}.json"
        stored, encoding, byte_size, digest = encode_artifact_payload(
            json.dumps(fields, ensure_ascii=False)
        )
        artifact = ArtifactRow(
            id=new_id(),
            task_id=page.task_id,
            run_id=None,
            kind="form_entry",
            title=title,
            inline=stored,
            content_encoding=encoding,
            content_sha256=digest,
            byte_size=byte_size,
            folder_id=page.folder_id,
        )
        session.add(artifact)
        await session.commit()
        return {"ok": True, "id": artifact.id}
