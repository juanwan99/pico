"""Fit the pane (#1224): the sandbox page lays out at the pane's own size.

Playwright and Chromium CDP set the viewport and pixel density. The existing
pane-input route carries both values (LibreChat → pico-api → sidecar).
"""

from __future__ import annotations

import asyncio
import base64
import io
import math
import os
import sys
import time
from contextlib import aclosing
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest
from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services"))
sys.path.insert(0, str(ROOT / "services" / "orchestrator"))
sys.path.insert(0, str(ROOT / "services" / "api"))

os.environ.setdefault("PICO_JWT_SECRET", "test-secret-at-least-32-bytes-long!!")

import sandbox_worker.runtime as runtime_mod
from sandbox_worker.browser import VIEWPORT_HEIGHT, VIEWPORT_MAX, VIEWPORT_MIN, VIEWPORT_WIDTH
from sandbox_worker.runtime import RUNTIME, SandboxRuntime, SandboxSession, SandboxWindow
from test_sandbox_live_pane import CastSurface, StillSurface, live_runtime  # noqa: F401


@pytest.mark.asyncio
async def test_failed_tab_fit_falls_back_to_png(
    live_runtime,  # noqa: F811
    tmp_path, monkeypatch,
) -> None:
    from sandbox_worker.browser import PlaywrightPage

    runtime, pages = live_runtime
    meta = await runtime.open_session(
        school_id="school-a", membership_id="member-a", run_id=None, url="https://example.com/"
    )
    sess = runtime.get(meta["session_id"])
    cdp = MagicMock(send=AsyncMock(), detach=AsyncMock())
    page = MagicMock()
    context = MagicMock(pages=[page], new_cdp_session=AsyncMock(return_value=cdp))
    surface = PlaywrightPage(context, page, tmp_path)
    tab = MagicMock()
    tab.is_closed.return_value = False
    fit = AsyncMock(side_effect=RuntimeError("tab fit failed"))
    monkeypatch.setattr(surface, "_apply_metrics", fit)
    monkeypatch.setattr(pages[0], "screencast", surface.screencast)
    surface._viewport = (900, 700)

    surface._use(tab)
    # The failed fit may already be complete by the time a viewer connects.
    await asyncio.wait({surface._viewport_task})
    for _ in range(2):
        async with aclosing(runtime.stream(sess)) as stream:
            assert await asyncio.wait_for(anext(stream), 1) == {
                "poll": True, "window_id": sess.focused_id,
            }
            assert (await runtime.pane_meta(sess))["mime"] == "image/png"
    assert pages[0].shots == 3
    cdp.send.assert_not_awaited()
    fit.assert_awaited_once()

    resizing = asyncio.Event()
    finish_resize = asyncio.Event()

    async def resize_metrics(*_args):
        resizing.set()
        await finish_resize.wait()

    fit.side_effect = resize_metrics
    resize = asyncio.create_task(surface.set_viewport(1000, 700))
    await resizing.wait()
    cast = asyncio.create_task(surface.screencast(MagicMock()))
    await asyncio.sleep(0)
    finish_resize.set()
    await resize
    stop = await cast
    try:
        assert cdp.send.await_args.args[0] == "Page.startScreencast"
    finally:
        await stop()


@pytest.mark.asyncio
async def test_screencast_discards_stale_bitmap_with_new_viewport_metadata(
    tmp_path, monkeypatch,
) -> None:
    from sandbox_worker.browser import PlaywrightPage

    cdp = MagicMock(send=AsyncMock(), detach=AsyncMock())
    page = MagicMock(viewport_size={"width": 480, "height": 620})
    context = MagicMock(pages=[page], new_cdp_session=AsyncMock(return_value=cdp))
    surface = PlaywrightPage(context, page, tmp_path)
    monkeypatch.setattr(surface, "_place_on_screen", AsyncMock())
    await surface.set_viewport(480, 620, 1.5)
    push = MagicMock()
    stop = await surface.screencast(push)
    try:
        on_frame = cdp.on.call_args.args[1]
        for session_id, height in enumerate((450, 930, 930), start=1):
            buf = io.BytesIO()
            with Image.new("RGB", (720, height)) as jpeg:
                jpeg.save(buf, format="JPEG")
            await on_frame({
                "data": base64.b64encode(buf.getvalue()).decode(),
                "sessionId": session_id,
                "metadata": {"deviceWidth": 480, "deviceHeight": 620},
            })
        push.assert_called_once()
        frame = push.call_args.args[0]
        assert (frame.width, frame.height) == (480, 620)
        with Image.open(io.BytesIO(base64.b64decode(frame.jpeg))) as jpeg:
            assert jpeg.size == (720, 930)
        for session_id in (1, 2, 3):
            cdp.send.assert_any_await("Page.screencastFrameAck", {"sessionId": session_id})
    finally:
        await stop()


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


