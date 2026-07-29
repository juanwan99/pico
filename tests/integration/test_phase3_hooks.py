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
