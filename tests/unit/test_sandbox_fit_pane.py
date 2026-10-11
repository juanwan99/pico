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
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services"))
sys.path.insert(0, str(ROOT / "services" / "orchestrator"))
sys.path.insert(0, str(ROOT / "services" / "api"))

os.environ.setdefault("PICO_JWT_SECRET", "test-secret-at-least-32-bytes-long!!")

from sandbox_worker.browser import VIEWPORT_HEIGHT, VIEWPORT_MAX, VIEWPORT_MIN, VIEWPORT_WIDTH
from sandbox_worker.runtime import RUNTIME, SandboxWindow
from test_sandbox_live_pane import CastSurface, StillSurface, live_runtime  # noqa: F401


class FitSurface(CastSurface):
    def __init__(self, url: str, login_state: Any = None) -> None:
        super().__init__(url, login_state)
        self.sizes: list[tuple[int, int]] = []

    async def set_viewport(self, width: int, height: int) -> tuple[int, int]:
        self.sizes.append((width, height))
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
    out = await runtime.apply_input(sess, viewport_width=480, viewport_height=620)
    assert pages[0].sizes == [(480, 620)]
    assert out["clicked"] is False and out["typed"] is False
    # Half a size is ignored; an office window has no viewport to set.
    await runtime.apply_input(sess, viewport_width=480)
    sess.windows.append(SandboxWindow(window_id="win_office", kind="writer", surface=StillSurface()))
    sess.focused_id = "win_office"
    await runtime.apply_input(sess, viewport_width=900, viewport_height=700)
    assert pages[0].sizes == [(480, 620)]


@pytest.mark.asyncio
async def test_real_chromium_page_reflows_new_tabs_follow_frames_match(tmp_path) -> None:
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
        frames: list[str] = []
        stop = await surface.screencast(frames.append)

        assert await surface.set_viewport(480, 620) == (480, 620)
        assert page.viewport_size == {"width": 480, "height": 620}
        assert await page.evaluate("innerWidth") == 480
        assert await page.is_visible("#w")  # the site's own narrow layout
        from PIL import Image

        def last_size() -> tuple[int, int] | None:
            return Image.open(io.BytesIO(base64.b64decode(frames[-1]))).size if frames else None

        for n in range(50):  # a still page sends nothing: repaint until a frame lands
            await page.evaluate("t => document.getElementById('w').textContent = t", f"narrow {n}")
            if last_size() == (480, 620):
                break
            await asyncio.sleep(0.1)
        await stop()
        assert last_size() == (480, 620)  # pane clicks map 1:1 onto the page

        assert await surface.set_viewport(10, 99_999) == (VIEWPORT_MIN[0], VIEWPORT_MAX[1])
        await surface.set_viewport(900, 700)
        await page.click("a")
        for _ in range(30):
            if surface.page_token:
                break
            await asyncio.sleep(0.1)
        await asyncio.sleep(0.3)
        assert surface._page is not page
        assert surface._page.viewport_size == {"width": 900, "height": 700}
    finally:
        await browser.close()
        await pw.stop()