@pytest.fixture()
async def chromium():
    pytest.importorskip("playwright.async_api")
    from playwright.async_api import async_playwright
    from sandbox_worker.browser import CHROMIUM_ARGS

    async with async_playwright() as pw:
        try:
            browser = await pw.chromium.launch(headless=True, args=list(CHROMIUM_ARGS))
        except Exception as exc:  # noqa: BLE001 — environment may lack browser bits
            pytest.skip(f"Chromium unavailable: {exc}")
        try:
            yield browser
        finally:
            await browser.close()


@pytest.mark.asyncio
async def test_real_chromium_page_reflows_new_tabs_follow_frames_match(
    tmp_path, monkeypatch, chromium,
) -> None:
    from sandbox_worker.browser import PlaywrightPage

    context = await chromium.new_context(
        viewport={"width": VIEWPORT_WIDTH, "height": VIEWPORT_HEIGHT}
    )
    page = await context.new_page()
    surface = PlaywrightPage(context, page, tmp_path / "profile")
    try:
        await page.set_content(
            "<style>html{background:navy}#w{display:none}"
            "@media(max-width:600px){html{background:lime}#w{display:block}}"
            "section{position:absolute;top:500px;left:0;width:100%;height:1000px;"
            "background:blue}button{position:absolute;left:30px;top:40px;width:60px;"
            "height:40px;background:red;border:0}</style>"
            "<p id=w>narrow</p><a href='about:blank' target=_blank>tab</a>"
            "<section><button aria-label='visible target' onclick='this.dataset.hit=1'>"
            "</button></section>"
        )
        monkeypatch.setattr(runtime_mod, "STREAM_CHECK_S", 5)
        monkeypatch.setenv("PICO_SANDBOX_DISK", str(tmp_path / "disks"))
        runtime = SandboxRuntime()
        win = SandboxWindow("win_browser", "browser", surface)
        sess = SandboxSession(
            "sbox_fit", "school-a", "member-a", "_norun", "ws", page.url, "", "", b"",
            time.time(), windows=[win], focused_id=win.window_id,
        )
        runtime._sessions[sess.session_id] = sess
        stream = runtime.stream(sess, ack=True)
        first = await asyncio.wait_for(anext(stream), 1)
        await runtime.apply_input(sess, frame_ack=first["frame_id"])
        frame = asyncio.create_task(anext(stream))
        await runtime.apply_input(
            sess, viewport_width=480, viewport_height=620, device_pixel_ratio=1.5,
        )
        assert await page.evaluate("[innerWidth, innerHeight]") == [480, 620]
        assert await page.evaluate("devicePixelRatio") == 1.5
        assert await page.is_visible("#w")  # the site's own narrow layout
        resized = await asyncio.wait_for(frame, 1)
        while resized["width"] != 480:
            await runtime.apply_input(sess, frame_ack=resized["frame_id"])
            resized = await asyncio.wait_for(anext(stream), 1)
        assert resized["height"] == 620
        with Image.open(io.BytesIO(base64.b64decode(resized["jpeg"]))) as jpeg:
            assert jpeg.size == (720, 930)
            red, green, blue = jpeg.getpixel((700, 40))
            assert green > 240 and red < 15 and blue < 15
        await runtime.apply_input(sess, frame_ack=resized["frame_id"])
        assert Image.open(io.BytesIO(await surface.screenshot_png())).size == (480, 620)
        assert await page.evaluate("devicePixelRatio") == 1.5

        await runtime.apply_input(sess, scroll_dy=500)
        await page.wait_for_function("scrollY === 500")
        async with asyncio.timeout(2):
            while True:
                scrolled = await anext(stream)
                await runtime.apply_input(sess, frame_ack=scrolled["frame_id"])
                with Image.open(io.BytesIO(base64.b64decode(scrolled["jpeg"]))) as jpeg:
                    red, green, blue = jpeg.getpixel((90, 90))
                    if red > 235 and green < 20 and blue < 20:
                        assert jpeg.size == (720, 930)
                        assert (scrolled["width"], scrolled["height"]) == (480, 620)
                        break
        assert Image.open(io.BytesIO(await surface.screenshot_png())).getpixel((60, 60)) == (
            255, 0, 0
        )
        await runtime.apply_input(sess, click_x=60, click_y=60)
        assert await page.get_attribute("button", "data-hit") == "1"
        await page.evaluate("scrollTo(0, 0)")

        frame = asyncio.create_task(anext(stream))
        await runtime.apply_input(
            sess, viewport_width=900, viewport_height=700, device_pixel_ratio=1.5,
        )
        async with asyncio.timeout(2):
            resized = await frame
            while True:
                await runtime.apply_input(sess, frame_ack=resized["frame_id"])
                if resized["width"] == 900:
                    break
                resized = await anext(stream)
        assert resized["height"] == 700
        with Image.open(io.BytesIO(base64.b64decode(resized["jpeg"]))) as jpeg:
            assert jpeg.size == (1350, 1050)
            red, green, blue = jpeg.getpixel((1300, 40))
            assert blue > 100 and green < 20 and red < 20
        await stream.aclose()

        assert await surface.set_viewport(10, 99_999) == (VIEWPORT_MIN[0], VIEWPORT_MAX[1])
        await surface.set_viewport(900, 700, 1.5)
        await page.click("a")
        for _ in range(30):
            if surface._page is not page:
                break
            await asyncio.sleep(0.1)
        await asyncio.sleep(0.3)
        assert surface._page is not page
        assert await surface._page.evaluate("[innerWidth, innerHeight]") == [900, 700]
        assert await surface._page.evaluate("devicePixelRatio") == 1.5
    finally:
        await surface.close()


