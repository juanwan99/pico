"""School materials for the workbench: membership-scoped catalog/search/excerpts.

Named items (checked in the UI) are the only school bodies that enter a round.
Search/list return titles + short excerpts for the human picker — never dump
the whole school into the model.
"""

from __future__ import annotations

import base64
import json
import logging
import re
from typing import Any

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import Principal, issue_edu_read_token, issue_edu_write_token, require_any_scope
from app.db import EduNamedBindRow, get_session, new_id
from app.edu_sso import sanitize_named_ids
from app.settings import Settings, get_settings

router = APIRouter(tags=["edu-school"])
logger = logging.getLogger(__name__)

_CONV_RE = re.compile(r"^[A-Za-z0-9._:-]{0,128}$")
NAMED_HINT = "只用下面「已点名」的学校材料。未勾选的学校文件不算已读，禁止装作读过整校。"


class NamedBody(BaseModel):
    conversation_id: str = ""
    ids: list[str] = Field(default_factory=list)
    field_id: str = ""


class LandBody(BaseModel):
    conversation_id: str = ""
    field_id: str = ""
    item_id: str = ""
    title: str = ""
    filename: str = ""
    kind: str = ""
    body_html: str = ""
    content_b64: str = ""


_UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$",
    re.IGNORECASE,
)
_PAGE_EXT = {"html", "htm"}
_MATERIAL_EXT = {"docx", "doc", "xlsx", "xls"}
_SKIP_EXT = {"pptx", "ppt", "png", "jpg", "jpeg", "gif", "webp"}
_BOOKKEEPING = {"回复摘要", "summary", "run summary", "工具产物"}


def sanitize_field_id(raw: str | None) -> str:
    value = str(raw or "").strip()
    return value if _UUID_RE.match(value) else ""


def classify_land_kind(filename: str, kind: str = "") -> str | None:
    ext = ""
    name = str(filename or "").strip().lower()
    if "." in name:
        ext = name.rsplit(".", 1)[-1]
    k = str(kind or "").strip().lower()
    if k in {"page", "html", "htm"} or ext in _PAGE_EXT:
        return "page"
    if k in {"material", "docx", "doc", "xlsx", "xls"} or ext in _MATERIAL_EXT:
        return "material"
    if k in _SKIP_EXT or ext in _SKIP_EXT:
        return "skip"
    return None


def _conversation_key(raw: str | None) -> str:
    value = str(raw or "").strip()
    if value.lower() in {"new", "new-conversation"}:
        return ""
    if not _CONV_RE.match(value):
        return ""
    return value[:128]


_OFFICE_EXT = {".xlsx", ".xls", ".docx", ".doc", ".csv"}


def _looks_b64_blob(val: str) -> bool:
    compact = "".join((val or "").split())
    if len(compact) < 80:
        return False
    return bool(re.fullmatch(r"[A-Za-z0-9+/]+=*", compact[:240]))


def _named_item_text(row: dict[str, Any] | None) -> str:
    if not isinstance(row, dict):
        return ""
    for key in ("excerpt", "text", "body", "body_text", "content", "html", "body_html", "preview"):
        val = row.get(key)
        if isinstance(val, str) and val.strip() and not _looks_b64_blob(val):
            return val.strip()
    slices = row.get("slices")
    if isinstance(slices, list):
        bits = []
        for slice_row in slices:
            if not isinstance(slice_row, dict):
                continue
            piece = str(slice_row.get("excerpt") or slice_row.get("text") or "").strip()
            if piece:
                bits.append(piece)
        if bits:
            return "\n".join(bits)
    for key in ("item", "document", "material", "file"):
        nested = row.get(key)
        if isinstance(nested, dict):
            got = _named_item_text(nested)
            if got:
                return got
    return ""


