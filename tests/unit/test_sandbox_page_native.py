"""Page-native save / query / delete (#1242).

Thin adapter: hang File on the page, call a dotted path. No eval, no cookie
back to the model, no second control kernel. Demo page, not a real hall.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services"))
sys.path.insert(0, str(ROOT / "services" / "orchestrator"))
sys.path.insert(0, str(ROOT / "services" / "api"))

os.environ.setdefault("PICO_JWT_SECRET", "test-secret-at-least-32-bytes-long!!")

from pico_orchestrator.gateway import ToolError
from sandbox_worker.browser import (
    CALL_PAGE_FN_JS,
    CHROMIUM_ARGS,
    HANG_FILES_JS,
    PAGE_FN_MAX_RESULT_BYTES,
    PAGE_TEXT_JS,
    RATE_LIMIT_PHRASES,
    VIEWPORT_HEIGHT,
    VIEWPORT_WIDTH,
    cap_page_result,
    json_safe_args,
    parse_page_fn_path,
    rate_limit_hit,
    sanitize_page_result,
)

DEMO_HTML = (ROOT / "testdata" / "sandbox" / "page-native-save.html").read_text(encoding="utf-8")


def test_page_fn_path_is_dotted_only() -> None:
    assert parse_page_fn_path("saveField") == ["saveField"]
    assert parse_page_fn_path("app.saveMaterial") == ["app", "saveMaterial"]
    for bad in (
        "",
        "foo()",
        "foo;bar",
        "foo['bar']",
        "new Function",
        "eval",
        "window.eval",
        "app.constructor",
        "foo\nbar",
        "..save",
        "1save",
    ):
        with pytest.raises(ToolError) as exc:
            parse_page_fn_path(bad)
        assert exc.value.code == "tool.invalid_arguments"
        assert "点号路径" in exc.value.message or "不能包含" in exc.value.message


def test_page_fn_refuses_browser_builtins() -> None:
    """#1246: setTimeout strings / cookieStore / storage never reach the page."""
    assert parse_page_fn_path("window.saveField") == ["saveField"]
    assert parse_page_fn_path("self.app.saveMaterial") == ["app", "saveMaterial"]
    for bad in (
        "setTimeout",
        "window.setTimeout",
        "globalThis.setInterval",
        "cookieStore.getAll",
        "localStorage.getItem",
        "window.sessionStorage.getItem",
        "location.assign",
        "document.write",
        "open",
        "top.saveField",
        "window",
    ):
        with pytest.raises(ToolError) as exc:
            parse_page_fn_path(bad)
        assert exc.value.code == "sandbox.fn_native_blocked", bad


def test_page_fn_result_is_capped() -> None:
    small = {"name": "成绩.xlsx", "count": 1}
    assert cap_page_result(small) == small
    big = cap_page_result({"rows": ["x" * 100] * 200})
    assert big["truncated"] is True
    assert len(big["preview"]) <= 2_000
    assert PAGE_FN_MAX_RESULT_BYTES == 8_192


def test_page_fn_args_must_be_json() -> None:
    assert json_safe_args(["proof", "__picoFile"]) == ["proof", "__picoFile"]
    assert json_safe_args(None) == []
    with pytest.raises(ToolError):
        json_safe_args({"x": 1})  # type: ignore[arg-type]
    with pytest.raises(ToolError):
        json_safe_args([object()])  # type: ignore[list-item]


def test_rate_limit_phrases_are_the_testable_list() -> None:
    assert RATE_LIMIT_PHRASES == (
        "IP访问量过大",
        "请求过于频繁",
        "访问过于频繁",
        "操作过于频繁",
        "请稍后再试",
        "请稍后重试",
        "too many requests",
        "rate limit",
    )
    assert rate_limit_hit(["正常页面"]) is None
    assert rate_limit_hit(["系统提示：IP访问量过大，请稍候"]) == "IP访问量过大"
    assert rate_limit_hit(["Too Many Requests"]) == "too many requests"


def test_sanitize_page_result_drops_cookie_keys() -> None:
    out = sanitize_page_result(
        {"cookie": "sid=secret", "cookies": "a=b", "name": "成绩.xlsx", "count": 1}
    )
    assert out == {"name": "成绩.xlsx", "count": 1}
    assert "secret" not in str(out)


def test_owned_scripts_forbid_eval_function_cookie_fetch() -> None:
    blob = HANG_FILES_JS + CALL_PAGE_FN_JS + PAGE_TEXT_JS
    for banned in ("eval(", "new Function", "document.cookie", "fetch("):
        assert banned not in blob, banned


