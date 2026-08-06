from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, patch

import httpx
import jwt
import pytest
from fastapi import HTTPException
from pydantic import ValidationError

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "api"))
sys.path.insert(0, str(ROOT / "services" / "orchestrator"))

from app.auth import decode_token, issue_test_token
from app.settings import Settings, get_settings


def _edu_token(settings: Settings, *, scopes: list[str] | None = None) -> str:
    import time

    now = int(time.time())
    payload = {
        "iss": settings.pico_edu_iss,
        "aud": "pico-api",
        "iat": now,
        "exp": now + 600,
        "school_id": "school-a",
        "membership_id": "m-edu",
    }
    if scopes is not None:
        payload["scopes"] = scopes
    return jwt.encode(
        payload,
        settings.pico_edu_jwt_secret,
        algorithm="HS256",
    )


def _handoff() -> dict:
    from pico_orchestrator.edu_adapter import build_change_handoff

    return build_change_handoff(
        pico_change_id="change-1",
        school_id="school-a",
        membership_id="m-edu",
        title="Update class note",
        summary="Teacher confirmed the proposal",
        payload={"domain": "classes", "action": "update"},
        confirmed_at=datetime(2026, 7, 30, 12, 0, tzinfo=timezone.utc),
        confirmed_by="m-edu",
    )


def test_edu_only_mode_accepts_contract_shaped_token():
    get_settings.cache_clear()
    s = Settings(
        pico_jwt_secret="test-secret-at-least-32-bytes-long!!",
        pico_jwt_iss="pico-test-issuer",
        pico_jwt_aud="pico-api",
        pico_edu_iss="https://edu.test/iss/pico",
        pico_edu_jwt_secret="edu-secret-at-least-32-bytes-long!!!",
        pico_accept_test_issuer=False,
    )
    token = _edu_token(s, scopes=["ai:run", "ai:read"])
    p = decode_token(token, s)
    assert p.school_id == "school-a"
    assert p.iss == s.pico_edu_iss
    assert p.membership_id == "m-edu"


def test_edu_only_mode_rejects_test_issuer_token():
    issuer = Settings(
        pico_jwt_secret="test-secret-at-least-32-bytes-long!!",
        pico_jwt_iss="pico-test-issuer",
        pico_jwt_aud="pico-api",
        pico_accept_test_issuer=True,
    )
    edu_only = Settings(
        pico_jwt_secret=issuer.pico_jwt_secret,
        pico_jwt_iss=issuer.pico_jwt_iss,
        pico_jwt_aud=issuer.pico_jwt_aud,
        pico_accept_test_issuer=False,
    )
    token = issue_test_token(
        school_id="school-a",
        membership_id="m1",
        settings=issuer,
    )
    with pytest.raises(HTTPException) as exc:
        decode_token(token, edu_only)
    assert exc.value.status_code == 401
    assert exc.value.detail["code"] == "auth.iss_unknown"


def test_edu_claims_require_non_empty_scope_array():
    s = Settings(
        pico_jwt_aud="pico-api",
        pico_edu_iss="https://edu.test/iss/pico",
        pico_edu_jwt_secret="edu-secret-at-least-32-bytes-long!!!",
        pico_accept_test_issuer=False,
    )
    with pytest.raises(HTTPException) as missing:
        decode_token(_edu_token(s), s)
    assert missing.value.detail["code"] == "auth.invalid"

    with pytest.raises(HTTPException) as empty:
        decode_token(_edu_token(s, scopes=[]), s)
    assert empty.value.detail["code"] == "auth.invalid"

    with pytest.raises(HTTPException) as unknown:
        decode_token(_edu_token(s, scopes=["ai:unknown"]), s)
    assert unknown.value.detail["code"] == "auth.invalid"


