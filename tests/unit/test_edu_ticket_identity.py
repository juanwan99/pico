"""T-SHELL-AI-EDU-ID: edu-minted ticket is the person; proxy key is not."""

from __future__ import annotations

import sys
import time
from pathlib import Path

import jwt
import pytest
from fastapi import HTTPException

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "api"))

from app.auth import LEGACY_PROXY_MEMBERSHIP_ID, decode_token
from app.settings import Settings

EDU_ISS = "https://edu.weiyuji.cn/iss/pico"
EDU_SECRET = "edu-secret-at-least-32-bytes-long!!!"
SCHOOL = "627bcf3a-a9a8-4047-afcc-3d4878e2a7af"
MEMBER = "aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee"


def _settings(**kwargs) -> Settings:
    base = {
        "pico_jwt_secret": "test-secret-at-least-32-bytes-long!!",
        "pico_jwt_iss": "pico-test-issuer",
        "pico_jwt_aud": "pico-api",
        "pico_edu_iss": EDU_ISS,
        "pico_edu_jwt_secret": EDU_SECRET,
        "pico_accept_test_issuer": False,
        "pico_env": "production",
        "pico_openai_proxy_key": "x" * 64,
    }
    base.update(kwargs)
    return Settings(**base)


def _edu_token(*, exp_offset: int = 600, **claims) -> str:
    now = int(time.time())
    payload = {
        "iss": EDU_ISS,
        "aud": "pico-api",
        "iat": now,
        "exp": now + exp_offset,
        "school_id": SCHOOL,
        "membership_id": MEMBER,
        "scopes": ["ai:run", "ai:read", "ai:confirm"],
        "sub": f"{SCHOOL}:{MEMBER}",
    }
    payload.update(claims)
    return jwt.encode(payload, EDU_SECRET, algorithm="HS256")


def test_edu_ticket_principal_is_membership_not_nextchat() -> None:
    p = decode_token(_edu_token(), _settings())
    assert p.school_id == SCHOOL
    assert p.membership_id == MEMBER
    assert p.membership_id != LEGACY_PROXY_MEMBERSHIP_ID
    assert p.iss == EDU_ISS
    assert p.aud == "pico-api"
    assert "ai:run" in p.scopes
    assert p.raw.get("proxy") is None


def test_expired_edu_ticket_is_auth_expired() -> None:
    with pytest.raises(HTTPException) as exc:
        decode_token(_edu_token(exp_offset=-120), _settings())
    assert exc.value.status_code == 401
    assert exc.value.detail["code"] == "auth.expired"


def test_bad_edu_ticket_is_auth_invalid_or_unknown() -> None:
    with pytest.raises(HTTPException) as exc:
        decode_token("not-a-jwt", _settings())
    assert exc.value.status_code == 401
    assert exc.value.detail["code"] in {"auth.invalid", "auth.iss_unknown"}


def test_no_edu_issuer_configured_rejects_ticket() -> None:
    s = _settings(pico_edu_iss="", pico_edu_jwt_secret="")
    with pytest.raises(HTTPException) as exc:
        decode_token(_edu_token(), s)
    assert exc.value.status_code == 401
    assert exc.value.detail["code"] == "auth.iss_unknown"


def test_production_proxy_key_is_legacy_nextchat_not_edu_person() -> None:
    s = _settings()
    p = decode_token("x" * 64, s)
    assert p.raw.get("proxy") is True
    assert p.membership_id == LEGACY_PROXY_MEMBERSHIP_ID
    assert p.school_id == "school-a"
