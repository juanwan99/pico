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
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services"))
sys.path.insert(0, str(ROOT / "services" / "orchestrator"))
sys.path.insert(0, str(ROOT / "services" / "api"))

os.environ.setdefault("PICO_JWT_SECRET", "test-secret-at-least-32-bytes-long!!")

import sandbox_worker.browser as browser_mod
import sandbox_worker.runtime as runtime_mod
from pico_orchestrator.gateway import ToolError
from pico_orchestrator.sandbox_sidecar import _TIMEOUT_S
from pico_orchestrator.tools_builtin import build_default_gateway
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


@pytest.fixture
def navigation_page(monkeypatch, tmp_path):
    page = Mock(
        url=SITE + "/a",
        goto=AsyncMock(return_value=SimpleNamespace(status=200)),
        go_back=AsyncMock(return_value=SimpleNamespace(status=200)),
        wait_for_load_state=AsyncMock(),
    )
    context = Mock(pages=[page], route=AsyncMock(), close=AsyncMock())
    monkeypatch.setattr(browser_mod, "_ensure_browser", AsyncMock(
        return_value=Mock(new_context=AsyncMock(return_value=context)),
    ))
    monkeypatch.setattr(browser_mod, "PROFILE_ROOT", tmp_path)
    surface = browser_mod.PlaywrightPage(context, page, tmp_path)
    return page, context, surface


@pytest.mark.parametrize("action", ["open", "from_files", "reopen", "navigate", "back"])
@pytest.mark.parametrize("capture_timeout", [False, True])
async def test_committed_navigation_survives_dom_timeout(
    action, capture_timeout, navigation_page, monkeypatch, caplog, tmp_path
) -> None:
    from playwright.async_api import TimeoutError as PlaywrightTimeoutError

    page, context, _ = navigation_page

    async def commit(url: str, **_):
        page.url = url
        return SimpleNamespace(status=200)

    async def go_back(**kwargs):
        return await commit(SITE + "/a", **kwargs)

    page.goto.side_effect = commit
    page.go_back.side_effect = go_back
    page.title = AsyncMock(return_value="慢页面")
    page.aria_snapshot = AsyncMock(return_value='- heading "慢页面"')
    page.frames = [page]
    page.evaluate = AsyncMock(return_value=[])
    page.screenshot = AsyncMock(return_value=browser_mod.PNG_MAGIC)
    page.is_closed.return_value = False
    context.storage_state = AsyncMock(return_value={})

    runtime = runtime_mod.SandboxRuntime()
    monkeypatch.setattr(runtime_mod, "RUNTIME", runtime)
    monkeypatch.setenv("PICO_SANDBOX_URL", "embedded")
    monkeypatch.setenv("PICO_SANDBOX_DISK", str(tmp_path / "disk"))
    gateway = build_default_gateway()
    owner = SimpleNamespace(school_id="school-a", membership_id="member-a", scopes=["ai:run"])
    if action == "from_files":
        await runtime.open_files_desk(
            school_id=owner.school_id, membership_id=owner.membership_id, run_id=None,
        )
    elif action in {"reopen", "navigate", "back"}:
        initial = SITE + ("/b" if action == "back" else "/a")
        opened = await gateway.invoke(owner, "sandbox_browser_open", {"url": initial})
        assert "note" not in opened
        page.goto.reset_mock()
        page.wait_for_load_state.reset_mock()

    target = SITE + ("/b" if action in {"reopen", "navigate"} else "/a")
    page.wait_for_load_state.side_effect = PlaywrightTimeoutError("fixture DOM wait expired")
    if capture_timeout:
        async def wait_forever(*args, **kwargs):
            await asyncio.Future()

        page.screenshot.side_effect = wait_forever
        page.aria_snapshot.side_effect = wait_forever
        context.storage_state.side_effect = wait_forever
        monkeypatch.setattr(runtime_mod, "LOADING_SCREENSHOT_TIMEOUT_S", 0)
        monkeypatch.setattr(runtime_mod, "LOADING_SNAPSHOT_TIMEOUT_S", 0)
        monkeypatch.setattr(runtime_mod, "LOADING_METADATA_TIMEOUT_S", 0)
    monkeypatch.setattr(browser_mod, "time", SimpleNamespace(
        monotonic=Mock(side_effect=[100.0, 125.0]),
    ))
    try:
        with caplog.at_level("INFO", logger=browser_mod.__name__):
            if action == "navigate":
                result = await gateway.invoke(owner, "sandbox_browser_navigate", {"url": target})
            elif action == "back":
                result = await gateway.invoke(owner, "sandbox_browser_navigate_back", {})
            else:
                result = await gateway.invoke(owner, "sandbox_browser_open", {"url": target})
        if action == "back":
            page.go_back.assert_awaited_once_with(wait_until="commit", timeout=45_000)
        else:
            page.goto.assert_awaited_once_with(target, wait_until="commit", timeout=45_000)
        page.wait_for_load_state.assert_awaited_once_with("domcontentloaded", timeout=20_000)
        assert result["ok"] is True
        assert result["url"] == target
        note = "页面还在加载，可稍后再取快照 / 截图。"
        if capture_timeout:
            note += "本次未能及时取得截图。"
            assert result["byte_size"] == 0
            assert runtime.get(result["session_id"]).screenshot_png == b""
            if action in {"navigate", "back"}:
                assert "snapshot" not in result
                assert "snapshot_mode" not in result
                note = (
                    "页面还在加载，可稍后再取快照 / 截图。"
                    "本次未能及时取得快照。本次未能及时取得截图。"
                    "本次未能及时更新登录状态或标签页。"
                )
        assert result["note"] == note
        assert "fixture DOM wait expired" in caplog.text
        context.close.assert_not_awaited()
    finally:
        context.storage_state.side_effect = None
        for sid in list(runtime._sessions):
            await runtime.destroy(sid)


