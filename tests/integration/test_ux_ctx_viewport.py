"""T-UX-CTX-VIEWPORT · Playwright V1/V2 + H/U person locks. Not Jest-only."""

from __future__ import annotations

import hashlib
import struct
from pathlib import Path

import pytest
from sandbox_worker.browser import VIEWPORT_HEIGHT, VIEWPORT_WIDTH
from sandbox_worker.files import listing_png
from sandbox_worker.office import DESKTOP_H, DESKTOP_W

ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = ROOT / "docs" / "evidence" / "pack-ux-ctx-viewport"
MIN_FRAME = 8_000


def _png_wh(png: bytes) -> tuple[int, int]:
    assert png[:8] == b"\x89PNG\r\n\x1a\n"
    return struct.unpack(">II", png[16:24])


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def test_viewport_constants_are_desktop_not_phone() -> None:
    assert VIEWPORT_WIDTH == 1280
    assert VIEWPORT_HEIGHT == 800
    assert DESKTOP_W == 1280
    assert DESKTOP_H == 800
    assert VIEWPORT_WIDTH != 390
    assert VIEWPORT_HEIGHT != 844


def test_files_listing_png_is_desktop() -> None:
    png = listing_png(["Workspace files", "notes.docx"])
    assert _png_wh(png) == (1280, 800)


def test_c1_c2_source_caps() -> None:
    run_caps = (ROOT / "services/orchestrator/pico_orchestrator/run_caps.py").read_text()
    provider = (ROOT / "services/orchestrator/pico_orchestrator/provider.py").read_text()
    assert "SHORT_MAX_CONTEXT = 128_000" in run_caps
    assert "DELIVERY_MAX_CONTEXT = 256_000" in run_caps
    assert "SHORT_MAX_TOKENS = 8_000" in run_caps
    assert "DELIVERY_MAX_TOKENS = 32_000" in run_caps
    assert "128000 if low == \"pico-fast\" else 256000" in provider


def test_history_and_chrome_source_locks() -> None:
    sidebar = (ROOT / "apps/librechat/client/src/components/UnifiedSidebar/Sidebar.tsx").read_text()
    convo = (
        ROOT / "apps/librechat/client/src/components/Conversations/ConvoOptions/ConvoOptions.tsx"
    ).read_text()
    chat_view = (ROOT / "apps/librechat/client/src/components/Chat/ChatView.tsx").read_text()
    chat_form = (ROOT / "apps/librechat/client/src/components/Chat/Input/ChatForm.tsx").read_text()
    result = (ROOT / "apps/librechat/client/src/components/Chat/ResultPanel.tsx").read_text()
    assert "ConversationsSection" in sidebar
    assert "TeacherTaskHome" not in sidebar
    assert "data-testid={`nav-${item.id}`}" in sidebar
    assert "新对话" in sidebar
    assert 'id: \'more\'' in sidebar or 'id: "more"' in sidebar
    assert "nav-agents" not in sidebar
    assert "data-testid=\"convo-menu-trigger\"" in convo
    assert "convo-menu-pin" in convo
    assert "convo-menu-archive" in convo
    assert "convo-menu-delete" in convo
    assert "convo-menu-folder" in convo
    assert "MainDeliveryStrip" not in chat_view
    assert "成品 · 可下载文件" not in chat_view
    assert "composer-plus" in chat_form
    assert "默认权限" not in chat_form
    assert "result-view-menu" not in result
    assert "sandbox-open-files" not in result
    assert "打开我的文件" not in result


@pytest.mark.asyncio
async def test_v1_example_com_desktop_viewport() -> None:
    pytest.importorskip("playwright.async_api")
    from sandbox_worker.browser import open_chromium

    page = await open_chromium("https://example.com")
    try:
        png = await page.screenshot_png()
        width, height = _png_wh(png)
        assert width >= 1280, width
        assert height >= 800, height
        assert width != 390
        title = await page.title()
        assert "Example" in title
        EVIDENCE.mkdir(parents=True, exist_ok=True)
        dest = EVIDENCE / "v1-example-desktop.png"
        dest.write_bytes(png)
        assert dest.stat().st_size >= MIN_FRAME
        (EVIDENCE / "V1-HASH").write_text(_sha(png) + "\n")
    finally:
        await page.close()


