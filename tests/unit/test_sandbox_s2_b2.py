"""S2-B2 sandbox sidecar: stronger isolate, human-in-loop, egress deny."""

from __future__ import annotations

import inspect
import os
import re
import struct
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services"))
sys.path.insert(0, str(ROOT / "services" / "orchestrator"))
sys.path.insert(0, str(ROOT / "services" / "api"))

os.environ.setdefault("PICO_JWT_SECRET", "test-secret-at-least-32-bytes-long!!")

from pico_orchestrator.gateway import ToolError
from pico_orchestrator.sandbox_s2 import PNG_MAGIC, RASTER_HEIGHT, RASTER_WIDTH, encode_rgb_png
from pico_orchestrator.sandbox_view import LOGIN_COPY, render_session_view_html
from pico_orchestrator.tools_builtin import build_default_gateway
from pico_orchestrator.web_guard import parse_public_http_url
from sandbox_worker.browser import ENGINE_NAME, VIEWPORT_HEIGHT, VIEWPORT_WIDTH
from sandbox_worker.ports import SANDBOX_DEFAULT_PORT, assert_listen_port
from sandbox_worker.runtime import HUMAN_LOGIN_COPY, RUNTIME, automation_hostile_reason


@dataclass
class P:
    school_id: str
    membership_id: str
    scopes: list[str]


class MemoryArtifactStore:
    def __init__(self, *, run_id: str | None = None) -> None:
        self.rows: dict[tuple[str, str], list[dict[str, Any]]] = {}
        self._run_id = run_id
        self._task_id = "task-s1"

    def _rows(self, principal: P) -> list[dict[str, Any]]:
        return self.rows.setdefault((principal.school_id, principal.membership_id), [])

    async def write(
        self,
        principal: P,
        *,
        title: str,
        content: str | bytes,
        kind: str,
    ) -> dict[str, Any]:
        import base64

        if isinstance(content, bytes):
            row = {
                "artifact_id": f"art-{sum(map(len, self.rows.values())) + 1}",
                "title": title,
                "content": None,
                "content_base64": base64.b64encode(content).decode("ascii"),
                "kind": kind,
                "run_id": self._run_id,
                "task_id": self._task_id,
                "size": len(content),
                "byte_size": len(content),
                "content_encoding": "base64",
            }
        else:
            body = content
            row = {
                "artifact_id": f"art-{sum(map(len, self.rows.values())) + 1}",
                "title": title,
                "content": body,
                "kind": kind,
                "run_id": self._run_id,
                "task_id": self._task_id,
                "size": len(body.encode("utf-8")),
                "byte_size": len(body.encode("utf-8")),
                "content_encoding": "utf8",
            }
        self._rows(principal).append(row)
        return {k: v for k, v in row.items() if k not in {"content", "content_base64"}}

    async def read(
        self,
        principal: P,
        *,
        artifact_id: str | None,
        title: str | None,
    ) -> dict[str, Any] | None:
        for row in reversed(self._rows(principal)):
            if artifact_id and row["artifact_id"] == artifact_id:
                return row
            if not artifact_id and title and row["title"] == title:
                return row
        return None

    async def list(self, principal: P, *, limit: int) -> list[dict[str, Any]]:
        return [
            {k: v for k, v in row.items() if k != "content"}
            for row in list(reversed(self._rows(principal)))[:limit]
        ]



def _png_wh(png: bytes) -> tuple[int, int]:
    return struct.unpack(">II", png[16:24])


def _viewport_png(tag: int) -> bytes:
    """Contract stand-in: 390×844 viewport, NOT the S2 720×400 HTML raster."""
    r = (40 + tag * 17) % 200
    g = (80 + tag * 9) % 200
    b = (120 + tag * 3) % 200
    rgb = bytes((r, g, b)) * (VIEWPORT_WIDTH * VIEWPORT_HEIGHT)
    return encode_rgb_png(
        VIEWPORT_WIDTH, VIEWPORT_HEIGHT, rgb, text_chunks={"b2": f"viewport-{tag}"}
    )


