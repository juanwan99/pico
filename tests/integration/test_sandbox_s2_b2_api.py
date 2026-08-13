"""Integration: B2 view, cross-account deny, loopback 18765, S1 inspect still works."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services"))
sys.path.insert(0, str(ROOT / "services" / "api"))
sys.path.insert(0, str(ROOT / "services" / "orchestrator"))

from pico_orchestrator.sandbox_view import LOGIN_COPY
from pico_orchestrator.web_guard import parse_public_http_url
from sandbox_worker.browser import VIEWPORT_HEIGHT, VIEWPORT_WIDTH
from sandbox_worker.runtime import RUNTIME

PAGE = """<!DOCTYPE html>
<html><head><title>教案首页</title></head>
<body><h1>第一课</h1></body></html>
"""


class _FakePage:
    def __init__(self, url: str) -> None:
        parse_public_http_url(url)
        self._url = url
        self._title = "Example Domain"
        self._h1 = "Example Domain"
        self._n = 1

    @property
    def url(self) -> str:
        return self._url

    async def title(self) -> str:
        return self._title

    async def h1(self) -> str:
        return self._h1

    async def screenshot_png(self) -> bytes:
        from pico_orchestrator.sandbox_s2 import encode_rgb_png

        rgb = bytes((20 + self._n, 40, 80)) * (VIEWPORT_WIDTH * VIEWPORT_HEIGHT)
        return encode_rgb_png(VIEWPORT_WIDTH, VIEWPORT_HEIGHT, rgb)

    async def click(self, x: int, y: int) -> None:
        _ = (x, y)
        if "example.com" in self._url:
            self._url = "https://www.iana.org/help/example-domains"
            self._title = "Example Domains"
            self._h1 = "Example domains"
            self._n += 1

    async def type_text(self, text: str, *, password: bool) -> None:
        _ = (text, password)
        self._n += 1

    async def close(self) -> None:
        return None


@pytest.fixture()
def client(tmp_path, monkeypatch):
    database = tmp_path / "sandbox-s2.db"
    monkeypatch.setenv("PICO_DATABASE_URL", f"sqlite+aiosqlite:///{database}")
    monkeypatch.setenv("PICO_JWT_SECRET", "test-secret-at-least-32-bytes-long!!")
    monkeypatch.setenv("PICO_ENV", "development")
    monkeypatch.setenv("PICO_SANDBOX_ROOT", str(tmp_path / "sandbox-root"))
    monkeypatch.setenv("PICO_SANDBOX_URL", "embedded")

    async def fake_open(url: str):
        return _FakePage(url)

    monkeypatch.setattr(RUNTIME, "_open_browser", fake_open)
    RUNTIME._sessions.clear()

    from app import db as dbmod
    from app.main import app
    from app.settings import get_settings

    get_settings.cache_clear()
    dbmod._engine = None
    dbmod._Session = None
    with TestClient(app) as test_client:
        yield test_client
    RUNTIME._sessions.clear()


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


def test_b2_view_and_cross_account_and_loopback(client) -> None:
    owner = _headers(client, "member-a")
    outsider = _headers(client, "member-b")

    opened = _invoke(
        client, owner, "sandbox_browser_open", {"url": "https://example.com/"}
    )
    assert opened.status_code == 200, opened.text
    result = opened.json()["result"]
    session_id = result["session_id"]
    assert LOGIN_COPY in result["human_copy"]
    assert result["engine"] == "playwright-chromium"
    assert result["view_path"] == f"/v1/sandbox/sessions/{session_id}/view"

    view = client.get(f"/v1/sandbox/sessions/{session_id}/view", headers=owner)
    assert view.status_code == 200, view.text
    assert "text/html" in view.headers.get("content-type", "")
    assert LOGIN_COPY in view.text
    assert "不要在聊天里发送密码" in view.text
    assert "Chromium" in view.text

    png = client.get(f"/v1/sandbox/sessions/{session_id}/screenshot", headers=owner)
    assert png.status_code == 200
    assert png.content[:8] == b"\x89PNG\r\n\x1a\n"
    import struct

    width, height = struct.unpack(">II", png.content[16:24])
    assert (width, height) == (VIEWPORT_WIDTH, VIEWPORT_HEIGHT)
    assert (width, height) != (720, 400)

    assert (
        client.get(f"/v1/sandbox/sessions/{session_id}/view", headers=outsider).status_code
        == 404
    )
    assert (
        client.get(
            f"/v1/sandbox/sessions/{session_id}/screenshot", headers=outsider
        ).status_code
        == 404
    )

    meta = client.get(f"/v1/sandbox/sessions/{session_id}", headers=owner)
    assert meta.status_code == 200, meta.text
    body = meta.json()
    assert body["session_id"] == session_id
    assert "example.com" in body["url"]
    assert "password" not in body
    assert "secret" not in body

    assert (
        client.get(f"/v1/sandbox/sessions/{session_id}", headers=outsider).status_code
        == 404
    )

    typed = client.post(
        f"/v1/sandbox/sessions/{session_id}/input",
        headers={**owner, "Accept": "application/json"},
        json={"secret": "do-not-log-this-password", "click_x": 10, "click_y": 20},
    )
    assert typed.status_code == 200, typed.text
    assert "do-not-log-this-password" not in typed.text
    typed_body = typed.json()
    assert "iana.org" in typed_body["url"]
    assert "password" not in typed_body
    assert "secret" not in typed_body

    sess = RUNTIME.get(session_id)
    assert sess is not None
    assert "iana.org" in sess.url

    loopback = _invoke(
        client,
        owner,
        "sandbox_browser_open",
        {"url": "http://127.0.0.1:18765/health"},
    )
    assert loopback.status_code == 400
    assert loopback.json()["detail"]["code"] == "web.denied"

    admin = _invoke(
        client,
        owner,
        "sandbox_browser_open",
        {"url": "https://pico.aivia.asia/login"},
    )
    assert admin.status_code == 400
    assert admin.json()["detail"]["code"] == "web.denied"

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
        assert extra.get("workspace_id") or extra.get("session_id") or extra.get(
            "artifact_id"
        )


def test_s1_inspect_still_works_on_own_html(client) -> None:
    owner = _headers(client, "member-a")
    created = _invoke(
        client,
        owner,
        "generate_html_document",
        {"title": "lesson.html", "marker": "mk-s2", "body": PAGE},
    )
    assert created.status_code == 200, created.text
    artifact_id = created.json()["result"]["artifact_id"]
    seen = _invoke(client, owner, "sandbox_preview_inspect", {"artifact_id": artifact_id})
    assert seen.status_code == 200, seen.text
    payload = seen.json()["result"]
    assert payload["title"] == "教案首页"
    assert payload["h1"] == "第一课"
    shot = payload.get("screenshot") or payload.get("raster")
    assert shot and shot.get("mime") == "image/png"
