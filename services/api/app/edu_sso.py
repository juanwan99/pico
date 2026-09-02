"""Consume one-time edu web SSO tickets (aud=pico-web). Not the API JWT."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, NoReturn

import jwt
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import EduSsoJtiRow, get_session
from app.settings import Settings, get_settings

WEB_AUD = "pico-web"
WEB_MAX_TTL_SECONDS = 180
FORBIDDEN_CLAIMS = frozenset(
    {"field", "student", "page", "material", "field_id", "student_id"}
)

router = APIRouter()


_UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$",
    re.IGNORECASE,
)
NAMED_IDS_MAX = 12


def sanitize_display_name(raw: Any) -> str:
    name = " ".join(str(raw or "").replace("\r", " ").replace("\n", " ").replace("\t", " ").split())
    name = name.strip()[:80]
    if not name or name == "学校账号":
        return ""
    return name


def sanitize_named_ids(raw: Any) -> tuple[str, ...]:
    if not isinstance(raw, list):
        return ()
    out: list[str] = []
    seen: set[str] = set()
    for value in raw:
        item = str(value or "").strip()
        if not _UUID_RE.match(item) or item in seen:
            continue
        seen.add(item)
        out.append(item)
        if len(out) >= NAMED_IDS_MAX:
            break
    return tuple(out)


@dataclass(frozen=True)
class WebTicket:
    school_id: str
    membership_id: str
    jti: str
    exp: int
    iss: str
    display_name: str = ""
    named_ids: tuple[str, ...] = ()


class ConsumeBody(BaseModel):
    ticket: str = Field(min_length=1, max_length=8192)


def _auth_error(code: str, message: str, http_status: int = status.HTTP_401_UNAUTHORIZED) -> NoReturn:
    raise HTTPException(
        status_code=http_status,
        detail={"code": code, "message": message},
    )


def decode_web_ticket(token: str, settings: Settings | None = None) -> WebTicket:
    """Verify an edu-minted web SSO JWT. API tickets (aud=pico-api) fail closed."""
    s = settings or get_settings()
    raw = (token or "").strip()
    if not raw:
        _auth_error("auth.missing", "ticket required")
    iss = (s.pico_edu_iss or "").strip()
    secret = (s.pico_edu_jwt_secret or "").strip()
    if not iss or not secret:
        _auth_error("auth.iss_unknown", "edu web issuer not configured")

    try:
        data: dict[str, Any] = jwt.decode(
            raw,
            secret,
            algorithms=["HS256"],
            audience=WEB_AUD,
            issuer=iss,
            leeway=60,
            options={"require": ["exp", "iat", "iss", "aud"]},
        )
    except jwt.ExpiredSignatureError:
        _auth_error("auth.expired", "ticket expired")
    except jwt.InvalidIssuerError:
        _auth_error("auth.iss_unknown", "issuer not trusted")
    except jwt.InvalidTokenError as exc:
        msg = str(exc).lower()
        if "audience" in msg or "aud" in msg:
            _auth_error("auth.aud_mismatch", "ticket is not a web SSO ticket")
        _auth_error("auth.invalid", "invalid ticket")

    hit = sorted(FORBIDDEN_CLAIMS.intersection(data))
    if hit:
        _auth_error("auth.invalid", f"web ticket must not carry {hit}")

    school_id = data.get("school_id")
    membership_id = data.get("membership_id")
    jti = data.get("jti")
    if not isinstance(school_id, str) or not school_id.strip():
        _auth_error("auth.invalid", "school_id required")
    if not isinstance(membership_id, str) or not membership_id.strip():
        _auth_error("auth.invalid", "membership_id required")
    if not isinstance(jti, str) or not jti.strip():
        _auth_error("auth.invalid", "jti required")

    try:
        iat = int(data["iat"])
        exp = int(data["exp"])
    except (KeyError, TypeError, ValueError):
        _auth_error("auth.invalid", "iat/exp required")
    if exp - iat > WEB_MAX_TTL_SECONDS:
        _auth_error("auth.invalid", "web ticket ttl too long")

    return WebTicket(
        school_id=school_id.strip(),
        membership_id=membership_id.strip(),
        jti=jti.strip(),
        exp=exp,
        iss=str(data.get("iss") or ""),
        display_name=sanitize_display_name(data.get("display_name")),
        named_ids=sanitize_named_ids(data.get("named_ids")),
    )


async def consume_web_ticket(
    token: str,
    session: AsyncSession,
    settings: Settings | None = None,
) -> WebTicket:
    ticket = decode_web_ticket(token, settings)
    session.add(
        EduSsoJtiRow(
            jti=ticket.jti,
            school_id=ticket.school_id,
            membership_id=ticket.membership_id,
            exp=ticket.exp,
        )
    )
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        _auth_error("auth.invalid", "ticket already used")
    return ticket


@router.post("/v1/edu-sso/consume")
async def consume_edu_sso(
    body: ConsumeBody,
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    ticket = await consume_web_ticket(body.ticket, session, settings)
    # Ticket may still carry named_ids for audit. Do not pre-check school
    # materials (本场成员 included). Teacher must tick them this turn.
    from app.edu_school import remember_named_ids

    await remember_named_ids(
        session, ticket.school_id, ticket.membership_id, "", [], ""
    )
    return {
        "ok": True,
        "school_id": ticket.school_id,
        "membership_id": ticket.membership_id,
        "display_name": ticket.display_name,
        "named_ids": [],
    }
