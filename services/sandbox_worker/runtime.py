"""In-memory B2 browser sessions + userspace egress filter.

Sessions die with this process (no durable cookies on the host).
Passwords are never written to logs, tool payloads, or screenshot text.
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
from pico_orchestrator.sandbox_s1 import extract_title_h1, workspace_id_for
from pico_orchestrator.sandbox_s2 import PNG_MAGIC, raster_html_to_png
from pico_orchestrator.web_guard import assert_public_http_url, parse_public_http_url

logger = logging.getLogger(__name__)

HUMAN_LOGIN_COPY = "请在此画面自行登录，不要在聊天里发送密码"
SESSION_TTL_S = 30 * 60
FETCH_TIMEOUT_S = 8.0
MAX_HTML_CHARS = 120_000
MAX_REDIRECTS = 5

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


FetchHtml = Callable[[str], Awaitable[tuple[str, str]]]


@dataclass
class SandboxSession:
    session_id: str
    school_id: str
    membership_id: str
    run_id: str
    workspace_id: str
    url: str
    html: str
    screenshot_png: bytes
    created_at: float
    form_values: dict[str, str] = field(default_factory=dict)
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


def _screen_html(url: str, page_html: str, *, typed_masked: str = "") -> str:
    title, h1 = extract_title_h1(page_html)
    extra = f"<p>typed: {typed_masked}</p>" if typed_masked else ""
    return (
        "<!DOCTYPE html><html><head>"
        f"<title>{title or 'sandbox'}</title></head><body>"
        f"<div id='pico-b2-banner'>{HUMAN_LOGIN_COPY}</div>"
        f"<p>url: {url}</p>"
        f"<h1>{h1 or title or 'public page'}</h1>"
        f"{extra}"
        "<p>Session cookies stay inside this sandbox and die with the box.</p>"
        "</body></html>"
    )


def render_screen_png(url: str, page_html: str, *, typed_masked: str = "") -> bytes:
    png = raster_html_to_png(_screen_html(url, page_html, typed_masked=typed_masked))
    if not png.startswith(PNG_MAGIC):
        raise ToolError("sandbox.raster_failed", "隔离画面未能生成截图")
    return png


async def default_fetch_html(url: str) -> tuple[str, str]:
    """Fetch a public page through web_guard. Never follows intranet redirects."""
    import httpx

    current = url
    async with httpx.AsyncClient(timeout=FETCH_TIMEOUT_S, trust_env=False) as client:
        for _hop in range(MAX_REDIRECTS + 1):
            target = await assert_public_http_url(current)
            try:
                resp = await client.get(
                    target.url,
                    headers={
                        "User-Agent": "PicoSandbox/1.0",
                        "Accept": "text/html,application/xhtml+xml,text/plain",
                    },
                    follow_redirects=False,
                )
            except httpx.TimeoutException as exc:
                raise ToolError("sandbox.fetch_failed", "公开页读取超时") from exc
            except httpx.HTTPError as exc:
                raise ToolError("sandbox.fetch_failed", "无法打开该公开页") from exc
            if resp.status_code in {301, 302, 303, 307, 308}:
                loc = resp.headers.get("location") or ""
                if not loc:
                    raise ToolError("sandbox.fetch_failed", "重定向缺少目标地址")
                if loc.startswith("/"):
                    parsed = urlparse(target.url)
                    loc = f"{parsed.scheme}://{parsed.netloc}{loc}"
                parse_public_http_url(loc)
                current = loc
                continue
            if resp.status_code >= 400:
                raise ToolError(
                    "sandbox.fetch_failed",
                    f"公开页返回 HTTP {resp.status_code}，无法打开登录画面。",
                )
            raw = resp.content[: MAX_HTML_CHARS + 1].decode("utf-8", errors="replace")
            return target.url, raw[:MAX_HTML_CHARS]
    raise ToolError("sandbox.fetch_failed", "重定向次数过多")


class SandboxRuntime:
    """Process-local session table. Not LibreChat. Not pico-api."""

    def __init__(self, fetch_html: FetchHtml | None = None) -> None:
        self._sessions: dict[str, SandboxSession] = {}
        self._fetch_html = fetch_html or default_fetch_html

    def _purge(self) -> None:
        now = time.time()
        dead = [
            sid
            for sid, sess in self._sessions.items()
            if now - sess.created_at > SESSION_TTL_S
        ]
        for sid in dead:
            self._sessions.pop(sid, None)

    def get(self, session_id: str) -> SandboxSession | None:
        self._purge()
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

    async def open_session(
        self,
        *,
        school_id: str,
        membership_id: str,
        run_id: str | None,
        url: str,
    ) -> dict[str, Any]:
        parse_public_http_url(url)
        hostile = automation_hostile_reason(url)
        if hostile:
            raise ToolError("sandbox.site_blocks_automation", hostile)
        final_url, html = await self._fetch_html(url)
        parse_public_http_url(final_url)
        hostile = automation_hostile_reason(final_url)
        if hostile:
            raise ToolError("sandbox.site_blocks_automation", hostile)
        png = render_screen_png(final_url, html)
        school, member, run = isolation_tuple(school_id, membership_id, run_id)
        session_id = "sbox_" + secrets.token_hex(12)
        ws = workspace_id_for(school, member, run)
        sess = SandboxSession(
            session_id=session_id,
            school_id=school,
            membership_id=member,
            run_id=run,
            workspace_id=ws,
            url=final_url,
            html=html,
            screenshot_png=png,
            created_at=time.time(),
        )
        self._sessions[session_id] = sess
        title, h1 = extract_title_h1(html)
        return redact_secrets(
            {
                "ok": True,
                "session_id": session_id,
                "workspace_id": ws,
                "url": final_url,
                "title": title,
                "h1": h1,
                "view_path": f"/v1/sandbox/sessions/{session_id}/view",
                "human_copy": HUMAN_LOGIN_COPY,
                "message": (
                    f"已在隔离沙箱打开公开页。{HUMAN_LOGIN_COPY}"
                    "会话随沙箱销毁，不会把 Cookie 写回宿主机。"
                ),
                "byte_size": len(png),
                "mime": "image/png",
            }
        )

    def screenshot(self, session: SandboxSession) -> dict[str, Any]:
        return redact_secrets(
            {
                "ok": True,
                "session_id": session.session_id,
                "workspace_id": session.workspace_id,
                "url": session.url,
                "view_path": f"/v1/sandbox/sessions/{session.session_id}/view",
                "human_copy": HUMAN_LOGIN_COPY,
                "byte_size": len(session.screenshot_png),
                "mime": "image/png",
                "png_sha256": hashlib.sha256(session.screenshot_png).hexdigest()[:16],
            }
        )

    def apply_input(
        self,
        session: SandboxSession,
        *,
        click_x: int | None = None,
        click_y: int | None = None,
        text: str | None = None,
        password: bool = False,
        field: str = "input",
    ) -> dict[str, Any]:
        if text is not None:
            if password:
                session.secret_fields.add(field)
                session.form_values[field] = text
            else:
                session.form_values[field] = text[:200]
        masked = ""
        if session.form_values:
            bits = []
            for key, value in session.form_values.items():
                if key in session.secret_fields:
                    bits.append(f"{key}=••••")
                else:
                    bits.append(f"{key}={value[:40]}")
            masked = "; ".join(bits)
        session.screenshot_png = render_screen_png(
            session.url, session.html, typed_masked=masked
        )
        # Never echo the typed secret.
        return redact_secrets(
            {
                "ok": True,
                "session_id": session.session_id,
                "workspace_id": session.workspace_id,
                "clicked": click_x is not None and click_y is not None,
                "typed": bool(text),
                "password_typed": bool(password and text),
                "human_copy": HUMAN_LOGIN_COPY,
                "message": (
                    "已把点击/输入送进隔离浏览器。"
                    f"{HUMAN_LOGIN_COPY}"
                ),
            },
            session.secret_fields,
        )

    def destroy(self, session_id: str) -> None:
        self._sessions.pop(session_id, None)


RUNTIME = SandboxRuntime()