def _named_item_bytes(row: dict[str, Any] | None) -> bytes | None:
    if not isinstance(row, dict):
        return None
    for key in ("content_b64", "contentBase64", "file_b64", "bytes_b64"):
        val = row.get(key)
        if isinstance(val, str) and val.strip():
            try:
                return base64.b64decode(val, validate=False)
            except (ValueError, TypeError):
                continue
    raw = row.get("content")
    if isinstance(raw, (bytes, bytearray)) and raw:
        return bytes(raw)
    if isinstance(raw, str) and _looks_b64_blob(raw):
        try:
            return base64.b64decode(raw, validate=False)
        except (ValueError, TypeError):
            pass
    for key in ("item", "document", "material", "file"):
        nested = row.get(key)
        if isinstance(nested, dict):
            got = _named_item_bytes(nested)
            if got:
                return got
    return None


def _named_item_filename(row: dict[str, Any]) -> str:
    for key in ("filename", "title", "name"):
        val = str(row.get(key) or "").strip()
        if val:
            return val[:180]
    return str(row.get("id") or "材料")[:180]


def _looks_office(filename: str) -> bool:
    name = (filename or "").strip().lower()
    return any(name.endswith(ext) for ext in _OFFICE_EXT)


def inject_named_school_materials(prompt: str, items: list[dict[str, Any]] | None) -> str:
    """Attach named excerpts to the user prompt. Empty list → prompt unchanged (no dump)."""
    named = [row for row in (items or []) if isinstance(row, dict)]
    if not named:
        return prompt
    lines = [NAMED_HINT, "已点名："]
    for row in named[:12]:
        title = str(row.get("title") or "").strip() or str(row.get("id") or "材料")
        item_id = str(row.get("id") or "")
        excerpt = str(row.get("excerpt") or "").strip()[:4000]
        workspace_title = str(row.get("workspace_title") or "").strip()
        workspace_id = str(row.get("workspace_artifact_id") or "").strip()
        workspace_note = ""
        if workspace_title:
            workspace_note = f"本轮工作区文件名：{workspace_title}"
            if workspace_id:
                workspace_note += f"（artifact_id {workspace_id}）"
        if row.get("unread") and not excerpt:
            lines.append(f"- 《{title}》（{item_id}）未读懂")
            continue
        if excerpt:
            extra = f"\n{workspace_note}" if workspace_note else ""
            lines.append(f"- 《{title}》（{item_id}）{extra}\n{excerpt}")
        elif workspace_note:
            lines.append(f"- 《{title}》（{item_id}）\n{workspace_note}")
        else:
            lines.append(f"- 《{title}》（{item_id}）")
    return "\n".join(lines) + "\n\n" + str(prompt or "")


async def remember_named_ids(
    session: AsyncSession,
    school_id: str,
    membership_id: str,
    conversation_id: str,
    ids: list[str],
    field_id: str = "",
) -> list[str]:
    named = list(sanitize_named_ids(ids))
    key = _conversation_key(conversation_id)
    target_field = sanitize_field_id(field_id)
    row = (
        await session.execute(
            select(EduNamedBindRow).where(
                EduNamedBindRow.school_id == school_id,
                EduNamedBindRow.membership_id == membership_id,
                EduNamedBindRow.conversation_id == key,
            )
        )
    ).scalar_one_or_none()
    payload = json.dumps(named, ensure_ascii=False)
    if row is None:
        session.add(
            EduNamedBindRow(
                id=new_id(),
                school_id=school_id,
                membership_id=membership_id,
                conversation_id=key,
                item_ids_json=payload,
                field_id=target_field,
            )
        )
    else:
        row.item_ids_json = payload
        row.field_id = target_field
    await session.commit()
    return named


async def load_named_ids(
    session: AsyncSession,
    school_id: str,
    membership_id: str,
    conversation_id: str,
) -> list[str]:
    key = _conversation_key(conversation_id)
    row = (
        await session.execute(
            select(EduNamedBindRow).where(
                EduNamedBindRow.school_id == school_id,
                EduNamedBindRow.membership_id == membership_id,
                EduNamedBindRow.conversation_id == key,
            )
        )
    ).scalar_one_or_none()
    if row is None and key:
        row = (
            await session.execute(
                select(EduNamedBindRow).where(
                    EduNamedBindRow.school_id == school_id,
                    EduNamedBindRow.membership_id == membership_id,
                    EduNamedBindRow.conversation_id == "",
                )
            )
        ).scalar_one_or_none()
    if row is None:
        return []
    try:
        parsed = json.loads(row.item_ids_json or "[]")
    except json.JSONDecodeError:
        return []
    return list(sanitize_named_ids(parsed))


