from __future__ import annotations

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "api"))
sys.path.insert(0, str(ROOT / "services" / "orchestrator"))


@pytest.fixture()
def client(tmp_path, monkeypatch):
    db = tmp_path / "t.db"
    monkeypatch.setenv("PICO_DATABASE_URL", f"sqlite+aiosqlite:///{db}")
    monkeypatch.setenv("PICO_HOOK_SERVICE_TOKEN", "hook-secret-token")
    monkeypatch.setenv("PICO_JWT_SECRET", "test-secret-at-least-32-bytes-long!!")
    from app import db as dbmod
    from app.settings import get_settings

    get_settings.cache_clear()
    dbmod._engine = None
    dbmod._Session = None
    from app.main import app

    with TestClient(app) as c:
        yield c


def test_phase3_meta_and_hook(client: TestClient):
    meta = client.get("/v1/meta/phase3").json()
    assert "edu_mode" in meta
    assert meta["auth_issuer_mode"] == "test_and_edu"
    assert meta["hook_token_configured"] is True

    # create + confirm change then hook
    tok = client.post(
        "/v1/dev/token",
        json={"school_id": "school-a", "membership_id": "m1"},
    ).json()["access_token"]
    h = {"Authorization": f"Bearer {tok}"}
    ch = client.post(
        "/v1/changes",
        headers=h,
        json={"title": "t", "summary": "s", "payload": {}},
    ).json()["change"]["id"]
    client.post(f"/v1/changes/{ch}/confirm", headers=h, json={})

    r = client.post(
        "/v1/hooks/edu/change-status",
        headers={"Authorization": "Bearer hook-secret-token"},
        json={
            "pico_change_id": ch,
            "edu_review_id": "rev-1",
            "status": "committed",
            "detail": {"ok": True},
        },
    )
    assert r.status_code == 200, r.text
    assert r.json()["ok"] is True


def _token(client: TestClient, scopes: list[str]) -> str:
    response = client.post(
        "/v1/dev/token",
        json={
            "school_id": "school-a",
            "membership_id": "m-scope",
            "scopes": scopes,
        },
    )
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


def test_route_scopes_are_enforced(client: TestClient):
    read = {"Authorization": f"Bearer {_token(client, ['ai:read'])}"}
    assert client.get("/v1/changes", headers=read).status_code == 200
    denied_create = client.post(
        "/v1/changes",
        headers=read,
        json={"title": "t", "summary": "s", "payload": {}},
    )
    assert denied_create.status_code == 403
    assert denied_create.json()["detail"]["code"] == "auth.forbidden"

    run = {"Authorization": f"Bearer {_token(client, ['ai:run'])}"}
    created = client.post(
        "/v1/changes",
        headers=run,
        json={"title": "t", "summary": "s", "payload": {}},
    )
    assert created.status_code == 200, created.text
    change_id = created.json()["change"]["id"]
    assert client.get("/v1/changes", headers=run).status_code == 403
    assert client.get("/v1/models", headers=run).status_code == 403

    confirm = {"Authorization": f"Bearer {_token(client, ['ai:confirm'])}"}
    confirmed = client.post(
        f"/v1/changes/{change_id}/confirm",
        headers=confirm,
        json={},
    )
    assert confirmed.status_code == 200, confirmed.text


def test_live_handoff_configuration_failure_is_audited(
    client: TestClient,
    monkeypatch,
):
    token = _token(client, ["ai:run", "ai:read", "ai:confirm"])
    headers = {"Authorization": f"Bearer {token}"}
    created = client.post(
        "/v1/changes",
        headers=headers,
        json={"title": "t", "summary": "s", "payload": {}},
    )
    change_id = created.json()["change"]["id"]

    monkeypatch.setenv("PICO_EDU_MODE", "live")
    monkeypatch.setenv("PICO_EDU_HANDOFF_ENABLED", "true")
    monkeypatch.delenv("PICO_EDU_BASE_URL", raising=False)
    monkeypatch.delenv("PICO_EDU_SERVICE_TOKEN", raising=False)
    confirmed = client.post(
        f"/v1/changes/{change_id}/confirm",
        headers=headers,
        json={},
    )
    assert confirmed.status_code == 200, confirmed.text
    change = confirmed.json()["change"]
    assert change["status"] == "confirmed"
    assert change["audit"][-1]["action"] == "handoff_failed"
    assert change["audit"][-1]["code"] == "edu.config_error"
