"""Thin edu file mouth: JWT → artifact + office extract. Not an Agent OS."""

from __future__ import annotations

import base64
import binascii
import json
import logging
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pico_orchestrator.meili_kb import PARSE_EXT, parse_office_bytes, project_material_artifact
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import Principal, require_any_scope
from app.db import ArtifactRow, TaskRow, new_id, session_factory
from app.office_extract import extract_office

router = APIRouter(tags=["edu-files"])
logger = logging.getLogger(__name__)

MAX_BYTES = 8 * 1024 * 1024
KIND_SRC = "edu_office"
KIND_EXCERPT = "edu_excerpt"
TEXT_KINDS = frozenset({"md", "txt", "json", "csv", "tsv", "html", "htm"})
RESERVED_CONVO = frozenset({"new", "search"})
EDU_READ_PREFIX = "edu-read ·"
PIXEL_KINDS = frozenset({"png", "jpg", "jpeg", "webp", "gif"})
PAPERCLIP_HINT = "本轮回形针文件（聊天上传，不是学校库）："
_MAX_UPLOAD_INJECT = 6
_MAX_UPLOAD_EXCERPT = 2000
_MAX_UPLOAD_BLOCK = 6000


class FileJsonIn(BaseModel):
    filename: str = Field(min_length=1, max_length=180)
    content_b64: str = Field(min_length=1)
    mime: str | None = None
    folder_id: str = ""


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


async def _read_upload(request: Request) -> tuple[str, bytes, str]:
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
        folder_id = str(form.get("folder_id") or "")
        return filename[:180], data, folder_id
    try:
        payload = await request.json()
    except Exception as exc:
        raise _bad_body("要 JSON 或 multipart 文件") from exc
    parsed = FileJsonIn.model_validate(payload)
    return parsed.filename, decode_b64(parsed.content_b64), parsed.folder_id or ""


def extract_for_kb(filename: str, data: bytes) -> dict[str, Any]:
    """PDF/DOCX via field-kb-ingest; other office via stdlib extract_office."""
    from pathlib import Path

    suffix = Path(filename or "file").suffix.lower()
    if suffix in {".png", ".jpg", ".jpeg", ".gif", ".webp"}:
        ext = "jpg" if suffix in {".jpg", ".jpeg"} else suffix.lstrip(".")
        return {
            "filename": (filename or "file")[:180],
            "kind": ext,
            "status": "ok",
            "headline": "图片",
            "rows": None,
            "cols": None,
            "sheets": [],
            "text": "",
            "error": None,
        }
    if suffix in PARSE_EXT:
        text = parse_office_bytes(filename=filename or "file", data=data)
        ext = suffix.lstrip(".")
        if text:
            return {
                "filename": (filename or "file")[:180],
                "kind": ext,
                "status": "ok",
                "headline": text[:80],
                "rows": None,
                "cols": None,
                "sheets": [],
                "text": text[:20000],
                "error": None,
            }
        office = extract_office(filename, data)
        if office.get("status") == "ok" and str(office.get("text") or "").strip():
            return office
        return {
            "filename": (filename or "file")[:180],
            "kind": ext,
            "status": "unread",
            "headline": "没抽出正文",
            "rows": None,
            "cols": None,
            "sheets": [],
            "text": "",
            "error": "没抽出正文",
        }
    return extract_office(filename, data)


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


def inject_conversation_uploads(prompt: str, items: list[dict[str, Any]] | None) -> str:
    """Put this-conversation paperclip extracts on the user turn. Empty → unchanged."""
    named = [row for row in (items or []) if isinstance(row, dict)]
    if not named:
        return prompt
    lines = [PAPERCLIP_HINT]
    for row in named[:_MAX_UPLOAD_INJECT]:
        title = str(row.get("title") or row.get("filename") or "文件").strip() or "文件"
        excerpt = str(row.get("excerpt") or "").strip()[:_MAX_UPLOAD_EXCERPT]
        error = str(row.get("error") or "").strip()
        art_id = str(row.get("id") or row.get("artifact_id") or "").strip()
        id_note = f"（artifact_id {art_id}）" if art_id else ""
        if excerpt:
            lines.append(f"- 《{title}》{id_note}\n{excerpt}")
        elif error:
            lines.append(f"- 《{title}》{id_note} {error}")
        else:
            lines.append(f"- 《{title}》{id_note} 没抽出正文。")
    block = "\n".join(lines)
    if len(block) > _MAX_UPLOAD_BLOCK:
        block = block[:_MAX_UPLOAD_BLOCK].rstrip() + "…"
    return block + "\n\n" + str(prompt or "")