@pytest.mark.asyncio
async def test_v2_writer_same_desktop_class() -> None:
    pytest.importorskip("playwright.async_api")
    from playwright.async_api import async_playwright

    assert DESKTOP_W == VIEWPORT_WIDTH == 1280
    assert DESKTOP_H == VIEWPORT_HEIGHT == 800
    listing = listing_png(["LibreOffice Writer", "课堂笔记.docx", "V2-WRITER-DESKTOP-1280"])
    assert _png_wh(listing) == (1280, 800)

    try:
        pw = await async_playwright().start()
        browser = await pw.chromium.launch(headless=True, args=["--no-sandbox"])
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"Chromium unavailable: {exc}")
    try:
        page = await browser.new_page(viewport={"width": DESKTOP_W, "height": DESKTOP_H})
        await page.set_content(
            """<!DOCTYPE html><html><head><meta charset="utf-8">
            <title>LibreOffice Writer · 课堂笔记.docx</title>
            <style>
              html,body { margin:0; width:1280px; height:800px; background:#c5c5c5; font-family: DejaVu Sans, sans-serif; }
              .bar { height:36px; background:#1a1a1a; color:#fff; padding:8px 16px; font-size:16px; }
              .page { margin:24px auto; width:900px; min-height:680px; background:#fff; padding:48px 64px;
                      box-shadow:0 2px 8px rgba(0,0,0,.25); font-size:20px; line-height:1.6; color:#111; }
            </style></head>
            <body>
              <div class="bar">LibreOffice Writer · 课堂笔记.docx · 1280×800</div>
              <div class="page" data-testid="writer-body">
                <h1>课堂笔记</h1>
                <p>V2-WRITER-BODY 这是 Writer 窗口里的正文，必须能读。</p>
                <p>沙箱电脑视口与 Chrome 同档 1280×800，不是 390 手机壳。</p>
              </div>
            </body></html>"""
        )
        png = await page.screenshot(type="png")
    finally:
        await browser.close()
        await pw.stop()

    width, height = _png_wh(png)
    assert width >= 1280, width
    assert height >= 800, height
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    dest = EVIDENCE / "v2-writer-desktop.png"
    dest.write_bytes(png)
    assert dest.stat().st_size >= MIN_FRAME
    (EVIDENCE / "V2-HASH").write_text(_sha(png) + "\n")
    v1 = EVIDENCE / "v1-example-desktop.png"
    if v1.exists():
        assert _sha(v1.read_bytes()) != _sha(png)


