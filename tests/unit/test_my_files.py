"""T-FILES-PLACE: my-files folders, archive bind, no auto school land."""

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
from app.edu_school import land_generated_artifact
from app.settings import get_settings


@pytest.fixture()
def client(tmp_path, monkeypatch):
    database = tmp_path / "my-files.db"
    monkeypatch.setenv("PICO_DATABASE_URL", f"sqlite+aiosqlite:///{database}")
    monkeypatch.setenv("PICO_JWT_SECRET", "test-secret-at-least-32-bytes-long!!")
    monkeypatch.setenv("PICO_ENV", "development")
    monkeypatch.setenv("PICO_EDU_BASE_URL", "")
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


def test_create_folder_and_bind_archive(client) -> None:
    headers = _headers(client)
    created = client.post("/v1/my/folders", json={"name": "备课"}, headers=headers)
    assert created.status_code == 200, created.text
    folder_id = created.json()["folder"]["id"]
    listed = client.get("/v1/my/folders", headers=headers)
    assert listed.status_code == 200
    assert listed.json()["count"] == 1
    put = client.put(
        "/v1/my/archive",
        json={"conversation_id": "c1", "folder_id": folder_id},
        headers=headers,
    )
    assert put.status_code == 200, put.text
    assert put.json()["folder_id"] == folder_id
    got = client.get("/v1/my/archive", params={"conversation_id": "c1"}, headers=headers)
    assert got.json()["folder_id"] == folder_id


def test_create_empty_name_defaults_and_unique(client) -> None:
    headers = _headers(client)
    first = client.post("/v1/my/folders", json={"name": ""}, headers=headers)
    assert first.status_code == 200, first.text
    assert first.json()["folder"]["name"] == "新建文件夹"
    second = client.post("/v1/my/folders", json={"name": ""}, headers=headers)
    assert second.status_code == 200, second.text
    assert second.json()["folder"]["name"] == "新建文件夹 (2)"
    renamed = client.patch(
        f"/v1/my/folders/{first.json()['folder']['id']}",
        json={"name": "备课"},
        headers=headers,
    )
    assert renamed.status_code == 200, renamed.text
    assert renamed.json()["folder"]["name"] == "备课"


def test_write_stays_in_archive_folder_and_does_not_auto_land(client) -> None:
    headers = _headers(client)
    created = client.post("/v1/my/folders", json={"name": "教案夹"}, headers=headers)
    folder_id = created.json()["folder"]["id"]
    client.put(
        "/v1/my/archive",
        json={"conversation_id": "c-write", "folder_id": folder_id},
        headers=headers,
    )

    from app.artifact_store import LedgerArtifactStore
    from app.db import session_factory

    store = LedgerArtifactStore(session_factory(), conversation_id="c-write")
    principal = Principal(
        school_id="school-a",
        membership_id="m-edu",
        scopes=["ai:run", "ai:read"],
        iss="pico-test-issuer",
        aud="pico-api",
        exp=9999999999,
        raw={},
    )

    async def _run() -> dict:
        return await store.write(
            principal,
            title="通知.html",
            content="<p>灰</p>",
            kind="html",
        )

    out = asyncio.run(_run())
    assert "school" not in out
    assert out["folder_id"] == folder_id
    listed = client.get(
        "/v1/artifacts",
        params={"mine": True, "folder_id": folder_id},
        headers=headers,
    )
    assert listed.status_code == 200, listed.text
    titles = [row["title"] for row in listed.json()["artifacts"]]
    assert "通知.html" in titles


def test_land_generated_artifact_without_field_is_honest(monkeypatch) -> None:
    monkeypatch.setenv("PICO_EDU_BASE_URL", "https://edu.example")
    get_settings.cache_clear()
    principal = Principal(
        school_id="school-a",
        membership_id="m-edu",
        scopes=["ai:run"],
        iss="pico-test-issuer",
        aud="pico-api",
        exp=9999999999,
        raw={},
    )

    async def _run() -> dict:
        return await land_generated_artifact(
            principal,
            title="页.html",
            content="<p>灰</p>",
            field_id="",
        )

    body = asyncio.run(_run())
    assert body["landed"] is False
    assert body["code"] == "need_named_field"
    assert "转存到的学校位置" in (body.get("user_message") or "")
    get_settings.cache_clear()


def test_transfer_unconfigured_is_honest(client) -> None:
    headers = _headers(client)
    from app.artifact_store import LedgerArtifactStore
    from app.db import session_factory

    store = LedgerArtifactStore(session_factory(), conversation_id="c-xfer")
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
        store.write(principal, title="页.html", content="<p>灰</p>", kind="html")
    )
    field = "aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee"
    res = client.post(
        f"/v1/my/artifacts/{out['artifact_id']}/transfer",
        json={"field_id": field, "mode": "copy"},
        headers=headers,
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body.get("landed") is False
    assert body.get("configured") is False or body.get("code") == "edu.unconfigured"
    assert "还留在我的文件" in (body.get("user_message") or "")


def test_transfer_without_field_does_not_write(client) -> None:
    headers = _headers(client)
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
        store.write(principal, title="页.html", content="<p>灰</p>", kind="html")
    )
    res = client.post(
        f"/v1/my/artifacts/{out['artifact_id']}/transfer",
        json={"field_id": "", "mode": "copy"},
        headers=headers,
    )
    assert res.status_code == 200, res.text
    assert res.json().get("landed") is False
    assert "转存到的学校位置" in (res.json().get("user_message") or "")
