"""Thin Playwright/Chromium adapter for B2.

Upstream: Playwright Chromium. Pico only wires web_guard, tmpfs/memory
cookies, screenshots, and human-in-the-loop input. Not a second agent loop.
"""

from __future__ import annotations

import asyncio
import logging
import os
import shutil
import tempfile
from pathlib import Path
from typing import Any, Protocol

from pico_orchestrator.gateway import ToolError
from pico_orchestrator.web_guard import parse_public_http_url

logger = logging.getLogger(__name__)

ENGINE_NAME = "playwright-chromium"
VIEWPORT_WIDTH = 390
VIEWPORT_HEIGHT = 844
PNG_MAGIC = b"\x89PNG\r\n\x1a\n"
GOTO_TIMEOUT_MS = 20_000
PROFILE_ROOT = Path(
    os.environ.get("PICO_SANDBOX_PROFILE_ROOT") or "/tmp/pico-sandbox-profiles"
)

# Non-privileged Docker: Chromium cannot use a sandbox. Not host Chrome.
CHROMIUM_ARGS = (
    "--no-sandbox",
    "--disable-setuid-sandbox",
    "--disable-dev-shm-usage",
    "--disable-gpu",
    "--disable-extensions",
    "--disable-background-networking",
    "--disable-sync",
    "--mute-audio",
    "--no-first-run",
    "--password-store=basic",
    "--hide-scrollbars",
)


class BrowserPage(Protocol):
    @property
    def url(self) -> str: ...

    async def title(self) -> str: ...

    async def h1(self) -> str: ...

    async def screenshot_png(self) -> bytes: ...

    async def click(self, x: int, y: int) -> None: ...

    async def type_text(self, text: str, *, password: bool) -> None: ...

    async def close(self) -> None: ...


def _is_browser_internal(url: str) -> bool:
    low = (url or "").strip().lower()
    return low.startswith(
        ("about:", "data:", "blob:", "chrome:", "chrome-error:", "devtools:")
    )


def assert_http_public_or_internal(url: str) -> None:
    if _is_browser_internal(url):
        return
    parse_public_http_url(url)


_PW: Any = None
_BROWSER: Any = None
_LOCK = asyncio.Lock()


async def shutdown_browser() -> None:
    """Close the process-wide Chromium (tests / evidence capture)."""
    global _PW, _BROWSER
    async with _LOCK:
        browser, pw = _BROWSER, _PW
        _BROWSER = None
        _PW = None
    if browser is not None:
        try:
            await browser.close()
        except Exception:
            logger.debug("shared chromium close failed", exc_info=True)
    if pw is not None:
        try:
            await pw.stop()
        except Exception:
            logger.debug("playwright stop failed", exc_info=True)


def _profile_root() -> Path:
    root = PROFILE_ROOT
    root.mkdir(parents=True, exist_ok=True)
    return root


async def _ensure_browser() -> Any:
    global _PW, _BROWSER
    async with _LOCK:
        if _BROWSER is not None:
            return _BROWSER
        try:
            from playwright.async_api import async_playwright
        except ImportError as exc:
            raise ToolError(
                "sandbox.unavailable",
                "隔离沙箱未安装 Playwright/Chromium，无法打开真页面。",
            ) from exc
        try:
            _PW = await async_playwright().start()
            _BROWSER = await _PW.chromium.launch(
                headless=True,
                args=list(CHROMIUM_ARGS),
            )
        except Exception as exc:
            raise ToolError(
                "sandbox.unavailable",
                "隔离沙箱未能启动 Chromium（不是 LibreChat，也不是宿主机 Chrome）。",
            ) from exc
        return _BROWSER


async def _guard_route(route: Any) -> None:
    url = route.request.url
    if _is_browser_internal(url):
        await route.continue_()
        return
    try:
        parse_public_http_url(url)
    except ToolError:
        await route.abort("blockedbyclient")
        return
    await route.continue_()


