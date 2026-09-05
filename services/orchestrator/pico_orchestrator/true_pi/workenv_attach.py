"""AttachTransport: official JSONL over one long-lived WebSocket.

Replaces SubprocessTransport.start only. TruePiRpcClient.send / abort /
wait_response stay unchanged. Not a unary POST prompt.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
from collections.abc import AsyncIterator, Mapping
from pathlib import Path as _Path
from typing import Any
from urllib.parse import urlparse

_SIDECAR = _Path(__file__).resolve().parents[3] / "workenv_sidecar"
if str(_SIDECAR) not in sys.path:
    sys.path.insert(0, str(_SIDECAR))

from pico_orchestrator.true_pi.client import (
    RpcEvent,
    TruePiClientError,
    TruePiTransport,
)
from pico_orchestrator.true_pi.thinking import thinking_delta_from_rpc

logger = logging.getLogger(__name__)


class _StdlibWs:
    def __init__(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
        *,
        leftover: bytes,
        op_text: int,
        op_close: int,
        op_ping: int,
        op_pong: int,
        send_client_frame: Any,
    ) -> None:
        self._reader = reader
        self._writer = writer
        self._buf = leftover
        self._op_text = op_text
        self._op_close = op_close
        self._op_ping = op_ping
        self._op_pong = op_pong
        self._send_client_frame = send_client_frame

    async def _read_exact(self, n: int) -> bytes:
        while len(self._buf) < n:
            chunk = await self._reader.read(4096)
            if not chunk:
                raise EOFError("ws closed")
            self._buf += chunk
        out, self._buf = self._buf[:n], self._buf[n:]
        return out

    async def __aiter__(self):
        while True:
            try:
                hdr = await self._read_exact(2)
            except EOFError:
                return
            b1, b2 = hdr[0], hdr[1]
            if not (b1 & 0x80):
                raise TruePiClientError("attach-rpc fragment not supported")
            opcode = b1 & 0x0F
            n = b2 & 0x7F
            if n == 126:
                n = int.from_bytes(await self._read_exact(2), "big")
            elif n == 127:
                n = int.from_bytes(await self._read_exact(8), "big")
            if n > 1024 * 1024:
                raise TruePiClientError("attach-rpc frame too large")
            if b2 & 0x80:
                mask = await self._read_exact(4)
                payload = await self._read_exact(n)
                payload = bytes(b ^ mask[i % 4] for i, b in enumerate(payload))
            else:
                payload = await self._read_exact(n) if n else b""
            if opcode == self._op_close:
                return
            if opcode == self._op_ping:
                self._send_client_frame(self._writer, self._op_pong, payload)
                continue
            if opcode == self._op_pong:
                continue
            if opcode == self._op_text:
                yield payload.decode("utf-8")
                continue
            return

    async def send(self, text: str) -> None:
        self._send_client_frame(self._writer, self._op_text, text.encode("utf-8"))
        await self._writer.drain()

    async def close(self) -> None:
        try:
            self._send_client_frame(self._writer, self._op_close, b"")
            await self._writer.drain()
        except Exception as exc:  # noqa: BLE001
            logger.debug("ws close frame: %s", type(exc).__name__)
        try:
            self._writer.close()
            await self._writer.wait_closed()
        except Exception as exc:  # noqa: BLE001
            logger.debug("ws writer close: %s", type(exc).__name__)


def workenv_attach_url() -> str:
    raw = (os.environ.get("PICO_WORKENV_ATTACH_URL") or "").strip()
    if raw:
        return raw
    return "ws://127.0.0.1:18768/v1/internal/workenv/attach-rpc"


def workenv_http_base() -> str:
    raw = (os.environ.get("PICO_WORKENV_HTTP_URL") or "").strip()
    if raw:
        return raw.rstrip("/")
    parsed = urlparse(workenv_attach_url())
    scheme = "https" if parsed.scheme == "wss" else "http"
    return f"{scheme}://{parsed.netloc}"


def workenv_token() -> str:
    return (
        os.environ.get("PICO_SANDBOX_TOKEN")
        or os.environ.get("PICO_WORKENV_TOKEN")
        or ""
    ).strip()


class AttachTransport(TruePiTransport):
    """Duplex JSONL peer: WS frames ↔ Pi stdin/stdout via overlay sidecar."""

    def __init__(
        self,
        *,
        run_id: str,
        box_id: str = "box-1",
        url: str | None = None,
        token: str | None = None,
        extra_headers: Mapping[str, str] | None = None,
    ) -> None:
        self.run_id = run_id
        self.box_id = box_id
        self.url = url or workenv_attach_url()
        self.token = token if token is not None else workenv_token()
        self._extra_headers = dict(extra_headers or {})
        self._ws: Any = None
        self._reader_task: asyncio.Task[None] | None = None
        self._queue: asyncio.Queue[RpcEvent | None] = asyncio.Queue()
        self._stderr_tail: list[str] = []
        self._closed = False
        self.ui_select = None
        self.plan_flag = False
        self.plan_hitl = False
        self.plan_execute_pending = False
        self.plan_agent_ends = 0
        self.plan_stayed = False
        self.plan_ask_timed_out = False
        self.ask_timed_out = False
        self.model = ""

    def _headers(self) -> dict[str, str]:
        headers = {
            "Authorization": f"Bearer {self.token}",
            "X-Pico-Box-Id": self.box_id,
            "X-Pico-Run-Id": self.run_id,
        }
        headers.update(self._extra_headers)
        return headers

    async def start(self) -> None:
        if not self.token:
            raise TruePiClientError("AttachTransport missing PICO_SANDBOX_TOKEN")
        parsed = urlparse(self.url)
        if parsed.scheme == "wss":
            raise TruePiClientError("attach-rpc wss is not implemented; use ws:// on loopback")
        if parsed.scheme not in {"ws", "http", ""}:
            raise TruePiClientError(f"attach-rpc scheme invalid: {parsed.scheme}")
        host = parsed.hostname or "127.0.0.1"
        port = parsed.port or 80
        path = parsed.path or "/v1/internal/workenv/attach-rpc"
        try:
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(host, port),
                timeout=10,
            )
        except Exception as exc:
            raise TruePiClientError(f"attach-rpc connect failed: {exc}") from exc
        from pico_workenv_ws import (
            OP_CLOSE,
            OP_PING,
            OP_PONG,
            OP_TEXT,
            accept_key,
            connect_headers,
            send_client_frame,
        )

        req, key = connect_headers(f"{host}:{port}", path, self._headers())
        writer.write(req)
        await writer.drain()
        header_buf = b""
        while b"\r\n\r\n" not in header_buf:
            chunk = await asyncio.wait_for(reader.read(1024), timeout=10)
            if not chunk:
                writer.close()
                raise TruePiClientError("attach-rpc handshake closed")
            header_buf += chunk
        head, rest = header_buf.split(b"\r\n\r\n", 1)
        status_line = head.split(b"\r\n", 1)[0].decode("latin1", errors="replace")
        if "101" not in status_line:
            writer.close()
            raise TruePiClientError(f"attach-rpc handshake {status_line[:80]}")
        accept = ""
        for line in head.split(b"\r\n")[1:]:
            if line.lower().startswith(b"sec-websocket-accept:"):
                accept = line.split(b":", 1)[1].strip().decode("ascii")
        if accept != accept_key(key):
            writer.close()
            raise TruePiClientError("attach-rpc accept mismatch")
        self._ws = _StdlibWs(
            reader,
            writer,
            leftover=rest,
            op_text=OP_TEXT,
            op_close=OP_CLOSE,
            op_ping=OP_PING,
            op_pong=OP_PONG,
            send_client_frame=send_client_frame,
        )
        self._closed = False
        self._reader_task = asyncio.create_task(self._read_ws())

    async def _reply_extension_ui(self, raw: dict[str, Any]) -> None:
        # Same HITL shape as SubprocessTransport; plan select stays on this duplex.
        from pico_orchestrator.true_pi.client import SubprocessTransport

        helper = SubprocessTransport.__dict__["_reply_extension_ui"]
        await helper(self, raw)

    async def _ingest(self, obj: dict[str, Any]) -> None:
        t = str(obj.get("type") or "?")
        if t == "extension_ui_request":
            await self._reply_extension_ui(obj)
        if t == "message_update":
            think = thinking_delta_from_rpc(obj)
            if think:
                await self._queue.put(RpcEvent({"type": "thinking_delta", "delta": think}))
            return
        await self._queue.put(RpcEvent(obj))

    async def _read_ws(self) -> None:
        assert self._ws is not None
        try:
            async for message in self._ws:
                if isinstance(message, bytes):
                    text = message.decode("utf-8", errors="replace")
                else:
                    text = str(message)
                for line in text.splitlines():
                    if not line.strip():
                        continue
                    try:
                        obj = json.loads(line)
                    except json.JSONDecodeError:
                        logger.warning(
                            "attach-rpc non-json run_id=%s line=%s",
                            self.run_id,
                            line[:200],
                        )
                        continue
                    if isinstance(obj, dict):
                        await self._ingest(obj)
        except Exception as exc:  # noqa: BLE001
            logger.info("attach-rpc reader end run_id=%s err=%s", self.run_id, type(exc).__name__)
        finally:
            await self._queue.put(None)

    async def send(self, command: Mapping[str, Any]) -> None:
        if self._ws is None:
            raise TruePiClientError("attach-rpc not started")
        line = json.dumps(dict(command), ensure_ascii=False)
        await self._ws.send(line)  # text frame; sidecar splits on \n

    async def events(self) -> AsyncIterator[RpcEvent]:
        while True:
            item = await self._queue.get()
            if item is None:
                return
            yield item

    async def wait_response(
        self, command_type: str, *, req_id: str | None = None, timeout: float = 30.0
    ) -> dict[str, Any]:
        deadline = asyncio.get_running_loop().time() + max(1.0, timeout)
        pending: list[RpcEvent] = []
        try:
            while asyncio.get_running_loop().time() < deadline:
                remaining = max(0.05, deadline - asyncio.get_running_loop().time())
                try:
                    item = await asyncio.wait_for(self._queue.get(), timeout=remaining)
                except TimeoutError as exc:
                    raise TruePiClientError(
                        f"timeout waiting for response {command_type}"
                    ) from exc
                if item is None:
                    raise TruePiClientError(
                        f"attach-rpc ended before response {command_type}"
                    )
                raw = item.raw
                if (
                    raw.get("type") == "response"
                    and raw.get("command") == command_type
                    and (req_id is None or raw.get("id") == req_id)
                ):
                    for p in pending:
                        await self._queue.put(p)
                    return raw
                pending.append(item)
            raise TruePiClientError(f"timeout waiting for response {command_type}")
        except Exception:
            for p in pending:
                await self._queue.put(p)
            raise

    async def close(self, *, kill: bool = True) -> None:
        del kill
        if self._closed:
            return
        self._closed = True
        ws = self._ws
        self._ws = None
        if ws is not None:
            try:
                await ws.close()
            except Exception as exc:  # noqa: BLE001
                logger.debug("attach-rpc close: %s", type(exc).__name__)
        if self._reader_task:
            self._reader_task.cancel()
            try:
                await self._reader_task
            except asyncio.CancelledError:
                pass
            except Exception as exc:  # noqa: BLE001
                logger.debug("attach-rpc reader cancel: %s", type(exc).__name__)
            self._reader_task = None
