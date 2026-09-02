"""Loopback pass-through: splice ledger originals onto GPT Responses."""

from __future__ import annotations

import logging

import httpx
from fastapi import APIRouter, Request, Response
from fastapi.responses import StreamingResponse
from pico_orchestrator.llm_file_pass import splice_responses_body, turn_files

from app.settings import Settings, get_settings

logger = logging.getLogger(__name__)
router = APIRouter()
_HOP = {"host", "content-length", "connection", "transfer-encoding"}


def _upstream_v1(settings: Settings) -> str:
    return (settings.deepseek_base_url or "http://127.0.0.1:3000/v1").rstrip("/")


def _loopback(request: Request) -> bool:
    host = (request.client.host if request.client else "") or ""
    return host in {"127.0.0.1", "::1", "localhost"}


@router.api_route(
    "/internal/llm-pass/{run_id}/v1/{path:path}",
    methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
)
async def llm_pass(run_id: str, path: str, request: Request) -> Response:
    if not _loopback(request):
        return Response(status_code=403, content=b"loopback only")
    settings = get_settings()
    target = f"{_upstream_v1(settings)}/{path}"
    headers = {
        key: value
        for key, value in request.headers.items()
        if key.lower() not in _HOP
    }
    raw = await request.body()
    if request.method == "POST" and path.rstrip("/") in {"responses"}:
        try:
            import json

            payload = json.loads(raw.decode("utf-8") or "{}")
            if isinstance(payload, dict):
                payload = splice_responses_body(payload, turn_files(run_id))
                raw = json.dumps(payload).encode("utf-8")
                headers["content-type"] = "application/json"
        except Exception:
            logger.exception("llm-pass splice skipped run_id=%s", run_id)
    timeout = httpx.Timeout(600.0, connect=10.0)
    client = httpx.AsyncClient(timeout=timeout, follow_redirects=False)
    req = client.build_request(
        request.method, target, headers=headers, content=raw or None
    )
    try:
        upstream = await client.send(req, stream=True)
    except Exception:
        await client.aclose()
        raise

    async def _iter():
        try:
            async for chunk in upstream.aiter_bytes():
                yield chunk
        finally:
            await upstream.aclose()
            await client.aclose()

    out_headers = {
        key: value
        for key, value in upstream.headers.items()
        if key.lower() not in _HOP
    }
    return StreamingResponse(
        _iter(),
        status_code=upstream.status_code,
        headers=out_headers,
        media_type=upstream.headers.get("content-type"),
    )
