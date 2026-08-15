"""T-SANDBOX-OPEN-REGRESS · source locks. Word stays Writer."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_open_browser_intent_resolves_default_and_tencent() -> None:
    pane = (ROOT / "apps/librechat/client/src/utils/picoOpenInPane.ts").read_text()
    view = (ROOT / "apps/librechat/client/src/components/Chat/ChatView.tsx").read_text()
    assert "BROWSER_DEFAULT_URL" in pane
    assert "https://example.com/" in pane
    assert "腾讯官网" in pane
    assert "https://www.qq.com/" in pane
    assert "looksLikeOfficeOpen" in pane
    assert "latestUserOpenWebsiteIntent" in view
    assert "websiteIntent" in view
    assert "回复摘要" in view
    # Writer path is not rewritten into a webpage.
    office = pane
    assert "detectOpenOfficeIntent" in office
    assert "kind: 'writer'" in office or 'kind: "writer"' in office


def test_hello_still_not_a_website_intent() -> None:
    pane = (ROOT / "apps/librechat/client/src/utils/picoOpenInPane.ts").read_text()
    assert "looksLikeOfficeOpen" in pane
    # Idle chat must not match the browser aliases.
    assert "浏览器" in pane
