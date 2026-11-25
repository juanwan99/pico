"""In-memory B2 Chromium sessions.

Sessions die with this process / TTL. The teacher's site login is kept on
their own disk (``.browser-login.json``, Playwright storage_state) so the next
open is already logged in — never the host home directory.
Passwords are never written to logs, tool payloads, or screenshot text overlays.
"""

from __future__ import annotations

import asyncio
import base64
import hashlib
import json
import logging
import mimetypes
import os
import secrets
import time
from collections.abc import AsyncGenerator, Awaitable, Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from pico_orchestrator.gateway import ToolError
from pico_orchestrator.sandbox_persist import (
    PERSIST_COPY,
    list_owner_disk_names,
    owner_disk_dir,
    owner_disk_meta,
    read_owner_disk_file,
    write_owner_disk_file,
)
from pico_orchestrator.sandbox_s1 import workspace_id_for
from pico_orchestrator.web_guard import parse_public_http_url

from sandbox_worker.browser import (
    ENGINE_NAME,
    PNG_MAGIC,
    BrowserHands,
    BrowserPage,
    RefBook,
    ScreencastFrame,
    open_chromium,
)
from sandbox_worker.files import FilesSurface, list_workspace_files, open_files_surface
from sandbox_worker.office import (
    KIND_LABEL,
    OFFICE_ENGINE,
    OfficeDesktop,
    open_office,
    resolve_kind,
)

logger = logging.getLogger(__name__)

HUMAN_LOGIN_COPY = "这是你的隔离浏览器，可以直接在画面里操作"
HUMAN_OFFICE_COPY = "沙箱已用 LibreOffice 打开这份文档。这是字处理窗口，不是 PDF，也不是下载。"
SESSION_TTL_S = int(os.environ.get("PICO_SANDBOX_TTL_S") or str(30 * 60))
MAX_SESSIONS = int(os.environ.get("PICO_SANDBOX_MAX_SESSIONS") or "10")
# A committed page can still stall Chromium calls. Leave room under the sidecar deadline.
LOADING_SCREENSHOT_TIMEOUT_S = 10.0
LOADING_SNAPSHOT_TIMEOUT_S = 8.0
LOADING_METADATA_TIMEOUT_S = 8.0
# 15 s in the queue + up to 71 s for navigation and sync fits pico-api's 90 s.
ACT_LOCK_TIMEOUT_S = 15.0
APPLIED_COPY = "已把操作送进 sidecar Chromium。登录状态存在你自己的老师盘上，下次打开不用再登。"
# Saved login (owner 2026-10-11 09:17): one file per teacher on their own disk.
# Clearing the teacher disk, or logging out on the site, drops it.
LOGIN_FILE = ".browser-login.json"
LOGIN_SAVE_EVERY_S = 15.0
# Live pane (#1215): follow tab/focus changes promptly, keep proxies awake.
STREAM_CHECK_S = 0.1
STREAM_PING_S = 15.0
STREAM_MAX_IN_FLIGHT = 2
# "current" = the caller's own desk (one per school+membership). Lets the AI act
# on a pane the teacher opened without having the session id in hand.
CURRENT_SESSION = "current"
# Takeover (#1230): the pane says「AI 正在操作」while the AI touched the page this recently.
AI_ACTING_S = 60.0
HUMAN_HOLD_COPY = "老师接管了这个画面，正在自己操作。先停下，等老师点「交还 AI」后再继续。"
HANDS_ACTIONS = frozenset(
    {
        "snapshot", "navigate", "navigate_back", "click", "hover", "type",
        "select_option", "press_key", "wait_for", "tabs", "fill_form", "file_upload",
        "page_file", "page_fn",
    }
)
HANDS_COPY = {
    "snapshot": "已读取当前页面快照（带编号）。",
    "navigate": "已在沙箱 Chromium 打开新网址。",
    "navigate_back": "已后退到上一页。",
    "click": "已点击。",
    "hover": "已移到元素上。",
    "tabs": "已列出标签页。",
    "fill_form": "已填好表单。",
    "file_upload": "已传上附件。",
    "page_file": "已把文件放进这一页（未点文件框）。",
    "page_fn": "已调用页内函数。",
    "type": "已填入文字。",
    "select_option": "已选中选项。",
    "press_key": "已按键。",
    "wait_for": "已等到。",
}

OpenBrowser = Callable[..., Awaitable[BrowserPage]]


@dataclass
class SandboxWindow:
    window_id: str
    kind: str
    surface: BrowserPage | OfficeDesktop
    # Stable element refs for AI hands (#1222); browser windows only.
    refs: RefBook = field(default_factory=RefBook)


