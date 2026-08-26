"""T-HTML-PUBLIC: public GET + collect lands on publisher archive."""

from __future__ import annotations

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


def test_publish_collect_unpublish_and_cross_account(client) -> None:
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

    pub = _invoke(client, owner, "publish_html_page", {"artifact_id": artifact_id})
    assert pub.status_code == 200, pub.text
    page_id = pub.json()["result"]["page_id"]
    assert page_id
    assert "/p/" in pub.json()["result"]["public_url"]

    opened = client.get(f"/p/{page_id}")
    assert opened.status_code == 200
    assert "text/html" in opened.headers.get("content-type", "")
    assert "__PICO_COLLECT__" in opened.text
    assert "form-action 'self'" in opened.headers.get("content-security-policy", "")

    posted = client.post(f"/p/{page_id}/collect", json={"n": "alice"})
    assert posted.status_code == 200, posted.text
    entry_id = posted.json()["id"]

    listed = client.get("/v1/artifacts?mine=true", headers=owner)
    assert listed.status_code == 200, listed.text
    titles = {row.get("title") for row in listed.json().get("artifacts", [])}
    kinds = {row.get("kind") for row in listed.json().get("artifacts", [])}
    assert any(str(t).startswith("entry-") for t in titles)
    assert "form_entry" in kinds

    assert client.get("/v1/artifacts?mine=true").status_code in {401, 403}

    other_list = client.get("/v1/artifacts?mine=true", headers=other)
    assert other_list.status_code == 200
    other_ids = {row.get("id") for row in other_list.json().get("artifacts", [])}
    assert entry_id not in other_ids

    stolen = _invoke(client, other, "publish_html_page", {"artifact_id": artifact_id})
    assert stolen.status_code == 400
    stolen_un = _invoke(client, other, "unpublish_html_page", {"page_id": page_id})
    assert stolen_un.status_code == 400

    other_html = _invoke(
        client,
        other,
        "generate_html_document",
        {"title": "other.html", "marker": "mk-other", "body": PAGE},
    )
    assert other_html.status_code == 200, other_html.text
    other_pub = _invoke(
        client,
        other,
        "publish_html_page",
        {"artifact_id": other_html.json()["result"]["artifact_id"]},
    )
    assert other_pub.status_code == 200, other_pub.text
    other_page = other_pub.json()["result"]["page_id"]
    other_post = client.post(f"/p/{other_page}/collect", json={"n": "bob"})
    assert other_post.status_code == 200, other_post.text
    owner_after = client.get("/v1/artifacts?mine=true", headers=owner)
    owner_ids = {row.get("id") for row in owner_after.json().get("artifacts", [])}
    assert other_post.json()["id"] not in owner_ids

    gone = _invoke(client, owner, "unpublish_html_page", {"page_id": page_id})
    assert gone.status_code == 200, gone.text
    assert client.get(f"/p/{page_id}").status_code == 404
    assert client.post(f"/p/{page_id}/collect", json={"n": "x"}).status_code == 404


def test_unpublished_page_is_404(client) -> None:
    assert client.get("/p/does-not-exist-page").status_code == 404
    assert client.post("/p/does-not-exist-page/collect", json={"n": "x"}).status_code == 404
