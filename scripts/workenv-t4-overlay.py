#!/usr/bin/env python3
"""Overlay T4: AttachTransport protocol + ledger gate. No pico_orchestrator import."""

from __future__ import annotations

import argparse
import asyncio
import base64
import hashlib
import json
import os
import sys
import zipfile
from io import BytesIO
from pathlib import Path
from typing import Any
from urllib.error import HTTPError
from urllib.request import Request, urlopen

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "services" / "workenv_sidecar"))
sys.path.insert(0, str(Path("/tmp/pico-t4/services/workenv_sidecar")))

from pico_workenv_ws import (
    OP_CLOSE,
    OP_PING,
    OP_PONG,
    OP_TEXT,
    accept_key,
    connect_headers,
    send_client_frame,
)

PROMPT = "把 D2:D7 写成期末40%加平时60%的公式，保存为 xlsx。"


def http_post(url: str, token: str, payload: dict[str, Any], timeout: float = 30.0) -> dict[str, Any]:
    raw = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = Request(
        url,
        data=raw,
        method="POST",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
    )
    try:
        with urlopen(req, timeout=timeout) as resp:
            text = resp.read().decode("utf-8")
            status = getattr(resp, "status", 200)
    except HTTPError as exc:
        text = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"http {exc.code}: {text[:400]}") from exc
    body = json.loads(text) if text else {}
    if status >= 400:
        raise RuntimeError(f"http {status}: {body}")
    if not isinstance(body, dict):
        raise TypeError(f"http not object: {body}")
    return body


def is_valid_xlsx(raw: bytes) -> bool:
    if not raw or raw[:2] != b"PK":
        return False
    try:
        with zipfile.ZipFile(BytesIO(raw)) as zf:
            names = set(zf.namelist())
    except zipfile.BadZipFile:
        return False
    return "[Content_Types].xml" in names and "xl/workbook.xml" in names


class WsPeer:
    def __init__(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter, leftover: bytes) -> None:
        self._reader = reader
        self._writer = writer
        self._buf = leftover

    async def _exact(self, n: int) -> bytes:
        while len(self._buf) < n:
            chunk = await self._reader.read(4096)
            if not chunk:
                raise EOFError("ws closed")
            self._buf += chunk
        out, self._buf = self._buf[:n], self._buf[n:]
        return out

    async def recv(self) -> str | None:
        try:
            hdr = await self._exact(2)
        except EOFError:
            return None
        b1, b2 = hdr[0], hdr[1]
        opcode = b1 & 0x0F
        n = b2 & 0x7F
        if n == 126:
            n = int.from_bytes(await self._exact(2), "big")
        elif n == 127:
            n = int.from_bytes(await self._exact(8), "big")
        if b2 & 0x80:
            mask = await self._exact(4)
            payload = await self._exact(n)
            payload = bytes(b ^ mask[i % 4] for i, b in enumerate(payload))
        else:
            payload = await self._exact(n) if n else b""
        if opcode == OP_CLOSE:
            return None
        if opcode == OP_PING:
            send_client_frame(self._writer, OP_PONG, payload)
            return await self.recv()
        if opcode == OP_PONG:
            return await self.recv()
        if opcode == OP_TEXT:
            return payload.decode("utf-8")
        return None

    async def send(self, text: str) -> None:
        send_client_frame(self._writer, OP_TEXT, text.encode("utf-8"))
        await self._writer.drain()

    async def close(self) -> None:
        try:
            send_client_frame(self._writer, OP_CLOSE, b"")
            await self._writer.drain()
        except Exception as exc:  # noqa: BLE001
            del exc
        self._writer.close()
        try:
            await self._writer.wait_closed()
        except Exception as exc:  # noqa: BLE001
            del exc


async def attach(url: str, token: str, run_id: str, box_id: str) -> WsPeer:
    from urllib.parse import urlparse

    parsed = urlparse(url)
    host = parsed.hostname or "127.0.0.1"
    port = parsed.port or 80
    path = parsed.path or "/v1/internal/workenv/attach-rpc"
    reader, writer = await asyncio.open_connection(host, port)
    headers = {
        "Authorization": f"Bearer {token}",
        "X-Pico-Box-Id": box_id,
        "X-Pico-Run-Id": run_id,
    }
    req, key = connect_headers(f"{host}:{port}", path, headers)
    writer.write(req)
    await writer.drain()
    buf = b""
    while b"\r\n\r\n" not in buf:
        chunk = await asyncio.wait_for(reader.read(1024), timeout=10)
        if not chunk:
            raise RuntimeError("handshake closed")
        buf += chunk
    head, rest = buf.split(b"\r\n\r\n", 1)
    status = head.split(b"\r\n", 1)[0].decode("latin1", errors="replace")
    if "101" not in status:
        raise RuntimeError(f"handshake {status}")
    accept = ""
    for line in head.split(b"\r\n")[1:]:
        if line.lower().startswith(b"sec-websocket-accept:"):
            accept = line.split(b":", 1)[1].strip().decode("ascii")
    if accept != accept_key(key):
        raise RuntimeError("accept mismatch")
    return WsPeer(reader, writer, rest)


