"""Live pane (#1215): Chromium pushes JPEG frames on repaint (CDP screencast).

Upstream = Chromium `Page.startScreencast` through Playwright 1.52
`new_cdp_session` — the same mechanism Steel / browserless live view use.
Pico only wires sidecar → pico-api → LibreChat → pane. Office / files windows
keep polling the PNG.
"""

from __future__ import annotations

import asyncio
import json
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

import sandbox_worker.runtime as runtime_mod
from pico_orchestrator.gateway import ToolError
from pico_orchestrator.sandbox_s2 import encode_rgb_png
from pico_orchestrator.sandbox_sidecar import sidecar_stream
from pico_orchestrator.web_guard import parse_public_http_url
from sandbox_worker.browser import HUMAN_KEYS, VIEWPORT_HEIGHT, VIEWPORT_WIDTH
from sandbox_worker.runtime import RUNTIME, SandboxWindow, sse_event


def _png() -> bytes:
    rgb = bytes((240, 240, 240)) * (VIEWPORT_WIDTH * VIEWPORT_HEIGHT)
    return encode_rgb_png(VIEWPORT_WIDTH, VIEWPORT_HEIGHT, rgb)


class StillSurface:
    """A window with no screencast (office / files)."""

    def __init__(self, url: str = "https://example.com/") -> None:
        self._url = url
        self.scrolled: list[int] = []
        self.keys: list[str] = []

    @property
    def url(self) -> str:
        return self._url

    async def title(self) -> str:
        return "Page"

    async def h1(self) -> str:
        return ""

    async def screenshot_png(self) -> bytes:
        return _png()

    async def click(self, x: int, y: int) -> None:
        _ = (x, y)

    async def type_text(self, text: str, *, password: bool) -> None:
        _ = (text, password)

    async def close(self) -> None:
        return None


class CastSurface(StillSurface):
    """Browser window stand-in: `screencast(push)` like PlaywrightPage."""

    def __init__(self, url: str, login_state: Any = None) -> None:
        parse_public_http_url(url)
        super().__init__(url)
        _ = login_state
        self.push = None
        self.casting = 0
        self.stops = 0

    async def screencast(self, push):
        self.push = push
        self.casting += 1
        push("FIRST")

        async def stop() -> None:
            self.stops += 1

        return stop

    async def scroll(self, dy: int) -> None:
        self.scrolled.append(dy)

    async def press_human_key(self, key: str) -> None:
        if key not in HUMAN_KEYS:
            raise ToolError("tool.invalid_arguments", "bad key")
        self.keys.append(key)