@dataclass
class SandboxSession:
    session_id: str
    school_id: str
    membership_id: str
    run_id: str
    workspace_id: str
    url: str
    title: str
    h1: str
    screenshot_png: bytes
    created_at: float
    last_used: float = 0.0
    windows: list[SandboxWindow] = field(default_factory=list)
    focused_id: str = ""
    kind: str = "browser"
    secret_fields: set[str] = field(default_factory=set)
    has_text_input: bool = False
    has_password_input: bool = False
    login_saved_at: float = 0.0
    # Takeover (#1230): while held, the AI's hands (/act) are refused.
    human_hold: bool = False
    ai_acted_at: float = 0.0
    act_lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    live_panes: dict[asyncio.Event, str] = field(default_factory=dict)
    frame_acks: dict[str, asyncio.Event] = field(default_factory=dict)

    def focused(self) -> SandboxWindow:
        for item in self.windows:
            if item.window_id == self.focused_id:
                return item
        if self.windows:
            return self.windows[-1]
        raise ToolError("sandbox.session_not_found", "隔离会话没有可截取的窗口")

    @property
    def browser(self) -> BrowserPage | None:
        for item in self.windows:
            if item.kind == "browser":
                return item.surface  # type: ignore[return-value]
        return None

    def is_streaming(self, win: SandboxWindow) -> bool:
        return win.window_id in self.live_panes.values()

    @property
    def desktop(self) -> OfficeDesktop | None:
        focused = None
        try:
            focused = self.focused()
        except ToolError:
            focused = None
        if focused is not None and focused.kind != "browser":
            return focused.surface  # type: ignore[return-value]
        for item in self.windows:
            if item.kind != "browser":
                return item.surface  # type: ignore[return-value]
        return None

    def engine_name(self) -> str:
        if self.kind == "files":
            return "sandbox-files"
        return OFFICE_ENGINE if self.kind != "browser" else ENGINE_NAME

    def human_copy(self) -> str:
        if self.kind == "files":
            return PERSIST_COPY
        return HUMAN_OFFICE_COPY if self.kind != "browser" else HUMAN_LOGIN_COPY

    def window_meta(self) -> list[dict[str, str]]:
        out: list[dict[str, str]] = []
        for item in self.windows:
            label = (
                "浏览器"
                if item.kind == "browser"
                else "文件"
                if item.kind == "files"
                else KIND_LABEL.get(item.kind, item.kind)
            )
            out.append(
                {
                    "window_id": item.window_id,
                    "kind": item.kind,
                    "title": label,
                    "focused": "1" if item.window_id == self.focused_id else "0",
                }
            )
        return out


def isolation_tuple(school_id: str, membership_id: str, run_id: str | None) -> tuple[str, str, str]:
    return (
        (school_id or "").strip(),
        (membership_id or "").strip(),
        (run_id or "").strip() or "_norun",
    )



def redact_secrets(payload: dict[str, Any], secret_fields: set[str] | None = None) -> dict[str, Any]:
    """Drop password-like values from anything that might be logged or returned."""
    banned_keys = {"password", "passwd", "secret", "credential", "cookie", "cookies"}
    out: dict[str, Any] = {}
    for key, value in payload.items():
        low = str(key).lower()
        if low in banned_keys or (secret_fields and key in secret_fields):
            continue
        if isinstance(value, str) and low.endswith("password"):
            continue
        out[key] = value
    return out


def _loading_meta(surface: BrowserPage) -> dict[str, str]:
    note = getattr(surface, "loading_note", "")
    return {"note": note} if note else {}


