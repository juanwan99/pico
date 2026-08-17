"""Thin edu file mouth: JWT → artifact + office extract. Not an Agent OS."""

from __future__ import annotations

import base64
import binascii
import json
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from app.auth import Principal, require_any_scope
from app.db import ArtifactRow, TaskRow, new_id, session_factory
from app.office_extract import extract_office

router = APIRouter(tags=["edu-files"])

MAX_BYTES = 8 * 1024 * 1024
KIND_SRC = "edu_office"
KIND_EXCERPT = "edu_excerpt"


class FileJsonIn(BaseModel):
    filename: str = Field(min_length=1, max_length=180)
    content_b64: str = Field(min_length=1)
    mime: str | None = None


def _too_large() -> HTTPException:
    return HTTPException(
        status_code=413,
        detail={"code": "file.too_large", "message": "文件太大（上限 8MB）"},
    )


def _bad_body(message: str) -> HTTPException:
    return HTTPException(
        status_code=400,
        detail={"code": "file.invalid", "message": message},
    )


def decode_b64(raw: str) -> bytes:
    compact = "".join(str(raw or "").split())
    if not compact:
        raise _bad_body("没有文件内容")
    try:
        data = base64.b64decode(compact, validate=False)
    except (binascii.Error, ValueError) as exc:
        raise _bad_body("文件内容不是合法的 base64") from exc
    if len(data) > MAX_BYTES:
        raise _too_large()
    return data


async def _read_upload(request: Request) -> tuple[str, bytes]:
    ctype = (request.headers.get("content-type") or "").lower()
    if "multipart/form-data" in ctype:
        form = await request.form()
        upload = form.get("file")
        if upload is None:
            raise _bad_body("没有文件")
        filename = str(getattr(upload, "filename", None) or form.get("filename") or "file")
        data = await upload.read()
        if len(data) > MAX_BYTES:
            raise _too_large()
        return filename[:180], data
    try:
        payload = await request.json()
    except Exception as exc:
        raise _bad_body("要 JSON 或 multipart 文件") from exc
    parsed = FileJsonIn.model_validate(payload)
    return parsed.filename, decode_b64(parsed.content_b64)


def _payload(file_id: str | None, extract: dict[str, Any]) -> dict[str, Any]:
    return {
        "ok": extract.get("status") == "ok",
        "id": file_id,
        "filename": extract.get("filename"),
        "kind": extract.get("kind"),
        "status": extract.get("status"),
        "headline": extract.get("headline"),
        "rows": extract.get("rows"),
        "cols": extract.get("cols"),
        "sheets": extract.get("sheets") or [],
        "text": extract.get("text") or "",
        "error": extract.get("error"),
    }


async def persist_edu_file(
    principal: Principal,
    *,
    filename: str,
    data: bytes,
    extract: dict[str, Any],
) -> str:
    from app.artifact_store import encode_artifact_payload

    stored, encoding, byte_size, digest = encode_artifact_payload(data)
    factory = session_factory()
    async with factory() as session:
        task = TaskRow(
            id=new_id(),
            school_id=principal.school_id,
            membership_id=principal.membership_id,
            title=f"edu-read · {filename}"[:512],
        )
        session.add(task)
        await session.flush()
        src = ArtifactRow(
            id=new_id(),
            task_id=task.id,
            kind=KIND_SRC,
            title=filename[:512],
            inline=stored,
            content_encoding=encoding,
            content_sha256=digest,
            byte_size=byte_size,
        )
        session.add(src)
        excerpt = ArtifactRow(
            id=new_id(),
            task_id=task.id,
            kind=KIND_EXCERPT,
            title=filename[:512],
            inline=json.dumps(extract, ensure_ascii=False),
            content_encoding="utf8",
            content_sha256="",
            byte_size=len(json.dumps(extract, ensure_ascii=False).encode("utf-8")),
        )
        session.add(excerpt)
        await session.commit()
        return src.id


async def load_edu_file(principal: Principal, file_id: str) -> dict[str, Any] | None:
    from sqlalchemy import select

    factory = session_factory()
    async with factory() as session:
        src = await session.get(ArtifactRow, file_id)
        if src is None or src.kind != KIND_SRC:
            return None
        task = await session.get(TaskRow, src.task_id)
        if (
            task is None
            or task.school_id != principal.school_id
            or task.membership_id != principal.membership_id
        ):
            return None
        excerpt_row = (
            await session.execute(
                select(ArtifactRow).where(
                    ArtifactRow.task_id == src.task_id,
                    ArtifactRow.kind == KIND_EXCERPT,
                )
            )
        ).scalars().first()
        if excerpt_row and excerpt_row.inline:
            try:
                extract = json.loads(excerpt_row.inline)
            except json.JSONDecodeError:
                extract = None
            if isinstance(extract, dict):
                return _payload(src.id, extract)
        return None


@router.post("/v1/files")
async def post_edu_file(
    request: Request,
    principal: Principal = Depends(require_any_scope("ai:run", "ai:read")),
) -> dict[str, Any]:
    filename, data = await _read_upload(request)
    extract = extract_office(filename, data)
    file_id = None
    if extract.get("status") == "ok":
        file_id = await persist_edu_file(
            principal, filename=filename, data=data, extract=extract
        )
    return _payload(file_id, extract)


@router.get("/v1/files/{file_id}")
async def get_edu_file(
    file_id: str,
    principal: Principal = Depends(require_any_scope("ai:run", "ai:read")),
) -> dict[str, Any]:
    got = await load_edu_file(principal, file_id)
    if not got:
        raise HTTPException(
            status_code=404,
            detail={"code": "file.not_found", "message": "没有这份文件"},
        )
    return got
