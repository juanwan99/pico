"""Single-instance chat admission control.

The production deployment runs one API instance. Keep this deliberately small;
multi-instance deployments must replace it with a shared limiter.
"""

from __future__ import annotations

import asyncio
import json
import time
from collections import defaultdict, deque
from collections.abc import MutableMapping
from typing import Any

from fastapi import HTTPException

from app.auth import decode_token, scope_proxy_principal
from app.settings import get_settings


class ChatAdmission:
    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self._requests: MutableMapping[str, deque[float]] = defaultdict(deque)
        self._active: MutableMapping[str, int] = defaultdict(int)

    async def acquire(self, key: str, *, rpm: int, max_concurrent: int) -> str | None:
        now = time.monotonic()
        async with self._lock:
            recent = self._requests[key]
            while recent and recent[0] <= now - 60:
                recent.popleft()
            if len(recent) >= rpm:
                return "rate_limit"
            if self._active[key] >= max_concurrent:
                return "concurrency_limit"
            recent.append(now)
            self._active[key] += 1
            return None

    async def release(self, key: str) -> None:
        async with self._lock:
            if self._active[key] <= 1:
                self._active.pop(key, None)
            else:
                self._active[key] -= 1


class ChatRateLimitMiddleware:
    """Apply membership RPM and concurrency caps to the expensive chat endpoint."""

    def __init__(self, app: Any) -> None:
        self.app = app
        self.admission = ChatAdmission()

    async def __call__(self, scope: dict, receive: Any, send: Any) -> None:
        if scope["type"] != "http" or scope.get("path") != "/v1/chat/completions":
            await self.app(scope, receive, send)
            return

        settings = get_settings()
        key = _rate_limit_key(scope, settings)
        reason = await self.admission.acquire(
            key,
            rpm=settings.pico_chat_rpm,
            max_concurrent=settings.pico_chat_max_concurrent,
        )
        if reason:
            # Human-readable Chinese for teachers; no bare 429 stacks.
            if reason == "concurrency_limit":
                message = "当前对话繁忙（并发已满）。请稍后再试，或关闭其他进行中的任务。"
            else:
                message = "请求过于频繁（限流）。请稍后再试，勿并行轰炸。"
            body = json.dumps(
                {
                    "detail": {
                        "code": reason,
                        "message": message,
                        "user_message": message,
                    }
                },
                ensure_ascii=False,
            ).encode("utf-8")
            await send(
                {
                    "type": "http.response.start",
                    "status": 429,
                    "headers": [
                        (b"content-type", b"application/json; charset=utf-8"),
                        (b"retry-after", b"1" if reason == "concurrency_limit" else b"60"),
                    ],
                }
            )
            await send({"type": "http.response.body", "body": body})
            return

        try:
            await self.app(scope, receive, send)
        finally:
            await self.admission.release(key)


def _rate_limit_key(scope: dict, settings: Any) -> str:
    """Prefer an authenticated tenant membership, falling back to client IP."""
    headers = {key.lower(): value for key, value in scope.get("headers", [])}
    authorization = headers.get(b"authorization", b"").decode("latin-1")
    membership_header = headers.get(b"x-pico-membership-id", b"").decode("latin-1")
    if authorization.lower().startswith("bearer "):
        token = authorization.split(" ", 1)[1].strip()
        if token:
            try:
                principal = decode_token(token, settings)
                principal = scope_proxy_principal(principal, membership_header)
                return f"membership:{principal.school_id}:{principal.membership_id}"
            except HTTPException:
                # Authentication remains the endpoint's responsibility. An
                # unparseable principal still receives the conservative IP cap.
                pass

    client = scope.get("client")
    client_ip = str(client[0]) if client else "unknown"
    return f"ip:{client_ip}"
