"""In-memory B2 Chromium sessions.

Sessions die with this process / TTL. Cookies stay in the Chromium context
and a tmpfs profile directory — never the host home directory.
Passwords are never written to logs, tool payloads, or screenshot text overlays.
"""

from __future__ import annotations

import hashlib
import logging
import os
import secrets
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

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
    BrowserPage,
    open_chromium,
)
from sandbox_worker.files import FilesSurface, list_workspace_files, open_files_surface
from sandbox_worker.office import KIND_LABEL, OFFICE_ENGINE, open_office, resolve_kind
from sandbox_worker.office_preview import OfficePages

logger = logging.getLogger(__name__)

HUMAN_LOGIN_COPY = "请在此画面自行登录，不要在聊天里发送密码"
HUMAN_OFFICE_COPY = "沙箱只显示文档内容页，没有字处理工具栏。"
SESSION_TTL_S = int(os.environ.get("PICO_SANDBOX_TTL_S") or str(30 * 60))
MAX_SESSIONS = int(os.environ.get("PICO_SANDBOX_MAX_SESSIONS") or "8")
APPLIED_COPY = (
    "已把操作送进 sidecar Chromium。"
    "Cookie 只在会话内存/临时 profile，随销毁消失。"
)

_WECHAT_HOST_MARKERS = (
    "wx.qq.com",
    "weixin.qq.com",
    "wechat.com",
    "work.weixin.qq.com",
    "open.weixin.qq.com",
    "mp.weixin.qq.com",
)
_JIAOWU_HOST_MARKERS = (
    "jwxt",
    "jiaowu",
    "jwglxt",
    "urp.school",
    "eas.admin",
)

OpenBrowser = Callable[[str], Awaitable[BrowserPage]]


@dataclass
class SandboxWindow:
    window_id: str
    kind: str
    surface: BrowserPage | OfficePages | FilesSurface


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

    @property
    def desktop(self) -> OfficePages | FilesSurface | None:
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


def _host_of(url: str) -> str:
    return (urlparse(url).hostname or "").strip().lower().rstrip(".")


def automation_hostile_reason(url: str) -> str | None:
    """Honest fail for sites that commonly block automation. Not a success path."""
    host = _host_of(url)
    if not host:
        return None
    if any(marker in host for marker in _WECHAT_HOST_MARKERS):
        return (
            "该站点（微信）通常禁止自动化登录，本卡不要求登录成功。"
            "请改用公开页演示，或在隔离画面里自行操作。"
            f"{HUMAN_LOGIN_COPY}"
        )
    if any(marker in host for marker in _JIAOWU_HOST_MARKERS):
        return (
            "该站点（教务）通常禁止自动化登录，本卡不要求登录成功。"
            "请改用公开页（例如 example.com）演示人在环画面。"
            f"{HUMAN_LOGIN_COPY}"
        )
    return None


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


class SandboxRuntime:
    """Process-local Chromium session table. Not LibreChat. Not pico-api."""

    def __init__(self, open_browser: OpenBrowser | None = None) -> None:
        self._sessions: dict[str, SandboxSession] = {}
        self._open_browser = open_browser or open_chromium

    async def _purge(self) -> None:
        now = time.time()
        dead = [
            sid
            for sid, sess in self._sessions.items()
            if now - (sess.last_used or sess.created_at) > SESSION_TTL_S
        ]
        for sid in dead:
            await self.destroy(sid)

    def get(self, session_id: str) -> SandboxSession | None:
        return self._sessions.get(session_id)

    def require_owner(
        self,
        session_id: str,
        *,
        school_id: str,
        membership_id: str,
    ) -> SandboxSession:
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

    async def _sync(self, sess: SandboxSession) -> None:
        win = sess.focused()
        surface = win.surface
        sess.kind = win.kind
        sess.url = surface.url
        sess.title = await surface.title()
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
        hostile = automation_hostile_reason(url)
        if hostile:
            raise ToolError("sandbox.site_blocks_automation", hostile)
        school, member, run = isolation_tuple(school_id, membership_id, run_id)
        existing = self._find_desk(school, member)
        if existing is not None:
            return await self._attach_browser(existing, url)
        if len(self._sessions) >= MAX_SESSIONS:
            raise ToolError("sandbox.quota", "沙箱已满（最多 8 路），请关掉一路再开。机器未继续扩进程。")
        page = await self._open_browser(url)
        stored = False
        try:
            parse_public_http_url(page.url)
            hostile = automation_hostile_reason(page.url)
            if hostile:
                raise ToolError("sandbox.site_blocks_automation", hostile)
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
            await self._sync(sess)
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
                "会话随沙箱销毁，不会把 Cookie 写回宿主机。"
            ),
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
        if len(self._sessions) >= MAX_SESSIONS:
            raise ToolError("sandbox.quota", "沙箱已满（最多 8 路），请关掉一路再开。机器未继续扩进程。")
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
        if len(self._sessions) >= MAX_SESSIONS:
            raise ToolError("sandbox.quota", "沙箱已满（最多 8 路），请关掉一路再开。机器未继续扩进程。")
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
                await self._sync(sess)
                return self._public_meta(
                    sess,
                    message=f"已切回 sidecar Chromium。{HUMAN_LOGIN_COPY}",
                )
        page = await self._open_browser(url)
        try:
            parse_public_http_url(page.url)
            win = SandboxWindow(window_id="win_" + secrets.token_hex(6), kind="browser", surface=page)
            sess.windows.append(win)
            sess.focused_id = win.window_id
            await self._ensure_files_window(sess)
            await self._sync(sess)
        except Exception:
            await page.close()
            raise
        return self._public_meta(
            sess,
            message=f"已在 sidecar Chromium 打开公开页。{HUMAN_LOGIN_COPY}",
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
            existing_name = str(getattr(item.surface, "filename", "") or "")
            if existing_name == filename:
                sess.focused_id = item.window_id
                await self._ensure_files_window(sess)
                await self._sync(sess)
                return self._public_meta(
                    sess,
                    message=f"已切到沙箱 {KIND_LABEL.get(kind, kind)}。{HUMAN_OFFICE_COPY}",
                )
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
        return self._public_meta(
            session,
            png_sha256=hashlib.sha256(session.screenshot_png).hexdigest()[:16],
        )

    async def apply_input(
        self,
        session: SandboxSession,
        *,
        click_x: int | None = None,
        click_y: int | None = None,
        text: str | None = None,
        password: bool = False,
        field: str = "input",
    ) -> dict[str, Any]:
        await self._purge()
        surface = session.focused().surface
        clicked = click_x is not None and click_y is not None
        if clicked:
            await surface.click(int(click_x), int(click_y))
        if text is not None:
            if password:
                session.secret_fields.add(field)
            await surface.type_text(text, password=password)
        await self._sync(session)
        return self._public_meta(
            session,
            clicked=clicked,
            typed=bool(text),
            password_typed=bool(password and text),
            message=APPLIED_COPY if session.kind == "browser" else HUMAN_OFFICE_COPY,
        )

    async def destroy(self, session_id: str) -> None:
        # Close Chromium / LibreOffice only. Owner disk stays on the host bind.
        sess = self._sessions.pop(session_id, None)
        if sess is None:
            return
        for item in sess.windows:
            try:
                await item.surface.close()
            except Exception:
                logger.debug("sandbox session close failed", exc_info=True)


RUNTIME = SandboxRuntime()
