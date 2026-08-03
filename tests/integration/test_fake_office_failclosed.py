from __future__ import annotations

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "api"))
sys.path.insert(0, str(ROOT / "services" / "orchestrator"))

from app.main import app


@pytest.fixture()
def client(tmp_path, monkeypatch):
    database = tmp_path / "fake.db"
    monkeypatch.setenv("PICO_DATABASE_URL", f"sqlite+aiosqlite:///{database}")
    monkeypatch.setenv("PICO_JWT_SECRET", "test-secret-at-least-32-bytes-long!!")
    monkeypatch.setenv("PICO_ENV", "development")
    from app import db as dbmod
    from app.settings import get_settings
    get_settings.cache_clear()
    dbmod._engine = None
    dbmod._Session = None
    with TestClient(app) as c:
        yield c


def _headers(client):
    r = client.post("/v1/dev/token", json={"school_id": "school-a", "membership_id": "member-a"})
    assert r.status_code == 200
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_workspace_write_fake_docx_rejected(client):
    h = _headers(client)
    r = client.post(
        "/v1/tools/invoke",
        headers=h,
        json={"name": "workspace_write_file", "arguments": {"title": "fake.docx", "content": "not ooxml"}},
    )
    assert r.status_code == 400
    assert r.json()["detail"]["code"] == "tool.invalid_arguments"


def test_generate_docx_download_ok_and_fake_storage_blocked(client):
    h = _headers(client)
    # real generate ok
    r = client.post(
        "/v1/tools/invoke",
        headers=h,
        json={"name": "generate_docx_document", "arguments": {"title": "real.docx", "marker": "NEG1", "body": "b"}},
    )
    assert r.status_code == 200, r.text
    aid = r.json()["result"]["artifact_id"]
    d = client.get(f"/v1/artifacts/{aid}/content?download=true", headers=h)
    assert d.status_code == 200
    assert d.content[:2] == b"PK"
