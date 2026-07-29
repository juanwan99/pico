"""Short-lived token validation + Phase 1 test issuer (S4 shape)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.settings import Settings, get_settings

_bearer = HTTPBearer(auto_error=False)


@dataclass(frozen=True)
class Principal:
    school_id: str
    membership_id: str
    scopes: list[str]
    iss: str
    aud: str
    exp: int
    raw: dict[str, Any]


def issue_test_token(
    *,
    school_id: str,
    membership_id: str,
    scopes: list[str] | None = None,
    settings: Settings | None = None,
) -> str:
    """Phase 1 test issuer — same claim shape as future edu issuer."""
    s = settings or get_settings()
    now = datetime.now(UTC)
    exp = now + timedelta(seconds=s.pico_jwt_ttl_seconds)
    payload = {
        "iss": s.pico_jwt_iss,
        "aud": s.pico_jwt_aud,
        "iat": int(now.timestamp()),
        "exp": int(exp.timestamp()),
        "school_id": school_id,
        "membership_id": membership_id,
        "scopes": scopes or ["ai:run", "ai:read"],
        "sub": f"{school_id}:{membership_id}",
    }
    return jwt.encode(payload, s.pico_jwt_secret, algorithm="HS256")


def decode_token(token: str, settings: Settings | None = None) -> Principal:
    s = settings or get_settings()
    try:
        data = jwt.decode(
            token,
            s.pico_jwt_secret,
            algorithms=["HS256"],
            audience=s.pico_jwt_aud,
            issuer=s.pico_jwt_iss,
        )
    except jwt.ExpiredSignatureError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "auth.expired", "message": "token expired"},
        ) from e
    except jwt.InvalidTokenError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "auth.invalid", "message": str(e)},
        ) from e

    school_id = data.get("school_id")
    membership_id = data.get("membership_id")
    if not school_id or not membership_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "code": "auth.invalid",
                "message": "school_id and membership_id required",
            },
        )
    scopes = data.get("scopes") or []
    if isinstance(scopes, str):
        scopes = [scopes]
    return Principal(
        school_id=str(school_id),
        membership_id=str(membership_id),
        scopes=list(scopes),
        iss=str(data.get("iss", "")),
        aud=str(data.get("aud", "")),
        exp=int(data.get("exp", 0)),
        raw=data,
    )


async def require_principal(
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
    settings: Settings = Depends(get_settings),
) -> Principal:
    if creds is None or not creds.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "auth.missing", "message": "bearer token required"},
        )
    return decode_token(creds.credentials, settings)
