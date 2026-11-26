"""Thin Playwright/Chromium adapter for B2.

Upstream: Playwright Chromium. Pico only wires web_guard, the teacher's saved
login (Playwright ``storage_state``), screenshots, and human-in-the-loop input.
Not a second agent loop.
"""

from __future__ import annotations

import asyncio
import base64
import difflib
import html
import io
import json
import logging
import math
import os
import re
import shutil
import tempfile
import time
from collections.abc import Awaitable, Callable, Iterable
from ctypes import c_float
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol
from urllib.parse import urlsplit, urlunsplit

from anyio import CancelScope
from pico_orchestrator.gateway import ToolError
from pico_orchestrator.web_guard import parse_public_http_url
from PIL import Image

logger = logging.getLogger(__name__)

ENGINE_NAME = "playwright-chromium"
# Sandbox desktop (teacher's computer), not the phone shell.
VIEWPORT_WIDTH = 1280
VIEWPORT_HEIGHT = 800
# Fit the pane (#1224): the page lays out at the pane's own size instead of a
# 1280x800 picture shrunk into it. Upstream = Playwright set_viewport_size.
VIEWPORT_MIN = (360, 300)
VIEWPORT_MAX = (1920, 1200)
MAX_DEVICE_SCALE = 2
PNG_MAGIC = b"\x89PNG\r\n\x1a\n"
GOTO_TIMEOUT_MS = 45_000
PAGE_LOADING_NOTE = "页面还在加载，可稍后再取快照 / 截图。"
CHROMIUM_ERROR_PAGE = "chrome-error://chromewebdata/"
CHROMIUM_NET_ERROR = re.compile(r"\bnet::(ERR_[A-Z0-9_]+)\b")
# AI hands (#1207): aria snapshot with Playwright refs. Bounded so one page
# cannot flood the model context.
SNAPSHOT_MAX_CHARS = 30_000
SECRET_MASK = "••••"
WAIT_MAX_S = 30.0
# Live pane (#1215): Chromium pushes a JPEG on each repaint (CDP screencast).
SCREENCAST_QUALITY = 75
MOTION_QUALITY = 32
MOTION_SCALE = 0.65
SCROLL_MAX_PX = 2000
# Tabs (#1217): a link that opens a new tab becomes the current page, like
# Playwright MCP. Bounded so a popup storm cannot eat the sidecar.
MAX_TABS = 8
DIALOG_NOTE_MAX = 200
# Whole-form fill + attachments (#1219), Playwright MCP fill_form / file_upload.
FILL_FORM_MAX = 40
_DATE_INPUT_FORMATS = {
    "date": "YYYY-MM-DD",
    "time": "HH:MM（可带 :SS 和小数秒）",
    "datetime-local": "YYYY-MM-DDTHH:MM（可带 :SS 和小数秒）",
    "month": "YYYY-MM",
    "week": "YYYY-Www（例如 2026-W48）",
}
_ACTIONABILITY_REASONS = re.compile(
    r"\b(element is not (?:editable|enabled|visible|stable)|intercepts pointer events"
    r"|did not find some options)$"
)
UPLOAD_MAX_FILES = 10
UPLOAD_MAX_BYTES = 25 * 1024 * 1024
# Page-native save (#1242): hang File on this page, then call a dotted path.
# Not a second control kernel — Playwright evaluate of Pico-owned functions.
PAGE_FILE_HANDLE = "__picoFile"
PAGE_FILES_HANDLE = "__picoFiles"
PAGE_FN_MAX_DOTS = 8
PAGE_FN_MAX_ARG_BYTES = 32_768
PAGE_FN_PATH_RE = re.compile(r"^[A-Za-z_$][\w$]*(?:\.[A-Za-z_$][\w$]*)*$")
FORBIDDEN_FN_SEGMENTS = frozenset(
    {"eval", "Function", "constructor", "prototype", "__proto__"}
)
# Leading global aliases are dropped before the root check (window.saveField == saveField).
GLOBAL_ALIASES = frozenset({"window", "self", "globalThis"})
# Browser built-ins that would run a string as code, leave the page, or hand
# cookies / tokens back to the model (#1246). The page's own functions never
# live under these roots; native functions are also refused inside the page.
BLOCKED_FN_ROOTS = frozenset(
    {
        "top", "parent", "frames", "opener",
        "document", "location", "navigator", "history",
        "cookieStore", "localStorage", "sessionStorage", "indexedDB", "caches",
        "open", "close", "setTimeout", "setInterval", "queueMicrotask",
        "requestAnimationFrame", "requestIdleCallback",
        "fetch", "XMLHttpRequest", "WebSocket", "EventSource", "Worker",
        "SharedWorker", "postMessage", "importScripts", "Reflect", "Object",
        "alert", "confirm", "prompt", "print",
    }
)
PAGE_FN_MAX_RESULT_BYTES = 8_192
# Specific copy only: a page that always shows "网络异常请稍后再试" is not limited (#1246).
# English matches on word boundaries ("Accurate limits apply." is not a hit).
RATE_LIMIT_PHRASES: tuple[str, ...] = (
    "IP访问量过大",
    "请求过于频繁",
    "访问过于频繁",
    "操作过于频繁",
    "too many requests",
    "rate limit",
)
_RATE_LIMIT_RES = tuple(
    re.compile(rf"\b{re.escape(p)}", re.IGNORECASE) if p.isascii() else re.compile(re.escape(p))
    for p in RATE_LIMIT_PHRASES
)
# One hit (page copy, dialog or return value) stops page_fn for this session,
# even after the banner goes away.
RATE_LIMIT_COOLDOWN_S = 600
_RESULT_BANNED = frozenset(
    {"cookie", "cookies", "password", "passwd", "secret", "credential"}
)
# Pico-owned scripts. Never interpolate model text into these strings.
# Tests assert they contain no eval / new Function / document.cookie / fetch.
HANG_FILES_JS = """(files) => {
  const out = [];
  for (const f of files) {
    const bin = atob(f.b64);
    const bytes = new Uint8Array(bin.length);
    for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
    out.push(new File([bytes], f.name, { type: f.mime || 'application/octet-stream' }));
  }
  window.__picoFiles = out;
  window.__picoFile = out.length === 1 ? out[0] : out;
  return {
    handle: out.length === 1 ? '__picoFile' : '__picoFiles',
    count: out.length,
    names: out.map((x) => x.name),
  };
}"""
PAGE_TEXT_JS = """() => (document.body && document.body.innerText) || ''"""
CALL_PAGE_FN_JS = """({ parts, args }) => {
  let receiver = window;
  let fn = window;
  for (const p of parts) {
    if (fn == null || (typeof fn !== 'object' && typeof fn !== 'function')) {
      return { missing: true };
    }
    receiver = fn;
    fn = fn[p];
  }
  if (typeof fn !== 'function') return { missing: true };
  // Only the page's own functions: browser built-ins (setTimeout with a string,
  // cookieStore, storage getters …) are native and refused (#1246).
  let src = '';
  try { src = Function.prototype.toString.call(fn); } catch (e) { return { native: true }; }
  if (src.includes('[native code]')) return { native: true };
  const resolved = args.map((a) => {
    if (a === '__picoFile') return window.__picoFile;
    if (a === '__picoFiles') return window.__picoFiles;
    return a;
  });
  const sanitize = (v, depth) => {
    if (depth > 6) return null;
    if (v == null) return v;
    if (typeof v === 'object' || typeof v === 'function') {
      try { if (v.window === v) return null; } catch (e) { return null; }
      if (typeof Node !== 'undefined' && v instanceof Node) return null;
    }
    if (typeof v === 'string' || typeof v === 'number' || typeof v === 'boolean') return v;
    if (typeof File !== 'undefined' && v instanceof File) {
      return { name: v.name, size: v.size, type: v.type };
    }
    if (Array.isArray(v)) return v.slice(0, 40).map((x) => sanitize(x, depth + 1));
    if (typeof v === 'object') {
      const out = {};
      for (const k of Object.keys(v).slice(0, 40)) {
        const low = String(k).toLowerCase();
        if (
          low === 'cookie' || low === 'cookies' || low === 'password'
          || low === 'passwd' || low === 'secret' || low === 'credential'
        ) continue;
        out[k] = sanitize(v[k], depth + 1);
      }
      return out;
    }
    return null;
  };
  try {
    const raw = fn.apply(receiver, resolved);
    if (raw && typeof raw.then === 'function') {
      return raw.then((v) => ({ ok: true, result: sanitize(v, 0) }));
    }
    return { ok: true, result: sanitize(raw, 0) };
  } catch (e) {
    return { failed: true, message: String((e && e.message) || e).slice(0, 200) };
  }
}"""
# Snapshot deltas (#1222): after an action only new / changed lines go back,
# like Playwright MCP's incremental snapshot. Since #1233 the snapshot is
# upstream `aria_snapshot(mode="ai")`: refs stay stable across snapshots and
# iframes come back inline with `f1eN` refs, so Pico no longer renumbers them.
DELTA_FULL_RATIO = 0.5
EDIT_HOST_XPATH = "xpath=ancestor::*[@contenteditable and @contenteditable!='false'][1]"
REF_RE = re.compile(r"(?:f\d+)?e\d+")
CHECK_ROLES = frozenset({"checkbox", "radio", "switch", "menuitemcheckbox", "menuitemradio"})
TRUE_WORDS = frozenset({"true", "1", "yes", "y", "on", "checked", "是", "对", "勾选", "选中"})
HUMAN_KEYS = frozenset(
    {
        "Enter", "Tab", "Backspace", "Delete", "Escape",
        "ArrowUp", "ArrowDown", "ArrowLeft", "ArrowRight", "PageUp", "PageDown",
        "Home", "End", "Control+a",
    }
)
# Human-only step: paying. Passwords and verification codes the teacher gives in
# chat are typed like any other value (pico#1320, owner 2026-10-16).
HANDOFF_RE = re.compile(
    r"支付|付款|缴费|付费|\bpay\b|checkout|结算",
    re.IGNORECASE,
)
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
    # JPEG chroma subsampling blurs LCD subpixel text. Rasterize grayscale text.
    "--disable-lcd-text",
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


