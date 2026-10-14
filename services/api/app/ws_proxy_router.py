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
import contextlib
import hmac
import json
import logging
import os
from collections import Counter

import httpx
from fastapi import APIRouter, Request, Response
from fastapi.responses import JSONResponse, StreamingResponse
from pico_orchestrator.hedge import hedge_delays, race_first
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
    return (
        bool(expected)
        and hmac.compare_digest(got, expected)
        and request_on_loopback_socket(request)
    )


def _bearer(request: Request) -> str:
    raw = request.headers.get("authorization") or ""
    return raw[7:].strip() if raw.lower().startswith("bearer ") else ""


class _Retry(Exception):
    """Attempt answered 429 / 5xx before any token: try another one."""

    def __init__(self, status: int, body: bytes, headers: dict[str, str]) -> None:
        super().__init__(f"upstream {status}")
        self.status = status
        self.body = body
        self.headers = headers


_RETRY_STATUS = frozenset({429, 500, 502, 503, 504, 520, 522, 524})


async def _open(method: str, target: str, headers: dict[str, str], body: bytes):
    """One upstream call up to its first body chunk: (client, upstream, first)."""
    client = httpx.AsyncClient(timeout=_TIMEOUT, follow_redirects=False)
    upstream = None
    try:
        req = client.build_request(method, target, headers=headers, content=body or None)
        upstream = await client.send(req, stream=True)
        if upstream.status_code in _RETRY_STATUS:
            raw = await upstream.aread()
            raise _Retry(upstream.status_code, raw, dict(upstream.headers))
        chunks = upstream.aiter_bytes()
        first = b""
        async for chunk in chunks:
            if chunk:
                first = chunk
                break
        return client, upstream, first, chunks
    except BaseException:
        with contextlib.suppress(Exception):
            if upstream is not None:
                await upstream.aclose()
        await client.aclose()
        raise


async def _stream(
    method: str,
    target: str,
    headers: dict[str, str],
    body: bytes,
    *,
    on_done=None,
    hedge: list[float] | None = None,
) -> Response:
    """Stream upstream back. ``on_done`` runs once the body is fully sent (or failed).

    ``hedge`` (model calls only, pico#1257): seconds at which to race another
    identical call when no first token has come back yet.
    """

    def _done() -> None:
        if on_done is not None:
            on_done()

    attempts = 1 + len(hedge or [])

    def start(k: int):
        return _open(method, target, headers, body) if k < attempts else None

    async def discard(opened) -> None:
        client, upstream, _first, _chunks = opened
        with contextlib.suppress(Exception):
            await upstream.aclose()
        await client.aclose()

    try:
        (client, upstream, first, chunks), won = await race_first(
            start,
            hedge or [],
            relaunch=lambda exc: isinstance(exc, (_Retry, httpx.HTTPError)),
            discard=discard,
        )
    except _Retry as exc:
        _done()
        logger.warning("ws-proxy upstream %s after %s attempts", exc.status, attempts)
        out = {k: v for k, v in exc.headers.items() if k.lower() not in _HOP}
        return Response(exc.body, status_code=exc.status, headers=out)
    except Exception as exc:  # noqa: BLE001 — any upstream failure is a 502 to the box
        _done()
        logger.warning("ws-proxy upstream error %s", type(exc).__name__)
        return _deny("proxy.upstream_unreachable", 502)
    except BaseException:
        _done()
        raise
    if won:
        logger.info("ws-proxy hedge won attempt=%s target=%s", won, target.rsplit("/", 1)[-1])

    async def _iter():
        try:
            if first:
                yield first
            async for chunk in chunks:
                yield chunk
        finally:
            try:
                await upstream.aclose()
                await client.aclose()
            finally:
                _done()

    out = {k: v for k, v in upstream.headers.items() if k.lower() not in _HOP}
    return StreamingResponse(
        _iter(),
        status_code=upstream.status_code,
        headers=out,
        media_type=upstream.headers.get("content-type"),
    )


