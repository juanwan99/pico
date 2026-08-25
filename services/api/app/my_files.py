"""「我的文件」folders and school transfer. School write only via membership/land."""

from __future__ import annotations

import re
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.artifact_store import decode_artifact_payload
from app.auth import Principal, require_any_scope
from app.db import PersonalFolderRow, TaskRow, get_session, new_id
from app.edu_school import (
    land_generated_artifact,
    load_archive_folder_id,
    remember_archive_folder_id,
    sanitize_field_id,
    sanitize_folder_id,
)
from app.run_service import get_artifact_for_principal

router = APIRouter(tags=["my-files"])

_FOLDER_NAME_RE = re.compile(r"^[^/\\\n\r]{1,40}$")
_MAX_FOLDERS = 40


class FolderCreateBody(BaseModel):
    name: str = ""


class ArchiveBody(BaseModel):
    conversation_id: str = ""
    folder_id: str = ""


class PlaceBody(BaseModel):
    folder_id: str = ""


class TransferBody(BaseModel):
    field_id: str = ""
    mode: str = Field(default="copy")


def _folder_name(raw: str | None) -> str:
    value = str(raw or "").strip()
    if not value or not _FOLDER_NAME_RE.match(value):
        raise HTTPException(
            status_code=422,
            detail={"code": "folder_name_invalid", "message": "夹名请用 1–40 个字，不要带斜杠"},
        )
    return value


async def owned_folder(
    session: AsyncSession,
    principal: Principal,
    folder_id: str,
) -> PersonalFolderRow | None:
    fid = sanitize_folder_id(folder_id)
    if not fid:
        return None
    return (
        await session.execute(
            select(PersonalFolderRow).where(
                PersonalFolderRow.id == fid,
                PersonalFolderRow.school_id == principal.school_id,
                PersonalFolderRow.membership_id == principal.membership_id,
            )
        )
    ).scalar_one_or_none()


def _folder_dict(row: PersonalFolderRow) -> dict[str, Any]:
    return {
        "id": row.id,
        "name": row.name,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


@router.get("/v1/my/folders")
async def list_my_folders(
    principal: Principal = Depends(require_any_scope("ai:read", "ai:run")),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    rows = (
        await session.execute(
            select(PersonalFolderRow)
            .where(
                PersonalFolderRow.school_id == principal.school_id,
                PersonalFolderRow.membership_id == principal.membership_id,
            )
            .order_by(PersonalFolderRow.created_at.asc())
        )
    ).scalars()
    folders = [_folder_dict(row) for row in rows]
    return {"folders": folders, "count": len(folders)}


@router.post("/v1/my/folders")
async def create_my_folder(
    body: FolderCreateBody,
    principal: Principal = Depends(require_any_scope("ai:run", "ai:read")),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    name = _folder_name(body.name)
    existing = (
        await session.execute(
            select(PersonalFolderRow).where(
                PersonalFolderRow.school_id == principal.school_id,
                PersonalFolderRow.membership_id == principal.membership_id,
            )
        )
    ).scalars()
    rows = list(existing)
    if len(rows) >= _MAX_FOLDERS:
        raise HTTPException(
            status_code=422,
            detail={"code": "folder_limit", "message": "夹太多了，先用现有的"},
        )
    if any(row.name == name for row in rows):
        raise HTTPException(
            status_code=409,
            detail={"code": "folder_exists", "message": "这个夹已经有了"},
        )
    row = PersonalFolderRow(
        id=new_id(),
        school_id=principal.school_id,
        membership_id=principal.membership_id,
        name=name,
    )
    session.add(row)
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(
            status_code=409,
            detail={"code": "folder_exists", "message": "这个夹已经有了"},
        ) from exc
    return {"folder": _folder_dict(row)}


@router.get("/v1/my/archive")
async def get_my_archive(
    conversation_id: str = "",
    principal: Principal = Depends(require_any_scope("ai:read", "ai:run")),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    folder_id = await load_archive_folder_id(
        session, principal.school_id, principal.membership_id, conversation_id
    )
    folder = await owned_folder(session, principal, folder_id) if folder_id else None
    return {
        "folder_id": folder.id if folder else "",
        "folder_name": folder.name if folder else "",
    }


@router.put("/v1/my/archive")
async def put_my_archive(
    body: ArchiveBody,
    principal: Principal = Depends(require_any_scope("ai:run", "ai:read")),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    folder_id = sanitize_folder_id(body.folder_id)
    folder = None
    if folder_id:
        folder = await owned_folder(session, principal, folder_id)
        if folder is None:
            raise HTTPException(
                status_code=404,
                detail={"code": "folder_not_found", "message": "找不到这个夹"},
            )
    saved = await remember_archive_folder_id(
        session,
        principal.school_id,
        principal.membership_id,
        body.conversation_id,
        folder.id if folder else "",
    )
    return {"folder_id": saved, "folder_name": folder.name if folder else ""}


@router.post("/v1/my/artifacts/{artifact_id}/place")
async def place_my_artifact(
    artifact_id: str,
    body: PlaceBody,
    principal: Principal = Depends(require_any_scope("ai:run", "ai:read")),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    artifact = await get_artifact_for_principal(session, artifact_id, principal)
    if artifact is None:
        raise HTTPException(
            status_code=404,
            detail={"code": "artifact.not_found", "message": "找不到这份文件"},
        )
    folder_id = sanitize_folder_id(body.folder_id)
    folder = None
    if folder_id:
        folder = await owned_folder(session, principal, folder_id)
        if folder is None:
            raise HTTPException(
                status_code=404,
                detail={"code": "folder_not_found", "message": "找不到这个夹"},
            )
    artifact.folder_id = folder.id if folder else ""
    await session.commit()
    return {"id": artifact.id, "folder_id": artifact.folder_id}


@router.post("/v1/my/artifacts/{artifact_id}/transfer")
async def transfer_my_artifact(
    artifact_id: str,
    body: TransferBody,
    principal: Principal = Depends(require_any_scope("ai:run", "ai:read")),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    artifact = await get_artifact_for_principal(session, artifact_id, principal)
    if artifact is None:
        raise HTTPException(
            status_code=404,
            detail={"code": "artifact.not_found", "message": "找不到这份文件"},
        )
    field_id = sanitize_field_id(body.field_id)
    if not field_id:
        return {
            "ok": False,
            "landed": False,
            "moved": False,
            "code": "need_named_field",
            "error": "请选择要转存到的学校位置",
            "user_message": "请选择要转存到的学校位置。没选不会写进学校。",
        }
    mode = str(body.mode or "copy").strip().lower()
    if mode not in {"copy", "move"}:
        mode = "copy"
    raw = decode_artifact_payload(artifact.inline, artifact.content_encoding)
    title = artifact.title or "file"
    kind = str(artifact.kind or "").strip().lower()
    content: str | bytes = raw
    if kind in {"html", "htm", "page"} or title.lower().endswith((".html", ".htm")):
        content = raw.decode("utf-8")
    task = await session.get(TaskRow, artifact.task_id)
    convo = str(getattr(task, "conversation_id", "") or "")
    school = await land_generated_artifact(
        principal,
        title=title,
        content=content,
        field_id=field_id,
        conversation_id=convo,
    )
    moved = False
    if school.get("landed") is True and mode == "move":
        await session.delete(artifact)
        await session.commit()
        moved = True
    school["moved"] = moved
    school["mode"] = mode
    return school