@dataclass
class ScreencastFrame:
    jpeg: str
    width: int
    height: int
    received_at: float | None = None
    page_token: int = 0

    def motion_jpeg(self) -> str:
        size = (round(self.width * MOTION_SCALE), round(self.height * MOTION_SCALE))
        with Image.open(io.BytesIO(base64.b64decode(self.jpeg))) as image:
            image.draft("RGB", size)
            thumb = image.resize(size, Image.Resampling.BILINEAR)
            out = io.BytesIO()
            thumb.save(out, format="JPEG", quality=MOTION_QUALITY)
        return base64.b64encode(out.getvalue()).decode("ascii")


class BrowserHands(Protocol):
    """AI hands on the same page (#1207). Shape follows Playwright MCP."""

    async def snapshot(self) -> str: ...

    async def navigate(self, url: str) -> None: ...

    async def click_ref(self, ref: str, *, double: bool = False) -> None: ...

    async def hover_ref(self, ref: str) -> None: ...

    async def navigate_back(self) -> None: ...

    async def tabs(self, action: str, index: int) -> list[dict[str, Any]]: ...

    def take_dialogs(self) -> list[str]: ...

    async def fill_form(self, fields: list[dict[str, Any]]) -> None: ...

    async def upload_files(self, ref: str, files: list[tuple[str, str, bytes]]) -> None: ...

    async def page_file(self, files: list[tuple[str, str, bytes]]) -> dict[str, Any]: ...

    async def page_fn(self, fn: str, args: list[Any]) -> Any: ...

    async def type_ref(
        self, ref: str, text: str, *, submit: bool, slowly: bool = False
    ) -> None: ...

    async def select_ref(self, ref: str, values: list[str]) -> None: ...

    async def press_key(self, key: str) -> None: ...

    async def wait_for(self, *, text: str, text_gone: str, seconds: float) -> None: ...


