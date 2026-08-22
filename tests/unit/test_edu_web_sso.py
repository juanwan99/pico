"""T-PICO-SSO-LOGIN: Pico web consumes a one-time edu ticket (not API JWT)."""

from __future__ import annotations

import sys
import time
from pathlib import Path

import jwt
import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "api"))

from app.edu_sso import WEB_AUD, consume_web_ticket, decode_web_ticket
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


def _web_token(*, exp_offset: int = 90, extra: dict | None = None, **claims) -> str:
    now = int(time.time())
    payload = {
        "iss": EDU_ISS,
        "aud": WEB_AUD,
        "iat": now,
        "exp": now + exp_offset,
        "school_id": SCHOOL,
        "membership_id": MEMBER,
        "sub": f"{SCHOOL}:{MEMBER}",
        "jti": "jti-web-1",
        "purpose": "web-sso",
    }
    payload.update(claims)
    if extra:
        payload.update(extra)
    return jwt.encode(payload, EDU_SECRET, algorithm="HS256")


def _api_token() -> str:
    now = int(time.time())
    return jwt.encode(
        {
            "iss": EDU_ISS,
            "aud": "pico-api",
            "iat": now,
            "exp": now + 900,
            "school_id": SCHOOL,
            "membership_id": MEMBER,
            "scopes": ["ai:run", "ai:read", "ai:confirm"],
            "sub": f"{SCHOOL}:{MEMBER}",
        },
        EDU_SECRET,
        algorithm="HS256",
    )


def test_web_ticket_is_membership_not_field_context() -> None:
    t = decode_web_ticket(_web_token(), _settings())
    assert t.school_id == SCHOOL
    assert t.membership_id == MEMBER
    assert t.jti == "jti-web-1"
    assert t.iss == EDU_ISS
    assert t.display_name == ""
    assert t.named_ids == ()


def test_web_ticket_carries_display_name_and_named_ids_not_bodies() -> None:
    item = "aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee"
    t = decode_web_ticket(
        _web_token(
            extra={
                "display_name": "孙骏博",
                "named_ids": [item, "not-a-uuid", item],
            }
        ),
        _settings(),
    )
    assert t.display_name == "孙骏博"
    assert t.named_ids == (item,)


def test_api_ticket_cannot_open_web_session() -> None:
    with pytest.raises(HTTPException) as exc:
        decode_web_ticket(_api_token(), _settings())
    assert exc.value.status_code == 401
    assert exc.value.detail["code"] == "auth.aud_mismatch"


def test_expired_web_ticket() -> None:
    with pytest.raises(HTTPException) as exc:
        decode_web_ticket(_web_token(exp_offset=-120), _settings())
    assert exc.value.detail["code"] == "auth.expired"


def test_forbidden_field_claim_rejected() -> None:
    with pytest.raises(HTTPException) as exc:
        decode_web_ticket(_web_token(extra={"field": "abc"}), _settings())
    assert exc.value.detail["code"] == "auth.invalid"


def test_ttl_too_long_rejected() -> None:
    with pytest.raises(HTTPException) as exc:
        decode_web_ticket(_web_token(exp_offset=900), _settings())
    assert exc.value.detail["code"] == "auth.invalid"


def test_missing_jti_rejected() -> None:
    now = int(time.time())
    raw = jwt.encode(
        {
            "iss": EDU_ISS,
            "aud": WEB_AUD,
            "iat": now,
            "exp": now + 90,
            "school_id": SCHOOL,
            "membership_id": MEMBER,
        },
        EDU_SECRET,
        algorithm="HS256",
    )
    with pytest.raises(HTTPException) as exc:
        decode_web_ticket(raw, _settings())
    assert exc.value.detail["code"] == "auth.invalid"


def test_no_edu_issuer_rejects_web_ticket() -> None:
    with pytest.raises(HTTPException) as raw:
        decode_web_ticket(_web_token(), _settings(pico_edu_iss="", pico_edu_jwt_secret=""))
    assert raw.value.detail["code"] == "auth.iss_unknown"


@pytest.fixture
async def sso_session(tmp_path, monkeypatch):
    monkeypatch.setenv("PICO_DATABASE_URL", f"sqlite+aiosqlite:///{tmp_path}/edu-sso.db")
    import app.db as dbmod

    dbmod._engine = None
    dbmod._Session = None
    await dbmod.init_db()
    async with dbmod.session_factory()() as session:
        yield session
    dbmod._engine = None
    dbmod._Session = None


@pytest.mark.asyncio
async def test_web_ticket_consumed_once(sso_session) -> None:
    settings = _settings()
    token = _web_token(jti="once-only")
    first = await consume_web_ticket(token, sso_session, settings)
    assert first.membership_id == MEMBER
    with pytest.raises(HTTPException) as exc:
        await consume_web_ticket(token, sso_session, settings)
    assert exc.value.detail["code"] == "auth.invalid"
    assert "already used" in exc.value.detail["message"]


def test_consume_http_replay_fails(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("PICO_DATABASE_URL", f"sqlite+aiosqlite:///{tmp_path}/edu-sso-http.db")
    import app.db as dbmod
    from app.edu_sso import router
    from app.settings import get_settings

    dbmod._engine = None
    dbmod._Session = None
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_settings] = lambda: _settings()
    token = _web_token(jti="http-once")
    with TestClient(app) as client:
        first = client.post("/v1/edu-sso/consume", json={"ticket": token})
        assert first.status_code == 200, first.text
        body = first.json()
        assert body["school_id"] == SCHOOL
        assert body["membership_id"] == MEMBER
        replay = client.post("/v1/edu-sso/consume", json={"ticket": token})
        assert replay.status_code == 401
        assert replay.json()["detail"]["code"] == "auth.invalid"
        api = client.post("/v1/edu-sso/consume", json={"ticket": _api_token()})
        assert api.status_code == 401
        assert api.json()["detail"]["code"] == "auth.aud_mismatch"
    dbmod._engine = None
    dbmod._Session = None