def _excerpt_from_sidecar(row: ArtifactRow | None) -> tuple[str, str]:
    if row is None or not row.inline:
        return "", ""
    try:
        parsed = json.loads(row.inline)
    except json.JSONDecodeError:
        return "", ""
    if not isinstance(parsed, dict):
        return "", ""
    text = str(parsed.get("text") or "").strip()
    error = str(parsed.get("error") or "").strip()
    return text, error


async def uploads_for_conversation(
    session: AsyncSession,
    principal: Principal,
    conversation_id: str,
) -> list[dict[str, Any]]:
    """Paperclip /v1/files rows for this conversation. Not generated deliverables."""
    cid = str(conversation_id or "").strip()
    if not cid or cid in RESERVED_CONVO:
        return []
    src_rows = (
        await session.execute(
            select(ArtifactRow)
            .join(TaskRow, ArtifactRow.task_id == TaskRow.id)
            .where(
                TaskRow.school_id == principal.school_id,
                TaskRow.membership_id == principal.membership_id,
                TaskRow.conversation_id == cid,
                TaskRow.title.startswith(EDU_READ_PREFIX),
                ArtifactRow.kind.notin_((KIND_EXCERPT, "kb_text", *PIXEL_KINDS)),
            )
            .order_by(ArtifactRow.created_at.desc())
            .limit(_MAX_UPLOAD_INJECT * 3)
        )
    ).scalars().all()
    seen_titles: set[str] = set()
    picked: list[ArtifactRow] = []
    for src in src_rows:
        title = str(src.title or "").strip()
        kind = str(src.kind or "").strip().lower()
        if kind in PIXEL_KINDS:
            continue
        key = title.lower() or src.id
        if key in seen_titles:
            continue
        seen_titles.add(key)
        picked.append(src)
        if len(picked) >= _MAX_UPLOAD_INJECT:
            break
    if not picked:
        return []
    task_ids = [row.task_id for row in picked]
    excerpt_rows = (
        await session.execute(
            select(ArtifactRow).where(
                ArtifactRow.task_id.in_(task_ids),
                ArtifactRow.kind == KIND_EXCERPT,
            )
        )
    ).scalars().all()
    excerpt_by_task = {row.task_id: row for row in excerpt_rows}
    out: list[dict[str, Any]] = []
    for src in picked:
        text, error = _excerpt_from_sidecar(excerpt_by_task.get(src.task_id))
        if not text and (src.content_encoding or "utf8") != "base64":
            text = str(src.inline or "").strip()[:_MAX_UPLOAD_EXCERPT]
        out.append(
            {
                "id": src.id,
                "title": str(src.title or "文件"),
                "kind": src.kind,
                "excerpt": text[:_MAX_UPLOAD_EXCERPT],
                "error": error,
            }
        )
    return out


async def resolve_owned_folder_id(principal: Principal, raw: str | None) -> str:
    """Empty folder_id → root. Unknown or malformed id fails closed (no silent root dump)."""
    from app.edu_school import sanitize_folder_id
    from app.my_files import owned_folder

    raw_s = str(raw or "").strip()
    if not raw_s:
        return ""
    fid = sanitize_folder_id(raw_s)
    if not fid:
        raise HTTPException(
            status_code=400,
            detail={"code": "folder_id_invalid", "message": "夹 id 不对"},
        )
    factory = session_factory()
    async with factory() as session:
        folder = await owned_folder(session, principal, fid)
        if folder is None:
            raise HTTPException(
                status_code=404,
                detail={"code": "folder_not_found", "message": "找不到这个夹"},
            )
        return folder.id