class RefBook:
    """Snapshot deltas of one browser window (#1222). Refs come from upstream
    (`aria_snapshot(mode="ai")`, stable since #1233); this only diffs lines."""

    def __init__(self) -> None:
        self._page: Any = None
        self._lines: list[str] = []

    def update(self, raw: str, *, page: Any = None) -> tuple[str, str | None]:
        """Returns (full snapshot, delta or None when the full snapshot should go
        back: new tab, or most of it changed)."""
        lines = raw.splitlines()
        old = [] if page != self._page else self._lines
        self._page, self._lines = page, lines
        changed = [True] * len(lines)
        removed = 0
        matcher = difflib.SequenceMatcher(None, old, lines, autojunk=False)
        for tag, i1, i2, j1, j2 in matcher.get_opcodes():
            removed += max(0, (i2 - i1) - (j2 - j1))
            if tag == "equal":
                for j in range(j1, j2):
                    changed[j] = False
        n_changed = sum(changed)
        if not old or n_changed > len(lines) * DELTA_FULL_RATIO:
            return raw, None
        if not n_changed and not removed:
            return raw, "（页面结构没变，编号照用。）"
        keep: set[int] = set()
        for j in (j for j, c in enumerate(changed) if c):
            keep.add(j)
            depth = len(lines[j]) - len(lines[j].lstrip())
            for a in range(j - 1, -1, -1):
                d = len(lines[a]) - len(lines[a].lstrip())
                if d < depth:
                    keep.add(a)
                    depth = d
        head = f"（只列新出现或改了的行和它们的上级；没列的没变，编号照用。消失 {removed} 行。）"
        return raw, "\n".join([head] + [lines[j] for j in sorted(keep)])


def mask_secret_values(snapshot: str, secrets: list[str]) -> str:
    """Password field values must never reach the model (#1207)."""
    out = snapshot
    for value in secrets:
        if value:
            out = out.replace(value, SECRET_MASK)
    return out


def _mask_action_values(detail: str, values: Iterable[str]) -> str:
    variants = {
        variant
        for value in values
        if value
        for variant in (value, json.dumps(value, ensure_ascii=False)[1:-1], html.escape(value))
    }
    return mask_secret_values(detail, sorted(variants, key=len, reverse=True))


# Code / password shaped: 4–32 chars, no spaces, no CJK. Mail bodies and names stay
# readable so the AI can check what it wrote.
_CODE_LIKE = re.compile(r"[\x21-\x7e]{4,32}")


def mask_typed_box_values(snapshot: str, typed: list[str]) -> str:
    """Code-like values the AI typed into a text box (codes, passwords the teacher
    gave) show masked on the box lines, so they do not ride the snapshot into the
    run ledger (pico#1320). Page text elsewhere is untouched."""
    values = [v for v in typed if _CODE_LIKE.fullmatch(v)]
    if not values:
        return snapshot
    lines = []
    box_indent: int | None = None  # inside a textbox: its value sits on child lines
    for line in snapshot.split("\n"):
        indent = len(line) - len(line.lstrip())
        if box_indent is not None and indent <= box_indent:
            box_indent = None
        if "textbox" in line:
            box_indent = indent
        if box_indent is not None:
            for value in values:
                line = line.replace(value, SECRET_MASK)
        lines.append(line)
    return "\n".join(lines)


