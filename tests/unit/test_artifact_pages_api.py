"""GET /v1/artifacts/{id}/pages serves content rasters, not Office chrome."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "api"))
sys.path.insert(0, str(ROOT / "services" / "orchestrator"))

from app.auth import Principal, issue_test_token
from app.settings import get_settings
from pico_orchestrator.sandbox_s2 import PNG_MAGIC


@pytest.fixture()
def client(tmp_path, monkeypatch):
    database = tmp_path / "pages.db"
    monkeypatch.setenv("PICO_DATABASE_URL", f"sqlite+aiosqlite:///{database}")
    monkeypatch.setenv("PICO_JWT_SECRET", "test-secret-at-least-32-bytes-long!!")
    monkeypatch.setenv("PICO_ENV", "development")
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


def _headers(client: TestClient) -> dict[str, str]:
    token = issue_test_token(
        school_id="school-a",
        membership_id="m-edu",
        scopes=["ai:run", "ai:read"],
        settings=get_settings(),
    )
    return {
        "Authorization": f"Bearer {token}",
        "X-Pico-Membership-Id": "school-a:m-edu",
    }


def test_artifact_pages_return_png(client, monkeypatch) -> None:
    from app.artifact_store import LedgerArtifactStore
    from app.db import session_factory

    store = LedgerArtifactStore(session_factory())
    principal = Principal(
        school_id="school-a",
        membership_id="m-edu",
        scopes=["ai:run", "ai:read"],
        iss="pico-test-issuer",
        aud="pico-api",
        exp=9999999999,
        raw={},
    )
    out = asyncio.run(
        store.write(principal, title="课.pptx", content=b"PK\x03\x04fake", kind="pptx")
    )

    async def fake_pages(filename: str, raw: bytes):
        _ = filename, raw
        return [PNG_MAGIC + b"page-one", PNG_MAGIC + b"page-two"]

    monkeypatch.setattr("app.office_pages.pages_for_document", fake_pages)
    headers = _headers(client)
    meta = client.get(f"/v1/artifacts/{out['artifact_id']}/pages", headers=headers)
    assert meta.status_code == 200, meta.text
    assert meta.json()["page_count"] == 2
    page = client.get(f"/v1/artifacts/{out['artifact_id']}/pages/2", headers=headers)
    assert page.status_code == 200
    assert page.content.startswith(PNG_MAGIC)
    assert page.headers["content-type"].startswith("image/png")