def test_test_issuer_reports_contract_error_codes():
    import time

    s = Settings(
        pico_jwt_secret="test-secret-at-least-32-bytes-long!!",
        pico_jwt_iss="pico-test-issuer",
        pico_jwt_aud="pico-api",
        pico_accept_test_issuer=True,
    )
    now = int(time.time())
    claims = {
        "iss": s.pico_jwt_iss,
        "aud": s.pico_jwt_aud,
        "iat": now,
        "exp": now + 600,
        "school_id": "school-a",
        "membership_id": "m1",
        "scopes": ["ai:read"],
    }
    wrong_aud = jwt.encode(
        {**claims, "aud": "other-api"},
        s.pico_jwt_secret,
        algorithm="HS256",
    )
    with pytest.raises(HTTPException) as aud:
        decode_token(wrong_aud, s)
    assert aud.value.detail["code"] == "auth.aud_mismatch"

    wrong_iss = jwt.encode(
        {**claims, "iss": "https://unknown.test/issuer"},
        s.pico_jwt_secret,
        algorithm="HS256",
    )
    with pytest.raises(HTTPException) as issuer:
        decode_token(wrong_iss, s)
    assert issuer.value.detail["code"] == "auth.iss_unknown"


def test_test_issuer_still_works():
    get_settings.cache_clear()
    s = Settings(
        pico_jwt_secret="test-secret-at-least-32-bytes-long!!",
        pico_jwt_iss="pico-test-issuer",
        pico_jwt_aud="pico-api",
    )
    tok = issue_test_token(school_id="school-a", membership_id="m1", settings=s)
    p = decode_token(tok, s)
    assert p.school_id == "school-a"


def test_settings_reject_unknown_edu_mode():
    with pytest.raises(ValidationError):
        Settings(pico_edu_mode="typo")


@pytest.mark.asyncio
async def test_list_classes_fake_default(monkeypatch):
    from pico_orchestrator.edu_adapter import list_classes

    monkeypatch.setenv("PICO_EDU_MODE", "fake")
    out = await list_classes("school-a")
    assert out["source"] == "fake_edu"
    assert len(out["classes"]) >= 1


@pytest.mark.asyncio
async def test_list_classes_live_http(monkeypatch):
    from pico_orchestrator.edu_adapter import list_classes

    monkeypatch.setenv("PICO_EDU_MODE", "live")
    monkeypatch.setenv("PICO_EDU_BASE_URL", "http://edu.test")
    monkeypatch.setenv("PICO_EDU_SERVICE_TOKEN", "svc")

    mock_resp = AsyncMock()
    mock_resp.status_code = 200
    mock_resp.json = lambda: {
        "school_id": "school-a",
        "classes": [{"id": "1", "name": "一班"}],
    }

    class FakeClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return None

        async def get(self, *a, **k):
            return mock_resp

    with patch("pico_orchestrator.edu_adapter.httpx.AsyncClient", return_value=FakeClient()):
        out = await list_classes("school-a")
    assert out["source"] == "edu_live"
    assert out["classes"][0]["name"] == "一班"


@pytest.mark.asyncio
async def test_list_classes_live_rejects_cross_school_response(monkeypatch):
    from pico_orchestrator.edu_adapter import EduAdapterError, list_classes

    monkeypatch.setenv("PICO_EDU_MODE", "live")
    monkeypatch.setenv("PICO_EDU_BASE_URL", "http://edu.test")
    monkeypatch.setenv("PICO_EDU_SERVICE_TOKEN", "svc")

    mock_resp = AsyncMock()
    mock_resp.status_code = 200
    mock_resp.json = lambda: {
        "school_id": "school-b",
        "classes": [{"id": "b1", "name": "Other tenant"}],
    }

    class FakeClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def get(self, *args, **kwargs):
            return mock_resp

    with (
        patch(
            "pico_orchestrator.edu_adapter.httpx.AsyncClient",
            return_value=FakeClient(),
        ),
        pytest.raises(EduAdapterError) as exc,
    ):
        await list_classes("school-a")
    assert exc.value.code == "tenant.cross_school"


@pytest.mark.asyncio
async def test_fake_handoff_validates_shape_without_network(monkeypatch):
    from pico_orchestrator.edu_adapter import push_change_proposal

    monkeypatch.setenv("PICO_EDU_MODE", "fake")
    monkeypatch.setenv("PICO_EDU_HANDOFF_ENABLED", "true")
    monkeypatch.delenv("PICO_EDU_BASE_URL", raising=False)
    monkeypatch.delenv("PICO_EDU_SERVICE_TOKEN", raising=False)
    with patch("pico_orchestrator.edu_adapter.httpx.AsyncClient") as client:
        result = await push_change_proposal(_handoff())
    assert result is None
    client.assert_not_called()


