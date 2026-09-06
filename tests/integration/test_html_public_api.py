"""T-HTML-PUBLIC: public GET + collect lands on publisher archive."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "api"))
sys.path.insert(0, str(ROOT / "services" / "orchestrator"))

from app.main import app

PAGE = """<!DOCTYPE html>
<html><head><title>demo</title></head>
<body><h1>demo</h1><form><input name="n" value="a"></form></body></html>
"""


@pytest.fixture()
def client(tmp_path, monkeypatch):
    database = tmp_path / "html-public.db"
    monkeypatch.setenv("PICO_DATABASE_URL", f"sqlite+aiosqlite:///{database}")
    monkeypatch.setenv("PICO_JWT_SECRET", "test-secret-at-least-32-bytes-long!!")
    monkeypatch.setenv("PICO_ENV", "development")

    from app import db as dbmod
    from app.settings import get_settings

    get_settings.cache_clear()
    dbmod._engine = None
    dbmod._Session = None
    with TestClient(app) as test_client:
        yield test_client


def _headers(client: TestClient, membership_id: str, school_id: str = "school-a") -> dict[str, str]:
    response = client.post(
        "/v1/dev/token",
        json={"school_id": school_id, "membership_id": membership_id},
    )
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def _invoke(client: TestClient, headers: dict[str, str], name: str, arguments: dict):
    return client.post(
        "/v1/tools/invoke",
        headers=headers,
        json={"name": name, "arguments": arguments},
    )


def _seed_legacy_live_html_page(
    artifact_id: str,
    *,
    page_id: str,
    school_id: str,
    membership_id: str,
) -> str:
    """Insert a leftover live /p row. Do not call the banned publish tool."""

    async def _insert() -> str:
        from app.db import ArtifactRow, HtmlPageRow, session_factory

        factory = session_factory()
        async with factory() as session:
            artifact = await session.get(ArtifactRow, artifact_id)
            assert artifact is not None
            session.add(
                HtmlPageRow(
                    id=page_id,
                    artifact_id=artifact_id,
                    school_id=school_id,
                    membership_id=membership_id,
                    task_id=artifact.task_id,
                    folder_id=artifact.folder_id or "",
                    status="live",
                )
            )
            await session.commit()
        return page_id

    return asyncio.run(_insert())


def test_publish_is_not_a_pico_capability(client) -> None:
    owner = _headers(client, "member-a")
    other = _headers(client, "member-b")
    created = _invoke(
        client,
        owner,
        "generate_html_document",
        {"title": "page.html", "marker": "mk-pub", "body": PAGE},
    )
    assert created.status_code == 200, created.text
    artifact_id = created.json()["result"]["artifact_id"]
    denied = _invoke(client, owner, "publish_html_page", {"artifact_id": artifact_id})
    assert denied.status_code == 400, denied.text
    detail = denied.json().get("detail") or {}
    assert detail.get("code") == "publish.edu_channel_required"
    assert "Edu" in str(detail.get("message") or "")
    from types import SimpleNamespace

    from pico_orchestrator.publish_confirm import issue_confirm_token

    principal = SimpleNamespace(
        school_id="school-a", membership_id="member-a", scopes=["ai:run"]
    )
    still = _invoke(
        client,
        owner,
        "publish_html_page",
        {
            "artifact_id": artifact_id,
            "confirm_token": issue_confirm_token(principal, artifact_id=artifact_id),
        },
    )
    assert still.status_code == 400, still.text
    assert (still.json().get("detail") or {}).get("code") == "publish.edu_channel_required"
    stolen = _invoke(client, other, "publish_html_page", {"artifact_id": artifact_id})
    assert stolen.status_code == 400
    listed = client.get("/v1/artifacts?mine=true", headers=owner)
    titles = {row.get("title") for row in listed.json().get("artifacts", [])}
    assert "page.html" in titles


def test_html_write_is_new_id_without_public_url(client) -> None:
    owner = _headers(client, "member-a")
    first = _invoke(
        client,
        owner,
        "generate_html_document",
        {"title": "page.html", "marker": "mk-a", "body": PAGE},
    )
    assert first.status_code == 200, first.text
    first_id = first.json()["result"]["artifact_id"]
    first_sha = first.json()["result"].get("content_sha256")
    second = _invoke(
        client,
        owner,
        "generate_html_document",
        {
            "title": "page.html",
            "marker": "mk-b",
            "body": PAGE.replace("demo", "other"),
        },
    )
    assert second.status_code == 200, second.text
    second_id = second.json()["result"]["artifact_id"]
    second_sha = second.json()["result"].get("content_sha256")
    assert second_id != first_id
    if first_sha and second_sha:
        assert first_sha != second_sha
    pub = _invoke(client, owner, "publish_html_page", {"artifact_id": first_id})
    assert pub.status_code == 400, pub.text
    assert (pub.json().get("detail") or {}).get("code") == "publish.edu_channel_required"


def test_unpublished_page_is_404(client) -> None:
    missing = client.get("/p/does-not-exist-page")
    assert missing.status_code == 404
    assert "text/html" in missing.headers.get("content-type", "")
    assert "not available" in missing.text
    assert '{"error":"not_found"}' not in missing.text
    assert client.post("/p/does-not-exist-page/collect", json={"n": "x"}).status_code == 404


def test_legacy_live_page_owner_unpublish_and_cross_account_denied(client) -> None:
    owner = _headers(client, "member-a")
    other = _headers(client, "member-b")
    other_school = _headers(client, "member-a", school_id="school-b")
    created = _invoke(
        client,
        owner,
        "generate_html_document",
        {"title": "page.html", "marker": "mk-legacy", "body": PAGE},
    )
    assert created.status_code == 200, created.text
    artifact_id = created.json()["result"]["artifact_id"]
    page_id = _seed_legacy_live_html_page(
        artifact_id,
        page_id="legacy-live-page-01",
        school_id="school-a",
        membership_id="member-a",
    )

    opened = client.get(f"/p/{page_id}")
    assert opened.status_code == 200, opened.text
    assert "<h1>demo</h1>" in opened.text

    stolen = _invoke(client, other, "unpublish_html_page", {"page_id": page_id})
    assert stolen.status_code == 400, stolen.text
    assert (stolen.json().get("detail") or {}).get("code") == "artifact.not_found"
    foreign = _invoke(client, other_school, "unpublish_html_page", {"page_id": page_id})
    assert foreign.status_code == 400, foreign.text
    assert (foreign.json().get("detail") or {}).get("code") == "artifact.not_found"
    still_live = client.get(f"/p/{page_id}")
    assert still_live.status_code == 200
    assert client.post(f"/p/{page_id}/collect", json={"n": "x"}).status_code == 200

    gone = _invoke(client, owner, "unpublish_html_page", {"page_id": page_id})
    assert gone.status_code == 200, gone.text
    assert gone.json()["result"]["revoked"] is True
    missing = client.get(f"/p/{page_id}")
    assert missing.status_code == 404
    assert "not available" in missing.text
    assert client.post(f"/p/{page_id}/collect", json={"n": "x"}).status_code == 404