async def load_named_field_id(
    session: AsyncSession,
    school_id: str,
    membership_id: str,
    conversation_id: str,
) -> str:
    key = _conversation_key(conversation_id)
    row = (
        await session.execute(
            select(EduNamedBindRow).where(
                EduNamedBindRow.school_id == school_id,
                EduNamedBindRow.membership_id == membership_id,
                EduNamedBindRow.conversation_id == key,
            )
        )
    ).scalar_one_or_none()
    if row is None and key:
        row = (
            await session.execute(
                select(EduNamedBindRow).where(
                    EduNamedBindRow.school_id == school_id,
                    EduNamedBindRow.membership_id == membership_id,
                    EduNamedBindRow.conversation_id == "",
                )
            )
        ).scalar_one_or_none()
    if row is None:
        return ""
    return sanitize_field_id(getattr(row, "field_id", "") or "")


async def promote_named_bind(
    session: AsyncSession,
    school_id: str,
    membership_id: str,
    conversation_id: str,
) -> list[str]:
    """Copy landing (`new`/empty) named ids onto the real conversation so checks survive."""
    key = _conversation_key(conversation_id)
    if not key:
        return await load_named_ids(session, school_id, membership_id, conversation_id)
    key_row = (
        await session.execute(
            select(EduNamedBindRow).where(
                EduNamedBindRow.school_id == school_id,
                EduNamedBindRow.membership_id == membership_id,
                EduNamedBindRow.conversation_id == key,
            )
        )
    ).scalar_one_or_none()
    if key_row is not None:
        return await load_named_ids(session, school_id, membership_id, key)
    landing_ids = await load_named_ids(session, school_id, membership_id, "")
    if not landing_ids:
        return []
    field_id = await load_named_field_id(session, school_id, membership_id, "")
    await remember_named_ids(session, school_id, membership_id, key, landing_ids, field_id)
    archive = await load_archive_folder_id(session, school_id, membership_id, "")
    if archive:
        await remember_archive_folder_id(session, school_id, membership_id, key, archive)
    return landing_ids


def sanitize_folder_id(raw: str | None) -> str:
    value = str(raw or "").strip()
    return value if _UUID_RE.match(value) else ""


async def _named_bind_row(
    session: AsyncSession,
    school_id: str,
    membership_id: str,
    conversation_id: str,
) -> EduNamedBindRow | None:
    key = _conversation_key(conversation_id)
    row = (
        await session.execute(
            select(EduNamedBindRow).where(
                EduNamedBindRow.school_id == school_id,
                EduNamedBindRow.membership_id == membership_id,
                EduNamedBindRow.conversation_id == key,
            )
        )
    ).scalar_one_or_none()
    if row is None and key:
        row = (
            await session.execute(
                select(EduNamedBindRow).where(
                    EduNamedBindRow.school_id == school_id,
                    EduNamedBindRow.membership_id == membership_id,
                    EduNamedBindRow.conversation_id == "",
                )
            )
        ).scalar_one_or_none()
    return row


async def load_archive_folder_id(
    session: AsyncSession,
    school_id: str,
    membership_id: str,
    conversation_id: str,
) -> str:
    row = await _named_bind_row(session, school_id, membership_id, conversation_id)
    if row is None:
        return ""
    return sanitize_folder_id(getattr(row, "archive_folder_id", "") or "")