@pytest.mark.asyncio
async def test_live_handoff_without_config_fails_before_network(monkeypatch):
    from pico_orchestrator.edu_adapter import EduAdapterError, push_change_proposal

    monkeypatch.setenv("PICO_EDU_MODE", "live")
    monkeypatch.setenv("PICO_EDU_HANDOFF_ENABLED", "true")
    monkeypatch.delenv("PICO_EDU_BASE_URL", raising=False)
    monkeypatch.delenv("PICO_EDU_SERVICE_TOKEN", raising=False)
    with (
        patch("pico_orchestrator.edu_adapter.httpx.AsyncClient") as client,
        pytest.raises(EduAdapterError) as exc,
    ):
        await push_change_proposal(_handoff())
    assert exc.value.code == "edu.config_error"
    assert "PICO_EDU_BASE_URL" in exc.value.message
    client.assert_not_called()


@pytest.mark.asyncio
async def test_live_handoff_posts_frozen_contract_envelope(monkeypatch):
    from pico_orchestrator.edu_adapter import CHANGE_HANDOFF_PATH, push_change_proposal

    monkeypatch.setenv("PICO_EDU_MODE", "live")
    monkeypatch.setenv("PICO_EDU_HANDOFF_ENABLED", "true")
    monkeypatch.setenv("PICO_EDU_BASE_URL", "http://edu.test")
    monkeypatch.setenv("PICO_EDU_SERVICE_TOKEN", "svc")
    sent: dict = {}

    mock_resp = AsyncMock()
    mock_resp.status_code = 200
    mock_resp.json = lambda: {
        "edu_review_id": "review-1",
        "status": "accepted_for_review",
    }

    class FakeClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def post(self, url, *, json, headers):
            sent.update(url=url, body=json, headers=headers)
            return mock_resp

    with patch(
        "pico_orchestrator.edu_adapter.httpx.AsyncClient",
        return_value=FakeClient(),
    ):
        result = await push_change_proposal(_handoff())

    assert sent["url"] == f"http://edu.test{CHANGE_HANDOFF_PATH}"
    assert sent["body"] == _handoff()
    assert sent["headers"] == {"Authorization": "Bearer svc"}
    assert result == {
        "edu_review_id": "review-1",
        "status": "accepted_for_review",
    }


@pytest.mark.asyncio
async def test_live_handoff_wraps_transport_failure(monkeypatch):
    from pico_orchestrator.edu_adapter import EduAdapterError, push_change_proposal

    monkeypatch.setenv("PICO_EDU_MODE", "live")
    monkeypatch.setenv("PICO_EDU_HANDOFF_ENABLED", "true")
    monkeypatch.setenv("PICO_EDU_BASE_URL", "http://edu.test")
    monkeypatch.setenv("PICO_EDU_SERVICE_TOKEN", "svc")

    class FailingClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def post(self, url, **kwargs):
            raise httpx.ConnectError(
                "offline",
                request=httpx.Request("POST", url),
            )

    with (
        patch(
            "pico_orchestrator.edu_adapter.httpx.AsyncClient",
            return_value=FailingClient(),
        ),
        pytest.raises(EduAdapterError) as exc,
    ):
        await push_change_proposal(_handoff())
    assert exc.value.code == "tool.upstream_error"


@pytest.mark.asyncio
async def test_live_handoff_rejects_invalid_response(monkeypatch):
    from pico_orchestrator.edu_adapter import EduAdapterError, push_change_proposal

    monkeypatch.setenv("PICO_EDU_MODE", "live")
    monkeypatch.setenv("PICO_EDU_HANDOFF_ENABLED", "true")
    monkeypatch.setenv("PICO_EDU_BASE_URL", "http://edu.test")
    monkeypatch.setenv("PICO_EDU_SERVICE_TOKEN", "svc")

    mock_resp = AsyncMock()
    mock_resp.status_code = 200
    mock_resp.json = dict

    class FakeClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def post(self, *args, **kwargs):
            return mock_resp

    with (
        patch(
            "pico_orchestrator.edu_adapter.httpx.AsyncClient",
            return_value=FakeClient(),
        ),
        pytest.raises(EduAdapterError) as exc,
    ):
        await push_change_proposal(_handoff())
    assert exc.value.code == "edu.contract_error"
