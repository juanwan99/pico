"""Localhost-only tool callback HTTP server for the Pi extension.

Deny-by-default: only ALLOWED_GATEWAY_TOOLS may be invoked.
Auth: Bearer token generated per run (never logged in full).
Uses stdlib asyncio only (no extra dependency).
"""

from __future__ import annotations

import asyncio
import json
import logging
import secrets
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlparse

from pico_orchestrator.gateway import AllowlistGateway, Principal, ToolError
from pico_orchestrator.true_pi.config import ALLOWED_GATEWAY_TOOLS
from pico_orchestrator.usage_hook import bind_usage_context, reset_usage_context

logger = logging.getLogger(__name__)


@dataclass
class ToolServer:
    principal: Principal
    gateway: AllowlistGateway
    run_id: str
    conversation_id: str | None = None
    token: str = field(default_factory=lambda: secrets.token_urlsafe(24))
    host: str = "127.0.0.1"
    port: int = 0
    emit: Any = None
    ask_timeout_hook: Any = None
    ask_timed_out: bool = False
    _server: asyncio.AbstractServer | None = None
    invocations: list[tuple[str, dict[str, Any], bool]] = field(default_factory=list)

    @property
    def base_url(self) -> str:
        if self.port <= 0:
            raise RuntimeError("tool server not started")
        return f"http://{self.host}:{self.port}"

    async def start(self) -> str:
        self._server = await asyncio.start_server(self._handle, self.host, self.port)
        socks = self._server.sockets or []
        if not socks:
            raise RuntimeError("tool server failed to bind")
        self.port = socks[0].getsockname()[1]
        url = self.base_url
        logger.info("true_pi tool_server up run_id=%s url=%s", self.run_id, url)
        return url

    async def stop(self) -> None:
        if self._server is not None:
            self._server.close()
            await self._server.wait_closed()
        self._server = None

    async def _handle(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> None:
        try:
            request_line = await asyncio.wait_for(reader.readline(), timeout=10.0)
            if not request_line:
                return
            parts = request_line.decode("latin-1", errors="replace").strip().split()
            if len(parts) < 2:
                await self._write(writer, 400, {"ok": False, "error": "bad request line"})
                return
            method, path = parts[0].upper(), parts[1]
            headers: dict[str, str] = {}
            while True:
                line = await asyncio.wait_for(reader.readline(), timeout=10.0)
                if line in (b"\r\n", b"\n", b""):
                    break
                text = line.decode("latin-1", errors="replace")
                if ":" in text:
                    k, v = text.split(":", 1)
                    headers[k.strip().lower()] = v.strip()
            length = int(headers.get("content-length") or "0")
            body = b""
            if length > 0:
                body = await asyncio.wait_for(reader.readexactly(length), timeout=30.0)

            if method == "GET" and path.startswith("/health"):
                await self._write(
                    writer,
                    200,
                    {"ok": True, "run_id": self.run_id, "service": "true-pi-tools"},
                )
                return
            if method == "POST" and path.startswith("/v1/tool"):
                await self._tool(writer, headers, body)
                return
            await self._write(writer, 404, {"ok": False, "error": "not found"})
        except Exception as exc:  # noqa: BLE001
            logger.debug("true_pi tool_server handler error: %s", type(exc).__name__)
            try:
                await self._write(
                    writer, 500, {"ok": False, "error": type(exc).__name__}
                )
            except Exception as write_exc:  # noqa: BLE001
                logger.debug("true_pi tool_server write error: %s", type(write_exc).__name__)
        finally:
            try:
                writer.close()
                await writer.wait_closed()
            except Exception as close_exc:  # noqa: BLE001
                logger.debug("true_pi tool_server close: %s", type(close_exc).__name__)

    async def _tool(
        self,
        writer: asyncio.StreamWriter,
        headers: dict[str, str],
        body: bytes,
    ) -> None:
        auth = headers.get("authorization", "")
        expected = f"Bearer {self.token}"
        if not secrets.compare_digest(auth, expected):
            await self._write(
                writer,
                401,
                {"ok": False, "code": "auth.denied", "error": "invalid tool token"},
            )
            return
        try:
            payload = json.loads(body.decode("utf-8") or "{}")
        except json.JSONDecodeError:
            await self._write(
                writer,
                400,
                {"ok": False, "code": "bad_request", "error": "invalid JSON"},
            )
            return
        if not isinstance(payload, dict):
            await self._write(
                writer,
                400,
                {"ok": False, "code": "bad_request", "error": "body must be object"},
            )
            return
        name = str(payload.get("tool") or "").strip()
        args = payload.get("arguments") or {}
        if not isinstance(args, dict):
            args = {}
        if name not in ALLOWED_GATEWAY_TOOLS:
            self.invocations.append((name, args, False))
            await self._write(
                writer,
                403,
                {
                    "ok": False,
                    "code": "tool.not_allowlisted",
                    "error": f"tool denied by true-pi bridge: {name}",
                },
            )
            return
        if name == "ask_user":
            from pico_orchestrator.ask_user import park as park_ask

            self.invocations.append((name, args, True))
            parked = await park_ask(
                self.run_id,
                str(args.get("question") or ""),
                args.get("options"),
                self.emit,
            )
            if str(parked.get("error") or "") == "timeout":
                self.ask_timed_out = True
                hook = self.ask_timeout_hook
                if callable(hook):
                    hook()
                await self._write(
                    writer,
                    409,
                    {"ok": False, "code": "ask.timeout", "error": "超时未选", "tool": name},
                )
                return
            await self._write(writer, 200, {"ok": True, "tool": name, "result": parked})
            return
        token = bind_usage_context(
            school_id=self.principal.school_id,
            membership_id=self.principal.membership_id,
            run_id=self.run_id,
            conversation_id=self.conversation_id,
        )
        try:
            result = await self.gateway.invoke(self.principal, name, args)
            self.invocations.append((name, args, True))
            await self._write(writer, 200, {"ok": True, "tool": name, "result": result})
        except ToolError as exc:
            self.invocations.append((name, args, False))
            await self._write(
                writer,
                400,
                {"ok": False, "code": exc.code, "error": exc.message, "tool": name},
            )
        except Exception as exc:
            logger.exception(
                "true_pi tool invoke failed run_id=%s tool=%s", self.run_id, name
            )
            self.invocations.append((name, args, False))
            await self._write(
                writer,
                500,
                {
                    "ok": False,
                    "code": "tool.internal",
                    "error": type(exc).__name__,
                    "tool": name,
                },
            )
        finally:
            reset_usage_context(token)

    async def _write(
        self, writer: asyncio.StreamWriter, status: int, payload: dict[str, Any]
    ) -> None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        reason = {
            200: "OK",
            400: "Bad Request",
            401: "Unauthorized",
            403: "Forbidden",
            404: "Not Found",
            500: "Internal Server Error",
        }.get(status, "OK")
        header = (
            f"HTTP/1.1 {status} {reason}\r\n"
            f"Content-Type: application/json; charset=utf-8\r\n"
            f"Content-Length: {len(data)}\r\n"
            f"Connection: close\r\n"
            f"\r\n"
        ).encode("latin-1")
        writer.write(header + data)
        await writer.drain()


def assert_localhost(url: str) -> None:
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    if host not in {"127.0.0.1", "localhost", "::1"}:
        raise RuntimeError(f"tool callback must be localhost, got {host!r}")
