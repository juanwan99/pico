"""Thin Playwright/Chromium adapter for B2.

Upstream: Playwright Chromium. Pico only wires web_guard, the teacher's saved
login (Playwright ``storage_state``), screenshots, and human-in-the-loop input.
Not a second agent loop.
"""

from __future__ import annotations

import asyncio
import difflib
import json
import logging
import os
import re
import shutil
import tempfile
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any, Protocol

from pico_orchestrator.gateway import ToolError
from pico_orchestrator.web_guard import parse_public_http_url

logger = logging.getLogger(__name__)

ENGINE_NAME = "playwright-chromium"
# Sandbox desktop (teacher's computer), not the phone shell.
VIEWPORT_WIDTH = 1280
VIEWPORT_HEIGHT = 800
PNG_MAGIC = b"\x89PNG\r\n\x1a\n"
GOTO_TIMEOUT_MS = 20_000
# AI hands (#1207): aria snapshot with Playwright refs. Bounded so one page
# cannot flood the model context.
SNAPSHOT_MAX_CHARS = 30_000
SECRET_MASK = "••••"
WAIT_MAX_S = 30.0
# Live pane (#1215): Chromium pushes a JPEG on each repaint (CDP screencast).
SCREENCAST_QUALITY = 70
SCROLL_MAX_PX = 2000
# Tabs (#1217): a link that opens a new tab becomes the current page, like
# Playwright MCP. Bounded so a popup storm cannot eat the sidecar.
MAX_TABS = 8
DIALOG_NOTE_MAX = 200
# Whole-form fill + attachments (#1219), Playwright MCP fill_form / file_upload.
FILL_FORM_MAX = 40
UPLOAD_MAX_FILES = 10
UPLOAD_MAX_BYTES = 25 * 1024 * 1024
# Snapshot deltas (#1222): after an action only new / changed lines go back,
# like Playwright MCP's incremental snapshot. Playwright 1.52 renumbers refs on
# every snapshot, so the book hands the AI stable `eN` refs and maps them back.
DELTA_FULL_RATIO = 0.5
PW_REF_RE = re.compile(r"\[ref=(s\d+e\d+)\]")
STABLE_REF_RE = re.compile(r"e(\d+)")
CHECK_ROLES = frozenset({"checkbox", "radio", "switch", "menuitemcheckbox", "menuitemradio"})
TRUE_WORDS = frozenset({"true", "1", "yes", "y", "on", "checked", "是", "对", "勾选", "选中"})
HUMAN_KEYS = frozenset(
    {
        "Enter", "Tab", "Backspace", "Delete", "Escape",
        "ArrowUp", "ArrowDown", "ArrowLeft", "ArrowRight", "PageUp", "PageDown",
    }
)
# Human-only steps: typing a password or captcha, and paying. Everything else
# (login button, submit) the AI may click (owner 2026-10-11 09:17「简单、有效」).
HANDOFF_RE = re.compile(
    r"支付|付款|缴费|付费|\bpay\b|checkout|结算",
    re.IGNORECASE,
)
CAPTCHA_RE = re.compile(r"验证码|captcha|短信码|动态码", re.IGNORECASE)
HUMAN_REQUIRED_CODE = "sandbox.human_required"
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

    async def describe_inputs(self) -> dict[str, bool]: ...

    async def screenshot_png(self) -> bytes: ...

    async def click(self, x: int, y: int) -> None: ...

    async def type_text(self, text: str, *, password: bool) -> None: ...

    async def close(self) -> None: ...