@pytest.mark.asyncio
async def test_real_chromium_png_does_not_change_live_frame_coordinates(tmp_path, chromium) -> None:
    from sandbox_worker.browser import PlaywrightPage

    context = await chromium.new_context(
        viewport={"width": VIEWPORT_WIDTH, "height": VIEWPORT_HEIGHT}
    )
    page = await context.new_page()
    surface = PlaywrightPage(context, page, tmp_path / "profile")
    try:
        await page.set_content(
            "<style>body{height:1500px;background:#000}"
            "button{position:absolute;left:330px;top:800px;width:60px;height:40px;"
            "background:red;border:0}button[data-hit]{background:lime}"
            "i{position:fixed;width:20px;height:20px;background:white;"
            "animation:repaint .5s linear infinite alternate}"
            "@keyframes repaint{to{background:blue}}</style>"
            "<i></i><button onclick='this.dataset.hit=1'></button>"
        )
        await surface.set_viewport(480, 620, 1.5)
        await page.evaluate("scrollTo(0, 500)")
        frames = asyncio.Queue()
        stop = await surface.screencast(frames.put_nowait)
        try:
            first = await asyncio.wait_for(frames.get(), 2)
            assert (first.width, first.height) == (480, 620)
            for _ in range(3):
                with Image.open(io.BytesIO(await surface.screenshot_png())) as png:
                    assert png.size == (480, 620)
                    assert png.getpixel((360, 320)) == (255, 0, 0)
            assert not frames.empty()
            assert await page.evaluate("devicePixelRatio") == 1.5

            clicked = False
            async with asyncio.timeout(3):
                while True:
                    frame = await frames.get()
                    assert (frame.width, frame.height) == (480, 620)
                    with Image.open(io.BytesIO(base64.b64decode(frame.jpeg))) as jpeg:
                        assert jpeg.size == (720, 930)
                        red, green, blue = jpeg.getpixel((540, 480))
                    if not clicked and red > 235 and green < 20 and blue < 20:
                        await surface.click(360, 320, settle=False)
                        clicked = True
                    if clicked and green > 235 and red < 20 and blue < 20:
                        break
            assert await page.get_attribute("button", "data-hit") == "1"
        finally:
            await stop()
    finally:
        await surface.close()