class FakeChromiumPage:
    """In-process DOM stand-in for gateway/isolation tests.

    Production open uses Playwright Chromium (see sandbox_worker.browser).
    Click on example.com navigates — the old banner raster never changed URL.
    """

    def __init__(self, url: str) -> None:
        parse_public_http_url(url)
        self._url = url
        self._title = "Example Domain"
        self._h1 = "Example Domain"
        self._tag = 1
        self._typed = ""
        self.closed = False

    @property
    def url(self) -> str:
        return self._url

    async def title(self) -> str:
        return self._title

    async def h1(self) -> str:
        return self._h1

    async def screenshot_png(self) -> bytes:
        return _viewport_png(self._tag)

    async def click(self, x: int, y: int) -> None:
        _ = (x, y)
        if "example.com" in self._url:
            self._url = "https://www.iana.org/help/example-domains"
            self._title = "Example Domains"
            self._h1 = "Example domains"
            self._tag += 1

    async def type_text(self, text: str, *, password: bool) -> None:
        if not password:
            self._typed = text
            self._tag += 1
        else:
            self._tag += 1

    async def close(self) -> None:
        self.closed = True


@pytest.fixture
async def embedded_runtime(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("PICO_SANDBOX_URL", "embedded")

    async def fake_open(url: str) -> FakeChromiumPage:
        return FakeChromiumPage(url)

    monkeypatch.setattr(RUNTIME, "_open_browser", fake_open)
    RUNTIME._sessions.clear()
    yield RUNTIME
    for sid in list(RUNTIME._sessions):
        await RUNTIME.destroy(sid)
    RUNTIME._sessions.clear()


@pytest.mark.asyncio
async def test_browser_open_public_page_and_view_copy(embedded_runtime) -> None:
    gw = build_default_gateway(MemoryArtifactStore(run_id="run-b2"))
    owner = P("school-a", "member-a", ["ai:run"])
    opened = await gw.invoke(
        owner, "sandbox_browser_open", {"url": "https://example.com/"}
    )
    assert opened["ok"] is True
    assert opened["session_id"].startswith("sbox_")
    assert opened["title"] == "Example Domain"
    assert opened["engine"] == ENGINE_NAME
    assert HUMAN_LOGIN_COPY in opened["human_copy"]
    assert "不要在聊天里发送密码" in opened["message"]
    assert opened["view_path"].startswith("/v1/sandbox/sessions/")
    shot = await gw.invoke(
        owner, "sandbox_browser_screenshot", {"session_id": opened["session_id"]}
    )
    assert shot["mime"] == "image/png"
    sess = embedded_runtime.get(opened["session_id"])
    assert sess is not None
    assert sess.screenshot_png.startswith(PNG_MAGIC)
    width, height = _png_wh(sess.screenshot_png)
    assert (width, height) == (VIEWPORT_WIDTH, VIEWPORT_HEIGHT)
    assert (width, height) != (RASTER_WIDTH, RASTER_HEIGHT)
    html = render_session_view_html(
        session_id=opened["session_id"],
        screenshot_path="/shot",
        page_url=opened["url"],
        workspace_id=opened["workspace_id"],
        input_path="/input",
    )
    assert LOGIN_COPY in html
    assert "不要在聊天里发送密码" in html


@pytest.mark.asyncio
async def test_browser_open_denies_loopback_18765(embedded_runtime) -> None:
    gw = build_default_gateway(MemoryArtifactStore(run_id="run-b2"))
    owner = P("school-a", "member-a", ["ai:run"])
    with pytest.raises(ToolError) as denied:
        await gw.invoke(
            owner,
            "sandbox_browser_open",
            {"url": "http://127.0.0.1:18765/health"},
        )
    assert denied.value.code == "web.denied"


@pytest.mark.asyncio
async def test_browser_open_denies_intranet_and_metadata(embedded_runtime) -> None:
    gw = build_default_gateway(MemoryArtifactStore(run_id="run-b2"))
    owner = P("school-a", "member-a", ["ai:run"])
    for url in (
        "http://10.1.2.3/",
        "http://169.254.169.254/latest/meta-data/",
        "http://127.0.0.1/",
        "https://pico.aivia.asia/login",
    ):
        with pytest.raises(ToolError) as denied:
            await gw.invoke(owner, "sandbox_browser_open", {"url": url})
        assert denied.value.code == "web.denied"


@pytest.mark.asyncio
async def test_browser_cross_account_denied(embedded_runtime) -> None:
    store = MemoryArtifactStore(run_id="run-b2")
    gw = build_default_gateway(store)
    owner = P("school-a", "member-a", ["ai:run"])
    outsider = P("school-a", "member-b", ["ai:run"])
    opened = await gw.invoke(
        owner, "sandbox_browser_open", {"url": "https://example.com/"}
    )
    with pytest.raises(ToolError) as denied:
        await gw.invoke(
            outsider,
            "sandbox_browser_screenshot",
            {"session_id": opened["session_id"]},
        )
    assert denied.value.code == "sandbox.session_not_found"


@pytest.mark.asyncio
async def test_wechat_jiaowu_fail_honestly_not_required(embedded_runtime) -> None:
    gw = build_default_gateway(MemoryArtifactStore(run_id="run-b2"))
    owner = P("school-a", "member-a", ["ai:run"])
    with pytest.raises(ToolError) as wechat:
        await gw.invoke(
            owner,
            "sandbox_browser_open",
            {"url": "https://open.weixin.qq.com/connect/qrconnect"},
        )
    assert wechat.value.code == "sandbox.site_blocks_automation"
    assert "微信" in wechat.value.message
    assert "不要在聊天里发送密码" in wechat.value.message
    with pytest.raises(ToolError) as jiaowu:
        await gw.invoke(
            owner,
            "sandbox_browser_open",
            {"url": "https://jwxt.example.edu.cn/login"},
        )
    assert jiaowu.value.code == "sandbox.site_blocks_automation"
    assert "教务" in jiaowu.value.message
    assert automation_hostile_reason("https://example.com/") is None


@pytest.mark.asyncio
async def test_password_input_not_echoed(embedded_runtime) -> None:
    owner_sess = await embedded_runtime.open_session(
        school_id="school-a",
        membership_id="member-a",
        run_id="run-b2",
        url="https://example.com/",
    )
    sess = embedded_runtime.require_owner(
        owner_sess["session_id"], school_id="school-a", membership_id="member-a"
    )
    out = await embedded_runtime.apply_input(
        sess, text="super-secret-pass", password=True, field="password"
    )
    blob = str(out)
    assert "super-secret-pass" not in blob
    assert out.get("password") is None
    assert "••••" not in str(out.get("message") or "") or "super-secret-pass" not in blob


@pytest.mark.asyncio
async def test_browser_usage_emit_kind_sandbox_no_money(embedded_runtime) -> None:
    captured: list[dict] = []

    async def fake_record(**kwargs):
        captured.append(kwargs)

    gw = build_default_gateway(MemoryArtifactStore(run_id="run-b2"))
    owner = P("school-a", "member-a", ["ai:run"])
    with patch("app.usage_ledger.record_usage_event", fake_record):
        await gw.invoke(owner, "sandbox_browser_open", {"url": "https://example.com/"})
    rows = [row for row in captured if row.get("kind") == "sandbox"]
    assert rows
    for row in rows:
        assert row.get("source") == "sandbox"
        extra = row.get("extra") or {}
        assert "duration_ms" in extra
        assert extra.get("workspace_id") or extra.get("session_id")
        joined = " ".join(extra.keys()).lower()
        for banned in ("price", "currency", "cost", "charge", "billing", "amount"):
            assert banned not in joined


def test_worker_refuses_product_ports() -> None:
    with pytest.raises(RuntimeError):
        assert_listen_port(8080)
    with pytest.raises(RuntimeError):
        assert_listen_port(18088)
    with pytest.raises(RuntimeError):
        assert_listen_port(18765)
    assert assert_listen_port(SANDBOX_DEFAULT_PORT) == 18767


def test_worker_source_does_not_bind_product_ports() -> None:
    import sandbox_worker.__main__ as mainmod
    import sandbox_worker.app as appmod
    import sandbox_worker.ports as portsmod

    src = inspect.getsource(mainmod) + inspect.getsource(appmod)
    assert "8080" not in src
    assert "18088" not in src
    # ports module names them only to refuse them
    assert "8080" in inspect.getsource(portsmod)
    assert "assert_listen_port" in inspect.getsource(portsmod)


def test_compose_sidecar_is_unprivileged_and_not_on_product_ports() -> None:
    for rel in (
        "docker-compose.host.yml",
        "docker-compose.yml",
        "docker-compose.product.yml",
    ):
        text = (ROOT / rel).read_text(encoding="utf-8")
        assert "pico-sandbox:" in text
        block = _service_block(text, "pico-sandbox")
        assert "privileged: true" not in block
        assert "cap_drop:" in block
        assert "ALL" in block
        assert "no-new-privileges:true" in block
        assert 'user: "65532:65532"' in block
        assert not re.search(r'["\']8080:', block)
        assert not re.search(r'["\']18088:', block)
        assert "18767" in block
        assert "network_mode: host" not in block
        assert "/dev/shm" in block
        assert "PICO_SANDBOX_PROFILE_ROOT" in block
        assert "/tmp/pico-sandbox" in block
    host = (ROOT / "docker-compose.host.yml").read_text(encoding="utf-8")
    assert "PICO_SANDBOX_URL: http://127.0.0.1:18767" in host
    libre = _service_block(host, "librechat")
    sandbox = _service_block(host, "pico-sandbox")
    assert sandbox != libre
    assert "18088" in libre  # product UI stays on LibreChat
    assert "18088" not in sandbox


def _service_block(text: str, name: str) -> str:
    lines = text.splitlines()
    start = None
    for i, line in enumerate(lines):
        if line.startswith(f"  {name}:"):
            start = i
            break
    if start is None:
        raise AssertionError(f"missing service {name}")
    end = len(lines)
    for j in range(start + 1, len(lines)):
        if (
            lines[j].startswith("  ")
            and not lines[j].startswith("    ")
            and lines[j].rstrip().endswith(":")
        ):
            end = j
            break
    return "\n".join(lines[start:end])


@pytest.mark.asyncio
async def test_click_navigates_changes_url_and_screenshot(embedded_runtime) -> None:
    opened = await embedded_runtime.open_session(
        school_id="school-a",
        membership_id="member-a",
        run_id="run-b2",
        url="https://example.com/",
    )
    sess = embedded_runtime.require_owner(
        opened["session_id"], school_id="school-a", membership_id="member-a"
    )
    before_url = sess.url
    before_png = sess.screenshot_png
    before_wh = _png_wh(before_png)
    out = await embedded_runtime.apply_input(sess, click_x=24, click_y=24)
    assert out["clicked"] is True
    assert "iana.org" in sess.url
    assert sess.url != before_url
    assert sess.title != "Example Domain"
    assert sess.screenshot_png != before_png
    assert _png_wh(sess.screenshot_png) == before_wh
    assert "已把点击/输入送进隔离浏览器" not in str(out.get("message") or "")
    assert "Chromium" in str(out.get("message") or "")


@pytest.mark.asyncio
async def test_visible_type_changes_screenshot_password_does_not_echo(
    embedded_runtime,
) -> None:
    opened = await embedded_runtime.open_session(
        school_id="school-a",
        membership_id="member-a",
        run_id="run-b2",
        url="https://example.com/",
    )
    sess = embedded_runtime.require_owner(
        opened["session_id"], school_id="school-a", membership_id="member-a"
    )
    before = sess.screenshot_png
    out = await embedded_runtime.apply_input(sess, text="hello-box")
    assert out["typed"] is True
    assert "hello-box" not in str(out.get("message") or "")
    assert sess.screenshot_png != before


def test_synthetic_banner_path_gone() -> None:
    """Old httpx + _screen_html + raster_html_to_png B2 path must not exist."""
    worker = ROOT / "services" / "sandbox_worker"
    blob = ""
    for path in worker.rglob("*.py"):
        blob += path.read_text(encoding="utf-8") + "\n"
    assert "pico-b2-banner" not in blob
    assert "_screen_html" not in blob
    assert "raster_html_to_png" not in blob
    assert "已把点击/输入送进隔离浏览器" not in blob
    assert "playwright" in blob.lower()
    assert "chromium" in blob.lower()
    runtime_src = (worker / "runtime.py").read_text(encoding="utf-8")
    assert "open_chromium" in runtime_src
    docs = (ROOT / "docs" / "SANDBOX-S2.md").read_text(encoding="utf-8")
    assert "当前默认用用户态抓取" not in docs
    assert "Playwright" in docs or "Chromium" in docs


def test_dockerfile_installs_chromium_not_host_chrome() -> None:
    df = (ROOT / "services" / "sandbox_worker" / "Dockerfile").read_text(encoding="utf-8")
    assert "playwright" in df.lower()
    assert "chromium" in df.lower()
    assert "8080" not in df
    assert "18088" not in df
    assert "PLAYWRIGHT_BROWSERS_PATH" in df
    assert "/tmp/pico-sandbox-profiles" in df
    assert "playwright install" in df.lower() or "chromium" in df.lower()


def test_s2_raster_of_banner_is_not_b2_viewport() -> None:
    """If B2 still re-rastered a subtitle banner, IHDR would be 720×400 — must fail."""
    from pico_orchestrator.sandbox_s2 import raster_html_to_png

    fake = raster_html_to_png(
        "<!DOCTYPE html><html><body>"
        "<div id='pico-b2-banner'>请在此画面自行登录，不要在聊天里发送密码</div>"
        "<p>url: https://example.com/</p><h1>Example Domain</h1></body></html>"
    )
    assert fake.startswith(PNG_MAGIC)
    assert _png_wh(fake) == (RASTER_WIDTH, RASTER_HEIGHT)
    assert _png_wh(fake) != (VIEWPORT_WIDTH, VIEWPORT_HEIGHT)


@pytest.mark.asyncio
async def test_chromium_click_and_type_act_on_dom() -> None:
    """Real Playwright page: click changes URL/title; type fills an input."""
    pytest.importorskip("playwright.async_api")
    from playwright.async_api import async_playwright
    from sandbox_worker.browser import CHROMIUM_ARGS

    try:
        pw = await async_playwright().start()
        browser = await pw.chromium.launch(headless=True, args=list(CHROMIUM_ARGS))
    except Exception as exc:  # noqa: BLE001 — environment may lack browser bits
        pytest.skip(f"Chromium unavailable: {exc}")
    page = await browser.new_page(
        viewport={"width": VIEWPORT_WIDTH, "height": VIEWPORT_HEIGHT}
    )
    try:
        await page.set_content(
            """<!DOCTYPE html>
            <html><head><title>Before</title></head>
            <body style="margin:0;font-family:sans-serif">
              <a id="go" href="#after"
                 style="display:block;width:160px;height:48px;line-height:48px">Go</a>
              <h1>Before</h1>
              <input id="box" style="width:200px;height:32px"/>
              <script>
                window.addEventListener('hashchange', () => {
                  document.title = 'After';
                  document.querySelector('h1').textContent = 'After';
                });
              </script>
            </body></html>"""
        )
        before = await page.screenshot(type="png")
        assert bytes(before).startswith(PNG_MAGIC)
        assert _png_wh(bytes(before)) == (VIEWPORT_WIDTH, VIEWPORT_HEIGHT)
        box = await page.locator("#go").bounding_box()
        assert box is not None
        await page.mouse.click(box["x"] + 8, box["y"] + 8)
        await page.wait_for_function("document.title === 'After'")
        assert await page.title() == "After"
        assert "#after" in page.url
        after_click = await page.screenshot(type="png")
        assert bytes(after_click) != bytes(before)
        await page.locator("#box").click()
        await page.keyboard.type("visible-token")
        assert await page.locator("#box").input_value() == "visible-token"
        after_type = await page.screenshot(type="png")
        assert bytes(after_type) != bytes(after_click)
        assert "visible-token" not in str(after_type[:80])
    finally:
        await browser.close()
        await pw.stop()