@pytest.fixture
async def live_runtime(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    monkeypatch.setenv("PICO_SANDBOX_URL", "embedded")
    monkeypatch.setenv("PICO_SANDBOX_DISK", str(tmp_path / "disks"))
    monkeypatch.setattr(runtime_mod, "STREAM_CHECK_S", 0.05)
    monkeypatch.setattr(runtime_mod, "STREAM_PING_S", 0.2)
    pages: list[CastSurface] = []

    async def fake_open(url: str, **_kw: Any) -> CastSurface:
        page = CastSurface(url)
        pages.append(page)
        return page

    monkeypatch.setattr(RUNTIME, "_open_browser", fake_open)
    RUNTIME._sessions.clear()
    yield RUNTIME, pages
    for sid in list(RUNTIME._sessions):
        await RUNTIME.destroy(sid)
    RUNTIME._sessions.clear()


async def _open(runtime) -> Any:
    meta = await runtime.open_session(
        school_id="school-a", membership_id="member-a", run_id=None, url="https://example.com/"
    )
    return runtime.get(meta["session_id"])


async def _next(agen) -> dict[str, Any]:
    return await asyncio.wait_for(agen.__anext__(), 2.0)


def test_sse_event_is_one_data_line() -> None:
    assert sse_event({"jpeg": "AAA"}) == b'data: {"jpeg":"AAA"}\n\n'


@pytest.mark.asyncio
async def test_frames_flow_and_stream_ends_when_sandbox_is_destroyed(live_runtime) -> None:
    runtime, pages = live_runtime
    sess = await _open(runtime)
    agen = runtime.stream(sess)
    first = await _next(agen)
    assert first == {"jpeg": "FIRST", "window_id": sess.focused_id or sess.windows[0].window_id}
    pages[0].push("NEXT")
    assert (await _next(agen))["jpeg"] == "NEXT"
    # A still page sends nothing but a keep-alive ping.
    assert await _next(agen) == {"ping": True}
    await runtime.destroy(sess.session_id)
    with pytest.raises(StopAsyncIteration):
        await _next(agen)
    assert pages[0].stops == 1


@pytest.mark.asyncio
async def test_slow_viewer_gets_latest_frame_not_a_backlog(live_runtime) -> None:
    runtime, pages = live_runtime
    sess = await _open(runtime)
    agen = runtime.stream(sess)
    await _next(agen)
    for n in range(5):
        pages[0].push(f"F{n}")
    assert (await _next(agen))["jpeg"] == "F4"
    await agen.aclose()
    assert pages[0].stops == 1


@pytest.mark.asyncio
async def test_office_window_says_poll_and_switching_back_restarts_cast(live_runtime) -> None:
    runtime, pages = live_runtime
    sess = await _open(runtime)
    browser_id = sess.windows[0].window_id
    sess.windows.append(SandboxWindow(window_id="win_office", kind="writer", surface=StillSurface()))
    sess.focused_id = "win_office"
    agen = runtime.stream(sess)
    assert await _next(agen) == {"poll": True, "window_id": "win_office"}
    sess.focused_id = browser_id
    assert (await _next(agen))["jpeg"] == "FIRST"
    assert pages[0].casting == 1
    await agen.aclose()


@pytest.mark.asyncio
async def test_pane_wheel_and_keys_reach_the_page(live_runtime) -> None:
    runtime, pages = live_runtime
    sess = await _open(runtime)
    await runtime.apply_input(sess, scroll_dy=600)
    await runtime.apply_input(sess, key="Enter")
    assert pages[0].scrolled == [600]
    assert pages[0].keys == ["Enter"]
    with pytest.raises(ToolError):
        await runtime.apply_input(sess, key="Control+A")


@pytest.mark.asyncio
async def test_api_stream_helper_checks_owner_then_streams(live_runtime) -> None:
    runtime, _pages = live_runtime
    sess = await _open(runtime)
    path = f"/v1/internal/sessions/{sess.session_id}/stream"
    with pytest.raises(ToolError) as denied:
        await sidecar_stream(path, params={"school_id": "school-b", "membership_id": "member-b"})
    assert denied.value.code == "sandbox.forbidden"
    chunks = await sidecar_stream(
        path, params={"school_id": "school-a", "membership_id": "member-a"}
    )
    first = await asyncio.wait_for(chunks.__anext__(), 2.0)
    assert json.loads(first.decode()[len("data: ") :])["jpeg"] == "FIRST"
    await chunks.aclose()


# ---------------------------------------------------------------- real Chromium


@pytest.mark.asyncio
async def test_real_chromium_pushes_frames_on_change_and_none_when_still() -> None:
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
            "<div style='height:3000px'><input id=q><p id=c>0</p></div>"
            "<script>let n=0;const t=setInterval(()=>{c.textContent=++n;if(n>8)clearInterval(t)},100)"
            "</script>"
        )
        surface = PlaywrightPage(context, page, Path("/tmp/unused-profile"))
        frames: list[str] = []
        stop = await surface.screencast(frames.append)
        await asyncio.sleep(1.5)
        moving = len(frames)
        await asyncio.sleep(1.0)
        still = len(frames) - moving
        await surface.scroll(800)
        await asyncio.sleep(0.5)
        scroll_y = await page.evaluate("window.scrollY")
        await page.focus("#q")
        await surface.press_human_key("Tab")
        with pytest.raises(ToolError):
            await surface.press_human_key("Control+A")
        await stop()
        assert moving >= 3
        assert still <= 1
        assert len(frames) > moving + still  # scrolling repainted
        assert frames[0].startswith("/9j/")  # base64 JPEG
        assert scroll_y >= 700
    finally:
        await browser.close()
        await pw.stop()
