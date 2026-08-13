"""In-memory B2 Chromium sessions.

Sessions die with this process / TTL. Cookies stay in the Chromium context
and a tmpfs profile directory — never the host home directory.
Passwords are never written to logs, tool payloads, or screenshot text overlays.
"""

from __future__ import annotations

import hashlib
import logging
import secrets
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlparse

from pico_orchestrator.gateway import ToolError
from pico_orchestrator.sandbox_s1 import workspace_id_for
from pico_orchestrator.web_guard import parse_public_http_url

from sandbox_worker.browser import (
    ENGINE_NAME,
    PNG_MAGIC,
    BrowserPage,
    open_chromium,
)

logger = logging.getLogger(__name__)

HUMAN_LOGIN_COPY = "请在此画面自行登录，不要在聊天里发送密码"
SESSION_TTL_S = 30 * 60
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
    browser: BrowserPage
    secret_fields: set[str] = field(default_factory=set)


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
            if now - sess.created_at > SESSION_TTL_S
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
            # Same 404-shaped miss as artifacts — do not leak the other account.
            raise ToolError("sandbox.session_not_found", "找不到该隔离会话")
        return sess

    async def _sync(self, sess: SandboxSession) -> None:
        sess.url = sess.browser.url
        sess.title = await sess.browser.title()
        sess.h1 = await sess.browser.h1()
        png = await sess.browser.screenshot_png()
        if not png.startswith(PNG_MAGIC):
            raise ToolError("sandbox.raster_failed", "隔离 Chromium 未能截取 viewport")
        sess.screenshot_png = png

    async def open_session(
        self,
        *,
        school_id: str,
        membership_id: str,
        run_id: str | None,
        url: str,
    ) -> dict[str, Any]:
        await self._purge()
        parse_public_http_url(url)
        hostile = automation_hostile_reason(url)
        if hostile:
            raise ToolError("sandbox.site_blocks_automation", hostile)
        page = await self._open_browser(url)
        stored = False
        try:
            parse_public_http_url(page.url)
            hostile = automation_hostile_reason(page.url)
            if hostile:
                raise ToolError("sandbox.site_blocks_automation", hostile)
            school, member, run = isolation_tuple(school_id, membership_id, run_id)
            session_id = "sbox_" + secrets.token_hex(12)
            ws = workspace_id_for(school, member, run)
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
                browser=page,
            )
            await self._sync(sess)
            self._sessions[session_id] = sess
            stored = True
        except Exception:
            if not stored:
                await page.close()
            raise
        return redact_secrets(
            {
                "ok": True,
                "session_id": session_id,
                "workspace_id": sess.workspace_id,
                "url": sess.url,
                "title": sess.title,
                "h1": sess.h1,
                "engine": ENGINE_NAME,
                "view_path": f"/v1/sandbox/sessions/{session_id}/view",
                "human_copy": HUMAN_LOGIN_COPY,
                "message": (
                    f"已在 sidecar Chromium 打开公开页。{HUMAN_LOGIN_COPY}"
                    "会话随沙箱销毁，不会把 Cookie 写回宿主机。"
                ),
                "byte_size": len(sess.screenshot_png),
                "mime": "image/png",
            }
        )

    async def screenshot(self, session: SandboxSession) -> dict[str, Any]:
        await self._purge()
        await self._sync(session)
        return redact_secrets(
            {
                "ok": True,
                "session_id": session.session_id,
                "workspace_id": session.workspace_id,
                "url": session.url,
                "title": session.title,
                "engine": ENGINE_NAME,
                "view_path": f"/v1/sandbox/sessions/{session.session_id}/view",
                "human_copy": HUMAN_LOGIN_COPY,
                "byte_size": len(session.screenshot_png),
                "mime": "image/png",
                "png_sha256": hashlib.sha256(session.screenshot_png).hexdigest()[:16],
            }
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
        clicked = click_x is not None and click_y is not None
        if clicked:
            await session.browser.click(int(click_x), int(click_y))
        if text is not None:
            if password:
                session.secret_fields.add(field)
            # Type into the live DOM. Do not overlay secrets onto a synthetic PNG.
            await session.browser.type_text(text, password=password)
        await self._sync(session)
        return redact_secrets(
            {
                "ok": True,
                "session_id": session.session_id,
                "workspace_id": session.workspace_id,
                "url": session.url,
                "title": session.title,
                "engine": ENGINE_NAME,
                "clicked": clicked,
                "typed": bool(text),
                "password_typed": bool(password and text),
                "human_copy": HUMAN_LOGIN_COPY,
                "message": APPLIED_COPY,
            },
            session.secret_fields,
        )

    async def destroy(self, session_id: str) -> None:
        sess = self._sessions.pop(session_id, None)
        if sess is None:
            return
        try:
            await sess.browser.close()
        except Exception:
            logger.debug("sandbox session close failed", exc_info=True)


RUNTIME = SandboxRuntime()
