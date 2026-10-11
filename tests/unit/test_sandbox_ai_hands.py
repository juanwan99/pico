"""AI hands on the B2 pane (#1207): act by snapshot ref; humans keep login / pay / submit.

Upstream = Playwright aria snapshot (`aria_snapshot(ref=True)`) + `aria-ref=` selector.
Pico only wires the gateway tool → sidecar → page, masks password values, and
refuses the human-only steps mechanically.
"""

from __future__ import annotations

import os
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
from pico_orchestrator.sandbox_s2 import encode_rgb_png
from pico_orchestrator.sandbox_session_event import public_tool_result, sandbox_session_payload
from pico_orchestrator.tools_builtin import build_default_gateway
from pico_orchestrator.web_guard import parse_public_http_url
from sandbox_worker.browser import (
    HUMAN_REQUIRED_CODE,
    SECRET_MASK,
    SNAPSHOT_MAX_CHARS,
    VIEWPORT_HEIGHT,
    VIEWPORT_WIDTH,
    is_handoff_control,
    is_human_only_field,
    mask_secret_values,
)
from sandbox_worker.runtime import CURRENT_SESSION, RUNTIME

HANDS = (
    "sandbox_browser_snapshot",
    "sandbox_browser_navigate",
    "sandbox_browser_click",
    "sandbox_browser_type",
    "sandbox_browser_select_option",
    "sandbox_browser_press_key",
    "sandbox_browser_wait_for",
)


@dataclass
class P:
    school_id: str
    membership_id: str
    scopes: list[str]
    subject: str = "user"
    role: str = "teacher"


class MemoryArtifactStore:
    def __init__(self, *, run_id: str | None = None) -> None:
        self.run_id = run_id
        self._rows: list[dict[str, Any]] = []

    async def write(self, principal: P, *, title: str, content: bytes, kind: str = "file", **_: Any):
        row = {"artifact_id": f"art_{len(self._rows) + 1}", "title": title, "kind": kind}
        self._rows.append(row)
        return row

    async def read(self, principal: P, artifact_id: str):
        raise ToolError("artifact.not_found", "no")

    async def list(self, principal: P, *, limit: int):
        return self._rows[:limit]


def _png() -> bytes:
    rgb = bytes((200, 200, 200)) * (VIEWPORT_WIDTH * VIEWPORT_HEIGHT)
    return encode_rgb_png(VIEWPORT_WIDTH, VIEWPORT_HEIGHT, rgb)


class FakeFormPage:
    """Stand-in for PlaywrightPage with the BrowserHands surface.

    Refs: s1e1 name box · s1e2 password box · s1e3 captcha box · s1e4 pizza
    select · s1e5 login button · s1e6 next link · s1e7 submit button.
    """

    def __init__(self, url: str) -> None:
        parse_public_http_url(url)
        self._url = url
        self.fields: dict[str, str] = {"s1e1": "", "s1e2": "hunter2", "s1e3": ""}
        self.selected = "small"
        self.keys: list[str] = []
        self.waited: list[tuple[str, str, float]] = []
        self.closed = False

    @property
    def url(self) -> str:
        return self._url

    async def title(self) -> str:
        return "Form"

    async def h1(self) -> str:
        return "报名"

    async def describe_inputs(self) -> dict[str, bool]:
        return {"has_text_input": True, "has_password_input": True}

    async def screenshot_png(self) -> bytes:
        return _png()

    async def click(self, x: int, y: int) -> None:
        _ = (x, y)

    async def type_text(self, text: str, *, password: bool) -> None:
        _ = (text, password)

    async def close(self) -> None:
        self.closed = True

    # ---- hands ----
    def _info(self, ref: str) -> dict[str, Any]:
        table = {
            "s1e1": {"tag": "INPUT", "type": "text", "name": "name"},
            "s1e2": {"tag": "INPUT", "type": "password", "name": "pwd"},
            "s1e3": {"tag": "INPUT", "type": "text", "name": "code", "placeholder": "请输入验证码"},
            "s1e4": {"tag": "SELECT", "type": "select-one"},
            "s1e5": {"tag": "BUTTON", "type": "submit", "text": "登录", "in_login_form": True},
            "s1e6": {"tag": "A", "text": "下一页"},
            "s1e7": {"tag": "INPUT", "type": "submit", "value": "提交报名"},
        }
        import re

        if not re.fullmatch(r"(?:s\d+)?e\d+", ref):
            raise ToolError("tool.invalid_arguments", "ref 必须是快照里的编号")
        if ref not in table:
            raise ToolError("sandbox.ref_stale", "这个编号在当前页面上找不到")
        return table[ref]

    async def snapshot(self) -> str:
        raw = (
            f'- textbox "姓名" [ref=s1e1]: {self.fields["s1e1"]}\n'
            f'- textbox "密码" [ref=s1e2]: {self.fields["s1e2"]}\n'
            f'- textbox "验证码" [ref=s1e3]: {self.fields["s1e3"]}\n'
            f'- combobox "披萨" [ref=s1e4]: {self.selected}\n'
            '- button "登录" [ref=s1e5]\n'
            '- link "下一页" [ref=s1e6]\n'
            '- button "提交报名" [ref=s1e7]\n'
        )
        return mask_secret_values(raw, [self.fields["s1e2"]])

    async def navigate(self, url: str) -> None:
        parse_public_http_url(url)
        self._url = url

    async def click_ref(self, ref: str) -> None:
        info = self._info(ref)
        step = is_handoff_control(info)
        if step:
            from sandbox_worker.browser import human_required

            raise human_required(step)
        if ref == "s1e6":
            self._url = self._url.rstrip("/") + "/page2"

    async def type_ref(self, ref: str, text: str, *, submit: bool) -> None:
        info = self._info(ref)
        step = is_human_only_field(info)
        if step:
            from sandbox_worker.browser import human_required

            raise human_required(step)
        self.fields[ref] = text
        if submit:
            self.keys.append("Enter")

    async def select_ref(self, ref: str, values: list[str]) -> None:
        self._info(ref)
        self.selected = values[0]

    async def press_key(self, key: str) -> None:
        self.keys.append(key)

    async def wait_for(self, *, text: str, text_gone: str, seconds: float) -> None:
        self.waited.append((text, text_gone, seconds))