def human_required(step: str) -> ToolError:
    return ToolError(
        HUMAN_REQUIRED_CODE,
        f"这一步（{step}）是付款，要老师自己在沙箱画面里点。"
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


def parse_page_fn_path(fn: str) -> list[str]:
    """Dotted path only. Never a JS string to eval."""
    token = (fn or "").strip()
    if (
        not token
        or len(token) > 200
        or not PAGE_FN_PATH_RE.fullmatch(token)
        or token.count(".") >= PAGE_FN_MAX_DOTS
    ):
        raise ToolError(
            "tool.invalid_arguments",
            "fn 必须是点号路径，例如 saveField 或 app.saveMaterial，不能是任意脚本",
        )
    parts = token.split(".")
    if any(len(p) > 64 for p in parts):
        raise ToolError(
            "tool.invalid_arguments",
            "fn 必须是点号路径，例如 saveField 或 app.saveMaterial，不能是任意脚本",
        )
    bad = [p for p in parts if p in FORBIDDEN_FN_SEGMENTS]
    if bad:
        raise ToolError(
            "tool.invalid_arguments",
            f"fn 不能包含 {' / '.join(bad)}（禁止 eval / Function / constructor）",
        )
    while len(parts) > 1 and parts[0] in GLOBAL_ALIASES:
        parts = parts[1:]
    if parts[0] in GLOBAL_ALIASES or parts[0] in BLOCKED_FN_ROOTS:
        raise ToolError(
            "sandbox.fn_native_blocked",
            f"{token} 是浏览器自带接口，不是这一页自己的保存 / 查询 / 删除，不能调",
        )
    return parts


def cap_page_result(value: Any) -> Any:
    """Keep page_fn results small enough for the model."""
    try:
        dumped = json.dumps(value, ensure_ascii=False)
    except (TypeError, ValueError):
        return None
    if len(dumped.encode("utf-8")) <= PAGE_FN_MAX_RESULT_BYTES:
        return value
    return {"truncated": True, "preview": dumped[:2_000]}


def json_safe_args(args: list[Any] | None) -> list[Any]:
    if args is None:
        return []
    if not isinstance(args, list) or len(args) > 20:
        raise ToolError("tool.invalid_arguments", "args 必须是最多 20 项的 JSON 列表")
    try:
        raw = json.dumps(args, ensure_ascii=False, allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise ToolError("tool.invalid_arguments", "args 必须是 JSON 能序列化的列表") from exc
    if len(raw.encode("utf-8")) > PAGE_FN_MAX_ARG_BYTES:
        raise ToolError("tool.invalid_arguments", "args 太长")
    return json.loads(raw)


def rate_limit_hit(texts: Iterable[str]) -> str | None:
    """First matching phrase from the testable list, or None."""
    blob = "\n".join(str(t or "") for t in texts)
    for phrase, pattern in zip(RATE_LIMIT_PHRASES, _RATE_LIMIT_RES):
        if pattern.search(blob):
            return phrase
    return None


def same_origin(url: str, origin: str) -> bool:
    """scheme://host:port match; about:blank / srcdoc inherit the parent's origin."""
    parts = urlsplit(url or "")
    if parts.scheme == "about":
        return True
    return f"{parts.scheme}://{parts.netloc}" == origin


def sanitize_page_result(value: Any, *, depth: int = 0) -> Any:
    """JSON-safe result. Never pass cookie / password keys back to the model."""
    if depth > 6:
        return None
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if isinstance(value, list):
        return [sanitize_page_result(v, depth=depth + 1) for v in value[:40]]
    if isinstance(value, dict):
        out: dict[str, Any] = {}
        for key, item in list(value.items())[:40]:
            if str(key).lower() in _RESULT_BANNED:
                continue
            out[str(key)[:80]] = sanitize_page_result(item, depth=depth + 1)
        return out
    return None


def read_login_state(path: Path | None) -> dict[str, Any] | None:
    """The teacher's saved browser login (cookies + localStorage), or None."""
    if path is None or not path.is_file():
        return None
    try:
        state = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return state if isinstance(state, dict) else None


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


async def _close_context(context: Any, profile_dir: Path) -> None:
    try:
        if context is not None:
            await context.close()
    except Exception:
        logger.debug("chromium context close failed", exc_info=True)
    finally:
        shutil.rmtree(profile_dir, ignore_errors=True)


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


@dataclass
class _ViewportCommit:
    size: tuple[int, int]
    scale: float
    frames: dict[Callable[[dict[str, Any]], None], dict[str, Any]]


class _NavigationFailure:
    """Track the top-level failed request, including failures after a redirect."""

    def __init__(self, page: Any) -> None:
        self.page = page
        self.failed: tuple[str, str] | None = None
        page.on("requestfailed", self._request_failed)
        page.on("framenavigated", self._navigated)

    def _request_failed(self, request: Any) -> None:
        if request.is_navigation_request() and request.frame is self.page.main_frame:
            match = CHROMIUM_NET_ERROR.search(request.failure or "")
            if match and match[1] != "ERR_ABORTED":
                self.failed = (request.url, match[1])

    def _navigated(self, frame: Any) -> None:
        if frame is self.page.main_frame and frame.url != CHROMIUM_ERROR_PAGE:
            self.failed = None

    def error_on_page(self) -> ToolError | None:
        if self.page.url == CHROMIUM_ERROR_PAGE and self.failed:
            return _navigation_error(*self.failed)
        return None

    def check_error_page(self) -> None:
        if error := self.error_on_page():
            raise error


class PlaywrightPage:
    """One Chromium context. Login is saved to the teacher's own disk, not host HOME."""

    def __init__(
        self, context: Any, page: Any, profile_dir: Path,
        *, initial_failure: _NavigationFailure | None = None,
    ) -> None:
        self._context = context
        self._page = page
        self._profile_dir = profile_dir
        self.loading_note = ""
        # Captures follow the tab. The page token also invalidates frames on resize.
        self.page_token = 0
        self.cast_token = 0
        self._viewport = (VIEWPORT_WIDTH, VIEWPORT_HEIGHT)
        self._device_scale = 1.0
        self._viewport_changed_at = 0.0
        self._viewport_lock = asyncio.Lock()
        self._viewport_task: asyncio.Task[None] | None = None
        # Present only during a resize, with one validated frame per cast.
        self._viewport_commit: _ViewportCommit | None = None
        self._metrics: dict[Any, Any] = {}
        self._screen_cdp: Any = None
        self._screen: dict[str, Any] | None = None
        self._dialogs: list[str] = []
        self._rate_limit: tuple[float, str] | None = None
        # Values the AI typed into boxes; masked on box lines in snapshots (pico#1320).
        self._typed: list[str] = []
        self._pages: dict[Any, _NavigationFailure] = {}
        self._watch(page, initial_failure)
        for existing in context.pages:
            if existing is not page:
                self._watch(existing)
        context.on("page", self._on_new_page)

    @property
    def url(self) -> str:
        return str(self._page.url or "")

    # ---- Tabs + dialogs (#1217). Upstream = Playwright context/page events. ----

    def _watch(self, page: Any, failure: _NavigationFailure | None = None) -> None:
        self._pages[page] = failure or _NavigationFailure(page)
        page.on("dialog", self._on_dialog)
        page.on("close", self._on_close)

    def _open_pages(self) -> list[Any]:
        return [p for p in self._context.pages if p in self._pages and not p.is_closed()]

    def _use(self, page: Any) -> None:
        if page is not self._page:
            self._page = page
            self.page_token += 1
            self.cast_token += 1
            if (
                self._viewport != (VIEWPORT_WIDTH, VIEWPORT_HEIGHT)
                or self._device_scale != 1
                or page in self._metrics
            ):
                self._viewport_task = asyncio.create_task(self._fit_page(page))
                self._viewport_task.add_done_callback(self._tab_fit_done)
            else:
                self._viewport_task = None

    async def _fit_page(self, page: Any) -> None:
        try:
            async with self._viewport_lock:
                if not page.is_closed():
                    await self._apply_metrics(page, self._viewport, self._device_scale)
        except Exception:
            if not page.is_closed():
                raise
            logger.debug("tab closed during viewport update", exc_info=True)

    def _tab_fit_done(self, task: asyncio.Task[None]) -> None:
        if task.cancelled():
            return
        error = task.exception()
        if error is not None:
            # Retain the failed fit so an existing or reconnecting stream polls PNG.
            logger.warning("sandbox tab viewport update failed", exc_info=error)
        elif self._viewport_task is task:
            self._viewport_task = None

    async def _apply_metrics(self, page: Any, viewport: tuple[int, int], scale: float) -> float:
        cdp = await self._page_metrics(page)
        await self._place_on_screen(cdp, max(1.0, scale))
        # CDP frame timestamps are Unix seconds. Start at dispatch so a frame
        # rendered before the command response still belongs to the new viewport.
        changed_at = time.time()
        await cdp.send(
            "Emulation.setDeviceMetricsOverride",
            {
                "width": viewport[0],
                "height": viewport[1],
                "mobile": False,
                "deviceScaleFactor": scale,
            },
        )
        return changed_at

    async def _place_on_screen(self, cdp: Any, scale: float) -> None:
        # Use Chromium's native headless display DPR so screencast has no resize filter.
        if scale == 1 and self._screen_cdp is None:
            return
        if self._screen_cdp is None:
            self._screen_cdp = await self._context.browser.new_browser_cdp_session()
        previous = self._screen
        if scale == 1:
            self._screen = None
        elif previous is None or scale != self._device_scale:
            # Moving to a new display updates the compositor DPR. Updating the
            # old display in place can leave Chromium capturing with its old DPR.
            async with _LOCK:
                screens = (await self._screen_cdp.send("Emulation.getScreenInfos"))["screenInfos"]
                full_width = VIEWPORT_MAX[0] * MAX_DEVICE_SCALE
                occupied = {screen["left"] for screen in screens}
                left = full_width
                while left in occupied:
                    left += full_width
                added = await self._screen_cdp.send(
                    "Emulation.addScreen",
                    {
                        "left": left,
                        "top": 0,
                        "width": full_width,
                        "height": VIEWPORT_MAX[1] * MAX_DEVICE_SCALE,
                        "devicePixelRatio": scale,
                    },
                )
                self._screen = added["screenInfo"]
        try:
            window = await cdp.send("Browser.getWindowForTarget")
            bounds = {"left": self._screen["left"] if self._screen is not None else 0, "top": 0}
            if any(window["bounds"][key] != value for key, value in bounds.items()):
                await cdp.send(
                    "Browser.setWindowBounds", {"windowId": window["windowId"], "bounds": bounds},
                )
        finally:
            if previous is not None and previous is not self._screen:
                await self._screen_cdp.send("Emulation.removeScreen", {"screenId": previous["id"]})

    async def _page_metrics(self, page: Any) -> Any:
        cdp = self._metrics.get(page)
        if cdp is None:
            cdp = self._metrics[page] = await self._context.new_cdp_session(page)
        return cdp

    async def set_viewport(
        self, width: int, height: int, device_scale: float = 1.0
    ) -> tuple[int, int]:
        """The teacher's pane size; new tabs follow it too."""
        size = (
            max(VIEWPORT_MIN[0], min(VIEWPORT_MAX[0], int(width))),
            max(VIEWPORT_MIN[1], min(VIEWPORT_MAX[1], int(height))),
        )
        scale = min(device_scale, MAX_DEVICE_SCALE)
        async with self._viewport_lock:
            if size != self._viewport or scale != self._device_scale:
                task = self._viewport_task
                self._viewport_commit = commit = _ViewportCommit(size, scale, {})
                try:
                    changed_at = await self._apply_metrics(self._page, size, scale)
                    # Publish the whole viewport generation without yielding to frame callbacks.
                    self._viewport_changed_at = changed_at
                    self._viewport = size
                    self._device_scale = scale
                    self.page_token += 1
                    if self._viewport_task is task:
                        self._viewport_task = None
                finally:
                    self._viewport_commit = None
                for check_frame, event in commit.frames.items():
                    check_frame(event)
        return size

    def _on_new_page(self, page: Any) -> None:
        """A link with target=_blank / window.open: the new tab becomes current."""
        self._watch(page)
        if len(self._open_pages()) > MAX_TABS:
            asyncio.ensure_future(page.close())
            return
        self._use(page)

    def _on_close(self, page: Any) -> None:
        self._pages.pop(page, None)
        self._metrics.pop(page, None)
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
        async with self._viewport_lock:
            cdp = await self._context.new_cdp_session(self._page)
            try:
                layout = (await cdp.send("Page.getLayoutMetrics"))["cssLayoutViewport"]
                viewport = (layout["clientWidth"], layout["clientHeight"])
                # Surface capture works without a screencast. A session with no
                # emulation override and no clip leaves the live viewport alone.
                screenshot = await cdp.send("Page.captureScreenshot", {"fromSurface": True})
            finally:
                await cdp.detach()
        png = base64.b64decode(screenshot["data"])
        if not png.startswith(PNG_MAGIC):
            raise ToolError("sandbox.raster_failed", "隔离 Chromium 未能截取 viewport")
        return await asyncio.to_thread(_png_at_css_size, png, viewport)

    async def click(self, x: int, y: int, *, settle: bool = True) -> None:
        before = self.url
        await self._page.mouse.click(float(x), float(y))
        if settle:
            await self._settle(before)
        else:
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
        if not REF_RE.fullmatch(token):
            raise ToolError("tool.invalid_arguments", "ref 必须是快照里的编号，例如 e8")
        return self._page.locator(f"aria-ref={token}")

    async def _each_frame(self, script: str) -> list[Any]:
        """Run `script` in every frame: since #1233 the AI sees and types into iframes,
        so password masking and the password-key guard look there too."""
        out: list[Any] = []
        for frame in self._page.frames:
            try:
                out.append(await frame.evaluate(script))
            except Exception:
                logger.debug("frame script failed", exc_info=True)
        return out

    async def _password_values(self) -> list[str]:
        found = await self._each_frame(
            """() => Array.from(document.querySelectorAll('input[type="password"]'))
                    .map((el) => String(el.value || ''))
                    .filter((v) => v.length > 0)"""
        )
        return [str(v) for raw in found if isinstance(raw, list) for v in raw]

    async def snapshot(self) -> str:
        page = self._page
        try:
            text = await page.aria_snapshot(mode="ai", timeout=10_000)
        except Exception as exc:
            raise ToolError("sandbox.raster_failed", "隔离 Chromium 未能生成页面快照") from exc
        text = mask_secret_values(str(text or ""), await self._password_values())
        text = mask_typed_box_values(text, self._typed)
        if len(text) > SNAPSHOT_MAX_CHARS:
            text = text[:SNAPSHOT_MAX_CHARS] + "\n- text: …（快照过长已截断，可滚动或翻页后再取）"
        return text

    def navigation_error(self) -> str | None:
        error = self._pages[self._page].error_on_page()
        return error.message if error else None

    async def navigate(self, url: str) -> None:
        from playwright.async_api import TimeoutError as PlaywrightTimeoutError

        parse_public_http_url(url)
        page = self._page
        failure = self._pages[page]
        before = page.url
        try:
            self.loading_note = await _navigate_page(failure, url)
        except ToolError:
            if before.startswith(("http://", "https://")):
                if page.url == before and failure.failed:
                    # goto can reject before Chromium commits the error document.
                    try:
                        await page.wait_for_url(
                            CHROMIUM_ERROR_PAGE, wait_until="commit", timeout=1_000,
                        )
                    except PlaywrightTimeoutError:
                        logger.debug("Chromium did not commit an error page", exc_info=True)
                if page.url == CHROMIUM_ERROR_PAGE:
                    self.loading_note = await _navigate_page(failure, None)
            raise
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
                        inside_editable: !!el.isContentEditable && !el.hasAttribute('contenteditable'),
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

    async def _action_error(
        self,
        exc: Exception,
        message: str,
        *,
        input_type: str = "",
        values: tuple[str, ...] | list[str] = (),
    ) -> ToolError:
        # Playwright includes call arguments and DOM previews in the call log.
        typed = [*self._typed, *values]
        passwords = await self._password_values()
        if input_type == "password":
            passwords.extend(values)
        detail = str(exc)
        logger.warning(
            "browser action failed: %s\n%s", message, _mask_action_values(detail, [*typed, *passwords])
        )
        first_line, _, call_log = detail.strip().partition("\n")
        for line in reversed(call_log.splitlines()):
            reason = _ACTIONABILITY_REASONS.search(line.strip())
            if reason:
                first_line += f"（{reason.group()}）"
                break
        if first_line:
            sensitive = [*passwords, *(v for v in typed if _CODE_LIKE.fullmatch(v))]
            message += f"。{_mask_action_values(first_line, sensitive)}"
        expected = _DATE_INPUT_FORMATS.get(input_type)
        if expected:
            message += f"。这个输入框要求 {expected} 格式。"
        return ToolError("sandbox.action_failed", message)

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
        from playwright.async_api import Error as PlaywrightError

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
        except PlaywrightError as exc:
            raise await self._action_error(exc, "点不到这个元素") from None
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
        self.loading_note = await _navigate_page(self._pages[self._page], None)
        assert_http_public_or_internal(self.url)

    async def type_ref(self, ref: str, text: str, *, submit: bool, slowly: bool = False) -> None:
        """`slowly` types key by key (Playwright MCP `browser_type` slowly): recipient,
        search and autocomplete boxes react to keys, not to a pasted value (#1233)."""
        from playwright.async_api import Error as PlaywrightError

        # Never log `text`.
        loc = self._ref(ref)
        info = await self._element_info(loc)
        before = self.url
        if info.get("inside_editable"):
            # A paragraph of a rich-text body (mail / TinyMCE, often in an iframe):
            # Playwright fills the editing host, not a line inside it (#1233).
            loc = loc.locator(EDIT_HOST_XPATH)
        self._typed.append(text)
        try:
            if slowly:
                await loc.press_sequentially(text, timeout=5_000 + 50 * len(text))
            else:
                await loc.fill(text, timeout=5_000)
            if submit:
                await loc.press("Enter", timeout=5_000)
        except PlaywrightError as exc:
            input_type = info.get("type", "") if info.get("tag") == "INPUT" else ""
            raise await self._action_error(
                exc, "无法输入或提交文字", input_type=input_type, values=[text]
            ) from None
        if submit:
            await self._settle(before)

    async def fill_form(self, fields: list[dict[str, Any]]) -> None:
        """Fill many fields in one call (#1219). Each element decides how: text box
        ``fill``, checkbox / radio ``set_checked``, dropdown ``select_option``.
        Never logs values."""
        from playwright.async_api import Error as PlaywrightError

        if not fields or len(fields) > FILL_FORM_MAX:
            raise ToolError("tool.invalid_arguments", f"fields 要 1–{FILL_FORM_MAX} 格")
        for i, field in enumerate(fields, start=1):
            ref = str(field.get("ref") or "")
            value = field.get("value")
            loc = self._ref(ref)
            info = await self._element_info(loc)
            tag = str(info.get("tag") or "").upper()
            kind = str(info.get("type") or "").lower()
            role = str(info.get("role") or "").lower()
            entered: list[str] = []
            try:
                if kind in {"checkbox", "radio"} or role in CHECK_ROLES:
                    await loc.set_checked(is_checked_value(value), timeout=5_000)
                elif tag == "SELECT":
                    entered = [str(v) for v in value] if isinstance(value, list) else [str(value)]
                    await self._select_options(loc, entered)
                else:
                    text = "" if value is None else str(value)
                    entered = [text]
                    self._typed.append(text)
                    await loc.fill(text, timeout=5_000)
            except PlaywrightError as exc:
                raise await self._action_error(
                    exc,
                    f"第 {i} 格（{ref}）填不进去，前面 {i - 1} 格已填",
                    input_type=kind if tag == "INPUT" else "",
                    values=entered,
                ) from None

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

    async def page_file(self, files: list[tuple[str, str, bytes]]) -> dict[str, Any]:
        """Put teacher-disk / ledger bytes on this page as File (#1242). No file picker."""
        if not files or len(files) > UPLOAD_MAX_FILES:
            raise ToolError("tool.invalid_arguments", f"一次传 1–{UPLOAD_MAX_FILES} 个文件")
        if sum(len(b) for _, _, b in files) > UPLOAD_MAX_BYTES:
            raise ToolError("tool.invalid_arguments", "附件合计超过 25 MB")
        payload = [
            {"name": n, "mime": m, "b64": base64.b64encode(b).decode("ascii")}
            for n, m, b in files
        ]
        hung = 0
        last: dict[str, Any] = {}
        for frame in self._same_origin_frames():
            try:
                raw = await frame.evaluate(HANG_FILES_JS, payload)
                if isinstance(raw, dict):
                    last = raw
                    hung += 1
            except Exception:
                logger.debug("page_file hang failed in a frame", exc_info=True)
        if hung == 0:
            raise ToolError(
                "sandbox.action_failed", "没法把文件放进这一页（主页面和同源 iframe 都试过了）"
            )
        names = [n for n, _, _ in files]
        return {
            "handle": PAGE_FILE_HANDLE if len(files) == 1 else PAGE_FILES_HANDLE,
            "count": len(files),
            "names": names,
            **{k: v for k, v in last.items() if k in {"handle", "count", "names"}},
        }

    def _same_origin_frames(self) -> list[Any]:
        """Main page + iframes of its origin (not cross-site ads, #1246)."""
        main = self._page.main_frame
        parts = urlsplit(main.url or "")
        origin = f"{parts.scheme}://{parts.netloc}"
        out = [main]
        for frame in self._page.frames:
            if frame is main:
                continue
            chain, ok = frame, True
            while chain is not None and chain is not main:
                if not same_origin(chain.url, origin):
                    ok = False
                    break
                chain = chain.parent_frame
            if ok:
                out.append(frame)
        return out

    def _rate_limited(self, phrase: str) -> ToolError:
        if phrase:
            self._rate_limit = (time.monotonic() + RATE_LIMIT_COOLDOWN_S, phrase)
        until, seen = self._rate_limit or (0.0, phrase)
        minutes = max(1, round((until - time.monotonic()) / 60))
        return ToolError(
            "sandbox.rate_limited",
            f"页上出现过限流文案「{seen}」，保存/查询/删除停 {minutes} 分钟。不要连打。",
        )

    async def page_fn(self, fn: str, args: list[Any]) -> Any:
        """Call an existing dotted-path function on this page or a same-page iframe."""
        parts = parse_page_fn_path(fn)
        safe_args = json_safe_args(args)
        if self._rate_limit and self._rate_limit[0] > time.monotonic():
            raise self._rate_limited("")
        texts = await self._each_frame(PAGE_TEXT_JS)
        phrase = rate_limit_hit(str(t) for t in texts if t is not None)
        if phrase:
            raise self._rate_limited(phrase)
        for frame in self._page.frames:
            try:
                raw = await frame.evaluate(CALL_PAGE_FN_JS, {"parts": parts, "args": safe_args})
            except Exception:
                logger.debug("page_fn frame failed", exc_info=True)
                continue
            if not isinstance(raw, dict):
                continue
            if raw.get("missing"):
                continue
            if raw.get("native"):
                raise ToolError(
                    "sandbox.fn_native_blocked",
                    f"{fn} 是浏览器自带函数，不是这一页自己的保存 / 查询 / 删除，不能调",
                )
            result = cap_page_result(sanitize_page_result(raw.get("result")))
            # The call itself may trip the limit: new copy, an alert, or the reply.
            after = await self._each_frame(PAGE_TEXT_JS)
            phrase = rate_limit_hit(
                [*(str(t) for t in after if t is not None), *self._dialogs, raw.get("message"),
                 json.dumps(result, ensure_ascii=False)]
            )
            if phrase:
                raise self._rate_limited(phrase)
            if raw.get("failed"):
                raise ToolError(
                    "sandbox.action_failed",
                    f"页内函数 {fn} 调用失败：{raw.get('message') or '未知错误'}",
                )
            if raw.get("ok"):
                return result
        raise ToolError(
            "sandbox.fn_missing",
            f"这一页上没有函数 {fn}（主页面和 iframe 都找过了）。不要猜别的名字。",
        )

    async def _select_options(self, loc: Any, values: list[str]) -> None:
        from playwright.async_api import Error as PlaywrightError

        try:
            await loc.select_option(values, timeout=5_000)
        except PlaywrightError:  # The tool also accepts visible labels.
            await loc.select_option(label=values, timeout=5_000)

    async def select_ref(self, ref: str, values: list[str]) -> None:
        from playwright.async_api import Error as PlaywrightError

        loc = self._ref(ref)
        info = await self._element_info(loc)
        try:
            await self._select_options(loc, values)
        except PlaywrightError as exc:
            input_type = info.get("type", "") if info.get("tag") == "INPUT" else ""
            raise await self._action_error(
                exc, "下拉框选项选不进去", input_type=input_type, values=values
            ) from None

    async def press_key(self, key: str) -> None:
        token = (key or "").strip()
        if not token or len(token) > 32:
            raise ToolError(
                "tool.invalid_arguments", "key 必须是按键名，例如 Enter / Tab / ArrowDown"
            )
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

    async def drag(self, phase: str, x: int, y: int, *, settle: bool = True) -> None:
        """Teacher drags on the pane (#1236): press, move, release — e.g. a slider check."""
        await self._page.mouse.move(float(x), float(y))
        if phase == "down":
            await self._page.mouse.down()
        elif phase == "up":
            await self._page.mouse.up()
            if settle:
                await self._settle(self.url)
            else:
                assert_http_public_or_internal(self.url)

    async def press_human_key(self, key: str, *, settle: bool = True) -> None:
        """Teacher presses Enter / Tab / arrows on the pane (#1215)."""
        if key not in HUMAN_KEYS:
            raise ToolError("tool.invalid_arguments", "画面上只支持 Enter / Tab / 退格 / 方向键 / 全选等按键")
        before = self.url
        await self._page.keyboard.press(key)
        if settle:
            await self._settle(before)
        else:
            assert_http_public_or_internal(self.url)

    async def screencast(
        self, push: Callable[[ScreencastFrame], None]
    ) -> Callable[[], Awaitable[None]]:
        """Chromium pushes a base64 JPEG each time the page repaints (#1215).

        Upstream CDP ``Page.startScreencast`` — the same thing Steel / browserless
        live view use. A still page sends nothing. Returns ``stop``.
        """
        from playwright.async_api import Error

        # A resize already in progress can replace the result of the tab fit.
        async with self._viewport_lock:
            task = self._viewport_task
        if task is not None:
            await asyncio.shield(task)
        async with self._viewport_lock:
            page = self._page
            cdp = await self._context.new_cdp_session(page)
        active = True
        last_jpeg: str | None = None
        last_page_token = self.page_token
        last_frame_at = 0.0

        def check_frame(event: dict[str, Any]) -> None:
            nonlocal last_jpeg, last_page_token, last_frame_at
            if not active or self._page is not page:
                return
            meta = event["metadata"]
            timestamp = meta.get("timestamp", 0.0)
            if timestamp < max(last_frame_at, self._viewport_changed_at):
                return
            commit = self._viewport_commit
            width, height = commit.size if commit is not None else self._viewport
            scale = commit.scale if commit is not None else self._device_scale
            scale = c_float(max(1.0, scale)).value
            # Match Chromium's float32 ScaleToCeiledSize. A one-pixel margin
            # could accept the old surface while the resize is taking effect.
            native_width = math.ceil(c_float(width * scale).value)
            native_height = math.ceil(c_float(height * scale).value)
            if (
                round(meta["deviceWidth"] * scale) != native_width
                or round(meta["deviceHeight"] * scale) != native_height
            ):
                return
            # Chromium can pair a queued bitmap with the current view's metadata on resize.
            # Check the JPEG header before using those coordinates for teacher input.
            jpeg = event["data"]
            with Image.open(io.BytesIO(base64.b64decode(jpeg))) as img:
                if img.size != (native_width, native_height):
                    return
            if commit is not None:
                # A late bitmap from the old layout must not replace a valid new frame.
                pending = commit.frames.get(check_frame)
                if pending is None or timestamp >= pending["metadata"].get("timestamp", 0.0):
                    commit.frames[check_frame] = event
                return
            last_frame_at = timestamp
            if self.page_token == last_page_token and jpeg == last_jpeg:
                return
            last_page_token, last_jpeg = self.page_token, jpeg
            push(ScreencastFrame(jpeg, width, height, time.monotonic(), self.page_token))

        async def on_frame(event: dict[str, Any]) -> None:
            if not active:
                return
            try:
                await cdp.send("Page.screencastFrameAck", {"sessionId": event["sessionId"]})
            except Error:
                if active:
                    raise
                logger.debug("screencast stopped while acknowledging a frame", exc_info=True)
            check_frame(event)

        async def stop() -> None:
            nonlocal active
            active = False
            if self._viewport_commit is not None:
                self._viewport_commit.frames.pop(check_frame, None)
            try:
                with CancelScope(shield=True):
                    await cdp.detach()
            except Exception:
                logger.debug("screencast stop failed", exc_info=True)

        cdp.on("Page.screencastFrame", on_frame)
        try:
            await cdp.send(
                "Page.startScreencast",
                {
                    "format": "jpeg",
                    "quality": SCREENCAST_QUALITY,
                    # Chromium follows changes in surface size within these bounds.
                    "maxWidth": VIEWPORT_MAX[0] * MAX_DEVICE_SCALE,
                    "maxHeight": VIEWPORT_MAX[1] * MAX_DEVICE_SCALE,
                },
            )
        except BaseException:
            await stop()
            raise
        return stop

    async def save_login(self, path: Path) -> None:
        """Keep the teacher's login for next time (Playwright storage_state)."""
        state = await self._context.storage_state()
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")
        tmp.replace(path)

    async def close(self) -> None:
        async with self._viewport_lock:
            await _close_context(self._context, self._profile_dir)
            cdp, self._screen_cdp = self._screen_cdp, None
            screen, self._screen = self._screen, None
            if cdp is not None:
                try:
                    if screen is not None:
                        await cdp.send("Emulation.removeScreen", {"screenId": screen["id"]})
                finally:
                    await cdp.detach()


def _png_at_css_size(png: bytes, viewport: tuple[int, int]) -> bytes:
    with Image.open(io.BytesIO(png)) as image:
        if image.size == viewport:
            return png
        resized = image.resize(viewport, Image.Resampling.LANCZOS)
        out = io.BytesIO()
        resized.save(out, format="PNG")
        return out.getvalue()


def _navigation_error(url: str, error_code: str, *, timed_out: bool = False) -> ToolError:
    message = "连不上该公开页，或访问被拦截"
    if timed_out or error_code in {"ERR_TIMED_OUT", "ERR_CONNECTION_TIMED_OUT"}:
        message = "打开公开页超时"
    elif error_code in {
        "ERR_NAME_NOT_RESOLVED", "ERR_NAME_RESOLUTION_FAILED",
    } or error_code.startswith("ERR_DNS_"):
        message = "无法解析该公开页的域名（DNS 失败）"
    elif error_code == "ERR_CONNECTION_REFUSED":
        message = "连不上该公开页（连接被拒绝）"
    elif error_code == "ERR_HTTP_RESPONSE_CODE_FAILURE":
        message = "公开页返回错误状态"
    if url:
        parts = urlsplit(url)
        # Redirect targets can include login tokens.
        safe_url = urlunsplit((parts.scheme, parts.netloc.rsplit("@", 1)[-1], parts.path, "", ""))
        reason = f"{error_code}，{message}" if error_code else message
        message = f"页面打开失败：地址 {safe_url}（{reason}）"
    elif error_code:
        message += f"（{error_code}）"
    return ToolError("sandbox.fetch_failed", message)


async def _navigate_page(failure: _NavigationFailure, url: str | None) -> str:
    from playwright.async_api import Error
    from playwright.async_api import TimeoutError as PlaywrightTimeoutError

    page = failure.page
    before = page.url
    failure.failed = None
    deadline = time.monotonic() + GOTO_TIMEOUT_MS / 1000
    try:
        if url is None:
            response = await page.go_back(wait_until="commit", timeout=GOTO_TIMEOUT_MS)
            if response is None and page.url == before:
                raise ToolError("sandbox.action_failed", "这个标签页没有上一页")
        else:
            response = await page.goto(url, wait_until="commit", timeout=GOTO_TIMEOUT_MS)
        failure.check_error_page()
        if response is not None and response.status >= 400:
            logger.warning("Chromium navigation returned HTTP %s", response.status)
            raise ToolError("sandbox.fetch_failed", f"公开页返回 HTTP {response.status}")

        remaining_ms = (deadline - time.monotonic()) * 1000
        if remaining_ms <= 0:
            return PAGE_LOADING_NOTE
        try:
            await page.wait_for_load_state("domcontentloaded", timeout=remaining_ms)
        except PlaywrightTimeoutError:
            failure.check_error_page()
            logger.info("Chromium committed but DOM is still loading", exc_info=True)
            return PAGE_LOADING_NOTE
        failure.check_error_page()
        return ""
    except Error as exc:
        logger.warning("Chromium navigation failed", exc_info=True)
        match = CHROMIUM_NET_ERROR.search(str(exc).partition("\n")[0])
        error_code = match[1] if match else ""
        failed_url, error_code = failure.failed or (url or "", error_code)
        if failed_url and error_code and error_code != "ERR_ABORTED":
            failure.failed = (failed_url, error_code)
        raise _navigation_error(
            failed_url, error_code, timed_out=isinstance(exc, PlaywrightTimeoutError),
        ) from exc


async def open_chromium(url: str, *, login_state: Path | None = None) -> PlaywrightPage:
    """Open a public URL in headless Chromium. Caller already ran web_guard.

    ``login_state`` = the teacher's saved login; the site opens already logged in.
    """
    parse_public_http_url(url)
    browser = await _ensure_browser()
    profile_dir = Path(tempfile.mkdtemp(prefix="sbox_", dir=str(_profile_root())))
    context = None
    opened = False
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
        failure = _NavigationFailure(page)
        loading_note = await _navigate_page(failure, url)
        parse_public_http_url(page.url)
        surface = PlaywrightPage(context, page, profile_dir, initial_failure=failure)
        surface.loading_note = loading_note
        opened = True
        return surface
    except ToolError:
        raise
    except Exception as exc:
        logger.warning("Chromium page setup failed", exc_info=True)
        raise ToolError("sandbox.fetch_failed", "无法创建隔离 Chromium 页面") from exc
    finally:
        if not opened:
            await _close_context(context, profile_dir)


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