async def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace", default="t4api")
    parser.add_argument("--fixture", required=True)
    parser.add_argument("--out", default="/tmp/t4api-report.json")
    parser.add_argument("--http", default=os.environ.get("PICO_WORKENV_HTTP_URL", "http://127.0.0.1:18768"))
    parser.add_argument(
        "--ws",
        default=os.environ.get(
            "PICO_WORKENV_ATTACH_URL", "ws://127.0.0.1:18768/v1/internal/workenv/attach-rpc"
        ),
    )
    args = parser.parse_args()
    token = (os.environ.get("PICO_SANDBOX_TOKEN") or "").strip()
    if not token:
        raise SystemExit("PICO_SANDBOX_TOKEN required")
    fixture = Path(args.fixture)
    raw = fixture.read_bytes()
    workspace = args.workspace
    events: list[dict[str, Any]] = []
    store_rows: list[dict[str, Any]] = []
    status = "running"

    created = http_post(
        args.http + "/v1/internal/workenv/create",
        token,
        {
            "workspace_id": workspace,
            "run_id": workspace,
            "conversation_id": "t4-api",
            "mode": "pi",
        },
    )
    http_post(
        args.http + "/v1/internal/workenv/attach",
        token,
        {
            "workspace_id": workspace,
            "files": [{"name": fixture.name, "bytes_b64": base64.b64encode(raw).decode("ascii")}],
        },
    )
    ws = await attach(args.ws, token, workspace, str(created.get("box_id") or "box-1"))
    prompt_id = "p-t4api"
    await ws.send(json.dumps({"id": prompt_id, "type": "prompt", "message": PROMPT}))
    abort_sent = False
    abort_ack = False
    first_tool = None
    try:
        while True:
            text = await asyncio.wait_for(ws.recv(), timeout=180)
            if text is None:
                break
            try:
                obj = json.loads(text)
            except json.JSONDecodeError:
                continue
            if not isinstance(obj, dict):
                continue
            kind = str(obj.get("type") or "")
            if kind == "message_update":
                continue
            events.append({"type": kind, "toolName": obj.get("toolName"), "command": obj.get("command")})
            if kind == "response" and obj.get("command") == "abort":
                abort_ack = True
            if kind == "tool_execution_start" and not abort_sent:
                first_tool = obj.get("toolName")
                status = "cancelling"
                await ws.send(json.dumps({"id": "a-t4api", "type": "abort"}))
                abort_sent = True
            if kind in {"agent_end", "agent_settled"}:
                break
            if abort_sent and kind == "tool_execution_end":
                # keep reading a little for abort ack / agent_end
                continue
    except TimeoutError:
        events.append({"type": "timeout"})
    finally:
        await ws.close()

    collect_error = None
    try:
        collected = http_post(
            args.http + "/v1/internal/workenv/collect",
            token,
            {"workspace_id": workspace, "glob": ["*.xlsx", "*.docx", "*.pptx", "*.html"]},
        )
        files = collected.get("files") or []
        if status in {"cancelling", "cancelled"}:
            collect_error = "collect-after-cancel discarded"
        else:
            for item in files:
                name = str(item.get("name") or "file.bin")
                blob = base64.b64decode(str(item.get("bytes_b64") or ""))
                if name.endswith(".xlsx") and not is_valid_xlsx(blob):
                    collect_error = f"invalid ooxml {name}"
                    break
                store_rows.append(
                    {
                        "title": name,
                        "n": len(blob),
                        "sha256": hashlib.sha256(blob).hexdigest(),
                    }
                )
    except Exception as exc:  # noqa: BLE001
        collect_error = f"{type(exc).__name__}:{exc}"

    destroyed = http_post(
        args.http + "/v1/internal/workenv/destroy-run",
        token,
        {"workspace_id": workspace},
        timeout=15.0,
    )
    if destroyed.get("ok"):
        status = "cancelled" if abort_sent else status
    else:
        status = "failed"

    report = {
        "abort_sent": abort_sent,
        "abort_ack": abort_ack,
        "first_tool": first_tool,
        "events": events[:50],
        "collect_error": collect_error,
        "store_rows": store_rows,
        "ledger_status": status,
        "destroyed": destroyed,
        "created": created,
    }
    out = Path(args.out)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "abort_sent": abort_sent,
                "abort_ack": abort_ack,
                "first_tool": first_tool,
                "collect_error": collect_error,
                "ledger_status": status,
                "store_rows": store_rows,
                "destroyed": destroyed,
            },
            ensure_ascii=False,
        )
    )
    ok = abort_sent and status == "cancelled" and not store_rows
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