async def remember_archive_folder_id(
    session: AsyncSession,
    school_id: str,
    membership_id: str,
    conversation_id: str,
    folder_id: str,
) -> str:
    key = _conversation_key(conversation_id)
    target = sanitize_folder_id(folder_id)
    row = (
        await session.execute(
            select(EduNamedBindRow).where(
                EduNamedBindRow.school_id == school_id,
                EduNamedBindRow.membership_id == membership_id,
                EduNamedBindRow.conversation_id == key,
            )
        )
    ).scalar_one_or_none()
    if row is None:
        session.add(
            EduNamedBindRow(
                id=new_id(),
                school_id=school_id,
                membership_id=membership_id,
                conversation_id=key,
                item_ids_json="[]",
                field_id="",
                archive_folder_id=target,
            )
        )
    else:
        row.archive_folder_id = target
    await session.commit()
    return target


async def _edu_get(
    principal: Principal,
    path: str,
    *,
    params: dict[str, str] | None = None,
    settings: Settings | None = None,
) -> dict[str, Any]:
    return await _edu_call(principal, "GET", path, params=params, settings=settings)


async def _edu_post(
    principal: Principal,
    path: str,
    *,
    body: dict[str, Any] | None = None,
    settings: Settings | None = None,
) -> dict[str, Any]:
    return await _edu_call(principal, "POST", path, body=body, settings=settings)


def _edu_http_message(response: httpx.Response, *, write: bool) -> tuple[str, str]:
    fallback = "学校拒绝了这次写入" if write else "学校拒绝了这次读取"
    try:
        data = response.json()
    except ValueError:
        return "edu.error", fallback
    if not isinstance(data, dict):
        return "edu.error", fallback
    detail = data.get("detail")
    if isinstance(detail, dict):
        code = str(detail.get("code") or data.get("code") or "edu.error")
        message = str(detail.get("message") or detail.get("error") or fallback)
        return code, message
    code = str(data.get("code") or "edu.error")
    message = str(data.get("error") or data.get("message") or fallback)
    return code, message or fallback


async def _edu_call(
    principal: Principal,
    method: str,
    path: str,
    *,
    params: dict[str, str] | None = None,
    body: dict[str, Any] | None = None,
    settings: Settings | None = None,
    write: bool = False,
) -> dict[str, Any]:
    s = settings or get_settings()
    base = (s.pico_edu_base_url or "").rstrip("/")
    if not base and (s.pico_env or "").strip().lower() == "production":
        base = "https://edu.weiyuji.cn"
    if base.endswith("/api"):
        root = base
    elif base:
        root = f"{base}/api"
    else:
        root = ""
    token = issue_edu_write_token(principal, s) if write else issue_edu_read_token(principal, s)
    if not root or not token:
        return {"configured": False, "items": [], "fields": [], "dumped": False, "landed": False}
    url = f"{root}{path}"
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
    timeout = float(s.pico_edu_timeout_seconds or 10)
    if write:
        timeout = max(timeout, 20)
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.request(
                method,
                url,
                params=params,
                json=body,
                headers=headers,
            )
    except httpx.HTTPError as exc:
        raise HTTPException(
            status_code=502,
            detail={"code": "edu.unreachable", "message": f"学校现在连不上（{exc}）"},
        ) from exc
    if response.status_code >= 400:
        code, message = _edu_http_message(response, write=write)
        if response.status_code == 403 and not write:
            message = message or "无权看这份材料"
            code = code if code not in {"edu.error", ""} else "forbidden"
        raise HTTPException(
            status_code=response.status_code,
            detail={"code": code or "edu.error", "message": message},
        )
    try:
        data = response.json()
    except ValueError as exc:
        raise HTTPException(
            status_code=502,
            detail={"code": "edu.contract_error", "message": "学校返回不是 JSON"},
        ) from exc
    if not isinstance(data, dict):
        raise HTTPException(
            status_code=502,
            detail={"code": "edu.contract_error", "message": "学校返回不是对象"},
        )
    data.setdefault("dumped", False)
    data["configured"] = True
    return data