@pytest.mark.asyncio
async def test_real_chromium_t1_t2_t3_demo_page(tmp_path: Path) -> None:
    """T1: total upload reports 未选择材料; page-native save records name+count.
    T2: AI path does not click 上传 or 去上传.
    T3: rate-limit copy refuses save/query/delete."""
    pytest.importorskip("playwright.async_api")
    from playwright.async_api import async_playwright
    from sandbox_worker.browser import PlaywrightPage

    try:
        pw = await async_playwright().start()
        browser = await pw.chromium.launch(headless=True, args=list(CHROMIUM_ARGS))
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"Chromium unavailable: {exc}")
    context = await browser.new_context(
        viewport={"width": VIEWPORT_WIDTH, "height": VIEWPORT_HEIGHT}
    )
    page = await context.new_page()
    try:
        await page.set_content(DEMO_HTML, wait_until="domcontentloaded")
        await page.wait_for_function(
            "() => { const f = document.getElementById('sub'); "
            "return !!(window.leakCookie && f && f.contentWindow && f.contentWindow.frameQuery); }"
        )
        hands = PlaywrightPage(context, page, tmp_path / "profile")

        # T1 setup: the page's own total upload refuses empty required fields.
        await page.click("#upload-all")
        assert await page.inner_text("#msg") == "未选择材料"
        clicks_after_human = await page.evaluate(
            "() => ({up: window.__clickedUploadAll, go: window.__clickedGoUpload})"
        )
        assert clicks_after_human == {"up": 1, "go": 0}

        hung = await hands.page_file([("成绩.xlsx", "application/zip", b"PK-xlsx")])
        assert hung["handle"] == "__picoFile"
        assert hung["names"] == ["成绩.xlsx"]
        saved = await hands.page_fn("saveField", ["proof", "__picoFile"])
        assert saved == {"name": "成绩.xlsx", "count": 1}
        queried = await hands.page_fn("queryField", ["proof"])
        assert queried == {"name": "成绩.xlsx", "count": 1}
        assert await page.inner_text("#proof-name") == "成绩.xlsx"
        assert await page.inner_text("#proof-count") == "1"

        dotted = await hands.page_fn("app.saveMaterial", ["proof", "__picoFile"])
        assert dotted["name"] == "成绩.xlsx"

        # iframe dotted path
        framed = await hands.page_fn("frameQuery", ["proof"])
        assert framed == {"name": "成绩.xlsx", "count": 1}

        # T2: the AI path did not click 上传 / 去上传.
        clicks = await page.evaluate(
            "() => ({up: window.__clickedUploadAll, go: window.__clickedGoUpload})"
        )
        assert clicks == {"up": 1, "go": 0}

        leaked = await hands.page_fn("leakCookie", [])
        assert leaked == {"name": "ok"}
        assert "cookie" not in (leaked or {})

        with pytest.raises(ToolError) as missing:
            await hands.page_fn("hallSave_99", [])
        assert missing.value.code == "sandbox.fn_missing"
        assert "hallSave_99" in missing.value.message

        # #1246: native functions are refused even when the page aliases them,
        # so a string never runs as code and cookies / tokens never come back.
        await page.evaluate(
            "() => { window.__secret = 'SECRET123';"
            " window.app.store = { getItem: Storage.prototype.getItem }; window.app.later = setTimeout;"
            " window.app.big = () => ({ rows: 'x'.repeat(20000) }); }"
        )
        for name, args in (
            ("app.later", ["document.body.insertAdjacentText('beforeend','LEAK='+window.__secret)"]),
            ("app.store.getItem", ["token"]),
        ):
            with pytest.raises(ToolError) as native:
                await hands.page_fn(name, args)
            assert native.value.code == "sandbox.fn_native_blocked", name
        for name, args in (
            ("setTimeout", ["document.title = window.__secret"]),
            ("cookieStore.getAll", []),
            ("localStorage.getItem", ["token"]),
        ):
            with pytest.raises(ToolError) as blocked:
                await hands.page_fn(name, args)
            assert blocked.value.code == "sandbox.fn_native_blocked", name
        await page.wait_for_timeout(50)
        assert "LEAK=" not in await page.inner_text("body")
        assert "SECRET123" not in await page.title()
        capped = await hands.page_fn("app.big", [])
        assert capped["truncated"] is True

        # T3
        await page.click("#show-limit")
        assert "IP访问量过大" in await page.inner_text("#limit")
        for name, args in (
            ("saveField", ["proof", "__picoFile"]),
            ("queryField", ["proof"]),
            ("deleteField", ["proof"]),
        ):
            with pytest.raises(ToolError) as limited:
                await hands.page_fn(name, args)
            assert limited.value.code == "sandbox.rate_limited"
            assert "IP访问量过大" in limited.value.message
    finally:
        await context.close()
        await browser.close()
        await pw.stop()
