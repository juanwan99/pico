"""School materials for the workbench: membership-scoped catalog/search/excerpts.

Named items (checked in the UI) are the only school bodies that enter a round.
Search/list return titles + short excerpts for the human picker — never dump
the whole school into the model.
"""

from __future__ import annotations

import json
import re
from typing import Any

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import Principal, issue_edu_read_token, require_any_scope
from app.db import EduNamedBindRow, get_session, new_id
from app.edu_sso import sanitize_named_ids
from app.settings import Settings, get_settings

router = APIRouter(tags=["edu-school"])

_CONV_RE = re.compile(r"^[A-Za-z0-9._:-]{0,128}$")
NAMED_HINT = "只用下面「已点名」的学校材料。未勾选的学校文件不算已读，禁止装作读过整校。"


class NamedBody(BaseModel):
    conversation_id: str = ""
    ids: list[str] = Field(default_factory=list)


def _conversation_key(raw: str | None) -> str:
    value = str(raw or "").strip()
    if value.lower() in {"new", "new-conversation"}:
        return ""
    if not _CONV_RE.match(value):
        return ""
    return value[:128]


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
        if row.get("unread"):
            lines.append(f"- 《{title}》（{item_id}）未读懂")
            continue
        if excerpt:
            lines.append(f"- 《{title}》（{item_id}）\n{excerpt}")
        else:
            lines.append(f"- 《{title}》（{item_id}）")
    return "\n".join(lines) + "\n\n" + str(prompt or "")


async def remember_named_ids(
    session: AsyncSession,
    school_id: str,
    membership_id: str,
    conversation_id: str,
    ids: list[str],
) -> list[str]:
    named = list(sanitize_named_ids(ids))
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
    payload = json.dumps(named, ensure_ascii=False)
    if row is None:
        session.add(
            EduNamedBindRow(
                id=new_id(),
                school_id=school_id,
                membership_id=membership_id,
                conversation_id=key,
                item_ids_json=payload,
            )
        )
    else:
        row.item_ids_json = payload
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


async def _edu_call(
    principal: Principal,
    method: str,
    path: str,
    *,
    params: dict[str, str] | None = None,
    body: dict[str, Any] | None = None,
    settings: Settings | None = None,
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
    token = issue_edu_read_token(principal, s)
    if not root or not token:
        return {"configured": False, "items": [], "fields": [], "dumped": False}
    url = f"{root}{path}"
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
    timeout = float(s.pico_edu_timeout_seconds or 10)
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
    if response.status_code == 403:
        raise HTTPException(
            status_code=403,
            detail={"code": "forbidden", "message": "无权看这份材料"},
        )
    if response.status_code >= 400:
        raise HTTPException(
            status_code=response.status_code,
            detail={"code": "edu.error", "message": "学校拒绝了这次读取"},
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


async def excerpts_for_conversation(
    principal: Principal,
    conversation_id: str,
    session: AsyncSession,
    settings: Settings | None = None,
) -> list[dict[str, Any]]:
    ids = await load_named_ids(session, principal.school_id, principal.membership_id, conversation_id)
    if not ids:
        return []
    data = await _edu_post(principal, "/v1/pico/membership/excerpts", body={"ids": ids}, settings=settings)
    items = data.get("items")
    if not isinstance(items, list):
        return []
    return [row for row in items if isinstance(row, dict)]


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
    return {"ids": ids, "dumped": False}


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
    )
    return {"ids": ids, "dumped": False}
