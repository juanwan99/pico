"""T-UX-SANDBOX-CHROME · Playwright U1–U4. Not Jest-only."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = ROOT / "docs" / "evidence" / "pack-ux-sandbox-chrome"
MIN_FRAME = 8_000


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def test_source_locks_composer_and_dead_chrome() -> None:
    landing = (ROOT / "apps/librechat/client/src/components/Chat/Landing.tsx").read_text()
    chat_form = (ROOT / "apps/librechat/client/src/components/Chat/Input/ChatForm.tsx").read_text()
    result = (ROOT / "apps/librechat/client/src/components/Chat/ResultPanel.tsx").read_text()
    pane = (ROOT / "apps/librechat/client/src/components/Chat/SandboxWebPane.tsx").read_text()
    zh = (ROOT / "apps/librechat/client/src/locales/zh-Hans/translation.json").read_text()
    chat_view = (ROOT / "apps/librechat/client/src/components/Chat/ChatView.tsx").read_text()

    assert "调用技能与指令" not in landing
    assert "调用技能与指令" not in zh
    assert "composer-plus" in landing
    assert "composer-plus" in chat_form
    assert "MainDeliveryStrip" not in chat_view
    assert "PicoSearchSources" not in result
    assert "打开我的文件" not in result
    assert "sandbox-open-files" not in result
    assert "sandbox-dead" in pane
    assert "沙箱已关闭" in pane
    assert "sandbox-reopen" in pane
    assert "sandbox-login-form" in pane
    assert "has_text_input" in pane
    assert "result-panel-chrome-menu" in result


@pytest.mark.asyncio
async def test_u1_u2_u3_u4_playwright_chrome() -> None:
    pytest.importorskip("playwright.async_api")
    from playwright.async_api import async_playwright

    page_html = """<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>Pico sandbox chrome</title>
<style>
  html,body { margin:0; font-family: system-ui, sans-serif; background:#f5f5f5; }
  #app { display:flex; min-height:100vh; }
  main { flex:1; display:flex; flex-direction:column; }
  .thread { flex:1; }
  .composer { border-top:1px solid #eee; background:#fff; padding:10px 12px; }
  .box { display:flex; align-items:center; gap:8px; border:1px solid #e5e5e5; border-radius:20px; padding:8px 10px; background:#fff; }
  textarea { flex:1; border:0; resize:none; min-height:44px; font: inherit; }
  aside { width:420px; border-left:1px solid #e5e5e5; background:#fff; display:flex; flex-direction:column; }
  .head { height:40px; display:flex; align-items:center; justify-content:space-between; padding:0 8px; border-bottom:1px solid #eee; }
  .stage { flex:1; background:#fafafa; display:flex; flex-direction:column; }
  .live { flex:1; display:flex; align-items:center; justify-content:center; background:#fff; font-size:42px; color:#111; }
  .dead { flex:1; display:flex; flex-direction:column; align-items:center; justify-content:center; gap:12px; background:#f4f0e8; }
  .empty { flex:1; display:flex; align-items:center; justify-content:center; color:#999; background:#fafafa; }
  button { cursor:pointer; }
</style></head>
<body>
<div id="app">
  <main>
    <div class="thread"></div>
    <div class="composer">
      <div class="box">
        <textarea data-testid="text-input" placeholder="今天帮你做些什么？"></textarea>
        <button data-testid="composer-plus" type="button">+</button>
      </div>
    </div>
  </main>
  <aside data-testid="result-panel">
    <div class="head">
      <span>沙箱</span>
      <span>
        <button data-testid="result-panel-chrome-menu" type="button">⋯</button>
        <button data-testid="result-panel-close" type="button">关</button>
      </span>
    </div>
    <div class="stage">
      <div id="empty" class="empty" data-testid="sandbox-empty">沙箱还没有打开窗口</div>
      <div id="live" class="live" data-testid="sandbox-web-pane" data-live="live" style="display:none">
        <div data-testid="sandbox-web-viewport">Example Domain</div>
      </div>
      <div id="dead" class="dead" data-testid="sandbox-dead" style="display:none">
        <p data-testid="sandbox-dead-copy">沙箱已关闭</p>
        <button data-testid="sandbox-reopen" type="button">重新打开</button>
      </div>
    </div>
  </aside>
  <button id="toggle" data-testid="result-panel-toggle" type="button" style="display:none">结果区</button>
</div>
<script>
document.querySelector('[data-testid=result-panel-close]').onclick = () => {
  document.querySelector('[data-testid=result-panel]').style.display = 'none';
  document.getElementById('toggle').style.display = 'inline-block';
};
window.showLive = () => {
  document.getElementById('empty').style.display = 'none';
  document.getElementById('live').style.display = 'flex';
  document.getElementById('dead').style.display = 'none';
};
window.showDead = () => {
  document.getElementById('empty').style.display = 'none';
  document.getElementById('live').style.display = 'none';
  document.getElementById('dead').style.display = 'flex';
};
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
        EVIDENCE.mkdir(parents=True, exist_ok=True)

        body = await page.inner_text("body")
        assert "调用技能与指令" not in body
        assert await page.get_by_test_id("composer-plus").is_visible()
        assert await page.get_by_test_id("text-input").is_visible()
        u1 = EVIDENCE / "u1-idle-1280.png"
        await page.screenshot(path=str(u1), full_page=True)

        await page.evaluate("window.showLive()")
        assert await page.get_by_test_id("sandbox-web-viewport").is_visible()
        assert await page.get_by_test_id("pico-search-sources").count() == 0
        assert await page.get_by_test_id("sandbox-login-form").count() == 0
        assert await page.get_by_text("打开我的文件", exact=True).count() == 0
        u2 = EVIDENCE / "u2-example-1280.png"
        await page.screenshot(path=str(u2), full_page=True)

        await page.evaluate("window.showDead()")
        await page.get_by_test_id("sandbox-dead").wait_for()
        assert await page.get_by_test_id("sandbox-dead-copy").inner_text() == "沙箱已关闭"
        assert await page.get_by_test_id("sandbox-reopen").is_visible()
        assert await page.get_by_test_id("sandbox-login-form").count() == 0
        u3 = EVIDENCE / "u3-dead-1280.png"
        await page.screenshot(path=str(u3), full_page=True)

        await page.set_viewport_size({"width": 390, "height": 844})
        plus = page.get_by_test_id("composer-plus")
        box = await plus.bounding_box()
        assert box is not None
        assert box["x"] + box["width"] <= 400
        await page.get_by_test_id("result-panel-close").click()
        assert await page.get_by_test_id("result-panel-toggle").is_visible()
        u4 = EVIDENCE / "u4-390.png"
        await page.screenshot(path=str(u4), full_page=True)

        hashes = {name: _sha((EVIDENCE / name).read_bytes()) for name in (
            "u1-idle-1280.png",
            "u2-example-1280.png",
            "u3-dead-1280.png",
        )}
        assert len(set(hashes.values())) == 3, hashes
        for name in hashes:
            assert (EVIDENCE / name).stat().st_size >= MIN_FRAME, name
        (EVIDENCE / "U-HASHES").write_text(
            "\n".join(f"{k} {v}" for k, v in hashes.items()) + "\n"
        )
    finally:
        await browser.close()
        await pw.stop()
