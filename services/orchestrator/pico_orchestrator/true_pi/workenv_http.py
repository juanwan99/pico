"""Thin HTTP client for overlay create/attach/collect/abort/destroy-run."""

from __future__ import annotations

import asyncio
import base64
import json
import urllib.error
import urllib.request
from typing import Any

from pico_orchestrator.true_pi.workenv_attach import workenv_http_base, workenv_token


class WorkenvHttpError(RuntimeError):
    def __init__(self, status: int, body: Any) -> None:
        super().__init__(f"workenv http {status}: {body}")
        self.status = status
        self.body = body


def _post_sync(path: str, payload: dict[str, Any], timeout: float) -> dict[str, Any]:
    url = workenv_http_base() + path
    raw = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=raw,
        method="POST",
        headers={
            "Authorization": f"Bearer {workenv_token()}",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            text = resp.read().decode("utf-8")
            status = getattr(resp, "status", 200)
    except urllib.error.HTTPError as exc:
        text = exc.read().decode("utf-8", errors="replace")
        try:
            body: Any = json.loads(text) if text else {"raw": ""}
        except json.JSONDecodeError:
            body = {"raw": text[:400]}
        raise WorkenvHttpError(int(exc.code), body) from exc
    try:
        body = json.loads(text) if text else {}
    except json.JSONDecodeError:
        body = {"raw": text[:400]}
    if status >= 400:
        raise WorkenvHttpError(status, body)
    if not isinstance(body, dict):
        raise WorkenvHttpError(status, body)
    return body


async def workenv_post(path: str, payload: dict[str, Any], *, timeout: float = 30.0) -> dict[str, Any]:
    return await asyncio.to_thread(_post_sync, path, payload, timeout)


def decode_collect_files(body: dict[str, Any]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for item in body.get("files") or []:
        if not isinstance(item, dict):
            continue
        raw_b64 = str(item.get("bytes_b64") or "")
        out.append(
            {
                "name": str(item.get("name") or "file.bin"),
                "bytes": base64.b64decode(raw_b64) if raw_b64 else b"",
                "sha256": item.get("sha256"),
            }
        )
    return out
