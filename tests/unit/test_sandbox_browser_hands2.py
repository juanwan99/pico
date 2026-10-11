"""AI hands, round 2 (#1217): new tabs follow, back, hover, double-click, dialogs.

Upstream = Playwright context ``page`` / page ``dialog`` events, ``go_back``,
``hover``, ``dblclick`` (shape of Playwright MCP ``browser_tabs`` /
``browser_navigate_back`` / ``browser_hover`` / ``browser_handle_dialog``).
"""

from __future__ import annotations

import asyncio
import os
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services"))
sys.path.insert(0, str(ROOT / "services" / "orchestrator"))
sys.path.insert(0, str(ROOT / "services" / "api"))

os.environ.setdefault("PICO_JWT_SECRET", "test-secret-at-least-32-bytes-long!!")

import sandbox_worker.browser as browser_mod
from pico_orchestrator.gateway import ToolError
from sandbox_worker.browser import VIEWPORT_HEIGHT, VIEWPORT_WIDTH

SITE = "https://site.example"
PAGES = {
    "/a": """<h1>A</h1>
<a href="/b" target="_blank">新窗口</a>
<a href="/c">下一页</a>
<button onclick="r.textContent = confirm('确定提交?') ? 'yes' : 'no'">提交</button>
<p id=r>-</p>
<div id=d ondblclick="this.textContent='dbl'" role=button>双击我</div>
<style>#sub{display:none}#m:hover #sub{display:block}</style>
<nav id=m><span role=button>菜单</span><a id=sub href="/c">子项</a></nav>""",
    "/b": "<h1>B</h1>",
    "/c": "<h1>C</h1>",
}


def _ref(snapshot: str, role: str, name: str) -> str:
    m = re.search(rf'{role} "{re.escape(name)}"[^\n]*\[ref=(\w+)\]', snapshot)
    assert m, f"{role} {name} not in snapshot:\n{snapshot}"
    return m.group(1)


async def _fulfil(route) -> None:
    path = "/" + route.request.url.split("/", 3)[-1].split("?")[0] if route.request.url.startswith(SITE) else ""
    body = PAGES.get(path)
    if body is None:
        await route.abort()
        return
    await route.fulfill(status=200, content_type="text/html; charset=utf-8", body=body)


@pytest.mark.asyncio
async def test_real_chromium_tabs_back_hover_dblclick_dialog(monkeypatch, tmp_path) -> None:
    pytest.importorskip("playwright.async_api")
    from playwright.async_api import async_playwright
    from sandbox_worker.browser import CHROMIUM_ARGS, PlaywrightPage

    monkeypatch.setattr(browser_mod, "parse_public_http_url", lambda url: url)
    try:
        pw = await async_playwright().start()
        browser = await pw.chromium.launch(headless=True, args=list(CHROMIUM_ARGS))
    except Exception as exc:  # noqa: BLE001 — environment may lack browser bits
        pytest.skip(f"Chromium unavailable: {exc}")
    try:
        context = await browser.new_context(
            viewport={"width": VIEWPORT_WIDTH, "height": VIEWPORT_HEIGHT}
        )
        await context.route("**/*", _fulfil)
        page = await context.new_page()
        await page.goto(SITE + "/a")
        surface = PlaywrightPage(context, page, tmp_path / "profile")

        # confirm() is answered OK — without a handler Playwright dismisses it.
        snap = await surface.snapshot()
        await surface.click_ref(_ref(snap, "button", "提交"))
        assert await page.inner_text("#r") == "yes"
        assert surface.take_dialogs() == ["确定提交?"]
        assert surface.take_dialogs() == []

        await surface.click_ref(_ref(snap, "button", "双击我"), double=True)
        assert await page.inner_text("#d") == "dbl"

        assert "子项" not in snap
        await surface.hover_ref(_ref(snap, "button", "菜单"))
        assert "子项" in await surface.snapshot()

        # Same-tab link, then back.
        await surface.click_ref(_ref(await surface.snapshot(), "link", "下一页"))
        assert surface.url == SITE + "/c"
        await surface.navigate_back()
        assert surface.url == SITE + "/a"

        # target=_blank: the new tab becomes current; the live pane re-attaches.
        token = surface.page_token
        await surface.click_ref(_ref(await surface.snapshot(), "link", "新窗口"))
        for _ in range(30):
            if surface.url == SITE + "/b":
                break
            await asyncio.sleep(0.1)
        assert surface.url == SITE + "/b"
        assert surface.page_token > token
        assert "B" in await surface.snapshot()
        rows = await surface.tabs("list", 0)
        assert [r["current"] for r in rows] == [False, True]

        rows = await surface.tabs("select", 0)
        assert surface.url == SITE + "/a"
        assert [r["current"] for r in rows] == [True, False]

        rows = await surface.tabs("close", 1)
        assert len(rows) == 1 and rows[0]["current"]
        with pytest.raises(ToolError):
            await surface.tabs("close", 0)
        with pytest.raises(ToolError):
            await surface.tabs("select", 5)

        # Closing the current tab falls back to the one left.
        await surface.click_ref(_ref(await surface.snapshot(), "link", "新窗口"))
        for _ in range(30):
            if surface.url == SITE + "/b":
                break
            await asyncio.sleep(0.1)
        await surface.tabs("close", 1)
        assert surface.url == SITE + "/a"
    finally:
        await browser.close()
        await pw.stop()
