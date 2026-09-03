"""Short-lived token validation: Phase 1 test issuer + Phase 3 edu issuer."""

from __future__ import annotations

import re
import time
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
from fastapi import Depends, Header, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.settings import Settings, get_settings

_bearer = HTTPBearer(auto_error=False)
SCHOOL_RUN_SCOPE = "ai:school-run"
REGISTERED_SCOPES = frozenset(
    {"ai:read", "ai:run", "ai:confirm", "ai:admin", SCHOOL_RUN_SCOPE}
)
BILL_TO_SCHOOL = "school"
BILL_TO_MEMBER = "member"
# Persisted fallback ledger key. Rename only with a data migration; normal
# LibreChat requests replace it with the authenticated membership header.
LEGACY_PROXY_MEMBERSHIP_ID = "nextchat-user"
_MEMBER_RE = re.compile(r"^[A-Za-z0-9_-]{1,128}$")


def bill_to_from_scopes(scopes: list[str] | None) -> str:
    """Payer tag for usage_events. Token scope only — request body cannot raise to school."""
    if SCHOOL_RUN_SCOPE in (scopes or []):
        return BILL_TO_SCHOOL
    return BILL_TO_MEMBER


def payer_for(principal: Any) -> str:
    """Works on Principal and test doubles (SimpleNamespace)."""
    tagged = getattr(principal, "bill_to", None)
    if tagged in {BILL_TO_SCHOOL, BILL_TO_MEMBER}:
        return str(tagged)
    return bill_to_from_scopes(getattr(principal, "scopes", None))


@dataclass(frozen=True)
class Principal:
    # edu-core: school_membership.school_id + school_membership.id (not user_id).
    school_id: str
    membership_id: str
    scopes: list[str]
    iss: str
    aud: str
    exp: int
    raw: dict[str, Any]

    @property
    def bill_to(self) -> str:
        return bill_to_from_scopes(self.scopes)


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


def issue_edu_read_token(principal: Principal, settings: Settings | None = None) -> str | None:
    """Short pico-api JWT for this membership so edu RLS runs as that person."""
    return _issue_edu_membership_token(principal, purpose="edu-read", scopes=["ai:read"], settings=settings)


def issue_edu_write_token(principal: Principal, settings: Settings | None = None) -> str | None:
    """Same person, write land. Not a school-wide service account."""
    return _issue_edu_membership_token(
        principal,
        purpose="edu-write",
        scopes=["ai:read", "ai:run"],
        settings=settings,
    )


def _issue_edu_membership_token(
    principal: Principal,
    *,
    purpose: str,
    scopes: list[str],
    settings: Settings | None = None,
) -> str | None:
    s = settings or get_settings()
    iss = (s.pico_edu_iss or "").strip()
    secret = (s.pico_edu_jwt_secret or "").strip()
    if not iss or not secret:
        return None
    now = datetime.now(UTC)
    payload = {
        "iss": iss,
        "aud": "pico-api",
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(seconds=90)).timestamp()),
        "school_id": principal.school_id,
        "membership_id": principal.membership_id,
        "scopes": scopes,
        "sub": f"{principal.school_id}:{principal.membership_id}",
        "purpose": purpose,
    }
    return jwt.encode(payload, secret, algorithm="HS256")


def _dev_proxy_keys(settings: Settings) -> set[str]:
    """Match openai_compat: explicit proxy keys only (never model API keys)."""
    keys = {"pico-dev", "sk-pico-dev"}
    extra = (getattr(settings, "pico_openai_proxy_key", None) or "").strip()
    if extra:
        keys.add(extra)
    return keys


def _production_proxy_key(settings: Settings) -> str | None:
    key = (settings.pico_openai_proxy_key or "").strip()
    if len(key) < 32 or key in {"pico-dev", "sk-pico-dev"}:
        return None
    return key


def _decode_with_key(
    token: str, *, key: str, algorithms: list[str], audience: str, issuer: str | None
) -> dict[str, Any]:
    opts: dict[str, Any] = {
        "require": [
            "exp",
            "iat",
            "iss",
            "aud",
            "school_id",
            "membership_id",
            "scopes",
        ]
    }
    kwargs: dict[str, Any] = {
        "algorithms": algorithms,
        "audience": audience,
        "options": opts,
        "leeway": 60,
    }
    if issuer is not None:
        kwargs["issuer"] = issuer
    return jwt.decode(token, key, **kwargs)


def _principal_from_claims(data: dict[str, Any]) -> Principal:
    school_id = data.get("school_id")
    membership_id = data.get("membership_id")
    scopes = data.get("scopes")
    if not isinstance(school_id, str) or not school_id.strip():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "auth.invalid", "message": "school_id must be a non-empty string"},
        )
    if not isinstance(membership_id, str) or not membership_id.strip():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "code": "auth.invalid",
                "message": "membership_id must be a non-empty string",
            },
        )
    if (
        not isinstance(scopes, list)
        or not scopes
        or any(not isinstance(scope, str) or not scope.strip() for scope in scopes)
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "code": "auth.invalid",
                "message": "scopes must be a non-empty string array",
            },
        )
    unknown_scopes = set(scopes) - REGISTERED_SCOPES
    if unknown_scopes:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "code": "auth.invalid",
                "message": f"unknown scopes: {sorted(unknown_scopes)}",
            },
        )
    return Principal(
        school_id=school_id,
        membership_id=membership_id,
        scopes=scopes,
        iss=str(data.get("iss", "")),
        aud=str(data.get("aud", "")),
        exp=int(data.get("exp", 0)),
        raw=data,
    )