def test_loading_navigation_leaves_room_under_sidecar_timeout() -> None:
    assert 0 < runtime_mod.LOADING_SCREENSHOT_TIMEOUT_S <= 10
    assert 0 < runtime_mod.LOADING_SNAPSHOT_TIMEOUT_S <= 10
    assert (
        browser_mod.GOTO_TIMEOUT_MS / 1000
        + runtime_mod.LOADING_SNAPSHOT_TIMEOUT_S
        + runtime_mod.LOADING_SCREENSHOT_TIMEOUT_S
        + runtime_mod.LOADING_METADATA_TIMEOUT_S
    ) < _TIMEOUT_S


@pytest.mark.parametrize(
    ("error_text", "reason"),
    [
        ("net::ERR_CONNECTION_REFUSED", "连接被拒绝"),
        ("net::ERR_NAME_NOT_RESOLVED", "DNS 失败"),
        ("net::ERR_NAME_RESOLUTION_FAILED", "DNS 失败"),
        ("net::ERR_BLOCKED_BY_CLIENT", "访问被拦截"),
        ("net::ERR_HTTP_RESPONSE_CODE_FAILURE", "公开页返回错误状态"),
        ("net::ERR_CONNECTION_TIMED_OUT", "超时"),
        ("timeout", "超时"),
    ],
)
async def test_open_reports_failure_before_commit(
    error_text, reason, navigation_page, caplog
) -> None:
    from playwright.async_api import Error
    from playwright.async_api import TimeoutError as PlaywrightTimeoutError

    page, context, _ = navigation_page
    error_type = PlaywrightTimeoutError if error_text == "timeout" else Error
    page.goto.side_effect = error_type(f"Page.goto: {error_text} at {page.url}")
    with pytest.raises(ToolError, match=reason) as failure:
        await browser_mod.open_chromium(page.url)
    assert failure.value.code == "sandbox.fetch_failed"
    assert error_text in caplog.text
    page.wait_for_load_state.assert_not_awaited()
    context.close.assert_awaited_once()


async def test_back_reports_http_error_before_waiting_for_dom(navigation_page) -> None:
    page, _, surface = navigation_page
    page.go_back.return_value = SimpleNamespace(status=503)
    with pytest.raises(ToolError, match="HTTP 503"):
        await surface.navigate_back()
    page.wait_for_load_state.assert_not_awaited()


async def test_real_chromium_open_keeps_original_page_during_popup(monkeypatch, tmp_path) -> None:
    async def fulfil_with_popup(route) -> None:
        await route.fulfill(
            status=200,
            content_type="text/html",
            body="<title>Original</title><script>window.open('about:blank')</script>",
        )

    monkeypatch.setattr(browser_mod, "PROFILE_ROOT", tmp_path)
    monkeypatch.setattr(browser_mod, "_guard_route", fulfil_with_popup)
    try:
        try:
            await browser_mod._ensure_browser()
        except ToolError as exc:
            pytest.skip(f"Chromium unavailable: {exc.__cause__}")
        surface = await browser_mod.open_chromium(SITE + "/popup")
        try:
            assert surface.url == SITE + "/popup"
            assert await surface.title() == "Original"
            rows = await surface.tabs("list", 0)
            assert [(r["url"], r["current"]) for r in rows] == [
                (SITE + "/popup", True), ("about:blank", False),
            ]
        finally:
            await surface.close()
    finally:
        await browser_mod.shutdown_browser()


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