async def search_green_library(
    principal: Principal,
    *,
    query: str,
    field_id: str = "",
    settings: Settings | None = None,
) -> dict[str, Any]:
    """Retrieve-only: membership search of edu green-zone slices. No Pico tree."""
    params = {"q": str(query or "")}
    scoped = sanitize_field_id(field_id)
    if scoped:
        params["field_id"] = scoped
    try:
        data = await _edu_get(
            principal, "/v1/pico/membership/search", params=params, settings=settings
        )
    except HTTPException as exc:
        detail = exc.detail if isinstance(exc.detail, dict) else {}
        return {
            "configured": True,
            "items": [],
            "dumped": False,
            "error_code": str(detail.get("code") or "edu.error"),
            "error": str(detail.get("message") or "学校绿区现在连不上"),
            "status": int(exc.status_code),
        }
    items = data.get("items") if isinstance(data.get("items"), list) else []
    return {
        "configured": bool(data.get("configured", True)),
        "items": [row for row in items if isinstance(row, dict)],
        "dumped": False,
        "error_code": "",
        "error": "",
        "status": 200,
    }


async def _fetch_membership_item(
    principal: Principal,
    item_id: str,
    settings: Settings | None = None,
) -> dict[str, Any]:
    if not item_id:
        return {}
    try:
        data = await _edu_get(
            principal, f"/v1/pico/membership/items/{item_id}", settings=settings
        )
    except HTTPException as exc:
        logger.warning(
            "membership item %s failed: %s", item_id, getattr(exc, "status_code", "?")
        )
        return {}
    if not isinstance(data, dict):
        return {}
    nested = data.get("item") if isinstance(data.get("item"), dict) else None
    return nested or data


async def _workspace_named_file(
    principal: Principal,
    *,
    filename: str,
    data: bytes,
    conversation_id: str,
) -> dict[str, Any]:
    from app.edu_files import extract_for_kb, persist_edu_file

    extract = extract_for_kb(filename, data)
    file_id = await persist_edu_file(
        principal,
        filename=filename,
        data=data,
        extract=extract,
        conversation_id=conversation_id,
    )
    text = str(extract.get("text") or "").strip()
    unread = extract.get("status") == "unread" and not text
    return {
        "excerpt": text,
        "unread": unread,
        "workspace_title": filename,
        "workspace_artifact_id": file_id,
    }


async def _fill_named_material(
    principal: Principal,
    row: dict[str, Any],
    conversation_id: str,
    settings: Settings | None = None,
) -> dict[str, Any]:
    filled = dict(row)
    item_id = str(filled.get("id") or "").strip()
    title = str(filled.get("title") or "").strip() or item_id or "材料"
    filled["title"] = title
    text = _named_item_text(filled)
    filename = _named_item_filename(filled)
    need_item = (not text) or filled.get("unread") is True
    need_file = _looks_office(filename) and (not text or len(text) < 40)
    if (need_item or need_file) and item_id:
        extra = await _fetch_membership_item(principal, item_id, settings)
        if extra:
            if not filled.get("title") or filled.get("title") == item_id:
                extra_title = str(extra.get("title") or extra.get("filename") or "").strip()
                if extra_title:
                    filled["title"] = extra_title
            if not str(filled.get("filename") or "").strip() and extra.get("filename"):
                filled["filename"] = extra.get("filename")
            filename = _named_item_filename(filled)
            if not text:
                text = _named_item_text(extra)
            raw = _named_item_bytes(extra) or _named_item_bytes(filled)
            if raw and (need_file or not text):
                try:
                    parked = await _workspace_named_file(
                        principal,
                        filename=filename,
                        data=raw,
                        conversation_id=conversation_id,
                    )
                    filled.update({k: v for k, v in parked.items() if v})
                    if parked.get("excerpt"):
                        text = str(parked["excerpt"])
                except Exception:
                    logger.exception("named school file pipeline failed for %s", item_id)
    if text:
        filled["excerpt"] = text[:20000]
        filled["unread"] = False
    elif filled.get("unread") is not True:
        filled["unread"] = False
    return filled