class BrowserHands(Protocol):
    """AI hands on the same page (#1207). Shape follows Playwright MCP."""

    async def snapshot(self) -> str: ...

    async def navigate(self, url: str) -> None: ...

    async def click_ref(self, ref: str, *, double: bool = False) -> None: ...

    async def hover_ref(self, ref: str) -> None: ...

    async def navigate_back(self) -> None: ...

    async def tabs(self, action: str, index: int) -> list[dict[str, Any]]: ...

    def take_dialogs(self) -> list[str]: ...

    async def fill_form(self, fields: list[dict[str, Any]]) -> list[str]: ...

    async def upload_files(self, ref: str, files: list[tuple[str, str, bytes]]) -> None: ...

    async def type_ref(self, ref: str, text: str, *, submit: bool) -> None: ...

    async def select_ref(self, ref: str, values: list[str]) -> None: ...

    async def press_key(self, key: str) -> None: ...

    async def wait_for(self, *, text: str, text_gone: str, seconds: float) -> None: ...


class RefBook:
    """Stable refs across snapshots of one browser window (#1222).

    Lines that survive a re-snapshot keep their `eN`; the AI's `eN` maps to the
    Playwright ref of the latest snapshot. Raw Playwright refs pass through.
    """

    def __init__(self) -> None:
        self._page: Any = None
        self._keys: list[str] = []
        self._ids: list[int] = []
        self._to_pw: dict[int, str] = {}
        self._next = 1

    def resolve(self, ref: str) -> str:
        token = (ref or "").strip()
        m = STABLE_REF_RE.fullmatch(token)
        if m and int(m.group(1)) in self._to_pw:
            return self._to_pw[int(m.group(1))]
        return token

    def update(self, raw: str, *, page: Any = None) -> tuple[str, str | None]:
        """Returns (full snapshot with stable refs, delta or None when the full
        snapshot should go back: new page, or most of it changed)."""
        lines = raw.splitlines()
        keys = [PW_REF_RE.sub("[ref]", ln) for ln in lines]
        fresh = page != self._page or not self._keys
        old_keys, old_ids = ([], []) if fresh else (self._keys, self._ids)
        ids = [0] * len(lines)
        changed = [True] * len(lines)
        removed = 0
        matcher = difflib.SequenceMatcher(None, old_keys, keys, autojunk=False)
        for tag, i1, i2, j1, j2 in matcher.get_opcodes():
            removed += max(0, (i2 - i1) - (j2 - j1))
            for k in range(min(i2 - i1, j2 - j1)):
                if tag == "equal":
                    ids[j1 + k], changed[j1 + k] = old_ids[i1 + k], False
                elif tag == "replace" and keys[j1 + k].split("[ref]")[0] == old_keys[i1 + k].split("[ref]")[0]:
                    ids[j1 + k] = old_ids[i1 + k]  # same element, new value
        to_pw: dict[int, str] = {}
        out: list[str] = []
        for j, line in enumerate(lines):
            m = PW_REF_RE.search(line)
            if m:
                if not ids[j]:
                    ids[j], self._next = self._next, self._next + 1
                to_pw[ids[j]] = m.group(1)
                line = line[: m.start()] + f"[ref=e{ids[j]}]" + line[m.end() :]
            out.append(line)
        self._page, self._keys, self._ids, self._to_pw = page, keys, ids, to_pw
        full = "\n".join(out)
        n_changed = sum(changed)
        if fresh or n_changed > len(lines) * DELTA_FULL_RATIO:
            return full, None
        if not n_changed and not removed:
            return full, "（页面结构没变，编号照用。）"
        keep: set[int] = set()
        for j in (j for j, c in enumerate(changed) if c):
            keep.add(j)
            depth = len(out[j]) - len(out[j].lstrip())
            for a in range(j - 1, -1, -1):
                d = len(out[a]) - len(out[a].lstrip())
                if d < depth:
                    keep.add(a)
                    depth = d
        head = f"（只列新出现或改了的行和它们的上级；没列的没变，编号照用。消失 {removed} 行。）"
        return full, "\n".join([head] + [out[j] for j in sorted(keep)])


def mask_secret_values(snapshot: str, secrets: list[str]) -> str:
    """Password field values must never reach the model (#1207)."""
    out = snapshot
    for value in secrets:
        if value:
            out = out.replace(value, SECRET_MASK)
    return out


