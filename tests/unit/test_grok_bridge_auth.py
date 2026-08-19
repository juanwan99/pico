from __future__ import annotations

import sys
import time
from pathlib import Path

import jwt
import pytest
from fastapi import HTTPException

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "api"))

from app.auth import decode_token, issue_test_token
from app.settings import Settings

GROK_ISS = "https://auth.grok.me"
GROK_SECRET = "grok-bridge-secret-at-least-32-bytes!!"
TEST_SECRET = "test-secret-at-least-32-bytes-long!!"


def _grok_settings(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "pico_jwt_secret": TEST_SECRET,
        "pico_jwt_iss": "pico-test-issuer",
        "pico_jwt_aud": "pico-api",
        "pico_accept_test_issuer": False,
        "pico_grok_iss": GROK_ISS,
        "pico_grok_jwt_secret": GROK_SECRET,
    }
    values.update(overrides)
    return Settings(**values)


def _grok_token(
    settings: Settings,
    *,
    ttl: int = 900,
    scopes: list[str] | None = None,
    extra: dict | None = None,
) -> str:
    now = int(time.time())
    payload = {
        "iss": settings.pico_grok_iss,
        "aud": settings.pico_jwt_aud,
        "iat": now,
        "exp": now + ttl,
        "school_id": "langtai",
        "membership_id": "grok-user-1",
        "scopes": scopes or ["ai:run", "ai:read", "ai:confirm"],
        "sub": "langtai:grok-user-1",
        "amr": ["grok-auth"],
    }
    if extra:
        payload.update(extra)
    return jwt.encode(payload, settings.pico_grok_jwt_secret, algorithm="HS256")


def test_grok_bridge_accepts_contract_shaped_token() -> None:
    s = _grok_settings()
    p = decode_token(_grok_token(s), s)
    assert p.school_id == "langtai"
    assert p.membership_id == "grok-user-1"
    assert p.iss == GROK_ISS
    assert p.aud == "pico-api"
    assert "ai:run" in p.scopes


def test_grok_bridge_disabled_when_secret_empty() -> None:
    s = _grok_settings(pico_grok_jwt_secret="")
    token = jwt.encode(
        {
            "iss": GROK_ISS,
            "aud": "pico-api",
            "iat": int(time.time()),
            "exp": int(time.time()) + 600,
            "school_id": "langtai",
            "membership_id": "grok-user-1",
            "scopes": ["ai:read"],
        },
        GROK_SECRET,
        algorithm="HS256",
    )
    with pytest.raises(HTTPException) as exc:
        decode_token(token, s)
    assert exc.value.status_code == 401
    assert exc.value.detail["code"] == "auth.iss_unknown"


def test_grok_bridge_rejects_wrong_secret() -> None:
    s = _grok_settings()
    token = jwt.encode(
        {
            "iss": GROK_ISS,
            "aud": "pico-api",
            "iat": int(time.time()),
            "exp": int(time.time()) + 600,
            "school_id": "langtai",
            "membership_id": "grok-user-1",
            "scopes": ["ai:read"],
        },
        "other-secret-at-least-32-bytes-long!!",
        algorithm="HS256",
    )
    with pytest.raises(HTTPException) as exc:
        decode_token(token, s)
    assert exc.value.status_code == 401


def test_grok_bridge_rejects_test_issuer_when_test_disabled() -> None:
    issuer = Settings(
        pico_jwt_secret=TEST_SECRET,
        pico_jwt_iss="pico-test-issuer",
        pico_jwt_aud="pico-api",
        pico_accept_test_issuer=True,
    )
    s = _grok_settings(pico_accept_test_issuer=False)
    token = issue_test_token(school_id="school-a", membership_id="m1", settings=issuer)
    with pytest.raises(HTTPException) as exc:
        decode_token(token, s)
    assert exc.value.status_code == 401
    # Grok issuer is tried last; wrong signature lands as invalid, not iss_unknown.
    assert exc.value.detail["code"] in {"auth.invalid", "auth.iss_unknown"}


def test_grok_bridge_rejects_ttl_over_30_minutes() -> None:
    s = _grok_settings()
    token = _grok_token(s, ttl=1801)
    with pytest.raises(HTTPException) as exc:
        decode_token(token, s)
    assert exc.value.status_code == 401
    assert "30 minutes" in exc.value.detail["message"]


def test_grok_bridge_accepts_30_minute_ceiling() -> None:
    s = _grok_settings()
    p = decode_token(_grok_token(s, ttl=1800), s)
    assert p.membership_id == "grok-user-1"


def test_grok_bridge_rejects_expired_token() -> None:
    s = _grok_settings()
    now = int(time.time())
    token = jwt.encode(
        {
            "iss": GROK_ISS,
            "aud": "pico-api",
            "iat": now - 3600,
            "exp": now - 120,
            "school_id": "langtai",
            "membership_id": "grok-user-1",
            "scopes": ["ai:read"],
        },
        GROK_SECRET,
        algorithm="HS256",
    )
    with pytest.raises(HTTPException) as exc:
        decode_token(token, s)
    assert exc.value.detail["code"] == "auth.expired"


def test_grok_bridge_rejects_wrong_aud() -> None:
    s = _grok_settings()
    token = _grok_token(s, extra={"aud": "other-api"})
    with pytest.raises(HTTPException) as exc:
        decode_token(token, s)
    assert exc.value.detail["code"] == "auth.aud_mismatch"


def test_production_rejects_reused_grok_secret() -> None:
    shared = "shared-secret-must-be-at-least-32b!!"
    s = Settings(
        pico_env="production",
        pico_jwt_secret=shared,
        pico_accept_test_issuer=False,
        pico_openai_proxy_key="proxy-" + "b" * 40,
        deepseek_api_key="model-key",
        pico_model_provider="deepseek",
        pico_allowed_models="pico-fast,pico-deep",
        pico_grok_iss=GROK_ISS,
        pico_grok_jwt_secret=shared,
    )
    with pytest.raises(ValueError, match="PICO_GROK_JWT_SECRET"):
        s.validate_production()


def test_production_rejects_weak_grok_secret() -> None:
    s = Settings(
        pico_env="production",
        pico_jwt_secret="jwt-" + "a" * 40,
        pico_accept_test_issuer=False,
        pico_openai_proxy_key="proxy-" + "b" * 40,
        deepseek_api_key="model-key",
        pico_model_provider="deepseek",
        pico_allowed_models="pico-fast,pico-deep",
        pico_grok_iss=GROK_ISS,
        pico_grok_jwt_secret="short",
    )
    with pytest.raises(ValueError, match="PICO_GROK_JWT_SECRET"):
        s.validate_production()


def test_production_accepts_distinct_grok_secret() -> None:
    s = Settings(
        pico_env="production",
        pico_jwt_secret="jwt-" + "a" * 40,
        pico_accept_test_issuer=False,
        pico_openai_proxy_key="proxy-" + "b" * 40,
        deepseek_api_key="model-key",
        pico_model_provider="deepseek",
        pico_allowed_models="pico-fast,pico-deep",
        pico_grok_iss=GROK_ISS,
        pico_grok_jwt_secret=GROK_SECRET,
    )
    s.validate_production()
    assert s.grok_bridge_enabled is True