async def excerpts_for_conversation(
    principal: Principal,
    conversation_id: str,
    session: AsyncSession,
    settings: Settings | None = None,
) -> list[dict[str, Any]]:
    await promote_named_bind(
        session, principal.school_id, principal.membership_id, conversation_id
    )
    ids = await load_named_ids(
        session, principal.school_id, principal.membership_id, conversation_id
    )
    if not ids:
        return []
    by_id: dict[str, dict[str, Any]] = {}
    try:
        data = await _edu_post(
            principal, "/v1/pico/membership/excerpts", body={"ids": ids}, settings=settings
        )
        items = data.get("items") if isinstance(data, dict) else None
        if isinstance(items, list):
            for row in items:
                if isinstance(row, dict) and row.get("id"):
                    by_id[str(row["id"])] = dict(row)
    except HTTPException as exc:
        logger.warning(
            "membership excerpts failed: %s", getattr(exc, "status_code", "?")
        )
    out: list[dict[str, Any]] = []
    for item_id in ids[:12]:
        row = dict(by_id.get(item_id) or {"id": item_id})
        row["id"] = item_id
        try:
            out.append(await _fill_named_material(principal, row, conversation_id, settings))
        except Exception:
            logger.exception("named school material fill failed for %s", item_id)
            out.append(row)
    return out