FORM = """<form id=f>
<label>姓名 <input name=who></label>
<label>密码 <input type=password name=pw></label>
<label><input type=checkbox name=agree> 同意</label>
<label><input type=radio name=size value=s> 小</label>
<label><input type=radio name=size value=l> 大</label>
<label>年级 <select name=grade><option value=g1>一年级</option><option value=g2>二年级</option></select></label>
<label>备注 <textarea name=note></textarea></label>
<div role=checkbox aria-checked=false tabindex=0 aria-label=提醒
  onclick="this.setAttribute('aria-checked', this.getAttribute('aria-checked') !== 'true')">提醒</div>
<label>附件 <input type=file name=att multiple></label>
<button type=button id=pick onclick="att2.click()">上传材料</button>
<input type=file id=att2 style="display:none">
</form>"""


@pytest.mark.asyncio
async def test_real_chromium_fill_form_and_upload(monkeypatch, tmp_path) -> None:
    """#1219: one call fills text / checkbox / radio / select / aria checkbox.
    pico#1320: a password the teacher gave goes in like any other value — it is
    no longer skipped and named back; fill_form returns None. Files go into a
    file input or through the chooser."""
    pytest.importorskip("playwright.async_api")
    from playwright.async_api import async_playwright
    from sandbox_worker.browser import CHROMIUM_ARGS, PlaywrightPage

    monkeypatch.setattr(browser_mod, "parse_public_http_url", lambda url: url)
    PAGES["/form"] = FORM
    try:
        pw = await async_playwright().start()
        browser = await pw.chromium.launch(headless=True, args=list(CHROMIUM_ARGS))
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"Chromium unavailable: {exc}")
    try:
        context = await browser.new_context()
        await context.route("**/*", _fulfil)
        page = await context.new_page()
        await page.goto(SITE + "/form")
        surface = PlaywrightPage(context, page, tmp_path / "profile")
        snap = await surface.snapshot()
        result = await surface.fill_form(
            [
                {"ref": _ref(snap, "textbox", "姓名"), "value": "张三"},
                {"ref": _ref(snap, "textbox", "密码"), "value": "hunter2"},
                {"ref": _ref(snap, "checkbox", "同意"), "value": True},
                {"ref": _ref(snap, "radio", "大"), "value": "true"},
                {"ref": _ref(snap, "combobox", "年级"), "value": "二年级"},
                {"ref": _ref(snap, "textbox", "备注"), "value": "第二行"},
                {"ref": _ref(snap, "checkbox", "提醒"), "value": "是"},
            ]
        )
        assert result is None
        got = await page.evaluate(
            """() => { const f = new FormData(document.getElementById('f'));
                return {who: f.get('who'), pw: f.get('pw'), agree: f.get('agree'),
                        size: f.get('size'), grade: f.get('grade'), note: f.get('note'),
                        remind: document.querySelector('[role=checkbox]').getAttribute('aria-checked')}; }"""
        )
        assert got == {
            "who": "张三", "pw": "hunter2", "agree": "on", "size": "l",
            "grade": "g2", "note": "第二行", "remind": "true",
        }
        with pytest.raises(ToolError):
            await surface.fill_form([])

        await surface.upload_files(
            _ref(snap, "button", "附件"), [("a.txt", "text/plain", b"abc"), ("b.txt", "text/plain", b"de")]
        )
        await surface.upload_files(_ref(snap, "button", "上传材料"), [("c.docx", "application/zip", b"PK")])
        files = await page.evaluate(
            """() => [...document.querySelectorAll('input[type=file]')]
                .map((el) => [...el.files].map((f) => f.name + ':' + f.size))"""
        )
        assert files == [["a.txt:3", "b.txt:2"], ["c.docx:2"]]
        with pytest.raises(ToolError):
            await surface.upload_files(_ref(snap, "textbox", "姓名"), [("x", "text/plain", b"x")])
    finally:
        await browser.close()
        await pw.stop()
