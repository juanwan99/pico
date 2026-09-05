"""Minimal RFC6455 server helpers. Sidecar-only; not a second RPC kernel."""

from __future__ import annotations

import base64
import hashlib
import os
import struct
from typing import Any

GUID = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"
OP_TEXT = 0x1
OP_CLOSE = 0x8
OP_PING = 0x9
OP_PONG = 0xA


class WebSocketError(RuntimeError):
    pass


class WebSocketConnection:
    def __init__(self, sock: Any) -> None:
        self.sock = sock
        self.closed = False
        self._wlock = __import__("threading").Lock()

    def recv_text(self) -> str | None:
        while True:
            opcode, payload = _read_frame_sock(self.sock)
            if opcode == OP_CLOSE or opcode is None:
                self.closed = True
                return None
            if opcode == OP_PING:
                send_frame_sock(self.sock, OP_PONG, payload, lock=self._wlock)
                continue
            if opcode == OP_PONG:
                continue
            if opcode == OP_TEXT:
                return payload.decode("utf-8")
            raise WebSocketError(f"unsupported opcode {opcode}")

    def close(self) -> None:
        if self.closed:
            return
        try:
            send_close(self)
        except Exception as exc:  # noqa: BLE001
            del exc
        self.closed = True
        try:
            self.sock.close()
        except Exception as exc:  # noqa: BLE001
            del exc


def accept_key(sec_key: str) -> str:
    digest = hashlib.sha1((sec_key.strip() + GUID).encode("ascii")).digest()
    return base64.b64encode(digest).decode("ascii")


def accept_websocket(handler: object) -> WebSocketConnection:
    headers = handler.headers
    wfile = handler.wfile
    key = headers.get("Sec-WebSocket-Key")
    if not key:
        raise WebSocketError("missing Sec-WebSocket-Key")
    accept = accept_key(key)
    send = handler.send_response
    send_header = handler.send_header
    end_headers = handler.end_headers
    send(101)
    send_header("Upgrade", "websocket")
    send_header("Connection", "Upgrade")
    send_header("Sec-WebSocket-Accept", accept)
    end_headers()
    wfile.flush()
    sock = handler.connection
    return WebSocketConnection(sock)


def _frame_header(opcode: int, payload: bytes, *, masked: bool = False) -> bytes:
    header = bytearray()
    header.append(0x80 | (opcode & 0x0F))
    n = len(payload)
    mask_bit = 0x80 if masked else 0
    if n < 126:
        header.append(mask_bit | n)
    elif n < 65536:
        header.append(mask_bit | 126)
        header.extend(struct.pack("!H", n))
    else:
        header.append(mask_bit | 127)
        header.extend(struct.pack("!Q", n))
    return bytes(header)


def send_frame_sock(sock: Any, opcode: int, payload: bytes = b"", *, lock: Any | None = None) -> None:
    blob = _frame_header(opcode, payload) + payload
    if lock is None:
        sock.sendall(blob)
        return
    with lock:
        sock.sendall(blob)


def send_text(ws: WebSocketConnection, text: str) -> None:
    send_frame_sock(ws.sock, OP_TEXT, text.encode("utf-8"), lock=ws._wlock)


def send_close(ws: WebSocketConnection) -> None:
    send_frame_sock(ws.sock, OP_CLOSE, b"", lock=ws._wlock)


def connect_headers(host: str, path: str, extra: dict[str, str] | None = None) -> tuple[bytes, str]:
    key = base64.b64encode(os.urandom(16)).decode("ascii")
    lines = [
        f"GET {path} HTTP/1.1",
        f"Host: {host}",
        "Upgrade: websocket",
        "Connection: Upgrade",
        f"Sec-WebSocket-Key: {key}",
        "Sec-WebSocket-Version: 13",
    ]
    for name, value in (extra or {}).items():
        lines.append(f"{name}: {value}")
    lines.append("")
    lines.append("")
    return "\r\n".join(lines).encode("utf-8"), key


def send_client_frame(wfile: Any, opcode: int, payload: bytes = b"") -> None:
    mask = os.urandom(4)
    masked = bytes(b ^ mask[i % 4] for i, b in enumerate(payload))
    header = bytearray()
    header.append(0x80 | (opcode & 0x0F))
    n = len(payload)
    if n < 126:
        header.append(0x80 | n)
    elif n < 65536:
        header.append(0x80 | 126)
        header.extend(struct.pack("!H", n))
    else:
        header.append(0x80 | 127)
        header.extend(struct.pack("!Q", n))
    header.extend(mask)
    blob = bytes(header) + masked
    wfile.write(blob)
    flush = getattr(wfile, "flush", None)
    if callable(flush):
        flush()


def _recv_exact(sock: Any, n: int) -> bytes:
    buf = b""
    while len(buf) < n:
        chunk = sock.recv(n - len(buf))
        if not chunk:
            return buf
        buf += chunk
    return buf


def _read_frame_sock(sock: Any) -> tuple[int | None, bytes]:
    hdr = _recv_exact(sock, 2)
    if len(hdr) < 2:
        return None, b""
    b1, b2 = hdr[0], hdr[1]
    opcode = b1 & 0x0F
    masked = bool(b2 & 0x80)
    n = b2 & 0x7F
    if n == 126:
        ext = _recv_exact(sock, 2)
        if len(ext) < 2:
            return None, b""
        n = struct.unpack("!H", ext)[0]
    elif n == 127:
        ext = _recv_exact(sock, 8)
        if len(ext) < 8:
            return None, b""
        n = struct.unpack("!Q", ext)[0]
    mask = b""
    if masked:
        mask = _recv_exact(sock, 4)
        if len(mask) < 4:
            return None, b""
    payload = _recv_exact(sock, n) if n else b""
    if len(payload) < n:
        return None, b""
    if masked:
        payload = bytes(b ^ mask[i % 4] for i, b in enumerate(payload))
    return opcode, payload