def human_required(step: str) -> ToolError:
    return ToolError(
        HUMAN_REQUIRED_CODE,
        f"这一步（{step}）要老师自己在沙箱画面里做：输密码、填验证码、付款只能人来。"
        "做完后再调用 sandbox_browser_snapshot 继续。",
    )


def is_handoff_control(info: dict[str, Any]) -> str | None:
    """Return the human-only step name for a clickable element (payment), else None."""
    text = " ".join(
        str(info.get(k) or "") for k in ("text", "value", "aria_label", "title", "name")
    )
    if HANDOFF_RE.search(text):
        return text.strip()[:40] or "付款"
    return None


def is_checked_value(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value or "").strip().lower() in TRUE_WORDS


def read_login_state(path: Path | None) -> dict[str, Any] | None:
    """The teacher's saved browser login (cookies + localStorage), or None."""
    if path is None or not path.is_file():
        return None
    try:
        state = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return state if isinstance(state, dict) else None


def is_human_only_field(info: dict[str, Any]) -> str | None:
    if str(info.get("type") or "").lower() == "password":
        return "密码"
    text = " ".join(
        str(info.get(k) or "")
        for k in ("name", "placeholder", "aria_label", "label", "autocomplete", "id")
    )
    if CAPTCHA_RE.search(text) or "one-time-code" in text:
        return "验证码"
    return None


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
    """One Chromium context. Login is saved to the teacher's own disk, not host HOME."""

    def __init__(self, context: Any, page: Any, profile_dir: Path) -> None:
        self._context = context
        self._page = page
        self._profile_dir = profile_dir
        # Bumps whenever the current tab changes; the live pane re-attaches (#1217).
        self.page_token = 0
        self._dialogs: list[str] = []
        for existing in list(getattr(context, "pages", []) or []):
            self._watch(existing)
        if page not in list(getattr(context, "pages", []) or []):
            self._watch(page)
        context.on("page", self._on_new_page)

    @property
    def url(self) -> str:
        return str(self._page.url or "")

    # ---- Tabs + dialogs (#1217). Upstream = Playwright context/page events. ----

    def _watch(self, page: Any) -> None:
        page.on("dialog", self._on_dialog)
        page.on("close", self._on_close)

    def _open_pages(self) -> list[Any]:
        return [p for p in self._context.pages if not p.is_closed()]

    def _use(self, page: Any) -> None:
        if page is not self._page:
            self._page = page
            self.page_token += 1

    def _on_new_page(self, page: Any) -> None:
        """A link with target=_blank / window.open: the new tab becomes current."""
        self._watch(page)
        if len(self._open_pages()) > MAX_TABS:
            asyncio.ensure_future(page.close())
            return
        self._use(page)

    def _on_close(self, page: Any) -> None:
        if page is self._page:
            rest = self._open_pages()
            if rest:
                self._use(rest[-1])

    async def _on_dialog(self, dialog: Any) -> None:
        """alert / confirm / prompt: press OK. The AI's click already was the intent;
        payment buttons are refused before the click. Without a handler Playwright
        dismisses, so confirm() silently returns false and the form never submits."""
        note = f"{dialog.message or ''}".strip()[:DIALOG_NOTE_MAX]
        self._dialogs.append(note or dialog.type)
        try:
            await dialog.accept()
        except Exception:
            logger.debug("dialog accept failed", exc_info=True)

    def take_dialogs(self) -> list[str]:
        out, self._dialogs = self._dialogs, []
        return out

    async def _tab_rows(self) -> list[dict[str, Any]]:
        rows = []
        for i, page in enumerate(self._open_pages()):
            try:
                title = str(await page.title() or "")
            except Exception:  # noqa: BLE001
                title = ""
            rows.append(
                {"index": i, "url": str(page.url or ""), "title": title[:120],
                 "current": page is self._page}
            )
        return rows

    async def tabs(self, action: str, index: int) -> list[dict[str, Any]]:
        verb = (action or "list").strip().lower()
        pages = self._open_pages()
        if verb not in {"list", "select", "close"}:
            raise ToolError("tool.invalid_arguments", "tabs 的 action 只能是 list / select / close")
        if verb != "list":
            if not 0 <= int(index) < len(pages):
                raise ToolError("tool.invalid_arguments", f"没有第 {index} 个标签页（共 {len(pages)} 个，从 0 数）")
            target = pages[int(index)]
            if verb == "select":
                self._use(target)
                await target.bring_to_front()
            else:
                if len(pages) == 1:
                    raise ToolError("tool.invalid_arguments", "只剩这一个标签页，不能关")
                await target.close()
            assert_http_public_or_internal(self.url)
        return await self._tab_rows()

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

    async def describe_inputs(self) -> dict[str, bool]:
        """Visible text/password fields on the live page. Login chrome uses this."""
        try:
            raw = await self._page.evaluate(
                """() => {
                    const visible = (el) => {
                        const s = window.getComputedStyle(el);
                        const r = el.getBoundingClientRect();
                        return (
                            s.display !== 'none' &&
                            s.visibility !== 'hidden' &&
                            r.width > 1 &&
                            r.height > 1
                        );
                    };
                    const nodes = Array.from(
                        document.querySelectorAll('input, textarea, [contenteditable="true"]')
                    ).filter(visible);
                    const skip = new Set([
                        'hidden', 'submit', 'button', 'checkbox', 'radio',
                        'file', 'image', 'reset', 'range', 'color',
                    ]);
                    let hasText = false;
                    let hasPassword = false;
                    for (const el of nodes) {
                        const tag = String(el.tagName || '').toUpperCase();
                        if (tag === 'TEXTAREA' || el.isContentEditable) {
                            hasText = true;
                            continue;
                        }
                        if (tag !== 'INPUT') {
                            continue;
                        }
                        const t = String(el.type || 'text').toLowerCase();
                        if (t === 'password') {
                            hasPassword = true;
                            hasText = true;
                        } else if (!skip.has(t)) {
                            hasText = true;
                        }
                    }
                    return { has_text_input: hasText, has_password_input: hasPassword };
                }"""
            )
            if isinstance(raw, dict):
                return {
                    "has_text_input": bool(raw.get("has_text_input")),
                    "has_password_input": bool(raw.get("has_password_input")),
                }
        except Exception:
            logger.debug("describe_inputs failed", exc_info=True)
        return {"has_text_input": False, "has_password_input": False}

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

    # ---- AI hands (#1207). Upstream = Playwright aria snapshot + aria-ref. ----

    def _ref(self, ref: str) -> Any:
        token = (ref or "").strip()
        if not re.fullmatch(r"(?:s\d+)?e\d+", token):
            raise ToolError("tool.invalid_arguments", "ref 必须是快照里的编号，例如 e8")
        return self._page.locator(f"aria-ref={token}")

    async def _password_values(self) -> list[str]:
        try:
            raw = await self._page.evaluate(
                """() => Array.from(document.querySelectorAll('input[type="password"]'))
                        .map((el) => String(el.value || ''))
                        .filter((v) => v.length > 0)"""
            )
            return [str(v) for v in raw] if isinstance(raw, list) else []
        except Exception:
            logger.debug("password value scan failed", exc_info=True)
            return []

    async def snapshot(self) -> str:
        try:
            text = await self._page.locator("body").aria_snapshot(ref=True, timeout=10_000)
        except Exception as exc:
            raise ToolError("sandbox.raster_failed", "隔离 Chromium 未能生成页面快照") from exc
        text = mask_secret_values(str(text or ""), await self._password_values())
        if len(text) > SNAPSHOT_MAX_CHARS:
            text = text[:SNAPSHOT_MAX_CHARS] + "\n- text: …（快照过长已截断，可滚动或翻页后再取）"
        return text

    async def navigate(self, url: str) -> None:
        parse_public_http_url(url)
        try:
            response = await self._page.goto(
                url, wait_until="domcontentloaded", timeout=GOTO_TIMEOUT_MS
            )
        except Exception as exc:
            raise ToolError("sandbox.fetch_failed", "无法在隔离 Chromium 打开该公开页") from exc
        if response is not None and response.status >= 400:
            raise ToolError("sandbox.fetch_failed", f"公开页返回 HTTP {response.status}")
        assert_http_public_or_internal(self.url)

    async def _element_info(self, loc: Any) -> dict[str, Any]:
        try:
            raw = await loc.evaluate(
                """(el) => {
                    const labelText = (() => {
                        try {
                            const labels = el.labels ? Array.from(el.labels) : [];
                            return labels.map((l) => l.innerText || '').join(' ');
                        } catch (e) { return ''; }
                    })();
                    return {
                        tag: String(el.tagName || ''),
                        role: String(el.getAttribute('role') || ''),
                        type: String(el.type || el.getAttribute('type') || ''),
                        name: String(el.getAttribute('name') || ''),
                        id: String(el.id || ''),
                        text: String((el.innerText || '').slice(0, 120)),
                        value: el.tagName === 'INPUT' && ['submit','button','image'].includes(String(el.type||'').toLowerCase()) ? String(el.value || '') : '',
                        aria_label: String(el.getAttribute('aria-label') || ''),
                        title: String(el.getAttribute('title') || ''),
                        placeholder: String(el.getAttribute('placeholder') || ''),
                        autocomplete: String(el.getAttribute('autocomplete') || ''),
                        label: labelText,
                    };
                }""",
                timeout=5_000,
            )
            return dict(raw) if isinstance(raw, dict) else {}
        except Exception as exc:
            raise ToolError(
                "sandbox.ref_stale",
                "这个编号在当前页面上找不到（页面变了）。先调用 sandbox_browser_snapshot 取新编号。",
            ) from exc

    async def _settle(self, before: str) -> None:
        for _ in range(25):
            if str(self._page.url or "") != before:
                try:
                    await self._page.wait_for_load_state("domcontentloaded", timeout=5_000)
                except Exception:
                    logger.debug("navigation load wait failed", exc_info=True)
                break
            await asyncio.sleep(0.1)
        assert_http_public_or_internal(self.url)

    async def click_ref(self, ref: str, *, double: bool = False) -> None:
        loc = self._ref(ref)
        info = await self._element_info(loc)
        step = is_handoff_control(info)
        if step:
            raise human_required(step)
        before = self.url
        try:
            if double:
                await loc.dblclick(timeout=5_000)
            else:
                await loc.click(timeout=5_000)
        except Exception as exc:
            raise ToolError(
                "sandbox.action_failed", "点不到这个元素（可能被遮住或已消失）"
            ) from exc
        await self._settle(before)

    async def hover_ref(self, ref: str) -> None:
        """Menus that open on hover (#1217)."""
        loc = self._ref(ref)
        await self._element_info(loc)
        try:
            await loc.hover(timeout=5_000)
        except Exception as exc:
            raise ToolError("sandbox.action_failed", "移不到这个元素上（可能被遮住或已消失）") from exc

    async def navigate_back(self) -> None:
        before = self.url
        try:
            await self._page.go_back(wait_until="domcontentloaded", timeout=GOTO_TIMEOUT_MS)
        except Exception as exc:
            raise ToolError("sandbox.fetch_failed", "后退失败（上一页打不开）") from exc
        if self.url == before:
            raise ToolError("sandbox.action_failed", "这个标签页没有上一页")
        assert_http_public_or_internal(self.url)

    async def type_ref(self, ref: str, text: str, *, submit: bool) -> None:
        # Never log `text`.
        loc = self._ref(ref)
        info = await self._element_info(loc)
        step = is_human_only_field(info)
        if step:
            raise human_required(step)
        before = self.url
        try:
            await loc.fill(text, timeout=5_000)
        except Exception as exc:
            raise ToolError("sandbox.action_failed", "这个元素不能输入文字") from exc
        if submit:
            await loc.press("Enter", timeout=5_000)
            await self._settle(before)

    async def fill_form(self, fields: list[dict[str, Any]]) -> list[str]:
        """Fill many fields in one call (#1219). Each element decides how: text box
        ``fill``, checkbox / radio ``set_checked``, dropdown ``select_option``.
        Password / captcha fields are left for the teacher and named back. Never logs values."""
        if not fields or len(fields) > FILL_FORM_MAX:
            raise ToolError("tool.invalid_arguments", f"fields 要 1–{FILL_FORM_MAX} 格")
        left: list[str] = []
        for i, field in enumerate(fields, start=1):
            ref = str(field.get("ref") or "")
            value = field.get("value")
            loc = self._ref(ref)
            info = await self._element_info(loc)
            step = is_human_only_field(info)
            if step:
                left.append(step)
                continue
            tag = str(info.get("tag") or "").upper()
            kind = str(info.get("type") or "").lower()
            role = str(info.get("role") or "").lower()
            try:
                if kind in {"checkbox", "radio"} or role in CHECK_ROLES:
                    await loc.set_checked(is_checked_value(value), timeout=5_000)
                elif tag == "SELECT":
                    picks = [str(v) for v in value] if isinstance(value, list) else [str(value)]
                    await self.select_ref(ref, picks)
                else:
                    await loc.fill("" if value is None else str(value), timeout=5_000)
            except ToolError:
                raise
            except Exception as exc:
                raise ToolError(
                    "sandbox.action_failed", f"第 {i} 格（{ref}）填不进去，前面 {i - 1} 格已填"
                ) from exc
        return left

    async def upload_files(self, ref: str, files: list[tuple[str, str, bytes]]) -> None:
        """Attach files (#1219): a file input takes them directly; an「上传」button opens
        the file chooser. Bytes come from the teacher's disk / ledger, not the host."""
        if not files or len(files) > UPLOAD_MAX_FILES:
            raise ToolError("tool.invalid_arguments", f"一次传 1–{UPLOAD_MAX_FILES} 个文件")
        if sum(len(b) for _, _, b in files) > UPLOAD_MAX_BYTES:
            raise ToolError("tool.invalid_arguments", "附件合计超过 25 MB")
        payload = [{"name": n, "mimeType": m, "buffer": b} for n, m, b in files]
        loc = self._ref(ref)
        info = await self._element_info(loc)
        is_input = (
            str(info.get("tag") or "").upper() == "INPUT"
            and str(info.get("type") or "").lower() == "file"
        )
        try:
            if is_input:
                await loc.set_input_files(payload, timeout=5_000)
            else:
                async with self._page.expect_file_chooser(timeout=5_000) as chooser:
                    await loc.click(timeout=5_000)
                await (await chooser.value).set_files(payload, timeout=5_000)
        except Exception as exc:
            raise ToolError(
                "sandbox.action_failed", "传不上：这个元素不是文件框，点了也没弹出选文件"
            ) from exc

    async def select_ref(self, ref: str, values: list[str]) -> None:
        loc = self._ref(ref)
        await self._element_info(loc)
        try:
            await loc.select_option([str(v) for v in values], timeout=5_000)
        except Exception:  # noqa: BLE001 — retry by visible label
            try:
                await loc.select_option(label=[str(v) for v in values], timeout=5_000)
            except Exception as exc:
                raise ToolError(
                    "sandbox.action_failed", "下拉框里没有这个选项（按 value 或显示文字都没找到）"
                ) from exc

    async def press_key(self, key: str) -> None:
        token = (key or "").strip()
        if not token or len(token) > 32:
            raise ToolError(
                "tool.invalid_arguments", "key 必须是按键名，例如 Enter / Tab / ArrowDown"
            )
        focused = await self._page.evaluate(
            """() => {
                const el = document.activeElement;
                return el ? String(el.type || '').toLowerCase() : '';
            }"""
        )
        if str(focused) == "password":
            raise human_required("密码")
        before = self.url
        await self._page.keyboard.press(token)
        await self._settle(before)

    async def wait_for(self, *, text: str, text_gone: str, seconds: float) -> None:
        budget = max(0.0, min(float(seconds or 0.0), WAIT_MAX_S))
        timeout_ms = int(budget * 1000) if budget else int(WAIT_MAX_S * 1000)
        try:
            if text:
                await self._page.get_by_text(text).first.wait_for(
                    state="visible", timeout=timeout_ms
                )
            if text_gone:
                await self._page.get_by_text(text_gone).first.wait_for(
                    state="hidden", timeout=timeout_ms
                )
            if not text and not text_gone:
                await asyncio.sleep(budget)
        except Exception as exc:
            raise ToolError(
                "sandbox.action_failed", "等到超时，页面上还没出现（或还没消失）那段文字"
            ) from exc
        assert_http_public_or_internal(self.url)

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

    async def scroll(self, dy: int) -> None:
        """Teacher's mouse wheel on the pane (#1215)."""
        step = max(-SCROLL_MAX_PX, min(SCROLL_MAX_PX, int(dy)))
        await self._page.mouse.wheel(0, float(step))

    async def press_human_key(self, key: str) -> None:
        """Teacher presses Enter / Tab / arrows on the pane (#1215)."""
        if key not in HUMAN_KEYS:
            raise ToolError("tool.invalid_arguments", "画面上只支持 Enter / Tab / 退格 / 方向键等按键")
        before = self.url
        await self._page.keyboard.press(key)
        await self._settle(before)

    async def screencast(self, push: Callable[[str], None]) -> Callable[[], Awaitable[None]]:
        """Chromium pushes a base64 JPEG each time the page repaints (#1215).

        Upstream CDP ``Page.startScreencast`` — the same thing Steel / browserless
        live view use. A still page sends nothing. Returns ``stop``.
        """
        cdp = await self._context.new_cdp_session(self._page)

        async def ack(frame_session: Any) -> None:
            try:
                await cdp.send("Page.screencastFrameAck", {"sessionId": frame_session})
            except Exception:
                logger.debug("screencast ack failed", exc_info=True)

        def on_frame(event: dict[str, Any]) -> None:
            push(str(event.get("data") or ""))
            asyncio.ensure_future(ack(event.get("sessionId")))

        cdp.on("Page.screencastFrame", on_frame)
        await cdp.send(
            "Page.startScreencast",
            {
                "format": "jpeg",
                "quality": SCREENCAST_QUALITY,
                "maxWidth": VIEWPORT_WIDTH,
                "maxHeight": VIEWPORT_HEIGHT,
            },
        )

        async def stop() -> None:
            try:
                await cdp.send("Page.stopScreencast")
                await cdp.detach()
            except Exception:
                logger.debug("screencast stop failed", exc_info=True)

        return stop

    async def save_login(self, path: Path) -> None:
        """Keep the teacher's login for next time (Playwright storage_state)."""
        state = await self._context.storage_state()
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")
        tmp.replace(path)

    async def close(self) -> None:
        try:
            await self._context.close()
        except Exception:
            logger.debug("chromium context close failed", exc_info=True)
        shutil.rmtree(self._profile_dir, ignore_errors=True)


async def open_chromium(url: str, *, login_state: Path | None = None) -> PlaywrightPage:
    """Open a public URL in headless Chromium. Caller already ran web_guard.

    ``login_state`` = the teacher's saved login; the site opens already logged in.
    """
    parse_public_http_url(url)
    browser = await _ensure_browser()
    profile_dir = Path(tempfile.mkdtemp(prefix="sbox_", dir=str(_profile_root())))
    try:
        context = await browser.new_context(
            viewport={"width": VIEWPORT_WIDTH, "height": VIEWPORT_HEIGHT},
            ignore_https_errors=False,
            accept_downloads=False,
            java_script_enabled=True,
            storage_state=read_login_state(login_state),
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
