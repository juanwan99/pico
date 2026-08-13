"""Integration: sandbox isolation, preview 404 for other accounts, usage emit."""

from __future__ import annotations

import sys
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "api"))
sys.path.insert(0, str(ROOT / "services" / "orchestrator"))

from app.main import app

PAGE = """<!DOCTYPE html>
<html><head><title>教案首页</title></head>
<body><h1>第一课</h1><button>go</button></body></html>
"""


@pytest.fixture()
def client(tmp_path, monkeypatch):
    database = tmp_path / "sandbox-s1.db"
    monkeypatch.setenv("PICO_DATABASE_URL", f"sqlite+aiosqlite:///{database}")
    monkeypatch.setenv("PICO_JWT_SECRET", "test-secret-at-least-32-bytes-long!!")
    monkeypatch.setenv("PICO_ENV", "development")
    monkeypatch.setenv("PICO_SANDBOX_ROOT", str(tmp_path / "sandbox-root"))

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


def test_html_preview_is_404_for_other_account_and_inspect_sees_page(client) -> None:
    owner = _headers(client, "member-a")
    outsider = _headers(client, "member-b")
    other_school = _headers(client, "member-a", school_id="school-b")

    created = _invoke(
        client,
        owner,
        "generate_html_document",
        {"title": "lesson.html", "marker": "mk-s1", "body": PAGE},
    )
    assert created.status_code == 200, created.text
    result = created.json()["result"]
    artifact_id = result["artifact_id"]
    preview_url = result["preview_url"]
    assert result["preview_path"] == f"/v1/artifacts/{artifact_id}/content"

    owner_open = client.get(f"/v1/artifacts/{artifact_id}/content", headers=owner)
    assert owner_open.status_code == 200
    parsed = urlparse(preview_url)
    qs = parse_qs(parsed.query)
    preview_get = client.get(
        f"/v1/artifacts/{artifact_id}/content",
        headers=owner,
        params={"preview": "1", "exp": qs.get("exp", [""])[0], "sig": qs.get("sig", [""])[0]},
    )
    assert preview_get.status_code == 200
    assert "text/html" in preview_get.headers.get("content-type", "")
    assert "教案首页" in preview_get.text

    assert client.get(f"/v1/artifacts/{artifact_id}/content", headers=outsider).status_code == 404
    assert client.get(
        f"/v1/artifacts/{artifact_id}/content",
        headers=outsider,
        params={"preview": "1", "exp": qs.get("exp", [""])[0], "sig": qs.get("sig", [""])[0]},
    ).status_code == 404
    assert client.get(f"/v1/artifacts/{artifact_id}/content", headers=other_school).status_code == 404

    seen = _invoke(
        client,
        owner,
        "sandbox_preview_inspect",
        {"artifact_id": artifact_id},
    )
    assert seen.status_code == 200, seen.text
    payload = seen.json()["result"]
    assert payload["title"] == "教案首页"
    assert payload["h1"] == "第一课"
    assert payload["seen"] is True
    shot = payload.get("screenshot") or payload.get("raster")
    assert isinstance(shot, dict)
    assert shot.get("mime") == "image/png"
    assert int(shot.get("byte_size") or 0) > 64
    shot_id = shot.get("artifact_id")
    assert shot_id
    png_get = client.get(f"/v1/artifacts/{shot_id}/content", headers=owner)
    assert png_get.status_code == 200, png_get.text
    assert png_get.content[:8] == b"\x89PNG\r\n\x1a\n"
    assert client.get(f"/v1/artifacts/{shot_id}/content", headers=outsider).status_code == 404

    denied = _invoke(
        client,
        outsider,
        "sandbox_preview_inspect",
        {"artifact_id": artifact_id},
    )
    assert denied.status_code == 400
    assert denied.json()["detail"]["code"] == "artifact.not_found"

    loopback = _invoke(
        client,
        owner,
        "sandbox_preview_inspect",
        {"preview_url": "http://127.0.0.1:18765/health"},
    )
    assert loopback.status_code == 400
    assert loopback.json()["detail"]["code"] == "web.denied"

    usage = client.get("/v1/usage/events", headers=owner, params={"kind": "sandbox"})
    assert usage.status_code == 200, usage.text
    events = usage.json()["events"]
    assert events
    for event in events:
        assert event["kind"] == "sandbox"
        assert event["billing"] is False
        extra = event.get("extra") or {}
        for banned in ("price", "currency", "cost", "charge", "amount", "billing"):
            assert banned not in extra
        assert extra.get("artifact_id") or extra.get("workspace_id")


def test_cross_school_workspace_read_denied(client) -> None:
    owner = _headers(client, "member-a", school_id="school-a")
    other = _headers(client, "member-a", school_id="school-b")
    created = _invoke(
        client,
        owner,
        "workspace_write_file",
        {"title": "note.md", "content": "only-a", "kind": "file"},
    )
    assert created.status_code == 200, created.text
    artifact_id = created.json()["result"]["artifact_id"]
    denied = _invoke(
        client, other, "workspace_read_file", {"artifact_id": artifact_id}
    )
    assert denied.status_code == 400
    assert denied.json()["detail"]["code"] == "artifact.not_found"
    assert client.get(f"/v1/artifacts/{artifact_id}/content", headers=other).status_code == 404
