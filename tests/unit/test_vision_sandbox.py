"""T-VISION-SANDBOX: sandbox raster → next /v1/chat/completions images.

Complex path (must pass): write HTML → sandbox_preview_inspect PNG →
text-only next turn reaches ``_run_and_collect(..., images=)``.
Screenshot tool same. Relative ``/images/`` still invents no pixels.
"""

from __future__ import annotations

import base64
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services"))
sys.path.insert(0, str(ROOT / "services" / "api"))
sys.path.insert(0, str(ROOT / "services" / "orchestrator"))

os.environ.setdefault("PICO_JWT_SECRET", "test-secret-at-least-32-bytes-long!!")

from app.main import app
from app.settings import Settings, get_settings
from pico_orchestrator.sandbox_s2 import PNG_MAGIC
from pico_orchestrator.tools_builtin import build_default_gateway
from pico_orchestrator.usage_hook import bind_usage_context, reset_usage_context
from pico_orchestrator.vision import (
    clear_conversation_images,
    conversation_images,
    remember_conversation_png,
)

PNG_B64 = (
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
)
PNG_RAW = base64.b64decode(PNG_B64)
assert PNG_RAW[:8] == PNG_MAGIC

PAGE = """<!DOCTYPE html>
<html><head><title>红点页</title></head>
<body><h1>看见红点</h1><p>复杂任务测</p></body></html>
"""


@dataclass
class P:
    school_id: str
    membership_id: str
    scopes: list[str]


class MemoryArtifactStore:
    def __init__(self, *, run_id: str | None = None) -> None:
        self.rows: dict[tuple[str, str], list[dict[str, Any]]] = {}
        self._run_id = run_id
        self._task_id = "task-vis"

    def _rows(self, principal: P) -> list[dict[str, Any]]:
        return self.rows.setdefault((principal.school_id, principal.membership_id), [])

    async def write(
        self,
        principal: P,
        *,
        title: str,
        content: str | bytes,
        kind: str,
    ) -> dict[str, Any]:
        if isinstance(content, bytes):
            row = {
                "artifact_id": f"art-{sum(map(len, self.rows.values())) + 1}",
                "title": title,
                "content": None,
                "content_base64": base64.b64encode(content).decode("ascii"),
                "kind": kind,
                "run_id": self._run_id,
                "task_id": self._task_id,
                "size": len(content),
                "byte_size": len(content),
                "content_encoding": "base64",
            }
        else:
            row = {
                "artifact_id": f"art-{sum(map(len, self.rows.values())) + 1}",
                "title": title,
                "content": content,
                "kind": kind,
                "run_id": self._run_id,
                "task_id": self._task_id,
                "size": len(content.encode("utf-8")),
                "byte_size": len(content.encode("utf-8")),
                "content_encoding": "utf8",
            }
        self._rows(principal).append(row)
        return {k: v for k, v in row.items() if k not in {"content", "content_base64"}}

    async def read(
        self,
        principal: P,
        *,
        artifact_id: str | None,
        title: str | None,
    ) -> dict[str, Any] | None:
        for row in reversed(self._rows(principal)):
            if artifact_id and row["artifact_id"] == artifact_id:
                return row
            if not artifact_id and title and row["title"] == title:
                return row
        return None

    async def list(self, principal: P, *, limit: int) -> list[dict[str, Any]]:
        return [
            {k: v for k, v in row.items() if k not in {"content", "content_base64"}}
            for row in list(reversed(self._rows(principal)))[:limit]
        ]


def _client() -> TestClient:
    settings = Settings(
        _env_file=None,
        pico_env="test",
        pico_openai_proxy_key="pico-dev",
        pico_allowed_models="pico-fast,pico-deep,pico-agent",
        pico_accept_test_issuer=True,
    )
    app.dependency_overrides[get_settings] = lambda: settings
    return TestClient(app)


def _capture_run(monkeypatch):
    captured: list[dict] = []

    async def fake_ledger(**kwargs):  # type: ignore[no-untyped-def]
        del kwargs
        return "task-vis-1", "run-vis-1"

    async def fake_run_and_collect(*_a, **kwargs):  # type: ignore[no-untyped-def]
        captured.append(kwargs)

        class R:
            status = "succeeded"
            final_text = "看见了沙箱页"
            error = None

        return R()

    async def fake_finalize(*_a, **_k):  # type: ignore[no-untyped-def]
        return None

    monkeypatch.setattr("app.openai_compat._ledger_task_run", fake_ledger)
    monkeypatch.setattr("app.openai_compat._run_and_collect", fake_run_and_collect)
    monkeypatch.setattr("app.openai_compat._finalize_run", fake_finalize)
    return captured


def _ask_what_is_this(conversation_id: str) -> dict:
    return {
        "model": "pico-fast",
        "messages": [{"role": "user", "content": "这是什么"}],
        "stream": False,
    }


@pytest.fixture(autouse=True)
def _clean_pending():
    clear_conversation_images()
    yield
    clear_conversation_images()
    app.dependency_overrides.pop(get_settings, None)


