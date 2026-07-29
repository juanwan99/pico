from __future__ import annotations

import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock, patch

import jwt
import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "api"))
sys.path.insert(0, str(ROOT / "services" / "orchestrator"))

from app.auth import decode_token, issue_test_token
from app.settings import Settings, get_settings


def test_edu_issuer_token_accepted():
    get_settings.cache_clear()
    s = Settings(
        pico_jwt_secret="test-secret-at-least-32-bytes-long!!",
        pico_jwt_iss="pico-test-issuer",
        pico_jwt_aud="pico-api",
        pico_edu_iss="https://edu.test/iss/pico",
        pico_edu_jwt_secret="edu-secret-at-least-32-bytes-long!!!",
        pico_accept_test_issuer=True,
    )
    # mint as edu would
    import time

    now = int(time.time())
    token = jwt.encode(
        {
            "iss": s.pico_edu_iss,
            "aud": "pico-api",
            "iat": now,
            "exp": now + 600,
            "school_id": "school-a",
            "membership_id": "m-edu",
            "scopes": ["ai:run", "ai:read"],
        },
        s.pico_edu_jwt_secret,
        algorithm="HS256",
    )
    p = decode_token(token, s)
    assert p.school_id == "school-a"
    assert p.iss == s.pico_edu_iss
    assert p.membership_id == "m-edu"


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


@pytest.mark.asyncio
async def test_list_classes_fake_default():
    from pico_orchestrator.edu_adapter import list_classes

    os.environ["PICO_EDU_MODE"] = "fake"
    out = await list_classes("school-a")
    assert out["source"] == "fake_edu"
    assert len(out["classes"]) >= 1


@pytest.mark.asyncio
async def test_list_classes_live_http():
    from pico_orchestrator.edu_adapter import list_classes

    os.environ["PICO_EDU_MODE"] = "live"
    os.environ["PICO_EDU_BASE_URL"] = "http://edu.test"
    os.environ["PICO_EDU_SERVICE_TOKEN"] = "svc"

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
    os.environ["PICO_EDU_MODE"] = "fake"