@router.get("/v1/edu/materials")
async def list_edu_materials(
    q: str = Query(default=""),
    field_id: str = Query(default=""),
    principal: Principal = Depends(require_any_scope("ai:read", "ai:run")),
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    params = {"q": q}
    if field_id:
        params["field_id"] = field_id
    return await _edu_get(principal, "/v1/pico/membership/search", params=params, settings=settings)


@router.get("/v1/edu/fields")
async def list_edu_fields(
    principal: Principal = Depends(require_any_scope("ai:read", "ai:run")),
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    return await _edu_get(principal, "/v1/pico/membership/fields", settings=settings)


@router.get("/v1/edu/materials/{item_id}")
async def get_edu_material(
    item_id: str,
    principal: Principal = Depends(require_any_scope("ai:read", "ai:run")),
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    return await _edu_get(principal, f"/v1/pico/membership/items/{item_id}", settings=settings)


@router.get("/v1/edu/named")
async def get_named(
    conversation_id: str = Query(default=""),
    principal: Principal = Depends(require_any_scope("ai:read", "ai:run")),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    ids = await load_named_ids(
        session, principal.school_id, principal.membership_id, conversation_id
    )
    field_id = await load_named_field_id(
        session, principal.school_id, principal.membership_id, conversation_id
    )
    return {"ids": ids, "field_id": field_id, "dumped": False}


@router.put("/v1/edu/named")
async def put_named(
    body: NamedBody,
    principal: Principal = Depends(require_any_scope("ai:read", "ai:run")),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    ids = await remember_named_ids(
        session,
        principal.school_id,
        principal.membership_id,
        body.conversation_id,
        body.ids,
        body.field_id,
    )
    field_id = sanitize_field_id(body.field_id)
    return {"ids": ids, "field_id": field_id, "dumped": False}


@router.post("/v1/edu/land")
async def post_edu_land(
    body: LandBody,
    principal: Principal = Depends(require_any_scope("ai:run", "ai:read")),
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    payload = await build_land_payload(principal, body, session)
    return await _edu_call(
        principal,
        "POST",
        "/v1/pico/membership/land",
        body=payload,
        settings=settings,
        write=True,
    )


async def build_land_payload(
    principal: Principal,
    body: LandBody,
    session: AsyncSession,
) -> dict[str, Any]:
    field_id = sanitize_field_id(body.field_id)
    if not field_id:
        field_id = await load_named_field_id(
            session, principal.school_id, principal.membership_id, body.conversation_id
        )
    item_id = sanitize_field_id(body.item_id)
    payload: dict[str, Any] = {
        "title": str(body.title or "").strip()[:80],
        "filename": str(body.filename or body.title or "").strip()[:180],
        "kind": str(body.kind or "").strip(),
    }
    if field_id:
        payload["field_id"] = field_id
    if item_id:
        payload["item_id"] = item_id
    if body.body_html:
        payload["body_html"] = body.body_html
    if body.content_b64:
        payload["content_b64"] = body.content_b64
    return payload


def _school_land_copy(result: dict[str, Any] | None) -> dict[str, Any]:
    data = result if isinstance(result, dict) else {}
    landed = data.get("landed") is True and data.get("ok") is not False
    green = data.get("green") is True
    if green:
        return {
            "ok": False,
            "landed": False,
            "code": "silent_green",
            "error": "学校拒绝静默进绿。灰稿才算落到场。",
            "user_message": "学校拒绝静默进绿。灰稿才算落到场。",
        }
    if landed:
        kind = str(data.get("kind") or "")
        where = "展示页灰稿" if kind == "page" else "资料"
        return {
            "ok": True,
            "landed": True,
            "green": False,
            "kind": kind,
            "id": data.get("id"),
            "fieldId": data.get("fieldId") or data.get("field_id"),
            "title": data.get("title") or "",
            "publish_state": data.get("publish_state") or "draft",
            "zone": data.get("zone") or "draft",
            "user_message": f"已转到学校那场{where}。刷新学校能看见。",
        }
    message = str(data.get("error") or data.get("message") or "学校没写上")
    return {
        "ok": False,
        "landed": False,
        "code": str(data.get("code") or "edu.land_failed"),
        "error": message,
        "user_message": f"学校没写上：{message}这份只留在对话草稿纸，刷新学校看不见。",
    }


async def land_generated_artifact(
    principal: Principal,
    *,
    title: str,
    content: str | bytes,
    field_id: str = "",
    conversation_id: str | None = None,
    item_id: str = "",
    settings: Settings | None = None,
) -> dict[str, Any]:
    """Explicit school write through membership/land. Never pretend it landed."""
    name = str(title or "").strip()
    if not name or name in _BOOKKEEPING:
        return {"ok": False, "landed": False, "code": "kind_skip"}
    kind = classify_land_kind(name)
    if kind == "skip":
        return {"ok": False, "landed": False, "code": "kind_skip"}
    if kind is None:
        return {
            "ok": False,
            "landed": False,
            "code": "kind_skip",
            "error": "这份不进学校场（只网页/Word/Excel）",
            "user_message": "这份不进学校场（只网页/Word/Excel）。还留在我的文件。",
        }
    target_field = sanitize_field_id(field_id)
    if not target_field:
        return {
            "ok": False,
            "landed": False,
            "code": "need_named_field",
            "error": "请选择要转存到的学校位置",
            "user_message": "请选择要转存到的学校位置。没选不会写进学校。",
        }
    convo = str(conversation_id or "").strip()
    payload: dict[str, Any] = {
        "title": name.rsplit(".", 1)[0][:80] if "." in name else name[:80],
        "filename": name[:180],
        "kind": kind,
        "conversation_id": convo,
        "field_id": target_field,
    }
    target_item = sanitize_field_id(item_id)
    if target_item:
        payload["item_id"] = target_item
    if kind == "page":
        payload["body_html"] = content if isinstance(content, str) else content.decode("utf-8")
    else:
        raw = content if isinstance(content, bytes) else str(content).encode("utf-8")
        payload["content_b64"] = base64.b64encode(raw).decode("ascii")
    try:
        data = await _edu_call(
            principal,
            "POST",
            "/v1/pico/membership/land",
            body=payload,
            settings=settings,
            write=True,
        )
    except HTTPException as exc:
        detail = exc.detail if isinstance(exc.detail, dict) else {}
        message = str(detail.get("message") or "学校这次没写成")
        code = str(detail.get("code") or "edu.land_failed")
        if code in {"need_named_field", "field_write_required"}:
            message = message or "这场你没有写权，进不去。"
        return {
            "ok": False,
            "landed": False,
            "code": code,
            "error": message,
            "user_message": f"学校没写上：{message}这份还留在我的文件。",
        }
    if data.get("configured") is False:
        return {
            "ok": False,
            "landed": False,
            "code": "edu.unconfigured",
            "error": "学校材料口还没接通",
            "user_message": "学校材料口还没接通。这份还留在我的文件。",
        }
    return _school_land_copy(data)
