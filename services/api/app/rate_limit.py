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
    """Apply IP RPM and concurrency caps to the expensive chat endpoint."""

    def __init__(self, app: Any) -> None:
        self.app = app
        self.admission = ChatAdmission()

    async def __call__(self, scope: dict, receive: Any, send: Any) -> None:
        if scope["type"] != "http" or scope.get("path") != "/v1/chat/completions":
            await self.app(scope, receive, send)
            return

        settings = get_settings()
        client = scope.get("client")
        key = str(client[0]) if client else "unknown"
        reason = await self.admission.acquire(
            key,
            rpm=settings.pico_chat_rpm,
            max_concurrent=settings.pico_chat_max_concurrent,
        )
        if reason:
            body = json.dumps(
                {"detail": {"code": reason, "message": "chat capacity exceeded"}}
            ).encode()
            await send(
                {
                    "type": "http.response.start",
                    "status": 429,
                    "headers": [
                        (b"content-type", b"application/json"),
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
