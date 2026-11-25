"""Fit the pane (#1224): the sandbox page lays out at the pane's own size.

Upstream = Playwright ``page.set_viewport_size``. Pico only carries the pane
size along the existing pane-input route (LibreChat → pico-api → sidecar).
"""

from __future__ import annotations

import asyncio
import base64
import io
import os
import sys
import time
from pathlib import Path
from typing import Any

import httpx
import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services"))
sys.path.insert(0, str(ROOT / "services" / "orchestrator"))
sys.path.insert(0, str(ROOT / "services" / "api"))

os.environ.setdefault("PICO_JWT_SECRET", "test-secret-at-least-32-bytes-long!!")

import sandbox_worker.runtime as runtime_mod
from sandbox_worker.browser import VIEWPORT_HEIGHT, VIEWPORT_MAX, VIEWPORT_MIN, VIEWPORT_WIDTH
from sandbox_worker.runtime import RUNTIME, SandboxRuntime, SandboxSession, SandboxWindow
from test_sandbox_live_pane import CastSurface, StillSurface, live_runtime  # noqa: F401


class FitSurface(CastSurface):
    def __init__(self, url: str, login_state: Any = None) -> None:
        super().__init__(url, login_state)
        self.sizes: list[tuple[int, int, float]] = []

    async def set_viewport(self, width: int, height: int, dpr: float = 1.0) -> tuple[int, int]:
        self.sizes.append((width, height, dpr))
        return width, height


@pytest.mark.asyncio
async def test_pane_size_reaches_the_browser_window_only(live_runtime, monkeypatch) -> None:  # noqa: F811
    runtime, _ = live_runtime
    pages: list[FitSurface] = []

    async def fake_open(url: str, **_kw: Any) -> FitSurface:
        pages.append(FitSurface(url))
        return pages[-1]

    monkeypatch.setattr(RUNTIME, "_open_browser", fake_open)
    meta = await runtime.open_session(
        school_id="school-a", membership_id="member-a", run_id=None, url="https://example.com/"
    )
    sess = runtime.get(meta["session_id"])
    out = await runtime.apply_input(
        sess, viewport_width=480, viewport_height=620, device_pixel_ratio=1.5,
    )
    assert pages[0].sizes == [(480, 620, 1.5)]
    assert out["clicked"] is False and out["typed"] is False
    # Half a size is ignored; an office window has no viewport to set.
    await runtime.apply_input(sess, viewport_width=480)
    sess.windows.append(SandboxWindow(window_id="win_office", kind="writer", surface=StillSurface()))
    sess.focused_id = "win_office"
    await runtime.apply_input(sess, viewport_width=900, viewport_height=700)
    assert pages[0].sizes == [(480, 620, 1.5)]