def decode_token(token: str, settings: Settings | None = None) -> Principal:
    s = settings or get_settings()
    aud = s.pico_jwt_aud
    last_err: Exception | None = None
    data: dict[str, Any] | None = None

    # 0) OpenAI-compat proxy: dev defaults only outside production; production
    # accepts only the explicit 32+ character internal credential.
    env = (s.pico_env or "development").lower()
    production = env in {"production", "prod"}
    if (not production and token in _dev_proxy_keys(s)) or (
        production and token == _production_proxy_key(s)
    ):
        return Principal(
            school_id="school-a",
            membership_id=LEGACY_PROXY_MEMBERSHIP_ID,
            scopes=["ai:run", "ai:read", "ai:confirm"],
            iss=s.pico_jwt_iss,
            aud=s.pico_jwt_aud,
            exp=int(time.time()) + 3600,
            raw={"proxy": True},
        )

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
        if isinstance(last_err, jwt.InvalidAudienceError):
            code = "auth.aud_mismatch"
        elif isinstance(last_err, jwt.InvalidIssuerError):
            code = "auth.iss_unknown"
        else:
            code = "auth.invalid" if last_err else "auth.iss_unknown"
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "code": code,
                "message": str(last_err) if last_err else "no trusted issuer matched",
            },
        )

    return _principal_from_claims(data)


def scope_proxy_principal(
    principal: Principal,
    membership_id: str | None,
) -> Principal:
    """When using dev/proxy key, bind ledger rows to LibreChat principal.

    Membership header may be a bare id (school stays proxy default) or a joint
    canary key ``school_id:membership_id`` matching production canary config shape.
    Joint form is required for reverse isolation tests on the proxy auth chain
    (same membership, different school) without inventing a second auth path.
    """
    if not principal.raw.get("proxy"):
        return principal
    mid = (membership_id or "").strip()
    if not mid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="proxy membership header required",
        )
    import re

    school_id = principal.school_id
    membership = mid
    # Joint key: school:membership (same grammar as canary allowlist entries).
    if ":" in mid:
        school_part, mem_part = mid.split(":", 1)
        school_part = school_part.strip()
        mem_part = mem_part.strip()
        if (
            school_part
            and mem_part
            and re.fullmatch(r"[A-Za-z0-9_-]{1,128}", school_part)
            and re.fullmatch(r"[A-Za-z0-9_-]{1,128}", mem_part)
        ):
            school_id = school_part
            membership = mem_part
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="invalid proxy joint membership header",
            )
    elif not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", mid):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="invalid proxy membership header",
        )
    return Principal(
        school_id=school_id,
        membership_id=membership,
        scopes=principal.scopes,
        iss=principal.iss,
        aud=principal.aud,
        exp=principal.exp,
        raw={
            **principal.raw,
            "scoped_membership": membership,
            "scoped_school": school_id,
            "joint_header": ":" in mid,
        },
    )


def prompt_membership_conflicts_header(marker: str | None, header: str | None) -> bool:
    """True when 【Pico-User】 is a competing tenant key.

    After chat headers switched to ``school:edu``, the browser still stamps the
    LibreChat user id. Header is authoritative; a bare leftover must not 403.
    A different joint key, or two different bare ids, still conflict.
    """
    marker_s = (marker or "").strip()
    header_s = (header or "").strip()
    if not marker_s or marker_s == header_s:
        return False
    legacy_lc_stamp = ":" in header_s and ":" not in marker_s
    return not legacy_lc_stamp


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


async def require_scoped_principal(
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
    settings: Settings = Depends(get_settings),
    x_pico_membership_id: str | None = Header(default=None, alias="X-Pico-Membership-Id"),
) -> Principal:
    if creds is None or not creds.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "auth.missing", "message": "bearer token required"},
        )
    p = decode_token(creds.credentials, settings)
    return scope_proxy_principal(p, x_pico_membership_id)


def billed_identity_ok(principal: Principal, *, production: bool) -> bool:
    """Edu membership only for metered runs. No LibreChat-local leftover ids."""
    school = (principal.school_id or "").strip()
    member = (principal.membership_id or "").strip()
    if not school or not member:
        return False
    if member == LEGACY_PROXY_MEMBERSHIP_ID:
        return False
    if not _MEMBER_RE.fullmatch(school) or not _MEMBER_RE.fullmatch(member):
        return False
    if production and principal.raw.get("proxy"):
        return bool(principal.raw.get("joint_header"))
    return True


def require_billed_identity(principal: Principal, settings: Settings | None = None) -> Principal:
    s = settings or get_settings()
    env = (s.pico_env or "development").lower()
    production = env in {"production", "prod"}
    if billed_identity_ok(principal, production=production):
        return principal
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail={
            "code": "auth.edu_membership_required",
            "message": "请用学校账号登录后再使用。本地邮箱不能计费。",
        },
    )


def enforce_scope(principal: Principal, required_scope: str) -> Principal:
    return enforce_any_scope(principal, required_scope)


def enforce_any_scope(
    principal: Principal,
    *required_scopes: str,
) -> Principal:
    if not required_scopes:
        raise RuntimeError("at least one required scope must be configured")
    unknown = set(required_scopes) - REGISTERED_SCOPES
    if unknown:
        raise RuntimeError(f"unregistered required scopes: {sorted(unknown)}")
    if not set(required_scopes).intersection(principal.scopes):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "auth.forbidden",
                "message": f"one of {list(required_scopes)} scopes required",
            },
        )
    return principal


def require_scope(required_scope: str):
    async def dependency(
        principal: Principal = Depends(require_scoped_principal),
    ) -> Principal:
        return enforce_scope(principal, required_scope)

    return dependency


def require_any_scope(*required_scopes: str):
    async def dependency(
        principal: Principal = Depends(require_scoped_principal),
    ) -> Principal:
        return enforce_any_scope(principal, *required_scopes)

    return dependency


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
