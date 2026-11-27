"""Bind a mobile task and its explicitly selected photo uploads."""

from typing import Annotated

from fastapi import HTTPException
from pydantic import BeforeValidator
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app import run_service
from app.auth import Principal
from app.db import UPLOAD_TASK_PREFIX, ArtifactRow, RunRow, TaskRow, lock_sqlite_writer, new_id
from app.edu_files import _MAX_UPLOAD_INJECT, KIND_EXCERPT, _row_is_pixel


def _uploads(principal: Principal):
    return (
        select(TaskRow, ArtifactRow.id, ArtifactRow.title, ArtifactRow.kind)
        .join(ArtifactRow, ArtifactRow.task_id == TaskRow.id)
        .where(
            TaskRow.school_id == principal.school_id,
            TaskRow.membership_id == principal.membership_id,
            TaskRow.title.startswith(UPLOAD_TASK_PREFIX),
            ArtifactRow.run_id.is_(None),
            ArtifactRow.origin.in_(("upload", "")),
            ArtifactRow.kind.notin_((KIND_EXCERPT, "kb_text")),
        )
    )


def _invalid_upload(message: str) -> HTTPException:
    return HTTPException(status_code=400, detail={"code": "upload.invalid", "message": message})


def _validate_source(value: object) -> str:
    if value != "mobile":
        raise HTTPException(
            status_code=400,
            detail={"code": "task.invalid_source", "message": "source 只支持 mobile"},
        )
    return "mobile"


TaskSource = Annotated[str | None, BeforeValidator(_validate_source)]


async def create_task(
    session: AsyncSession,
    principal: Principal,
    title: str,
    prompt: str,
    skill_id: str | None,
    source: str | None,
    upload_ids: list[str],
) -> tuple[TaskRow, RunRow]:
    if upload_ids and source is None:
        raise _invalid_upload("照片只能添加到手机任务")
    if len(upload_ids) > _MAX_UPLOAD_INJECT:
        raise _invalid_upload(f"最多可以添加 {_MAX_UPLOAD_INJECT} 张照片")

    conversation_id = new_id() if source == "mobile" else None
    if upload_ids:
        await lock_sqlite_writer(session)
        rows = await session.execute(
            _uploads(principal).where(
                ArtifactRow.id.in_(upload_ids),
                or_(
                    TaskRow.conversation_id.is_(None),
                    TaskRow.conversation_id == "",
                    TaskRow.conversation_id.startswith("pending_", autoescape=True),
                ),
            )
        )
        photos = {
            aid: task for task, aid, name, kind in rows if _row_is_pixel(name, kind)
        }
        for aid in upload_ids:
            if aid not in photos:
                raise _invalid_upload(f"照片 {aid} 不可用，请重新上传")
        for photo in photos.values():
            photo.conversation_id = conversation_id

    task, run = await run_service.create_task(
        session, principal, title, prompt, skill_id, conversation_id=conversation_id, source=source
    )
    await run_service.start_run_background(run.id, principal)
    return task, run


async def mobile_photo_rows(session: AsyncSession, principal: Principal, conversation_id: str):
    rows = await session.execute(
        _uploads(principal)
        .where(TaskRow.conversation_id == conversation_id)
        .order_by(ArtifactRow.created_at, ArtifactRow.id)
    )
    return [{"id": aid} for _, aid, name, kind in rows if _row_is_pixel(name, kind)]