@pytest.mark.asyncio
async def test_real_chromium_page_reflows_new_tabs_follow_frames_match(tmp_path, monkeypatch) -> None:
    pytest.importorskip("playwright.async_api")
    from playwright.async_api import async_playwright
    from sandbox_worker.browser import CHROMIUM_ARGS, PlaywrightPage

    try:
        pw = await async_playwright().start()
        browser = await pw.chromium.launch(headless=True, args=list(CHROMIUM_ARGS))
    except Exception as exc:  # noqa: BLE001 — environment may lack browser bits
        pytest.skip(f"Chromium unavailable: {exc}")
    try:
        context = await browser.new_context(
            viewport={"width": VIEWPORT_WIDTH, "height": VIEWPORT_HEIGHT}
        )
        page = await context.new_page()
        await page.set_content(
            "<style>#w{display:none}@media(max-width:600px){#w{display:block}}</style>"
            "<p id=w>narrow</p><a href='about:blank' target=_blank>tab</a>"
        )
        surface = PlaywrightPage(context, page, tmp_path / "profile")
        monkeypatch.setattr(runtime_mod, "STREAM_CHECK_S", 5)
        monkeypatch.setenv("PICO_SANDBOX_DISK", str(tmp_path / "disks"))
        runtime = SandboxRuntime()
        win = SandboxWindow("win_browser", "browser", surface)
        sess = SandboxSession(
            "sbox_fit", "school-a", "member-a", "_norun", "ws", page.url, "", "", b"",
            time.time(), windows=[win], focused_id=win.window_id,
        )
        runtime._sessions[sess.session_id] = sess
        stream = runtime.stream(sess)
        first = await asyncio.wait_for(anext(stream), 1)
        await runtime.apply_input(sess, frame_ack=first["frame_id"])
        frame = asyncio.create_task(anext(stream))
        await runtime.apply_input(
            sess, viewport_width=480, viewport_height=620, device_pixel_ratio=1.5,
        )
        assert page.viewport_size == {"width": 480, "height": 620}
        assert await page.evaluate("innerWidth") == 480
        assert await page.evaluate("devicePixelRatio") == 1.5
        assert await page.is_visible("#w")  # the site's own narrow layout
        from PIL import Image

        resized = await asyncio.wait_for(frame, 1)
        while resized["width"] != 480:
            await runtime.apply_input(sess, frame_ack=resized["frame_id"])
            resized = await asyncio.wait_for(anext(stream), 1)
        assert resized["height"] == 620
        assert Image.open(io.BytesIO(base64.b64decode(resized["jpeg"]))).size == (720, 930)
        await stream.aclose()
        assert Image.open(io.BytesIO(await surface.screenshot_png())).size == (480, 620)

        assert await surface.set_viewport(10, 99_999) == (VIEWPORT_MIN[0], VIEWPORT_MAX[1])
        await surface.set_viewport(900, 700, 1.5)
        await page.click("a")
        for _ in range(30):
            if surface._page is not page:
                break
            await asyncio.sleep(0.1)
        await asyncio.sleep(0.3)
        assert surface._page is not page
        assert surface._page.viewport_size == {"width": 900, "height": 700}
        assert await surface._page.evaluate("devicePixelRatio") == 1.5
    finally:
        await browser.close()
        await pw.stop()


@pytest.mark.asyncio
async def test_api_relays_dpr_and_frame_ack_to_worker(live_runtime, monkeypatch) -> None:  # noqa: F811
    from app.auth import issue_test_token
    from app.main import app
    from pico_orchestrator import sandbox_sidecar
    from sandbox_worker.app import app as worker_app

    runtime, _pages = live_runtime
    page = FitSurface("https://example.com/")

    async def fake_open(_url, **_kw):
        return page

    monkeypatch.setattr(runtime, "_open_browser", fake_open)
    monkeypatch.setenv("PICO_SANDBOX_TOKEN", "local-test-only")
    meta = await runtime.open_session(
        school_id="school-a", membership_id="member-a", run_id=None, url="https://example.com/"
    )
    sess = runtime.get(meta["session_id"])

    async with (
        httpx.AsyncClient(
            transport=httpx.ASGITransport(app=worker_app), base_url="http://worker"
        ) as worker,
        httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://api") as api,
    ):
        async def forward(method, path, *, json_body):
            response = await worker.request(
                method, path, json=json_body, headers={"X-Pico-Sandbox-Token": "local-test-only"},
            )
            if not response.is_success:
                sandbox_sidecar._raise_detail(response)
            return response.json()

        monkeypatch.setattr(sandbox_sidecar, "sidecar_json", forward)
        path = f"/v1/sandbox/sessions/{sess.session_id}/input"
        token = issue_test_token(school_id="school-a", membership_id="member-a")
        headers = {"Authorization": f"Bearer {token}"}
        agen = runtime.stream(sess)
        first = await asyncio.wait_for(anext(agen), 2)
        ack = {"frame_ack": first["frame_id"]}
        outsider = issue_test_token(school_id="school-a", membership_id="member-b")
        denied = await api.post(path, json=ack, headers={"Authorization": f"Bearer {outsider}"})
        assert denied.status_code >= 400 and page.acks == []
        assert (await api.post(path, json=ack, headers=headers)).json() == {"ok": True}
        assert page.acks == ["FIRST"]

        resize = {"viewport_width": 480, "viewport_height": 620, "device_pixel_ratio": 1.5}
        response = await api.post(path, json=resize, headers=headers)
        assert response.status_code == 200, response.text
        assert page.sizes == [(480, 620, 1.5)] and page.shots == 1
        await agen.aclose()
