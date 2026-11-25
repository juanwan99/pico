"""Live pane (#1215): Chromium pushes JPEG frames on repaint (CDP screencast).

Upstream = Chromium `Page.startScreencast` through Playwright `new_cdp_session`,
the same mechanism Steel / browserless live view use.
Pico only wires sidecar → pico-api → LibreChat → pane. Office / files windows
keep polling the PNG.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import threading
import time
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
from sandbox_worker.browser import HUMAN_KEYS, VIEWPORT_HEIGHT, VIEWPORT_WIDTH, ScreencastFrame
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
        self.shots = 0

    @property
    def url(self) -> str:
        return self._url

    async def title(self) -> str:
        return "Page"

    async def h1(self) -> str:
        return ""

    async def screenshot_png(self) -> bytes:
        self.shots += 1
        return _png()

    async def click(self, x: int, y: int, *, settle: bool = True) -> None:
        self.click_settled = settle

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
        self.saves = 0

    def frame(self, jpeg: str) -> None:
        self.push(ScreencastFrame(jpeg, VIEWPORT_WIDTH, VIEWPORT_HEIGHT))

    async def screencast(self, push):
        self.push = push
        self.casting += 1
        self.frame("FIRST")

        async def stop() -> None:
            self.stops += 1

        return stop

    async def save_login(self, _path: Path) -> None:
        self.saves += 1

    async def scroll(self, dy: int) -> None:
        self.scrolled.append(dy)

    async def press_human_key(self, key: str, *, settle: bool = True) -> None:
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
    agen = runtime.stream(sess, ack=True)
    first = await _next(agen)
    assert first["jpeg"] == "FIRST" and first["window_id"] == sess.focused_id
    await runtime.apply_input(sess, frame_ack=first["frame_id"])
    pages[0].frame("NEXT")
    second = await _next(agen)
    assert second["jpeg"] == "NEXT"
    await runtime.apply_input(sess, frame_ack=second["frame_id"])
    # A still page sends nothing but a keep-alive ping.
    assert await _next(agen) == {"ping": True}
    await runtime.destroy(sess.session_id)
    with pytest.raises(StopAsyncIteration):
        await _next(agen)
    assert pages[0].stops == 1


@pytest.mark.asyncio
async def test_slow_viewer_receives_final_frame_after_page_stops_repainting(live_runtime) -> None:
    runtime, pages = live_runtime
    sess = await _open(runtime)
    agen = runtime.stream(sess, ack=True)
    first = await _next(agen)
    pages[0].frame("SECOND")
    assert (await _next(agen))["jpeg"] == "SECOND"
    for n in range(5):
        pages[0].frame(f"F{n}")
    await runtime.apply_input(sess, frame_ack=first["frame_id"])
    assert (await _next(agen))["jpeg"] == "F4"
    await agen.aclose()
    assert not sess.frame_acks and not sess.live_panes
    assert pages[0].stops == 1


@pytest.mark.asyncio
async def test_stream_has_at_most_two_unconfirmed_frames(live_runtime, monkeypatch) -> None:
    runtime, pages = live_runtime
    monkeypatch.setattr(runtime_mod, "STREAM_PING_S", 5)
    sess = await _open(runtime)
    agen = runtime.stream(sess, ack=True)
    first = await _next(agen)
    pages[0].frame("SECOND")
    second = await _next(agen)
    pages[0].frame("THIRD")
    third = asyncio.create_task(_next(agen))
    done, _ = await asyncio.wait({third}, timeout=0.05)
    assert not done
    assert set(sess.frame_acks) == {first["frame_id"], second["frame_id"]}
    # POST responses and arrivals can be out of order.
    await runtime.apply_input(sess, frame_ack=second["frame_id"])
    received = await third
    assert received["jpeg"] == "THIRD"
    assert set(sess.frame_acks) == {first["frame_id"], received["frame_id"]}
    await agen.aclose()


@pytest.mark.asyncio
async def test_lost_ack_expires_within_the_ping_interval(live_runtime, monkeypatch) -> None:
    runtime, pages = live_runtime
    monkeypatch.setattr(runtime_mod, "STREAM_CHECK_S", 5)
    sess = await _open(runtime)
    agen = runtime.stream(sess, ack=True)
    first = await _next(agen)
    pages[0].frame("SECOND")
    await _next(agen)
    pages[0].frame("STALE")
    pages[0].frame("FINAL")
    # No acknowledgements or further repaints. The timeout alone opens a slot.
    delivered = await asyncio.wait_for(anext(agen), runtime_mod.STREAM_PING_S + 0.1)
    assert delivered["jpeg"] == "FINAL"
    assert first["frame_id"] not in sess.frame_acks
    await runtime.apply_input(sess, frame_ack=first["frame_id"])
    assert delivered["frame_id"] in sess.frame_acks
    await agen.aclose()


@pytest.mark.asyncio
async def test_legacy_stream_does_not_wait_for_acks(live_runtime, monkeypatch) -> None:
    runtime, pages = live_runtime
    monkeypatch.setattr(runtime_mod, "STREAM_PING_S", 5)
    sess = await _open(runtime)
    agen = runtime.stream(sess)
    try:
        assert "frame_id" not in await _next(agen)
        for n in range(3):
            pages[0].frame(str(n))
            event = await _next(agen)
            assert event["jpeg"] == str(n) and "frame_id" not in event
        assert not sess.frame_acks
    finally:
        await agen.aclose()


@pytest.mark.asyncio
async def test_progressive_stream_refines_only_the_latest_frame(live_runtime, monkeypatch):
    runtime, pages = live_runtime
    monkeypatch.setattr(runtime_mod, "STREAM_FIRST_REFINE_S", 0.1)
    monkeypatch.setattr(runtime_mod, "STREAM_REFINE_S", 0.1)
    monkeypatch.setattr(ScreencastFrame, "motion_jpeg", lambda frame: f"motion:{frame.jpeg}")
    sess = await _open(runtime)
    agen = runtime.stream(sess, ack=True)
    first = await _next(agen)
    await runtime.apply_input(sess, frame_ack=first["frame_id"])
    page = pages[0]

    def repaint(value: str) -> None:
        page.push(ScreencastFrame(value, 1920, 1080, time.monotonic()))

    try:
        repaint("one")
        first_motion = await _next(agen)
        assert first_motion["jpeg"] == "motion:one"
        await runtime.apply_input(sess, frame_ack=first_motion["frame_id"])
        repaint("old")
        await runtime.apply_input(sess, scroll_dy=100)
        # A newer wheel request keeps the pane in motion while Chromium repaints.
        page.push(ScreencastFrame("latest", 1920, 1080, time.monotonic() - 1))
        last_motion = await _next(agen)
        assert last_motion["jpeg"] == "motion:latest"
        assert (last_motion["width"], last_motion["height"]) == (1920, 1080)
        # The last motion frame still awaits acknowledgement. The second slot
        # lets the quiet repaint be refined without another viewer round trip.
        clear = await _next(agen)
        assert clear["jpeg"] == "latest"
        assert set(sess.frame_acks) == {last_motion["frame_id"], clear["frame_id"]}
        await runtime.apply_input(sess, frame_ack=last_motion["frame_id"])
        assert (await _next(agen)) == {"ping": True}
    finally:
        await agen.aclose()


@pytest.mark.asyncio
async def test_motion_encode_skips_superseded_frame_before_spending_ack_slot(
    live_runtime, monkeypatch,
) -> None:
    runtime, pages = live_runtime
    monkeypatch.setattr(runtime_mod, "STREAM_PING_S", 5)
    monkeypatch.setattr(runtime_mod, "STREAM_FIRST_REFINE_S", 1)
    monkeypatch.setattr(runtime_mod, "STREAM_REFINE_S", 1)
    loop = asyncio.get_running_loop()
    encoding = asyncio.Event()
    release = threading.Event()

    def motion(frame):
        if frame.jpeg == "stale":
            loop.call_soon_threadsafe(encoding.set)
            assert release.wait(2)
        return f"motion:{frame.jpeg}"

    monkeypatch.setattr(ScreencastFrame, "motion_jpeg", motion)
    sess = await _open(runtime)
    agen = runtime.stream(sess, ack=True)
    first = await _next(agen)
    page = pages[0]
    page.push(ScreencastFrame("stale", 1920, 1080, time.monotonic()))
    pending = asyncio.create_task(_next(agen))
    try:
        await asyncio.wait_for(encoding.wait(), 1)
        page.push(ScreencastFrame("latest", 1920, 1080, time.monotonic()))
        release.set()
        latest = await pending
        assert latest["jpeg"] == "motion:latest"
        assert set(sess.frame_acks) == {first["frame_id"], latest["frame_id"]}
        await runtime.apply_input(sess, frame_ack=latest["frame_id"])
        assert (await _next(agen))["jpeg"] == "latest"
    finally:
        release.set()
        await asyncio.gather(pending, return_exceptions=True)
        await agen.aclose()


@pytest.mark.asyncio
async def test_office_window_says_poll_and_switching_back_restarts_cast(live_runtime) -> None:
    runtime, pages = live_runtime
    sess = await _open(runtime)
    browser_id = sess.windows[0].window_id
    sess.windows.append(SandboxWindow(window_id="win_office", kind="writer", surface=StillSurface()))
    sess.focused_id = "win_office"
    agen = runtime.stream(sess)
    assert await _next(agen) == {"poll": True, "window_id": "win_office"}
    office = sess.focused().surface
    await runtime.apply_input(sess, click_x=10, click_y=20)
    assert office.shots == 1
    sess.focused_id = browser_id
    assert (await _next(agen))["jpeg"] == "FIRST"
    assert pages[0].casting == 1
    await agen.aclose()


@pytest.mark.asyncio
async def test_live_input_and_meta_skip_png_and_throttle_login(live_runtime, monkeypatch) -> None:
    runtime, pages = live_runtime
    sess = await _open(runtime)
    page = pages[0]
    agen = runtime.stream(sess)
    await _next(agen)
    for _ in range(2):
        meta = await runtime.apply_input(sess, click_x=10, click_y=20)
        assert meta["clicked"] and meta["title"] == "Page"
    async def live_h1() -> str:
        return "Updated heading"

    monkeypatch.setattr(page, "h1", live_h1)
    assert sess.h1 == ""
    assert (await runtime.pane_meta(sess))["h1"] == "Updated heading"
    assert page.click_settled is False
    assert page.shots == 1 and page.saves == 1
    await agen.aclose()
    await runtime.apply_input(sess, click_x=10, click_y=20)
    assert page.click_settled is True
    assert page.shots == 2 and page.saves == 2


@pytest.mark.asyncio
async def test_failed_cast_keeps_polling_png(live_runtime, monkeypatch) -> None:
    runtime, pages = live_runtime
    sess = await _open(runtime)

    async def fail(_push):
        raise RuntimeError("CDP unavailable")

    monkeypatch.setattr(pages[0], "screencast", fail)
    agen = runtime.stream(sess)
    assert (await _next(agen))["poll"] is True
    await runtime.apply_input(sess, click_x=10, click_y=20)
    assert pages[0].shots == 2
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
@pytest.mark.parametrize("ack", [False, True])
async def test_api_stream_helper_checks_owner_then_streams(live_runtime, ack) -> None:
    runtime, _pages = live_runtime
    sess = await _open(runtime)
    path = f"/v1/internal/sessions/{sess.session_id}/stream"
    with pytest.raises(ToolError) as denied:
        await sidecar_stream(path, params={"school_id": "school-b", "membership_id": "member-b"})
    assert denied.value.code == "sandbox.forbidden"
    chunks = await sidecar_stream(
        path, params={"school_id": "school-a", "membership_id": "member-a", "ack": ack}
    )
    first = await asyncio.wait_for(chunks.__anext__(), 2.0)
    event = json.loads(first.decode()[len("data: ") :])
    assert event["jpeg"] == "FIRST" and ("frame_id" in event) is ack
    await chunks.aclose()


@pytest.mark.asyncio
async def test_parallel_opens_reserve_capacity_before_starting_chromium(
    live_runtime, monkeypatch
) -> None:
    runtime, _pages = live_runtime
    monkeypatch.setattr(runtime_mod, "MAX_SESSIONS", 1)
    opening = asyncio.Event()
    release = asyncio.Event()

    async def delayed_open(url, **_kw):
        opening.set()
        await release.wait()
        return CastSurface(url)

    monkeypatch.setattr(runtime, "_open_browser", delayed_open)
    first = asyncio.create_task(_open(runtime))
    await opening.wait()
    try:
        with pytest.raises(ToolError) as denied:
            await runtime.open_session(
                school_id="school-a", membership_id="member-b", run_id=None,
                url="https://example.com/",
            )
        assert denied.value.code == "sandbox.quota"
    finally:
        release.set()
        await first


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

        def push(frame: ScreencastFrame) -> None:
            frames.append(frame.jpeg)

        stop = await surface.screencast(push)
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
            await surface.press_human_key("F5")
        # #1236: a slider check — press, move, release on the pane.
        await page.evaluate("window.scrollTo(0, 0)")
        await page.evaluate(
            """() => {
              const s = document.createElement('div');
              s.id = 'knob';
              s.style.cssText = 'position:fixed;left:20px;top:20px;width:40px;height:40px;background:#08f';
              window.trail = [];
              let on = false;
              s.onmousedown = (e) => { on = true; trail.push('down'); };
              document.onmousemove = (e) => { if (on) { trail.push('move'); s.style.left = (e.clientX - 20) + 'px'; } };
              document.onmouseup = (e) => { if (on) { on = false; trail.push('up:' + e.clientX); } };
              document.body.appendChild(s);
            }"""
        )
        await surface.drag("down", 40, 40)
        for x in (90, 160, 230):
            await surface.drag("move", x, 42)
        await surface.drag("up", 260, 42)
        trail = await page.evaluate("window.trail")
        knob_left = await page.evaluate("document.getElementById('knob').style.left")
        await stop()
        assert moving >= 3
        assert still <= 1
        assert len(frames) > moving + still  # scrolling repainted
        assert frames[0].startswith("/9j/")  # base64 JPEG
        assert scroll_y >= 700
        assert trail[0] == "down" and trail[-1] == "up:260"
        assert trail.count("move") >= 4
        assert knob_left == "240px"
    finally:
        await browser.close()
        await pw.stop()
