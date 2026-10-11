"""Snapshot deltas (#1222): after an action only new / changed lines go back.

Upstream = Playwright ``aria_snapshot(ref=True)`` + ``aria-ref=`` (shape of
Playwright MCP incremental snapshots). Playwright 1.52 renumbers refs on every
snapshot; ``RefBook`` keeps the AI's ``eN`` stable and maps it back.
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

PAGE1 = """- heading "报名" [level=1] [ref=s1e3]
- button "加一行" [ref=s1e4]
- list [ref=s1e5]:
  - listitem [ref=s1e6]: 第一行
  - listitem [ref=s1e7]: 第二行
- textbox "姓名" [ref=s1e8]
- button "提交" [ref=s1e9]
- link "帮助" [ref=s1e10]
- link "关于" [ref=s1e11]"""

# Same page after "加一行": a new list item shifts every ref after it.
PAGE2 = """- heading "报名" [level=1] [ref=s2e3]
- button "加一行" [ref=s2e4]
- list [ref=s2e5]:
  - listitem [ref=s2e6]: 第一行
  - listitem [ref=s2e7]: 第二行
  - listitem [ref=s2e8]: 第三行
- textbox "姓名" [ref=s2e9]
- button "提交" [ref=s2e10]
- link "帮助" [ref=s2e11]
- link "关于" [ref=s2e12]"""


def _stable(text: str, needle: str) -> str:
    m = re.search(rf"{re.escape(needle)}[^\n]*\[ref=(e\d+)\]", text)
    assert m, f"{needle} not in:\n{text}"
    return m.group(1)


def test_refbook_keeps_refs_and_returns_only_the_change() -> None:
    book = RefBook()
    full, delta = book.update(PAGE1, page=0)
    assert delta is None  # first look: the whole page
    assert "s1e" not in full
    name_ref = _stable(full, 'textbox "姓名"')
    assert book.resolve(name_ref) == "s1e8"

    full2, delta2 = book.update(PAGE2, page=0)
    # The textbox kept its ref and now points at the renumbered element.
    assert _stable(full2, 'textbox "姓名"') == name_ref
    assert book.resolve(name_ref) == "s2e9"
    assert delta2 is not None
    assert "第三行" in delta2
    assert '- list [ref=' in delta2  # parent comes along for context
    assert "提交" not in delta2 and "第一行" not in delta2
    assert len(delta2) < len(full2)

    # Typing changes one line's value: same element, same ref, listed as changed.
    _, delta3 = book.update(PAGE2.replace('textbox "姓名" [ref=s2e9]', 'textbox "姓名" [ref=s3e9]: 张三'), page=0)
    assert delta3 is not None and f'textbox "姓名" [ref={name_ref}]: 张三' in delta3

    _, same = book.update(PAGE2.replace('[ref=s2e9]', '[ref=s4e9]: 张三'), page=0)
    assert same == "（页面结构没变，编号照用。）"

    # A line disappears: counted, not listed.
    _, gone = book.update("\n".join(ln for ln in PAGE2.splitlines() if "关于" not in ln).replace("[ref=s2e9]", "[ref=s4e9]: 张三"), page=0)
    assert gone is not None and "消失 1 行" in gone

    # Another tab (page token bumped) or a different page: whole snapshot.
    assert book.update(PAGE2, page=1)[1] is None
    assert book.update('- heading "别的页" [level=1] [ref=s9e3]\n- link "x" [ref=s9e4]', page=1)[1] is None


def test_refbook_passes_raw_playwright_refs_and_unknown_refs_through() -> None:
    book = RefBook()
    book.update(PAGE1, page=0)
    assert book.resolve("s1e4") == "s1e4"
    assert book.resolve("e999") == "e999"  # browser adapter reports「页面变了」
    assert book.resolve(" e1 ") == book.resolve("e1")


LIST_PAGE = (
    "<h1>报名</h1><button onclick=\"var li=document.createElement('li');"
    "li.textContent='新的一行';document.getElementById('l').prepend(li)\">加一行</button>"
    "<ul id=l>" + "".join(f"<li>课程 {i}</li>" for i in range(40)) + "</ul>"
    "<label>姓名 <input id=who></label>"
)


@pytest.mark.asyncio
async def test_real_chromium_delta_and_old_ref_still_hits_the_right_box(tmp_path) -> None:
    pytest.importorskip("playwright.async_api")
    from playwright.async_api import async_playwright
    from sandbox_worker.browser import CHROMIUM_ARGS, PlaywrightPage

    try:
        pw = await async_playwright().start()
        browser = await pw.chromium.launch(headless=True, args=list(CHROMIUM_ARGS))
    except Exception as exc:  # noqa: BLE001 — environment may lack browser bits
        pytest.skip(f"Chromium unavailable: {exc}")
    try:
        context = await browser.new_context()
        page = await context.new_page()
        await page.set_content(LIST_PAGE)
        surface = PlaywrightPage(context, page, tmp_path / "profile")
        book = RefBook()

        full, _ = book.update(await surface.snapshot(), page=surface.page_token)
        who = _stable(full, 'textbox "姓名"')
        await surface.click_ref(book.resolve(_stable(full, 'button "加一行"')))
        full2, delta = book.update(await surface.snapshot(), page=surface.page_token)
        assert delta is not None and "新的一行" in delta
        assert "课程 39" not in delta
        assert len(delta) * 5 < len(full2)

        # Playwright renumbered everything below the new row; the AI's old ref works.
        await surface.type_ref(book.resolve(who), "张三", submit=False)
        assert await page.input_value("#who") == "张三"
    finally:
        await browser.close()
        await pw.stop()