@pytest.mark.asyncio
async def test_real_chromium_screencast_accepts_float32_dpr_rounding(tmp_path, chromium) -> None:
    from sandbox_worker.browser import PlaywrightPage

    context = await chromium.new_context(
        viewport={"width": VIEWPORT_WIDTH, "height": VIEWPORT_HEIGHT}
    )
    page = await context.new_page()
    surface = PlaywrightPage(context, page, tmp_path / "profile")
    dpr = 1.100000023841858
    try:
        await surface.set_viewport(1000, 700, dpr)
        assert await page.evaluate("[innerWidth, innerHeight, devicePixelRatio]") == [
            1000, 700, dpr,
        ]
        frames = asyncio.Queue()
        stop = await surface.screencast(frames.put_nowait)
        try:
            frame = await asyncio.wait_for(frames.get(), 2)
            assert (frame.width, frame.height) == (1000, 700)
            with Image.open(io.BytesIO(base64.b64decode(frame.jpeg))) as jpeg:
                assert jpeg.size == (1100, 770)
        finally:
            await stop()
    finally:
        await surface.close()


@pytest.mark.asyncio
async def test_real_chromium_displays_follow_each_desk_dpr_and_are_removed(tmp_path, chromium) -> None:
    from sandbox_worker.browser import PlaywrightPage

    cdp = await chromium.new_browser_cdp_session()
    original = await cdp.send("Emulation.getScreenInfos")
    desks = []
    try:
        for i in range(2):
            context = await chromium.new_context(
                viewport={"width": VIEWPORT_WIDTH, "height": VIEWPORT_HEIGHT}
            )
            page = await context.new_page()
            desks.append((PlaywrightPage(context, page, tmp_path / f"profile-{i}"), page))
        (left, left_page), (right, right_page) = desks
        await asyncio.gather(
            left.set_viewport(481, 621, 1.5),
            right.set_viewport(481, 621, 2),
        )
        for surface, page, scale in (
            (left, left_page, 1.1),
            (left, left_page, 1.75),
            (left, left_page, 1),
            (right, right_page, 2),
        ):
            await surface.set_viewport(481, 621, scale)
            assert await page.evaluate("devicePixelRatio") == pytest.approx(scale)
            frames = asyncio.Queue()
            stop = await surface.screencast(frames.put_nowait)
            try:
                frame = await asyncio.wait_for(frames.get(), 2)
                assert (frame.width, frame.height) == (481, 621)
                with Image.open(io.BytesIO(base64.b64decode(frame.jpeg))) as jpeg:
                    assert jpeg.size == (math.ceil(481 * scale), math.ceil(621 * scale))
            finally:
                await stop()
    finally:
        for surface, _page in desks:
            await surface.close()
        assert await cdp.send("Emulation.getScreenInfos") == original
        await cdp.detach()


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
        agen = runtime.stream(sess, ack=True)
        first = await asyncio.wait_for(anext(agen), 2)
        ack = {"frame_ack": first["frame_id"]}
        outsider = issue_test_token(school_id="school-a", membership_id="member-b")
        denied = await api.post(path, json=ack, headers={"Authorization": f"Bearer {outsider}"})
        assert denied.status_code >= 400 and first["frame_id"] in sess.frame_acks
        assert (await api.post(path, json=ack, headers=headers)).json() == {"ok": True}
        assert first["frame_id"] not in sess.frame_acks

        runtime.hold(sess, hold=True)
        resize = {"viewport_width": 480, "viewport_height": 620, "device_pixel_ratio": 1.5}
        response = await api.post(path, json=resize, headers=headers)
        assert response.status_code == 200, response.text
        assert response.json() == {
            "ok": True,
            "url": "https://example.com/",
            "title": "Page",
            "has_text_input": False,
            "has_password_input": False,
            "clicked": False,
            "typed": False,
        }
        assert sess.human_hold
        assert page.sizes == [(480, 620, 1.5)] and page.shots == 1
        await agen.aclose()