def deep_request(body: bytes) -> bool:
    """Reasoning effort medium+ asked for: first token may honestly take long."""
    try:
        payload = json.loads(body.decode("utf-8") or "{}")
    except (UnicodeDecodeError, json.JSONDecodeError):
        return False
    if not isinstance(payload, dict):
        return False
    effort = ""
    reasoning = payload.get("reasoning")
    if isinstance(reasoning, dict):
        effort = str(reasoning.get("effort") or "")
    effort = effort or str(payload.get("reasoning_effort") or "")
    return effort.lower() in {"medium", "high", "xhigh"}


def model_hedge(body: bytes) -> list[float]:
    """Hedge schedule for one model call; streaming only (a JSON reply has no first token)."""
    try:
        payload = json.loads(body.decode("utf-8") or "{}")
    except (UnicodeDecodeError, json.JSONDecodeError):
        return []
    if not isinstance(payload, dict) or payload.get("stream") is not True:
        return []
    return hedge_delays(deep=deep_request(body))


MODEL_PATHS = frozenset({"chat/completions", "responses", "models"})
# Chaos switch for #1104 T1 (ops only, no restart): write ``N [cut] [K]`` into
# this file and model calls N..N+K-1 of the next run fail (K default 1); the
# file is removed after the K-th hit. ``502`` and a ``cut`` stream (200 SSE,
# one chunk, no finish_reason) are both retried by Pi itself (prod runs
# d130322d / 93a3e9e6: agent.end will_retry=true, then done). K above Pi's
# retry.maxRetries makes Pi give up — that is where Pico's same-session
# resume takes over, which is what T1 has to show.
FAULT_FILE_ENV = "PICO_WS_PROXY_FAULT_FILE"
_FAULT_FILE_DEFAULT = "/app/data/ws-proxy-fault"
_model_calls: Counter[str] = Counter()
_fault_hits = 0
_CUT_CHUNK = (
    'data: {"id":"pico-fault","object":"chat.completion.chunk","choices":'
    '[{"index":0,"delta":{"role":"assistant","content":"（"},"finish_reason":null}]}\n\n'
)


def fault_injected(run_id: str) -> str:
    """'' (no fault), '502', or 'cut' for this model call."""
    global _fault_hits
    path = os.environ.get(FAULT_FILE_ENV, _FAULT_FILE_DEFAULT).strip()
    if not path or not os.path.exists(path):
        return ""
    _model_calls[run_id] += 1
    mode, nth, count = "502", 2, 1
    try:
        with open(path, encoding="utf-8") as fh:
            words = fh.read().split()
        if words:
            nth = max(1, int(words[0]))
        if "cut" in words[1:]:
            mode = "cut"
        nums = [w for w in words[1:] if w.isdigit()]
        if nums:
            count = max(1, int(nums[0]))
    except (OSError, ValueError):
        pass
    if _model_calls[run_id] < nth:
        return ""
    _fault_hits += 1
    hit = _fault_hits
    if hit >= count:
        with contextlib.suppress(OSError):
            os.remove(path)
        _model_calls.clear()
        _fault_hits = 0
    logger.warning(
        "ws-proxy fault injected run_id=%s call=%s mode=%s hit=%s/%s",
        run_id,
        _model_calls[run_id] or nth,
        mode,
        hit,
        count,
    )
    return mode


def _cut_stream() -> Response:
    async def _iter():
        yield _CUT_CHUNK.encode("utf-8")

    return StreamingResponse(_iter(), status_code=200, media_type="text/event-stream")


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
    headers["content-type"] = (
        "application/json"
        if request.method == "POST"
        else headers.get("content-type", "application/json")
    )
    target = f"{entry.llm_upstream.rstrip('/')}/{path}"
    fault = fault_injected(run_id) if request.method == "POST" else ""
    if fault == "cut":
        return _cut_stream()
    if fault:
        return _deny("proxy.fault_injected", 502)
    try:
        await asyncio.wait_for(entry.slots.acquire(), timeout=120)
    except TimeoutError:
        return _deny("proxy.busy", 429)
    # Slot is held until the streamed body is done, not just the headers.
    # Hedged copies ride the same slot: they race for one answer (pico#1257).
    hedge = model_hedge(body) if request.method == "POST" else []
    return await _stream(
        request.method, target, headers, body, on_done=entry.slots.release, hedge=hedge
    )


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