class SandboxRuntime:
    """Process-local Chromium session table. Not LibreChat. Not pico-api."""

    def __init__(self, open_browser: OpenBrowser | None = None) -> None:
        self._sessions: dict[str, SandboxSession] = {}
        self._opening = 0
        self._open_browser = open_browser or open_chromium

    @contextmanager
    def _reserve_session(self) -> Iterator[None]:
        if len(self._sessions) + self._opening >= MAX_SESSIONS:
            raise ToolError("sandbox.quota", f"沙箱已满（最多 {MAX_SESSIONS} 路），请关掉一路再开。")
        self._opening += 1
        try:
            yield
        finally:
            self._opening -= 1

    async def _purge(self) -> None:
        now = time.time()
        for sess in list(self._sessions.values()):
            # Recheck after each awaited close. Another request may now be acting
            # on this session or may have refreshed it.
            if (
                not sess.act_lock.locked()
                and now - (sess.last_used or sess.created_at) > SESSION_TTL_S
            ):
                await self.destroy(sess.session_id)

    def get(self, session_id: str) -> SandboxSession | None:
        return self._sessions.get(session_id)

    def require_owner(
        self,
        session_id: str,
        *,
        school_id: str,
        membership_id: str,
    ) -> SandboxSession:
        if (session_id or "").strip() == CURRENT_SESSION:
            sess = self._find_desk((school_id or "").strip(), (membership_id or "").strip())
            if sess is None:
                raise ToolError(
                    "sandbox.session_not_found",
                    "还没有打开沙箱浏览器。先调用 sandbox_browser_open 打开一个公开页。",
                )
            return sess
        sess = self.get(session_id)
        if sess is None:
            raise ToolError("sandbox.session_not_found", "找不到该隔离会话")
        if sess.school_id != school_id or sess.membership_id != membership_id:
            raise ToolError("sandbox.forbidden", "无权查看该隔离会话")
        return sess

    def _find_desk(self, school_id: str, membership_id: str) -> SandboxSession | None:
        for sess in self._sessions.values():
            if sess.school_id == school_id and sess.membership_id == membership_id:
                return sess
        return None

    @staticmethod
    def _login_path(school_id: str, membership_id: str) -> Path:
        return owner_disk_dir(school_id, membership_id) / LOGIN_FILE

    async def _save_login(self, sess: SandboxSession, *, throttle: bool = False) -> None:
        now = time.time()
        if throttle and now - sess.login_saved_at < LOGIN_SAVE_EVERY_S:
            return
        for item in sess.windows:
            save = getattr(item.surface, "save_login", None)
            if item.kind != "browser" or not callable(save):
                continue
            try:
                await save(self._login_path(sess.school_id, sess.membership_id))
                sess.login_saved_at = now
            except Exception:
                logger.debug("sandbox login save failed", exc_info=True)

    def _workspace(self, sess: SandboxSession) -> Path:
        root = owner_disk_dir(sess.school_id, sess.membership_id)
        root.mkdir(parents=True, exist_ok=True)
        return root

    def _file_names(self, sess: SandboxSession) -> list[str]:
        names = list_owner_disk_names(sess.school_id, sess.membership_id)
        if names:
            return names
        return list_workspace_files(self._workspace(sess))

    def _write_workspace_file(self, sess: SandboxSession, filename: str, document: bytes) -> None:
        write_owner_disk_file(sess.school_id, sess.membership_id, filename, document)

    def _read_workspace_file(self, sess: SandboxSession, filename: str) -> bytes:
        return read_owner_disk_file(sess.school_id, sess.membership_id, filename)

    async def _ensure_files_window(self, sess: SandboxSession) -> None:
        names = self._file_names(sess)
        for item in sess.windows:
            if item.kind == "files":
                surface = item.surface
                if isinstance(surface, FilesSurface):
                    await surface.render(names)
                return
        surface = await open_files_surface(names)
        win = SandboxWindow(window_id="win_" + secrets.token_hex(6), kind="files", surface=surface)
        sess.windows.append(win)

    async def _sync(self, sess: SandboxSession, *, capture: bool = True) -> None:
        win = sess.focused()
        surface = win.surface
        sess.kind = win.kind
        sess.url = surface.url
        sess.title = await surface.title()
        if capture:
            sess.h1 = await surface.h1()
            png = await surface.screenshot_png()
            if not png.startswith(PNG_MAGIC):
                raise ToolError("sandbox.raster_failed", "隔离窗口未能截取画面")
            sess.screenshot_png = png
        describe = getattr(surface, "describe_inputs", None)
        if callable(describe):
            try:
                flags = await describe()
            except Exception:
                logger.debug("describe_inputs failed", exc_info=True)
                flags = {}
        else:
            flags = {}
        sess.has_text_input = bool((flags or {}).get("has_text_input"))
        sess.has_password_input = bool((flags or {}).get("has_password_input"))
        sess.last_used = time.time()

    async def _sync_after_navigation(
        self, sess: SandboxSession, loading: dict[str, str]
    ) -> None:
        timeout = asyncio.timeout(LOADING_SCREENSHOT_TIMEOUT_S if loading else None)
        try:
            async with timeout:
                await self._sync(sess)
        except TimeoutError:
            if not timeout.expired():
                raise
            logger.info("Chromium screen sync timed out while loading", exc_info=True)
            sess.title = sess.h1 = ""
            sess.screenshot_png = b""
            sess.has_text_input = sess.has_password_input = False
            sess.last_used = time.time()
            loading["note"] += "本次未能及时取得截图。"

    def _public_meta(self, sess: SandboxSession, **extra: Any) -> dict[str, Any]:
        disk = owner_disk_meta(sess.school_id, sess.membership_id)
        persist_note = PERSIST_COPY if sess.kind == "files" else sess.human_copy()
        return redact_secrets(
            {
                "ok": True,
                "session_id": sess.session_id,
                "workspace_id": sess.workspace_id,
                "url": sess.url,
                "title": sess.title,
                "h1": sess.h1,
                "kind": sess.kind,
                "engine": sess.engine_name(),
                "view_path": f"/v1/sandbox/sessions/{sess.session_id}/view",
                "human_copy": persist_note,
                "windows": sess.window_meta(),
                "focused_window_id": sess.focused_id,
                "files": disk.get("files") or [{"name": name} for name in self._file_names(sess)],
                "persist": True,
                "disk_bytes": disk.get("disk_bytes"),
                "disk_quota_bytes": disk.get("disk_quota_bytes"),
                "byte_size": len(sess.screenshot_png),
                "mime": "image/png",
                "has_text_input": sess.has_text_input,
                "has_password_input": sess.has_password_input,
                "human_hold": sess.human_hold,
                "ai_acting": not sess.human_hold
                and time.time() - sess.ai_acted_at < AI_ACTING_S,
                **extra,
            },
            sess.secret_fields,
        )

    async def open_session(
        self,
        *,
        school_id: str,
        membership_id: str,
        run_id: str | None,
        url: str = "",
        kind: str = "",
        filename: str = "",
        document: bytes | None = None,
    ) -> dict[str, Any]:
        kind_l = (kind or "").strip().lower()
        if kind_l == "files":
            return await self.open_files_desk(
                school_id=school_id,
                membership_id=membership_id,
                run_id=run_id,
            )
        if document or (kind_l and kind_l != "browser"):
            return await self.open_document(
                school_id=school_id,
                membership_id=membership_id,
                run_id=run_id,
                kind=kind_l,
                filename=filename,
                document=document or b"",
            )
        await self._purge()
        parse_public_http_url(url)
        school, member, run = isolation_tuple(school_id, membership_id, run_id)
        existing = self._find_desk(school, member)
        if existing is not None:
            return await self._attach_browser(existing, url)
        with self._reserve_session():
            page = await self._open_browser(url, login_state=self._login_path(school, member))
            loading = _loading_meta(page)
            stored = False
            try:
                parse_public_http_url(page.url)
                session_id = "sbox_" + secrets.token_hex(12)
                ws = workspace_id_for(school, member, run)
                win = SandboxWindow(window_id="win_" + secrets.token_hex(6), kind="browser", surface=page)
                sess = SandboxSession(
                    session_id=session_id,
                    school_id=school,
                    membership_id=member,
                    run_id=run,
                    workspace_id=ws,
                    url=page.url,
                    title="",
                    h1="",
                    screenshot_png=b"",
                    created_at=time.time(),
                    windows=[win],
                    focused_id=win.window_id,
                    kind="browser",
                )
                await self._ensure_files_window(sess)
                await self._sync_after_navigation(sess, loading)
                self._sessions[session_id] = sess
                stored = True
            except Exception:
                if not stored:
                    await page.close()
                raise
        return self._public_meta(
            sess,
            message=(
                f"已在 sidecar Chromium 打开公开页。{HUMAN_LOGIN_COPY}"
                "登录一次后存在你的老师盘上，下次打开自动带上。"
            ),
            **loading,
        )

    async def open_files_desk(
        self,
        *,
        school_id: str,
        membership_id: str,
        run_id: str | None,
    ) -> dict[str, Any]:
        await self._purge()
        school, member, run = isolation_tuple(school_id, membership_id, run_id)
        existing = self._find_desk(school, member)
        if existing is not None:
            await self._ensure_files_window(existing)
            for item in existing.windows:
                if item.kind == "files":
                    existing.focused_id = item.window_id
                    break
            await self._sync(existing)
            return self._public_meta(existing, message=PERSIST_COPY)
        with self._reserve_session():
            session_id = "sbox_" + secrets.token_hex(12)
            ws = workspace_id_for(school, member, run)
            sess = SandboxSession(
                session_id=session_id,
                school_id=school,
                membership_id=member,
                run_id=run,
                workspace_id=ws,
                url="sandbox://files",
                title="",
                h1="",
                screenshot_png=b"",
                created_at=time.time(),
                windows=[],
                focused_id="",
                kind="files",
            )
            await self._ensure_files_window(sess)
            if not sess.windows:
                raise ToolError("sandbox.session_not_found", "老师盘未能打开")
            sess.focused_id = sess.windows[-1].window_id
            await self._sync(sess)
            self._sessions[session_id] = sess
        return self._public_meta(sess, message=PERSIST_COPY)

    async def open_document(
        self,
        *,
        school_id: str,
        membership_id: str,
        run_id: str | None,
        kind: str,
        filename: str,
        document: bytes,
    ) -> dict[str, Any]:
        await self._purge()
        resolved = resolve_kind(filename, kind)
        safe_name = Path(filename or "document.docx").name or "document.docx"
        school, member, run = isolation_tuple(school_id, membership_id, run_id)
        payload = document or b""
        if not payload:
            payload = read_owner_disk_file(school, member, safe_name)
        existing = self._find_desk(school, member)
        if existing is not None:
            return await self._attach_office(
                existing, kind=resolved, filename=safe_name, document=payload
            )
        with self._reserve_session():
            desktop = await open_office(kind=resolved, filename=safe_name, document=payload)
            session_id = "sbox_" + secrets.token_hex(12)
            ws = workspace_id_for(school, member, run)
            win = SandboxWindow(window_id="win_" + secrets.token_hex(6), kind=resolved, surface=desktop)
            sess = SandboxSession(
                session_id=session_id,
                school_id=school,
                membership_id=member,
                run_id=run,
                workspace_id=ws,
                url=desktop.url,
                title="",
                h1="",
                screenshot_png=b"",
                created_at=time.time(),
                windows=[win],
                focused_id=win.window_id,
                kind=resolved,
            )
            try:
                self._write_workspace_file(sess, safe_name, payload)
                await self._ensure_files_window(sess)
                await self._sync(sess)
            except Exception:
                await desktop.close()
                raise
            self._sessions[session_id] = sess
        label = KIND_LABEL.get(resolved, resolved)
        return self._public_meta(
            sess,
            message=f"已在沙箱 {label} 打开 {safe_name}。{HUMAN_OFFICE_COPY}",
        )

    async def _attach_browser(self, sess: SandboxSession, url: str) -> dict[str, Any]:
        for item in sess.windows:
            if item.kind == "browser":
                sess.focused_id = item.window_id
                copy = "已切回 sidecar Chromium。"
                loading: dict[str, str] = {}
                # A new address goes to the open window; the same one just switches back.
                go = getattr(item.surface, "navigate", None)
                if callable(go) and url.rstrip("/") != item.surface.url.rstrip("/"):
                    await go(url)
                    copy = "已在 sidecar Chromium 打开公开页。"
                    loading = _loading_meta(item.surface)
                await self._sync_after_navigation(sess, loading)
                return self._public_meta(sess, message=f"{copy}{HUMAN_LOGIN_COPY}", **loading)
        page = await self._open_browser(
            url, login_state=self._login_path(sess.school_id, sess.membership_id)
        )
        loading = _loading_meta(page)
        try:
            parse_public_http_url(page.url)
            win = SandboxWindow(window_id="win_" + secrets.token_hex(6), kind="browser", surface=page)
            sess.windows.append(win)
            sess.focused_id = win.window_id
            await self._ensure_files_window(sess)
            await self._sync_after_navigation(sess, loading)
        except Exception:
            await page.close()
            raise
        return self._public_meta(
            sess,
            message=f"已在 sidecar Chromium 打开公开页。{HUMAN_LOGIN_COPY}",
            **loading,
        )

    async def _attach_office(
        self,
        sess: SandboxSession,
        *,
        kind: str,
        filename: str,
        document: bytes,
    ) -> dict[str, Any]:
        self._write_workspace_file(sess, filename, document)
        for item in list(sess.windows):
            if item.kind != kind:
                continue
            # Always reload. Focusing a live Impress/Writer window keeps the old bytes
            # even after the teacher-disk file was overwritten (same-chat edit).
            try:
                await item.surface.close()
            except Exception:
                logger.debug("replace office window close failed", exc_info=True)
            sess.windows = [w for w in sess.windows if w.window_id != item.window_id]
            break
        desktop = await open_office(kind=kind, filename=filename, document=document)
        try:
            win = SandboxWindow(window_id="win_" + secrets.token_hex(6), kind=kind, surface=desktop)
            sess.windows.append(win)
            sess.focused_id = win.window_id
            await self._ensure_files_window(sess)
            await self._sync(sess)
        except Exception:
            await desktop.close()
            raise
        return self._public_meta(
            sess,
            message=f"已在沙箱 {KIND_LABEL.get(kind, kind)} 打开 {filename}。{HUMAN_OFFICE_COPY}",
        )

    async def focus(self, session: SandboxSession, *, window_id: str = "", kind: str = "") -> dict[str, Any]:
        target = (window_id or "").strip()
        want_kind = (kind or "").strip().lower()
        chosen: SandboxWindow | None = None
        for item in session.windows:
            if target and item.window_id == target:
                chosen = item
                break
            if want_kind and item.kind == want_kind:
                chosen = item
        if chosen is None:
            raise ToolError("sandbox.session_not_found", "找不到要切换的窗口")
        session.focused_id = chosen.window_id
        await self._sync(session)
        return self._public_meta(session, message=f"已切到{chosen.kind}窗口")

    async def screenshot(self, session: SandboxSession) -> dict[str, Any]:
        await self._purge()
        await self._sync(session)
        await self._save_login(session, throttle=True)
        return self._public_meta(
            session,
            png_sha256=hashlib.sha256(session.screenshot_png).hexdigest()[:16],
        )

    async def pane_meta(self, session: SandboxSession) -> dict[str, Any]:
        win = session.focused()
        if not session.is_streaming(win):
            return await self.screenshot(session)
        await self._sync(session, capture=False)
        await self._save_login(session, throttle=True)
        return self._public_meta(session)

    async def apply_input(
        self,
        session: SandboxSession,
        *,
        click_x: int | None = None,
        click_y: int | None = None,
        text: str | None = None,
        password: bool = False,
        field: str = "input",
        scroll_dy: int | None = None,
        key: str = "",
        viewport_width: int | None = None,
        viewport_height: int | None = None,
        device_pixel_ratio: float | None = None,
        drag: str = "",
        frame_ack: str = "",
    ) -> dict[str, Any]:
        if frame_ack:
            wake = session.frame_acks.pop(frame_ack, None)
            if wake is not None:
                wake.set()
            return {"ok": True}
        await self._purge()
        win = session.focused()
        surface = win.surface
        streaming = session.is_streaming(win)
        motion = {"settle": False} if streaming else {}
        hand = getattr(surface, "drag", None)
        if drag and callable(hand) and click_x is not None and click_y is not None:
            await hand(drag, int(click_x), int(click_y), **motion)
            if drag != "up":
                # Mid-drag: the pane watches the stream; no full screenshot per move.
                return {"ok": True, "drag": drag}
            click_x = click_y = None
        fit = getattr(surface, "set_viewport", None)
        if viewport_width and viewport_height and callable(fit):
            for wake in session.live_panes:
                wake.set()
            if device_pixel_ratio is None:
                await fit(viewport_width, viewport_height)
            else:
                await fit(viewport_width, viewport_height, device_pixel_ratio)
        clicked = click_x is not None and click_y is not None
        if clicked:
            await surface.click(int(click_x), int(click_y), **motion)
        if text is not None:
            if password:
                session.secret_fields.add(field)
            await surface.type_text(text, password=password)
        scroll = getattr(surface, "scroll", None)
        if scroll_dy and callable(scroll):
            await scroll(int(scroll_dy))
        press = getattr(surface, "press_human_key", None)
        if key and callable(press):
            await press(key, **motion)
        if streaming:
            await self._sync(session, capture=False)
            await self._save_login(session, throttle=True)
            return {
                "ok": True,
                "url": session.url,
                "title": session.title,
                "has_text_input": session.has_text_input,
                "has_password_input": session.has_password_input,
                "clicked": clicked,
                "typed": bool(text),
            }
        await self._sync(session)
        await self._save_login(session)
        return self._public_meta(
            session,
            clicked=clicked,
            typed=bool(text),
            password_typed=bool(password and text),
            message=APPLIED_COPY if session.kind == "browser" else HUMAN_OFFICE_COPY,
        )

    def hold(self, session: SandboxSession, *, hold: bool) -> dict[str, Any]:
        """Takeover (#1230): the teacher holds the page; 交还 AI releases it."""
        session.human_hold = bool(hold)
        session.ai_acted_at = 0.0
        return self._public_meta(
            session, message="你在操作，AI 已停手" if hold else "已交还 AI"
        )

    def _hands(self, session: SandboxSession) -> SandboxWindow:
        """The browser window the AI may act on. Office/files windows are not pages."""
        for item in session.windows:
            if item.kind == "browser":
                session.focused_id = item.window_id
                if not callable(getattr(item.surface, "snapshot", None)):
                    raise ToolError("sandbox.unavailable", "这个浏览器窗口不支持 AI 操作")
                return item
        raise ToolError(
            "sandbox.session_not_found",
            "这路沙箱没有浏览器窗口。先调用 sandbox_browser_open 打开一个公开页。",
        )

    async def act(
        self,
        session: SandboxSession,
        *,
        action: str,
        ref: str = "",
        text: str = "",
        values: list[str] | None = None,
        key: str = "",
        submit: bool = False,
        slowly: bool = False,
        url: str = "",
        seconds: float = 0.0,
        text_gone: str = "",
        double_click: bool = False,
        tab_action: str = "",
        index: int = 0,
        fields: list[dict[str, Any]] | None = None,
        filenames: list[str] | None = None,
        files: list[dict[str, Any]] | None = None,
        fn: str = "",
        fn_args: list[Any] | None = None,
    ) -> dict[str, Any]:
        """AI hands (#1207): one Playwright action, then the page snapshot — after
        an action only what changed (#1222); `snapshot` itself is always full.

        Payment clicks are refused inside the browser adapter
        (sandbox.human_required). Never logs `text`.
        """
        await self._purge()
        # Playwright changes the current tab and refreshes aria refs on snapshot.
        # Keep each action and its snapshot together on this teacher's desk.
        try:
            await asyncio.wait_for(session.act_lock.acquire(), ACT_LOCK_TIMEOUT_S)
        except TimeoutError as exc:
            raise ToolError("browser.busy", "上一个浏览器操作还没做完，稍后再试") from exc
        try:
            self.require_owner(
                session.session_id, school_id=session.school_id, membership_id=session.membership_id
            )
            if session.human_hold:
                raise ToolError("sandbox.human_took_over", HUMAN_HOLD_COPY)
            verb = (action or "").strip().lower()
            if verb not in HANDS_ACTIONS:
                raise ToolError("tool.invalid_arguments", f"未知动作 {verb or '(空)'}")
            session.ai_acted_at = time.time()
            window = self._hands(session)
            hands: BrowserHands = window.surface  # type: ignore[assignment]
            try:
                page_result: Any = None
                page_file_meta: dict[str, Any] = {}
                if verb == "navigate":
                    parse_public_http_url(url)
                    await hands.navigate(url)
                elif verb == "navigate_back":
                    await hands.navigate_back()
                elif verb == "click":
                    await hands.click_ref(ref, double=bool(double_click))
                elif verb == "hover":
                    await hands.hover_ref(ref)
                elif verb == "tabs":
                    await hands.tabs(tab_action or "list", int(index or 0))
                elif verb == "fill_form":
                    await hands.fill_form(list(fields or []))
                elif verb == "file_upload":
                    await hands.upload_files(ref, self._upload_payload(session, filenames, files))
                elif verb == "page_file":
                    page_file_meta = await hands.page_file(self._upload_payload(session, filenames, files))
                elif verb == "page_fn":
                    page_result = await hands.page_fn(fn, list(fn_args or []))
                elif verb == "type":
                    await hands.type_ref(ref, text, submit=bool(submit), slowly=bool(slowly))
                elif verb == "select_option":
                    await hands.select_ref(ref, [str(v) for v in (values or [])])
                elif verb == "press_key":
                    await hands.press_key(key)
                elif verb == "wait_for":
                    await hands.wait_for(text=text, text_gone=text_gone, seconds=float(seconds or 0))
                loading = (
                    _loading_meta(window.surface) if verb in {"navigate", "navigate_back"} else {}
                )
                extra: dict[str, Any] = {}
                timeout = asyncio.timeout(LOADING_SNAPSHOT_TIMEOUT_S if loading else None)
                try:
                    async with timeout:
                        snapshot = await hands.snapshot()
                except TimeoutError:
                    if not timeout.expired():
                        raise
                    logger.info("Chromium snapshot timed out while loading", exc_info=True)
                    loading["note"] += "本次未能及时取得快照。"
                else:
                    full, delta = window.refs.update(snapshot, page=getattr(hands, "page_token", 0))
                    whole = verb == "snapshot" or delta is None
                    extra.update(snapshot=full if whole else delta, snapshot_mode="full" if whole else "delta")
                await self._sync_after_navigation(session, loading)

                message = HANDS_COPY.get(verb, APPLIED_COPY)
                timeout = asyncio.timeout(LOADING_METADATA_TIMEOUT_S if loading else None)
                try:
                    async with timeout:
                        await self._save_login(session)
                        dialogs = hands.take_dialogs()
                        if dialogs:
                            message += "".join(f"页面弹窗「{d}」，已点确定。" for d in dialogs)
                            extra["dialogs"] = dialogs
                        tabs = await hands.tabs("list", 0)
                except TimeoutError:
                    if not timeout.expired():
                        raise
                    logger.info("Chromium metadata sync timed out while loading", exc_info=True)
                    loading["note"] += "本次未能及时更新登录状态或标签页。"
                else:
                    if len(tabs) > 1 or verb == "tabs":
                        # A new tab opened (or the AI asked): it is already the current page.
                        extra["tabs"] = tabs
                if page_file_meta:
                    extra.update(page_file_meta)
                if verb == "page_fn":
                    extra["page_result"] = page_result
                return self._public_meta(
                    session,
                    action=verb,
                    message=message,
                    **loading,
                    **extra,
                )
            finally:
                session.last_used = time.time()
        finally:
            session.act_lock.release()

    def _upload_payload(
        self,
        session: SandboxSession,
        filenames: list[str] | None,
        files: list[dict[str, Any]] | None,
    ) -> list[tuple[str, str, bytes]]:
        """Attachments from the teacher's own disk (by name) or the ledger (bytes the
        gateway already read for this teacher). Never the host filesystem."""
        out: list[tuple[str, str, bytes]] = []
        for name in filenames or []:
            clean = Path(str(name)).name
            out.append((clean, _mime_of(clean), self._read_workspace_file(session, clean)))
        for item in files or []:
            name = Path(str(item.get("name") or "附件")).name
            try:
                raw = base64.b64decode(str(item.get("b64") or ""), validate=True)
            except (ValueError, TypeError) as exc:
                raise ToolError("tool.invalid_arguments", "附件内容不是 base64") from exc
            out.append((name, str(item.get("mime") or _mime_of(name)), raw))
        return out

    def _alive_focus(self, sess: SandboxSession) -> str:
        if self._sessions.get(sess.session_id) is not sess or not sess.windows:
            return ""
        return sess.focused().window_id

    async def stream(self, sess: SandboxSession) -> AsyncGenerator[dict[str, Any], None]:
        """Live pane (#1215): JPEG frames from the focused browser window.

        Office / files windows yield ``poll`` once; the pane keeps polling PNG.
        Ends when the session is destroyed. Watching does not keep it alive.
        """
        wake = asyncio.Event()
        sess.live_panes[wake] = ""
        waiting: dict[str, float] = {}
        last = time.monotonic()
        try:
            while window_id := self._alive_focus(sess):
                win = sess.focused()
                token = getattr(win.surface, "page_token", 0)
                cast = getattr(win.surface, "screencast", None)
                stop = None
                frames: asyncio.Queue[ScreencastFrame] = asyncio.Queue(maxsize=1)
                if callable(cast):
                    try:
                        stop = await cast(_keep_latest(frames, wake))
                    except Exception:
                        logger.debug("screencast start failed", exc_info=True)
                if stop is None:
                    sess.live_panes[wake] = ""
                    yield {"poll": True, "window_id": window_id}
                    last = time.monotonic()
                try:
                    # A tab switch or new viewport starts a cast at the new size.
                    while (
                        self._alive_focus(sess) == window_id
                        and getattr(win.surface, "page_token", 0) == token
                    ):
                        wake.clear()
                        now = time.monotonic()
                        for frame_id, expires in tuple(waiting.items()):
                            if now >= expires or frame_id not in sess.frame_acks:
                                sess.frame_acks.pop(frame_id, None)
                                del waiting[frame_id]
                        if len(waiting) < STREAM_MAX_IN_FLIGHT and not frames.empty():
                            frame = frames.get_nowait()
                            frame_id = secrets.token_hex(12)
                            waiting[frame_id] = now + STREAM_PING_S
                            sess.frame_acks[frame_id] = wake
                            sess.live_panes[wake] = window_id
                            last = now
                            yield {
                                "jpeg": frame.jpeg,
                                "width": frame.width,
                                "height": frame.height,
                                "frame_id": frame_id,
                                "window_id": window_id,
                            }
                            continue
                        if now - last >= STREAM_PING_S:
                            last = now
                            yield {"ping": True}
                            continue
                        deadline = next(iter(waiting.values()), last + STREAM_PING_S)
                        wait_s = min(STREAM_CHECK_S, deadline - now)
                        try:
                            await asyncio.wait_for(wake.wait(), wait_s)
                        except TimeoutError:  # swallow-ok: next iteration checks focus and deadlines
                            continue
                finally:
                    if stop is not None:
                        await stop()
        finally:
            for frame_id in waiting:
                sess.frame_acks.pop(frame_id, None)
            del sess.live_panes[wake]

    async def destroy(self, session_id: str) -> None:
        # Close Chromium / LibreOffice only. Owner disk stays on the host bind.
        sess = self._sessions.pop(session_id, None)
        if sess is None:
            return
        await self._save_login(sess)
        for item in sess.windows:
            try:
                await item.surface.close()
            except Exception:
                logger.debug("sandbox session close failed", exc_info=True)


def _mime_of(name: str) -> str:
    return mimetypes.guess_type(name)[0] or "application/octet-stream"


def _keep_latest(
    frames: asyncio.Queue[ScreencastFrame], wake: asyncio.Event
) -> Callable[[ScreencastFrame], None]:
    """A slow viewer skips stale frames instead of piling them up."""

    def push(frame: ScreencastFrame) -> None:
        if frames.full():
            frames.get_nowait()
        frames.put_nowait(frame)
        wake.set()

    return push


def sse_event(event: dict[str, Any]) -> bytes:
    return f"data: {json.dumps(event, separators=(',', ':'))}\n\n".encode()


RUNTIME = SandboxRuntime()