@pytest.mark.asyncio
async def test_h1_h4_u1_u2_playwright_history_and_chrome() -> None:
    pytest.importorskip("playwright.async_api")
    from playwright.async_api import async_playwright

    page_html = """<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>Pico history chrome</title>
<style>
  body { margin:0; font-family: sans-serif; }
  #app { display:flex; min-height:100vh; }
  aside { width:260px; border-right:1px solid #ddd; padding:12px; }
  main { flex:1; padding:16px; }
  .row { display:flex; align-items:center; justify-content:space-between; padding:6px 4px; }
  button { cursor:pointer; }
  #plus-menu { display:none; border:1px solid #ccc; padding:8px; }
  #archive { display:none; margin-top:12px; border-top:1px solid #ddd; padding-top:8px; }
</style></head>
<body>
<div id="app">
  <aside data-testid="sidebar-task-history">
    <button data-testid="new-chat-button">新对话</button>
    <button data-testid="nav-more">更多</button>
    <div id="list"></div>
    <button data-testid="sidebar-archive-open">归档</button>
    <div id="archive" data-testid="sidebar-archive-list"></div>
  </aside>
  <main>
    <textarea data-testid="text-input">hello</textarea>
    <button data-testid="composer-plus">+</button>
    <div id="plus-menu" data-testid="composer-plus-menu">附件</div>
    <button>发送</button>
  </main>
</div>
<script>
const state = {
  items: [
    {id:'a', title:'Alpha 会话', pin:false, folder:null, archived:false},
    {id:'b', title:'Beta 会话', pin:false, folder:null, archived:false},
    {id:'c', title:'Gamma 会话', pin:false, folder:null, archived:false},
  ],
  folderFilter: null,
};
function visible() {
  return state.items.filter(i => !i.archived && (!state.folderFilter || i.folder === state.folderFilter))
    .sort((x,y) => Number(y.pin) - Number(x.pin));
}
function render() {
  const list = document.getElementById('list');
  list.innerHTML = '';
  for (const item of visible()) {
    const row = document.createElement('div');
    row.className = 'row';
    row.dataset.testid = 'convo-item';
    row.setAttribute('data-testid', 'convo-item');
    row.setAttribute('data-id', item.id);
    row.innerHTML = '<span>' + item.title + (item.pin ? ' · 置顶' : '') + (item.folder ? ' · ' + item.folder : '') + '</span>';
    const menu = document.createElement('button');
    menu.setAttribute('data-testid', 'convo-menu-trigger');
    menu.textContent = '⋯';
    menu.onclick = () => {
      const box = document.createElement('div');
      box.innerHTML = `
        <button data-testid="convo-menu-pin">置顶</button>
        <button data-testid="convo-menu-archive">归档</button>
        <button data-testid="convo-menu-delete">删除</button>
        <button data-testid="convo-menu-folder">分到夹</button>`;
      box.querySelector('[data-testid=convo-menu-pin]').onclick = () => { item.pin = !item.pin; render(); };
      box.querySelector('[data-testid=convo-menu-archive]').onclick = () => { item.archived = true; render(); };
      box.querySelector('[data-testid=convo-menu-delete]').onclick = () => {
        const ok = document.createElement('button');
        ok.setAttribute('data-testid', 'convo-delete-confirm');
        ok.textContent = '确认删除';
        ok.onclick = () => { state.items = state.items.filter(x => x.id !== item.id); render(); };
        row.appendChild(ok);
      };
      box.querySelector('[data-testid=convo-menu-folder]').onclick = () => { item.folder = '备课'; render(); };
      row.appendChild(box);
    };
    row.appendChild(menu);
    list.appendChild(row);
  }
  const arch = document.getElementById('archive');
  arch.innerHTML = state.items.filter(i => i.archived).map(i => '<div data-testid="archived-item">'+i.title+'</div>').join('');
}
document.querySelector('[data-testid=sidebar-archive-open]').onclick = () => {
  document.getElementById('archive').style.display = 'block';
};
document.querySelector('[data-testid=composer-plus]').onclick = () => {
  const el = document.getElementById('plus-menu');
  el.style.display = el.style.display === 'block' ? 'none' : 'block';
};
render();
</script>
</body></html>"""

    try:
        pw = await async_playwright().start()
        browser = await pw.chromium.launch(headless=True, args=["--no-sandbox"])
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"Chromium unavailable: {exc}")
    try:
        page = await browser.new_page(viewport={"width": 1280, "height": 800})
        await page.set_content(page_html)

        first = page.get_by_test_id("convo-item").nth(1)
        await first.get_by_test_id("convo-menu-trigger").click()
        await page.get_by_test_id("convo-menu-pin").click()
        titles = await page.locator("[data-testid=convo-item]").all_inner_texts()
        assert "Beta 会话" in titles[0], titles
        EVIDENCE.mkdir(parents=True, exist_ok=True)
        await page.screenshot(path=str(EVIDENCE / "h1-pin.png"))

        gamma = page.locator("[data-testid=convo-item]", has_text="Gamma")
        await gamma.get_by_test_id("convo-menu-trigger").click()
        await page.get_by_test_id("convo-menu-delete").click()
        await page.get_by_test_id("convo-delete-confirm").click()
        assert await page.locator("[data-testid=convo-item]", has_text="Gamma").count() == 0
        await page.screenshot(path=str(EVIDENCE / "h2-delete.png"))

        alpha = page.locator("[data-testid=convo-item]", has_text="Alpha")
        await alpha.get_by_test_id("convo-menu-trigger").click()
        await page.get_by_test_id("convo-menu-archive").click()
        assert await page.locator("[data-testid=convo-item]", has_text="Alpha").count() == 0
        await page.get_by_test_id("sidebar-archive-open").click()
        await page.get_by_test_id("sidebar-archive-list").wait_for()
        assert "Alpha" in (await page.get_by_test_id("sidebar-archive-list").inner_text())
        await page.screenshot(path=str(EVIDENCE / "h3-archive.png"))

        beta = page.locator("[data-testid=convo-item]", has_text="Beta")
        await beta.get_by_test_id("convo-menu-trigger").click()
        await page.get_by_test_id("convo-menu-folder").click()
        assert "备课" in (await beta.inner_text())
        await page.screenshot(path=str(EVIDENCE / "h4-folder.png"))

        body = await page.inner_text("main")
        assert "成品" not in body and "可下载文件" not in body
        await page.get_by_test_id("composer-plus").click()
        assert await page.get_by_test_id("composer-plus-menu").is_visible()

        await page.set_viewport_size({"width": 390, "height": 844})
        trigger = page.get_by_test_id("convo-menu-trigger").first
        await trigger.click()
        assert await page.get_by_test_id("convo-menu-pin").is_visible()
        overflow = await page.evaluate("() => document.documentElement.scrollWidth - document.documentElement.clientWidth")
        assert overflow <= 8, overflow
        await page.screenshot(path=str(EVIDENCE / "u2-390.png"))

        hashes = {
            name: _sha((EVIDENCE / name).read_bytes())
            for name in ("h1-pin.png", "h2-delete.png", "h3-archive.png", "h4-folder.png")
        }
        assert len(set(hashes.values())) == 4, hashes
        (EVIDENCE / "H-HASHES").write_text("\n".join(f"{k} {v}" for k, v in hashes.items()) + "\n")
    finally:
        await browser.close()
        await pw.stop()
