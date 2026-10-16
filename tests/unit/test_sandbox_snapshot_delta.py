"""Snapshot deltas (#1222) on upstream AI snapshots (#1233).

Upstream = Playwright ``aria_snapshot(mode="ai")`` + ``aria-ref=`` (shape of
Playwright MCP incremental snapshots). Refs stay stable across snapshots and
iframe content comes back inline with ``f1eN`` refs; ``RefBook`` only diffs.
"""

from __future__ import annotations

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

from sandbox_worker.browser import RefBook

PAGE1 = """- heading "报名" [level=1] [ref=e3]
- button "加一行" [ref=e4]
- list [ref=e5]:
  - listitem [ref=e6]: 第一行
  - listitem [ref=e7]: 第二行
- textbox "姓名" [ref=e8]
- button "提交" [ref=e9]
- link "帮助" [ref=e10]
- link "关于" [ref=e11]"""

# Same page after "加一行": the new item gets a new ref, the rest keep theirs.
PAGE2 = PAGE1.replace(
    "  - listitem [ref=e7]: 第二行", "  - listitem [ref=e7]: 第二行\n  - listitem [ref=e12]: 第三行"
)


def _ref(text: str, needle: str) -> str:
    line = next((ln for ln in text.splitlines() if needle in ln), "")
    m = re.search(r"\[ref=((?:f\d+)?e\d+)\]", line)
    assert m, f"{needle} not in:\n{text}"
    return m.group(1)


def test_refbook_returns_only_the_change() -> None:
    book = RefBook()
    full, delta = book.update(PAGE1, page=0)
    assert delta is None and full == PAGE1  # first look: the whole page

    full2, delta2 = book.update(PAGE2, page=0)
    assert full2 == PAGE2
    assert delta2 is not None
    assert "第三行" in delta2
    assert "- list [ref=e5]:" in delta2  # parent comes along for context
    assert "提交" not in delta2 and "第一行" not in delta2
    assert len(delta2) < len(full2)

    # Typing changes one line's value: listed as changed, ref unchanged upstream.
    typed = PAGE2.replace('textbox "姓名" [ref=e8]', 'textbox "姓名" [ref=e8]: 张三')
    _, delta3 = book.update(typed, page=0)
    assert delta3 is not None and 'textbox "姓名" [ref=e8]: 张三' in delta3

    _, same = book.update(typed, page=0)
    assert same == "（页面结构没变，编号照用。）"

    # A line disappears: counted, not listed.
    _, gone = book.update("\n".join(ln for ln in typed.splitlines() if "关于" not in ln), page=0)
    assert gone is not None and "消失 1 行" in gone

    # Another tab (page token bumped) or a different page: whole snapshot.
    assert book.update(PAGE2, page=1)[1] is None
    assert book.update('- heading "别的页" [level=1] [ref=e2]\n- link "x" [ref=e3]', page=1)[1] is None


LIST_PAGE = (
    "<h1>报名</h1><button onclick=\"var li=document.createElement('li');"
    "li.textContent='新的一行';document.getElementById('l').prepend(li)\">加一行</button>"
    "<ul id=l>" + "".join(f"<li>课程 {i}</li>" for i in range(40)) + "</ul>"
    "<label>姓名 <input id=who></label>"
)

# Mail-style compose (#1233): a recipient box that only reacts to keys, and the
# body in an iframe editor, like QQ Mail / TinyMCE.
COMPOSE_PAGE = (
    "<label>收件人 <input id=to></label><ul id=sug></ul>"
    "<iframe title=正文 srcdoc=\"<body contenteditable=true><p>旧正文</p></body>\"></iframe>"
    "<label>密码框 <input id=pw type=password value=hidden-secret></label>"
    "<script>to.addEventListener('keyup',()=>{sug.innerHTML='<li>建议 '+to.value+'</li>'})</script>"
)


async def _chromium():
    pytest.importorskip("playwright.async_api")
    from playwright.async_api import async_playwright
    from sandbox_worker.browser import CHROMIUM_ARGS

    try:
        pw = await async_playwright().start()
        browser = await pw.chromium.launch(headless=True, args=list(CHROMIUM_ARGS))
    except Exception as exc:  # noqa: BLE001 — environment may lack browser bits
        pytest.skip(f"Chromium unavailable: {exc}")
    return pw, browser


@pytest.mark.asyncio
async def test_real_chromium_delta_and_old_ref_still_hits_the_right_box(tmp_path) -> None:
    from sandbox_worker.browser import PlaywrightPage

    pw, browser = await _chromium()
    try:
        context = await browser.new_context()
        page = await context.new_page()
        await page.set_content(LIST_PAGE)
        surface = PlaywrightPage(context, page, tmp_path / "profile")
        book = RefBook()

        full, _ = book.update(await surface.snapshot(), page=surface.page_token)
        who = _ref(full, 'textbox "姓名"')
        await surface.click_ref(_ref(full, 'button "加一行"'))
        full2, delta = book.update(await surface.snapshot(), page=surface.page_token)
        assert delta is not None and "新的一行" in delta
        assert "课程 39" not in delta
        assert len(delta) * 5 < len(full2)

        # A row was inserted above the box; the AI's old ref still hits it.
        assert _ref(full2, 'textbox "姓名"') == who
        await surface.type_ref(who, "张三", submit=False)
        assert await page.input_value("#who") == "张三"
    finally:
        await browser.close()
        await pw.stop()


@pytest.mark.asyncio
async def test_real_chromium_sees_and_types_into_iframes_and_types_slowly(tmp_path) -> None:
    from sandbox_worker.browser import PlaywrightPage

    pw, browser = await _chromium()
    try:
        context = await browser.new_context()
        page = await context.new_page()
        await page.set_content(COMPOSE_PAGE)
        await page.wait_for_timeout(200)
        surface = PlaywrightPage(context, page, tmp_path / "profile")

        snap = await surface.snapshot()
        assert "旧正文" in snap  # 1.52 showed only `- iframe`
        body = _ref(snap, "旧正文")
        assert body.startswith("f")
        assert "hidden-secret" not in snap

        # Pasting does not wake the recipient box; typing key by key does.
        to = _ref(snap, 'textbox "收件人"')
        await surface.type_ref(to, "wan", submit=False)
        assert "建议" not in await surface.snapshot()
        await surface.type_ref(to, "", submit=False)
        await surface.type_ref(to, "wan@x.cn", submit=False, slowly=True)
        assert "建议 wan@x.cn" in await surface.snapshot()

        # The body inside the iframe takes text through its own ref.
        await surface.type_ref(body, "你好，这是测试邮件", submit=False)
        frame_text = await page.frames[1].evaluate("document.body.innerText")
        assert "你好，这是测试邮件" in frame_text
        assert "你好，这是测试邮件" in await surface.snapshot()

        # pico#1320: keys go into a password box too (inside an iframe as well).
        await page.set_content(
            "<iframe srcdoc=\"<input id=p type=password>\"></iframe>"
        )
        await page.wait_for_timeout(200)
        await page.frames[1].focus("#p")
        await surface.press_key("a")
        assert await page.frames[1].evaluate("document.getElementById('p').value") == "a"
    finally:
        await browser.close()
        await pw.stop()