@pytest.mark.asyncio
async def test_html_inspect_then_next_chat_sees_pixels(monkeypatch) -> None:
    """Complex: generate HTML → inspect PNG → next chat images non-empty."""
    store = MemoryArtifactStore(run_id="run-vis")
    gw = build_default_gateway(store)
    owner = P("school-a", "member-a", ["ai:run"])
    tok = bind_usage_context(
        school_id="school-a",
        membership_id="member-a",
        conversation_id="convo-vis-inspect",
    )
    try:
        created = await gw.invoke(
            owner,
            "generate_html_document",
            {"title": "page.html", "marker": "mk-vis", "body": PAGE},
        )
        assert created.get("artifact_id")
        seen = await gw.invoke(
            owner,
            "sandbox_preview_inspect",
            {"artifact_id": created["artifact_id"]},
        )
        assert seen.get("ok") is True
        shot = seen.get("screenshot") or seen.get("raster")
        assert shot and shot.get("mime") == "image/png"
        pending = conversation_images("convo-vis-inspect")
        assert pending, "inspect PNG was not remembered for the conversation"
        assert pending[0]["data"]
        assert base64.b64decode(pending[0]["data"])[:8] == PNG_MAGIC
    finally:
        reset_usage_context(tok)

    captured = _capture_run(monkeypatch)
    client = _client()
    try:
        r = client.post(
            "/v1/chat/completions",
            headers={
                "Authorization": "Bearer pico-dev",
                "X-Pico-Membership-Id": "test-member",
                "X-Conversation-Id": "convo-vis-inspect",
            },
            json=_ask_what_is_this("convo-vis-inspect"),
        )
        assert r.status_code == 200, r.text
        images = (captured[0].get("images") or []) if captured else []
        assert images, "next text-only turn never received inspect pixels"
        assert images[0].get("data")
        assert "看见了沙箱页" in r.json()["choices"][0]["message"]["content"]
    finally:
        app.dependency_overrides.pop(get_settings, None)


@pytest.mark.asyncio
async def test_screenshot_then_next_chat_sees_pixels(monkeypatch) -> None:
    """Complex: browser screenshot PNG → next chat images non-empty."""
    from pico_orchestrator.sandbox_s2 import encode_rgb_png
    from pico_orchestrator.web_guard import parse_public_http_url
    from sandbox_worker.browser import VIEWPORT_HEIGHT, VIEWPORT_WIDTH
    from sandbox_worker.runtime import RUNTIME

    class _FakePage:
        def __init__(self, url: str) -> None:
            parse_public_http_url(url)
            self._url = url

        @property
        def url(self) -> str:
            return self._url

        async def title(self) -> str:
            return "Example Domain"

        async def h1(self) -> str:
            return "Example Domain"

        async def screenshot_png(self) -> bytes:
            rgb = bytes((200, 30, 30)) * (VIEWPORT_WIDTH * VIEWPORT_HEIGHT)
            return encode_rgb_png(VIEWPORT_WIDTH, VIEWPORT_HEIGHT, rgb)

        async def click(self, x: int, y: int) -> None:
            _ = (x, y)

        async def type_text(self, text: str, *, password: bool) -> None:
            _ = (text, password)

        async def close(self) -> None:
            return None

    async def fake_open(url: str):
        return _FakePage(url)

    monkeypatch.setenv("PICO_SANDBOX_URL", "embedded")
    monkeypatch.setattr(RUNTIME, "_open_browser", fake_open)
    RUNTIME._sessions.clear()
    store = MemoryArtifactStore(run_id="run-shot")
    gw = build_default_gateway(store)
    owner = P("school-a", "member-a", ["ai:run"])
    tok = bind_usage_context(
        school_id="school-a",
        membership_id="member-a",
        conversation_id="convo-vis-shot",
    )
    try:
        opened = await gw.invoke(
            owner, "sandbox_browser_open", {"url": "https://example.com/"}
        )
        shot = await gw.invoke(
            owner,
            "sandbox_browser_screenshot",
            {"session_id": opened["session_id"]},
        )
        assert shot["mime"] == "image/png"
        pending = conversation_images("convo-vis-shot")
        assert pending, "screenshot PNG was not remembered"
        assert base64.b64decode(pending[0]["data"])[:8] == PNG_MAGIC
    finally:
        reset_usage_context(tok)
        for sid in list(RUNTIME._sessions):
            await RUNTIME.destroy(sid)
        RUNTIME._sessions.clear()

    captured = _capture_run(monkeypatch)
    client = _client()
    try:
        r = client.post(
            "/v1/chat/completions",
            headers={
                "Authorization": "Bearer pico-dev",
                "X-Pico-Membership-Id": "test-member",
                "X-Conversation-Id": "convo-vis-shot",
            },
            json=_ask_what_is_this("convo-vis-shot"),
        )
        assert r.status_code == 200, r.text
        images = (captured[0].get("images") or []) if captured else []
        assert images, "next text-only turn never received screenshot pixels"
    finally:
        app.dependency_overrides.pop(get_settings, None)


def test_http_remembered_png_reaches_run_and_relative_path_still_empty(
    monkeypatch,
) -> None:
    assert remember_conversation_png(PNG_RAW, conversation_id="convo-vis-http")
    captured = _capture_run(monkeypatch)
    client = _client()
    try:
        r = client.post(
            "/v1/chat/completions",
            headers={
                "Authorization": "Bearer pico-dev",
                "X-Pico-Membership-Id": "test-member",
                "X-Conversation-Id": "convo-vis-http",
            },
            json=_ask_what_is_this("convo-vis-http"),
        )
        assert r.status_code == 200, r.text
        images = (captured[0].get("images") or []) if captured else []
        assert images and images[0]["data"] == PNG_B64

        captured.clear()
        r2 = client.post(
            "/v1/chat/completions",
            headers={
                "Authorization": "Bearer pico-dev",
                "X-Pico-Membership-Id": "test-member",
                "X-Conversation-Id": "convo-other",
            },
            json={
                "model": "pico-fast",
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": "这是什么"},
                            {
                                "type": "image_url",
                                "image_url": {"url": "/images/u1/shot.png"},
                            },
                        ],
                    }
                ],
            },
        )
        assert r2.status_code == 200, r2.text
        other = (captured[0].get("images") or []) if captured else []
        assert other == [], "relative /images/ must not invent pixels or leak convo A"
    finally:
        app.dependency_overrides.pop(get_settings, None)
