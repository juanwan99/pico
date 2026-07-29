"""Short-lived token validation: Phase 1 test issuer + Phase 3 edu issuer."""

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
    """Phase 1 test issuer — same claim shape as edu Phase 3 issuer."""
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
        "scopes": scopes or ["ai:run", "ai:read", "ai:confirm"],
        "sub": f"{school_id}:{membership_id}",
    }
    return jwt.encode(payload, s.pico_jwt_secret, algorithm="HS256")


def _decode_with_key(
    token: str, *, key: str, algorithms: list[str], audience: str, issuer: str | None
) -> dict[str, Any]:
    opts: dict[str, Any] = {"require": ["exp", "iat", "iss", "aud"]}
    kwargs: dict[str, Any] = {
        "algorithms": algorithms,
        "audience": audience,
        "options": opts,
        "leeway": 60,
    }
    if issuer is not None:
        kwargs["issuer"] = issuer
    return jwt.decode(token, key, **kwargs)


def decode_token(token: str, settings: Settings | None = None) -> Principal:
    s = settings or get_settings()
    aud = s.pico_jwt_aud
    last_err: Exception | None = None
    data: dict[str, Any] | None = None

    # 1) Phase 1 test issuer
    if s.pico_accept_test_issuer and s.pico_jwt_secret:
        try:
            data = _decode_with_key(
                token,
                key=s.pico_jwt_secret,
                algorithms=["HS256"],
                audience=aud,
                issuer=s.pico_jwt_iss,
            )
        except jwt.ExpiredSignatureError as e:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={"code": "auth.expired", "message": "token expired"},
            ) from e
        except jwt.InvalidTokenError as e:
            last_err = e

    # 2) Phase 3 edu HS256 shared secret
    if data is None and s.pico_edu_iss and s.pico_edu_jwt_secret:
        try:
            data = _decode_with_key(
                token,
                key=s.pico_edu_jwt_secret,
                algorithms=["HS256"],
                audience=aud,
                issuer=s.pico_edu_iss,
            )
        except jwt.ExpiredSignatureError as e:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={"code": "auth.expired", "message": "token expired"},
            ) from e
        except jwt.InvalidTokenError as e:
            last_err = e

    # 3) Phase 3 edu RS256 public key
    if data is None and s.pico_edu_iss and s.pico_edu_jwt_public_key_pem:
        try:
            data = _decode_with_key(
                token,
                key=s.pico_edu_jwt_public_key_pem,
                algorithms=["RS256"],
                audience=aud,
                issuer=s.pico_edu_iss,
            )
        except jwt.ExpiredSignatureError as e:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={"code": "auth.expired", "message": "token expired"},
            ) from e
        except jwt.InvalidTokenError as e:
            last_err = e

    if data is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "code": "auth.invalid" if last_err else "auth.iss_unknown",
                "message": str(last_err) if last_err else "no trusted issuer matched",
            },
        )

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


def require_service_token(
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
    settings: Settings = Depends(get_settings),
) -> bool:
    """edu → Pico hooks use a shared service token (not user JWT)."""
    expected = (settings.pico_hook_service_token or "").strip()
    if not expected:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"code": "hook.disabled", "message": "PICO_HOOK_SERVICE_TOKEN not set"},
        )
    if creds is None or creds.credentials != expected:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "auth.invalid", "message": "invalid service token"},
        )
    return True