@pytest.fixture
async def hands_runtime(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("PICO_SANDBOX_URL", "embedded")
    pages: list[FakeFormPage] = []

    async def fake_open(url: str) -> FakeFormPage:
        page = FakeFormPage(url)
        pages.append(page)
        return page

    monkeypatch.setattr(RUNTIME, "_open_browser", fake_open)
    RUNTIME._sessions.clear()
    yield RUNTIME, pages
    for sid in list(RUNTIME._sessions):
        await RUNTIME.destroy(sid)
    RUNTIME._sessions.clear()


def _gw():
    return build_default_gateway(MemoryArtifactStore(run_id="run-hands"))


# ---------------------------------------------------------------- latches


def test_handoff_latch_names_login_pay_submit() -> None:
    assert is_handoff_control({"text": "登录"}) == "登录"
    assert is_handoff_control({"text": "Sign in"})
    assert is_handoff_control({"value": "立即支付"})
    assert is_handoff_control({"text": "提交报名"})
    assert is_handoff_control({"aria_label": "Submit"})
    assert is_handoff_control({"type": "submit", "in_login_form": True}) == "登录"
    assert is_handoff_control({"text": "下一步"}) is None
    assert is_handoff_control({"text": "查询进度", "type": "button"}) is None
    assert is_handoff_control({"type": "submit", "in_login_form": False, "text": "搜索"}) is None


def test_human_only_fields_password_and_captcha() -> None:
    assert is_human_only_field({"type": "password"}) == "密码"
    assert is_human_only_field({"type": "text", "placeholder": "请输入验证码"}) == "验证码"
    assert is_human_only_field({"type": "text", "name": "captcha"}) == "验证码"
    assert is_human_only_field({"type": "text", "autocomplete": "one-time-code"}) == "验证码"
    assert is_human_only_field({"type": "text", "name": "phone"}) is None


def test_mask_secret_values_hides_password_text() -> None:
    raw = '- textbox "密码" [ref=s1e2]: hunter2\n- text: hunter2 appears again\n'
    out = mask_secret_values(raw, ["hunter2", ""])
    assert "hunter2" not in out
    assert out.count(SECRET_MASK) == 2
    assert mask_secret_values("plain", []) == "plain"


# ---------------------------------------------------------------- gateway → runtime


@pytest.mark.asyncio
async def test_snapshot_uses_current_desk_and_masks_password(hands_runtime) -> None:
    runtime, _pages = hands_runtime
    gw = _gw()
    owner = P("school-a", "member-a", ["ai:run"])
    opened = await gw.invoke(owner, "sandbox_browser_open", {"url": "https://example.com/"})
    assert opened["session_id"].startswith("sbox_")
    # No session_id → the caller's own desk ("current").
    out = await gw.invoke(owner, "sandbox_browser_snapshot", {})
    assert out["ok"] is True
    assert out["session_id"] == opened["session_id"]
    assert out["action"] == "snapshot"
    assert "[ref=s1e1]" in out["snapshot"]
    assert "hunter2" not in out["snapshot"]
    assert SECRET_MASK in out["snapshot"]
    # The ledger event still points the pane at the same session.
    payload = sandbox_session_payload(public_tool_result(out))
    assert payload and payload["session_id"] == opened["session_id"]
    banned = {"cookie", "cookies", "password", "passwd", "secret", "credential"}
    assert not (banned & {k.lower() for k in out})
    assert runtime.require_owner(CURRENT_SESSION, school_id="school-a", membership_id="member-a")


@pytest.mark.asyncio
async def test_fill_select_click_act_on_page_and_return_fresh_snapshot(hands_runtime) -> None:
    _, pages = hands_runtime
    gw = _gw()
    owner = P("school-a", "member-a", ["ai:run"])
    await gw.invoke(owner, "sandbox_browser_open", {"url": "https://example.com/"})
    typed = await gw.invoke(
        owner, "sandbox_browser_type", {"ref": "s1e1", "text": "张三", "element": "姓名"}
    )
    assert pages[0].fields["s1e1"] == "张三"
    assert '[ref=s1e1]: 张三' in typed["snapshot"]
    picked = await gw.invoke(
        owner, "sandbox_browser_select_option", {"ref": "s1e4", "values": ["medium"]}
    )
    assert pages[0].selected == "medium"
    assert "medium" in picked["snapshot"]
    clicked = await gw.invoke(owner, "sandbox_browser_click", {"ref": "s1e6"})
    assert clicked["url"].endswith("/page2")
    pressed = await gw.invoke(owner, "sandbox_browser_press_key", {"key": "Tab"})
    assert pages[0].keys == ["Tab"]
    assert pressed["action"] == "press_key"
    waited = await gw.invoke(owner, "sandbox_browser_wait_for", {"text": "完成", "time": 2})
    assert pages[0].waited == [("完成", "", 2.0)]
    assert waited["action"] == "wait_for"


@pytest.mark.asyncio
async def test_login_pay_submit_and_password_stay_with_the_human(hands_runtime) -> None:
    _, pages = hands_runtime
    gw = _gw()
    owner = P("school-a", "member-a", ["ai:run"])
    await gw.invoke(owner, "sandbox_browser_open", {"url": "https://example.com/"})
    for args in (
        ("sandbox_browser_click", {"ref": "s1e5"}),  # 登录 button
        ("sandbox_browser_click", {"ref": "s1e7"}),  # 提交报名
        ("sandbox_browser_type", {"ref": "s1e2", "text": "pw"}),  # password box
        ("sandbox_browser_type", {"ref": "s1e3", "text": "1234"}),  # captcha box
    ):
        with pytest.raises(ToolError) as exc:
            await gw.invoke(owner, *args)
        assert exc.value.code == HUMAN_REQUIRED_CODE
        assert "自己" in exc.value.message
    assert pages[0].fields["s1e2"] == "hunter2"  # untouched
    assert pages[0].fields["s1e3"] == ""
    assert pages[0].url == "https://example.com/"


@pytest.mark.asyncio
async def test_navigate_denies_intranet_and_needs_open_session(hands_runtime) -> None:
    gw = _gw()
    owner = P("school-a", "member-a", ["ai:run"])
    with pytest.raises(ToolError) as exc:
        await gw.invoke(owner, "sandbox_browser_snapshot", {})
    assert exc.value.code == "sandbox.session_not_found"
    assert "sandbox_browser_open" in exc.value.message
    await gw.invoke(owner, "sandbox_browser_open", {"url": "https://example.com/"})
    for bad in ("http://127.0.0.1:18765/health", "http://169.254.169.254/latest/meta-data"):
        with pytest.raises(ToolError) as exc:
            await gw.invoke(owner, "sandbox_browser_navigate", {"url": bad})
        assert exc.value.code == "web.denied"
    moved = await gw.invoke(owner, "sandbox_browser_navigate", {"url": "https://example.org/x"})
    assert moved["url"] == "https://example.org/x"
    with pytest.raises(ToolError) as exc:
        await gw.invoke(owner, "sandbox_browser_click", {"ref": "zzz"})
    assert exc.value.code == "tool.invalid_arguments"


@pytest.mark.asyncio
async def test_other_tenant_cannot_act_on_my_desk(hands_runtime) -> None:
    gw = _gw()
    owner = P("school-a", "member-a", ["ai:run"])
    other = P("school-b", "member-b", ["ai:run"])
    opened = await gw.invoke(owner, "sandbox_browser_open", {"url": "https://example.com/"})
    with pytest.raises(ToolError) as exc:
        await gw.invoke(other, "sandbox_browser_click", {"ref": "s1e6", "session_id": opened["session_id"]})
    assert exc.value.code == "sandbox.forbidden"
    with pytest.raises(ToolError) as exc:
        await gw.invoke(other, "sandbox_browser_snapshot", {})
    assert exc.value.code == "sandbox.session_not_found"


@pytest.mark.asyncio
async def test_hands_bill_as_sandbox_usage(hands_runtime) -> None:
    captured: list[dict] = []

    async def fake_record(**kwargs):
        captured.append(kwargs)

    gw = _gw()
    owner = P("school-a", "member-a", ["ai:run"])
    with patch("app.usage_ledger.record_usage_event", fake_record):
        await gw.invoke(owner, "sandbox_browser_open", {"url": "https://example.com/"})
        await gw.invoke(owner, "sandbox_browser_type", {"ref": "s1e1", "text": "secret-name"})
    rows = [r for r in captured if (r.get("extra") or {}).get("tool") == "sandbox_browser_type"]
    assert rows and rows[0].get("kind") == "sandbox"
    extra = rows[0]["extra"]
    assert extra["phase"] == "browser_type"
    assert "secret-name" not in str(extra)


# ---------------------------------------------------------------- real Chromium


@pytest.mark.asyncio
async def test_real_chromium_snapshot_refs_fill_select_and_handoff() -> None:
    """Playwright 1.52 `aria_snapshot(ref=True)` + `aria-ref=` drive a real form."""
    pytest.importorskip("playwright.async_api")
    from playwright.async_api import async_playwright
    from sandbox_worker.browser import CHROMIUM_ARGS, PlaywrightPage

    try:
        pw = await async_playwright().start()
        browser = await pw.chromium.launch(headless=True, args=list(CHROMIUM_ARGS))
    except Exception as exc:  # noqa: BLE001 — environment may lack browser bits
        pytest.skip(f"Chromium unavailable: {exc}")
    context = await browser.new_context(viewport={"width": VIEWPORT_WIDTH, "height": VIEWPORT_HEIGHT})
    page = await context.new_page()
    try:
        await page.set_content(
            """<!DOCTYPE html><html><head><title>Form</title></head><body>
            <h1>报名</h1>
            <form onsubmit="return false">
              <label>姓名<input name="name"></label>
              <label>密码<input type="password" name="pwd" value="secret123"></label>
              <label>验证码<input name="code" placeholder="请输入验证码"></label>
              <label>披萨<select name="size"><option value="small">小</option>
                <option value="medium">中</option></select></label>
              <button type="button" id="next">下一步</button>
              <button type="submit">提交报名</button>
              <a id="go" href="#after">帮助</a>
            </form>
            <script>
              document.getElementById('next').addEventListener('click', () => {
                document.querySelector('h1').textContent = '第二步';
              });
            </script></body></html>"""
        )
        hands = PlaywrightPage(context, page, Path("/tmp/pico-test-profile-unused"))
        snap = await hands.snapshot()
        assert "[ref=" in snap
        assert "secret123" not in snap
        assert SECRET_MASK in snap
        assert len(snap) <= SNAPSHOT_MAX_CHARS

        def ref_of(label: str) -> str:
            import re

            m = re.search(rf'"{label}" \[ref=([a-z0-9]+)\]', snap)
            assert m, snap
            return m.group(1)

        await hands.type_ref(ref_of("姓名"), "张三", submit=False)
        assert await page.locator("input[name=name]").input_value() == "张三"
        await hands.select_ref(ref_of("披萨"), ["中"])
        assert await page.locator("select").input_value() == "medium"
        await hands.click_ref(ref_of("下一步"))
        assert await hands.h1() == "第二步"
        for label in ("密码", "验证码"):
            with pytest.raises(ToolError) as exc:
                await hands.type_ref(ref_of(label), "x", submit=False)
            assert exc.value.code == HUMAN_REQUIRED_CODE
        assert await page.locator("input[name=pwd]").input_value() == "secret123"
        with pytest.raises(ToolError) as exc:
            await hands.click_ref(ref_of("提交报名"))
        assert exc.value.code == HUMAN_REQUIRED_CODE
        await hands.click_ref(ref_of("帮助"))
        assert page.url.endswith("#after")
        await hands.wait_for(text="第二步", text_gone="", seconds=2)
        with pytest.raises(ToolError) as exc:
            await hands.wait_for(text="不存在的字", text_gone="", seconds=0.5)
        assert exc.value.code == "sandbox.action_failed"
        # Refs from a stale snapshot are a clean error, not a crash.
        with pytest.raises(ToolError) as exc:
            await hands.click_ref("s9e999")
        assert exc.value.code == "sandbox.ref_stale"
    finally:
        await context.close()
        await browser.close()
        await pw.stop()