async def persist_edu_file(
    principal: Principal,
    *,
    filename: str,
    data: bytes,
    extract: dict[str, Any],
    conversation_id: str | None = None,
    folder_id: str = "",
) -> str:
    from app.artifact_store import encode_artifact_payload

    convo = (conversation_id or "").strip() or None
    if convo in RESERVED_CONVO:
        convo = None
    kind = str(extract.get("kind") or "").strip().lower()
    text_body = str(extract.get("text") or "")
    if kind in TEXT_KINDS and text_body:
        stored, encoding, byte_size, digest = encode_artifact_payload(text_body)
        artifact_kind = "file"
    else:
        stored, encoding, byte_size, digest = encode_artifact_payload(data)
        artifact_kind = KIND_SRC
    factory = session_factory()
    async with factory() as session:
        task = TaskRow(
            id=new_id(),
            school_id=principal.school_id,
            membership_id=principal.membership_id,
            title=f"edu-read · {filename}"[:512],
            conversation_id=convo,
        )
        session.add(task)
        await session.flush()
        src = ArtifactRow(
            id=new_id(),
            task_id=task.id,
            kind=artifact_kind,
            title=filename[:512],
            inline=stored,
            content_encoding=encoding,
            content_sha256=digest,
            byte_size=byte_size,
            folder_id=folder_id or "",
        )
        session.add(src)
        if artifact_kind == KIND_SRC and text_body:
            text_stored, text_enc, text_size, text_digest = encode_artifact_payload(text_body)
            kb_row = ArtifactRow(
                id=new_id(),
                task_id=task.id,
                kind="kb_text",
                title=filename[:512],
                inline=text_stored,
                content_encoding=text_enc,
                content_sha256=text_digest,
                byte_size=text_size,
            )
            session.add(kb_row)
            try:
                project_material_artifact(
                    principal,
                    artifact_id=kb_row.id,
                    title=filename[:512],
                    kind="kb_text",
                    content=text_body,
                )
            except Exception as exc:  # noqa: BLE001
                logger.warning("meili project kb_text failed: %s", type(exc).__name__)
        if artifact_kind == KIND_SRC:
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
        index_body: str | bytes
        if artifact_kind == KIND_SRC:
            index_body = data
        else:
            index_body = stored
        try:
            project_material_artifact(
                principal,
                artifact_id=src.id,
                title=filename[:512],
                kind=artifact_kind,
                content=index_body,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("meili project after file persist failed: %s", type(exc).__name__)
        return src.id


async def load_edu_file(principal: Principal, file_id: str) -> dict[str, Any] | None:
    from sqlalchemy import select

    from app.artifact_store import decode_artifact_payload

    factory = session_factory()
    async with factory() as session:
        src = await session.get(ArtifactRow, file_id)
        if src is None or src.kind in {KIND_EXCERPT, "kb_text"}:
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
        raw = decode_artifact_payload(src.inline, src.content_encoding)
        text = ""
        if src.content_encoding == "utf8":
            text = raw.decode("utf-8", errors="replace") if isinstance(raw, bytes) else str(raw or "")
        return _payload(
            src.id,
            {
                "filename": src.title,
                "kind": src.kind,
                "status": "ok",
                "headline": (text or src.title or "")[:80],
                "rows": None,
                "cols": None,
                "sheets": [],
                "text": text[:20000],
                "error": None,
            },
        )


@router.post("/v1/files")
async def post_edu_file(
    request: Request,
    principal: Principal = Depends(require_any_scope("ai:run", "ai:read")),
    x_conversation_id: str | None = Header(default=None, alias="X-Conversation-Id"),
) -> dict[str, Any]:
    filename, data, folder_raw = await _read_upload(request)
    folder_id = await resolve_owned_folder_id(principal, folder_raw)
    extract = extract_for_kb(filename, data)
    file_id = await persist_edu_file(
        principal,
        filename=filename,
        data=data,
        extract=extract,
        conversation_id=x_conversation_id,
        folder_id=folder_id,
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
