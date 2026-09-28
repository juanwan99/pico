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

import asyncio
import hmac
import json
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


async def _stream(
    method: str,
    target: str,
    headers: dict[str, str],
    body: bytes,
    *,
    on_done=None,
) -> Response:
    """Stream upstream back. ``on_done`` runs once the body is fully sent (or failed)."""

    def _done() -> None:
        if on_done is not None:
            on_done()

    client = httpx.AsyncClient(timeout=_TIMEOUT, follow_redirects=False)
    req = client.build_request(method, target, headers=headers, content=body or None)
    try:
        upstream = await client.send(req, stream=True)
    except Exception as exc:  # noqa: BLE001 — any upstream failure is a 502 to the box
        await client.aclose()
        _done()
        logger.warning("ws-proxy upstream error %s", type(exc).__name__)
        return _deny("proxy.upstream_unreachable", 502)

    async def _iter():
        try:
            async for chunk in upstream.aiter_bytes():
                yield chunk
        finally:
            await upstream.aclose()
            await client.aclose()
            _done()

    out = {k: v for k, v in upstream.headers.items() if k.lower() not in _HOP}
    return StreamingResponse(
        _iter(),
        status_code=upstream.status_code,
        headers=out,
        media_type=upstream.headers.get("content-type"),
    )


MODEL_PATHS = frozenset({"chat/completions", "responses", "models"})
TOOL_PATHS = frozenset({"v1/tool", "health"})
MAX_BODY = 16 * 1024 * 1024


def _raw_path_ok(request: Request) -> bool:
    raw = (request.scope.get("raw_path") or b"").lower()
    return not (b"%" in raw or b".." in raw or b"\\" in raw or b"//" in raw)


@router.api_route("/internal/ws-proxy/l/{run_id}/v1/{path:path}", methods=["GET", "POST"])
async def ws_llm(run_id: str, path: str, request: Request) -> Response:
    if not _runner_ok(request):
        return _deny("auth.denied", 401)
    if path not in MODEL_PATHS or not _raw_path_ok(request):
        return _deny("proxy.denied", 404)
    entry = proxy_entry(run_id)
    if entry is None:
        return _deny("proxy.no_run")
    if not hmac.compare_digest(_bearer(request), entry.llm_token):
        return _deny("auth.denied", 401)
    body = await request.body()
    if len(body) > MAX_BODY:
        return _deny("proxy.too_large", 413)
    if request.method == "POST":
        # The box may only spend on this run's model (curl in the box can call
        # the proxy directly; it must not pick another model or endpoint).
        payload = pinned_model_body(body, entry.model)
        if payload is None:
            return _deny("proxy.model_denied")
        body = payload
    headers = {k: v for k, v in request.headers.items() if k.lower() in _KEEP}
    headers["authorization"] = f"Bearer {entry.llm_key}"
    headers["content-type"] = "application/json" if request.method == "POST" else headers.get(
        "content-type", "application/json"
    )
    target = f"{entry.llm_upstream.rstrip('/')}/{path}"
    try:
        await asyncio.wait_for(entry.slots.acquire(), timeout=120)
    except TimeoutError:
        return _deny("proxy.busy", 429)
    # Slot is held until the streamed body is done, not just the headers.
    return await _stream(request.method, target, headers, body, on_done=entry.slots.release)


def pinned_model_body(body: bytes, model: str) -> bytes | None:
    """Re-serialised JSON with ``model`` forced; None if the box tried another.

    Go JSON decoders (New API) match keys case-insensitively, so any key that
    folds to "model" other than the exact one is refused.
    """
    try:
        payload = json.loads(body.decode("utf-8") or "{}")
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict) or not model:
        return None
    if any(k != "model" and k.casefold() == "model" for k in payload):
        return None
    if str(payload.get("model") or "") != model:
        return None
    payload["model"] = model
    return json.dumps(payload, ensure_ascii=False).encode("utf-8")


@router.api_route("/internal/ws-proxy/t/{run_id}/{path:path}", methods=["GET", "POST"])
async def ws_tool(run_id: str, path: str, request: Request) -> Response:
    if not _runner_ok(request):
        return _deny("auth.denied", 401)
    if path not in TOOL_PATHS or not _raw_path_ok(request):
        return _deny("proxy.denied", 404)
    entry = proxy_entry(run_id)
    if entry is None or not entry.tool_url:
        return _deny("proxy.no_run")
    headers = {k: v for k, v in request.headers.items() if k.lower() in _KEEP}
    auth = request.headers.get("authorization")
    if auth:
        headers["authorization"] = auth
    body = await request.body()
    if len(body) > MAX_BODY:
        return _deny("proxy.too_large", 413)
    return await _stream(request.method, f"{entry.tool_url.rstrip('/')}/{path}", headers, body)
