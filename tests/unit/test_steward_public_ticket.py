"""#1180 ③: edu's public steward patrol ticket — no membership_id, scope
ai:steward-public. Pico books it per school, bills the school, and keeps it
out of every membership door (named materials, my files, kb ingest, landing)."""

from __future__ import annotations

import sys
import time
from pathlib import Path

import jwt
import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "api"))
sys.path.insert(0, str(ROOT / "services" / "orchestrator"))

from app.auth import (
    STEWARD_PUBLIC_MEMBERSHIP_ID,
    decode_token,
    is_steward_public,
    issue_edu_read_token,
    issue_edu_write_token,
)
from app.settings import Settings

STEWARD_SCOPES = ["ai:run", "ai:read", "ai:school-run", "ai:steward-public"]
EDU_SECRET = "edu-shared-secret-at-least-32-bytes!!"


def _settings() -> Settings:
    return Settings(
        pico_jwt_secret="test-secret-at-least-32-bytes-long!!",
        pico_jwt_iss="pico-test-issuer",
        pico_jwt_aud="pico-api",
        pico_edu_iss="edu-core",
        pico_edu_jwt_secret=EDU_SECRET,
    )


def _edu_ticket(*, scopes: list[str], membership_id: str | None = None) -> str:
    now = int(time.time())
    payload = {
        "iss": "edu-core",
        "aud": "pico-api",
        "iat": now,
        "exp": now + 600,
        "school_id": "school-a",
        "scopes": scopes,
    }
    if membership_id is not None:
        payload["membership_id"] = membership_id
    return jwt.encode(payload, EDU_SECRET, algorithm="HS256")


def test_steward_ticket_without_membership_books_per_school() -> None:
    s = _settings()
    p = decode_token(_edu_ticket(scopes=STEWARD_SCOPES), s)
    assert p.school_id == "school-a"
    assert p.membership_id == STEWARD_PUBLIC_MEMBERSHIP_ID
    assert p.bill_to == "school"
    assert is_steward_public(p)
    # no person behind it → Pico never mints an edu membership ticket for it
    assert issue_edu_read_token(p, s) is None
    assert issue_edu_write_token(p, s) is None


def test_steward_ticket_bills_school_even_without_school_run_scope() -> None:
    p = decode_token(_edu_ticket(scopes=["ai:run", "ai:steward-public"]), _settings())
    assert p.bill_to == "school"


def test_steward_ticket_with_membership_is_rejected() -> None:
    from fastapi import HTTPException

    with pytest.raises(HTTPException) as exc:
        decode_token(_edu_ticket(scopes=STEWARD_SCOPES, membership_id="m-edu"), _settings())
    assert exc.value.status_code == 401
    assert "must not carry membership_id" in exc.value.detail["message"]


def test_person_ticket_still_needs_membership() -> None:
    from fastapi import HTTPException

    with pytest.raises(HTTPException) as exc:
        decode_token(_edu_ticket(scopes=["ai:run", "ai:read"]), _settings())
    assert exc.value.status_code == 401
    assert "membership_id must be" in exc.value.detail["message"]


def test_person_ticket_still_mints_edu_tokens() -> None:
    s = _settings()
    p = decode_token(_edu_ticket(scopes=["ai:run", "ai:read"], membership_id="m-edu"), s)
    assert p.membership_id == "m-edu"
    assert issue_edu_read_token(p, s)


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("PICO_DATABASE_URL", f"sqlite+aiosqlite:///{tmp_path}/steward.db")
    monkeypatch.setenv("PICO_JWT_SECRET", "test-secret-at-least-32-bytes-long!!")
    monkeypatch.setenv("PICO_ENV", "development")
    monkeypatch.setenv("PICO_EDU_BASE_URL", "https://edu.example")
    monkeypatch.setenv("PICO_EDU_ISS", "edu-core")
    monkeypatch.setenv("PICO_EDU_JWT_SECRET", EDU_SECRET)
    from app import db as dbmod
    from app.main import app
    from app.settings import get_settings as gs

    dbmod._engine = None
    dbmod._Session = None
    gs.cache_clear()
    with TestClient(app) as test_client:
        yield test_client
    dbmod._engine = None
    dbmod._Session = None
    gs.cache_clear()


def _auth() -> dict[str, str]:
    return {"Authorization": f"Bearer {_edu_ticket(scopes=STEWARD_SCOPES)}"}


def test_me_and_models_open_for_steward(client) -> None:
    me = client.get("/v1/me", headers=_auth())
    assert me.status_code == 200, me.text
    assert me.json()["membership_id"] == STEWARD_PUBLIC_MEMBERSHIP_ID
    models = client.get("/v1/models", headers=_auth())
    assert models.status_code == 200, models.text


@pytest.mark.parametrize(
    "method,path,body",
    [
        ("GET", "/v1/edu/named", None),
        ("PUT", "/v1/edu/named", {"conversation_id": "c1", "ids": []}),
        ("POST", "/v1/edu/land", {"filename": "页.html", "body_html": "<p>x</p>"}),
        ("GET", "/v1/my/folders", None),
        ("POST", "/v1/kb/search", {"query": "校历", "scope": "school"}),
    ],
)
def test_membership_doors_shut_for_steward(client, monkeypatch, method, path, body) -> None:
    async def boom(*_a, **_k):
        raise AssertionError("edu must never be called on a steward ticket")

    # belt and braces: the door 403s before any edu call could happen
    monkeypatch.setattr("app.edu_school._edu_call", boom)
    res = client.request(method, path, json=body, headers=_auth())
    assert res.status_code == 403, f"{method} {path}: {res.status_code} {res.text}"
    assert res.json()["detail"]["code"] == "auth.steward_public_denied"
