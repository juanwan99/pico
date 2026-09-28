"""pi-runner → pico-api hop for workspace containers (card #1093).

A workspace box can only reach the runner proxy; the runner forwards here
with ``X-Pico-Runner-Token``. Each call must also carry the per-run token
of a run that is alive in this process:

* ``/internal/ws-proxy/l/<run>/v1/...`` — model. Box token in, real New API
  key out (added here, never seen by the box). Ledger files are spliced by
  the existing llm-pass route when the run has paperclips.
* ``/internal/ws-proxy/t/<run>/v1/tool`` — Pico gateway tools; forwarded to
  the run's localhost ToolServer, which checks its own bearer token.
"""

from __future__ import annotations

import hmac
import logging

import httpx
from fastapi import APIRouter, Request, Response
from fastapi.responses import JSONResponse, StreamingResponse
from pico_orchestrator.true_pi.runner import proxy_entry, runner_token

from app.loopback import request_on_loopback_socket

logger = logging.getLogger(__name__)
router = APIRouter()

_HOP = {"host", "content-length", "connection", "transfer-encoding", "content-encoding"}
_KEEP = {"content-type", "accept", "user-agent", "openai-beta"}
_TIMEOUT = httpx.Timeout(900.0, connect=10.0)


def _deny(code: str, status: int = 403) -> JSONResponse:
    return JSONResponse({"ok": False, "code": code}, status_code=status)


def _runner_ok(request: Request) -> bool:
    expected = runner_token()
    got = request.headers.get("x-pico-runner-token") or ""
    return bool(expected) and hmac.compare_digest(got, expected) and request_on_loopback_socket(
        request
    )


def _bearer(request: Request) -> str:
    raw = request.headers.get("authorization") or ""
    return raw[7:].strip() if raw.lower().startswith("bearer ") else ""


async def _stream(method: str, target: str, headers: dict[str, str], body: bytes) -> Response:
    client = httpx.AsyncClient(timeout=_TIMEOUT, follow_redirects=False)
    req = client.build_request(method, target, headers=headers, content=body or None)
    try:
        upstream = await client.send(req, stream=True)
    except Exception as exc:  # noqa: BLE001 — any upstream failure is a 502 to the box
        await client.aclose()
        logger.warning("ws-proxy upstream error %s", type(exc).__name__)
        return _deny("proxy.upstream_unreachable", 502)

    async def _iter():
        try:
            async for chunk in upstream.aiter_bytes():
                yield chunk
        finally:
            await upstream.aclose()
            await client.aclose()

    out = {k: v for k, v in upstream.headers.items() if k.lower() not in _HOP}
    return StreamingResponse(
        _iter(),
        status_code=upstream.status_code,
        headers=out,
        media_type=upstream.headers.get("content-type"),
    )


@router.api_route("/internal/ws-proxy/l/{run_id}/v1/{path:path}", methods=["GET", "POST"])
async def ws_llm(run_id: str, path: str, request: Request) -> Response:
    if not _runner_ok(request):
        return _deny("auth.denied", 401)
    entry = proxy_entry(run_id)
    if entry is None:
        return _deny("proxy.no_run")
    if not hmac.compare_digest(_bearer(request), entry.llm_token):
        return _deny("auth.denied", 401)
    headers = {k: v for k, v in request.headers.items() if k.lower() in _KEEP}
    headers["authorization"] = f"Bearer {entry.llm_key}"
    target = f"{entry.llm_upstream.rstrip('/')}/{path}"
    if request.url.query:
        target = f"{target}?{request.url.query}"
    return await _stream(request.method, target, headers, await request.body())


@router.api_route("/internal/ws-proxy/t/{run_id}/{path:path}", methods=["GET", "POST"])
async def ws_tool(run_id: str, path: str, request: Request) -> Response:
    if not _runner_ok(request):
        return _deny("auth.denied", 401)
    entry = proxy_entry(run_id)
    if entry is None or not entry.tool_url:
        return _deny("proxy.no_run")
    if path not in {"v1/tool", "health"}:
        return _deny("proxy.denied", 404)
    headers = {k: v for k, v in request.headers.items() if k.lower() in _KEEP}
    auth = request.headers.get("authorization")
    if auth:
        headers["authorization"] = auth
    return await _stream(request.method, f"{entry.tool_url.rstrip('/')}/{path}", headers, await request.body())