class PlaywrightPage:
    """One Chromium context. Cookies live in this context / tmpfs, not host HOME."""

    def __init__(self, context: Any, page: Any, profile_dir: Path) -> None:
        self._context = context
        self._page = page
        self._profile_dir = profile_dir

    @property
    def url(self) -> str:
        return str(self._page.url or "")

    async def title(self) -> str:
        try:
            return str(await self._page.title() or "")
        except Exception:  # noqa: BLE001
            return ""

    async def h1(self) -> str:
        try:
            text = await self._page.evaluate(
                """() => {
                    const h = document.querySelector('h1');
                    return h ? (h.innerText || '').trim() : '';
                }"""
            )
            return str(text or "")[:200]
        except Exception:  # noqa: BLE001
            return ""

    async def screenshot_png(self) -> bytes:
        raw = await self._page.screenshot(type="png", full_page=False)
        png = bytes(raw)
        if not png.startswith(PNG_MAGIC):
            raise ToolError("sandbox.raster_failed", "隔离 Chromium 未能截取 viewport")
        return png

    async def click(self, x: int, y: int) -> None:
        before = str(self._page.url or "")
        await self._page.mouse.click(float(x), float(y))
        for _ in range(25):
            if str(self._page.url or "") != before:
                try:
                    await self._page.wait_for_load_state("domcontentloaded", timeout=5_000)
                except Exception:
                    logger.debug("navigation load wait failed", exc_info=True)
                break
            await asyncio.sleep(0.1)
        assert_http_public_or_internal(self.url)

    async def type_text(self, text: str, *, password: bool) -> None:
        # Never log `text`. Password keystrokes go to the focused DOM node only.
        _ = password
        tag = await self._page.evaluate(
            """() => {
                const el = document.activeElement;
                return el ? el.tagName : '';
            }"""
        )
        if str(tag or "").upper() in {"", "BODY", "HTML"}:
            loc = self._page.locator(
                "input:visible, textarea:visible, [contenteditable=true]"
            ).first
            try:
                if await loc.count():
                    await loc.click(timeout=1_500)
            except Exception:
                logger.debug("no visible input to focus before typing", exc_info=True)
        await self._page.keyboard.type(text, delay=15)

    async def click_point_for(self, selector: str) -> tuple[int, int] | None:
        box = await self._page.locator(selector).first.bounding_box()
        if box is None:
            return None
        return int(box["x"] + box["width"] / 2), int(box["y"] + box["height"] / 2)

    async def input_value(self, selector: str) -> str:
        loc = self._page.locator(selector).first
        try:
            return str(await loc.input_value(timeout=2_000) or "")
        except Exception:
            logger.debug("input value read failed", exc_info=True)
            return ""

    async def close(self) -> None:
        try:
            await self._context.close()
        except Exception:
            logger.debug("chromium context close failed", exc_info=True)
        shutil.rmtree(self._profile_dir, ignore_errors=True)


async def open_chromium(url: str) -> PlaywrightPage:
    """Open a public URL in headless Chromium. Caller already ran web_guard."""
    parse_public_http_url(url)
    browser = await _ensure_browser()
    profile_dir = Path(tempfile.mkdtemp(prefix="sbox_", dir=str(_profile_root())))
    try:
        context = await browser.new_context(
            viewport={"width": VIEWPORT_WIDTH, "height": VIEWPORT_HEIGHT},
            ignore_https_errors=False,
            accept_downloads=False,
            java_script_enabled=True,
        )
        await context.route("**/*", _guard_route)
        page = context.pages[0] if context.pages else await context.new_page()
        response = await page.goto(url, wait_until="domcontentloaded", timeout=GOTO_TIMEOUT_MS)
        if response is not None and response.status >= 400:
            await context.close()
            shutil.rmtree(profile_dir, ignore_errors=True)
            raise ToolError(
                "sandbox.fetch_failed",
                f"公开页返回 HTTP {response.status}，无法打开登录画面。",
            )
        final = str(page.url or url)
        parse_public_http_url(final)
        return PlaywrightPage(context, page, profile_dir)
    except ToolError:
        shutil.rmtree(profile_dir, ignore_errors=True)
        raise
    except Exception as exc:
        shutil.rmtree(profile_dir, ignore_errors=True)
        raise ToolError("sandbox.fetch_failed", "无法在隔离 Chromium 打开该公开页") from exc


async def open_html_page(html: str):
    """Local HTML surface (file manager). Not a public site; no host Chrome."""
    browser = await _ensure_browser()
    context = await browser.new_context(
        viewport={"width": VIEWPORT_WIDTH, "height": VIEWPORT_HEIGHT},
        java_script_enabled=True,
    )
    page = context.pages[0] if context.pages else await context.new_page()
    await page.set_content(html, wait_until="domcontentloaded")
    return page
