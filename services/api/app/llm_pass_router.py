"""Loopback pass-through: splice ledger originals onto GPT Responses."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Request, Response
from pico_orchestrator import upstream as door
from pico_orchestrator.llm_file_pass import splice_responses_body, turn_files

from app.loopback import is_loopback_host, request_on_loopback_socket
from app.settings import Settings, get_settings
from app.ws_proxy_router import DOOR_HEADER, _stream, gemini_thinking_body, model_hedge, session_of

logger = logging.getLogger(__name__)
router = APIRouter()
_HOP = {"host", "content-length", "connection", "transfer-encoding"}
_is_loopback_host = is_loopback_host
_loopback = request_on_loopback_socket


def _upstream_v1(settings: Settings) -> str:
    return (settings.deepseek_base_url or "http://127.0.0.1:3000/v1").rstrip("/")


@router.api_route(
    "/internal/llm-pass/{run_id}/v1/{path:path}",
    methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
)
async def llm_pass(run_id: str, path: str, request: Request) -> Response:
    if not _loopback(request):
        client = request.client.host if request.client else ""
        logger.warning(
            "llm-pass denied client=%s server=%s",
            client,
            request.scope.get("server"),
        )
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
                files = turn_files(run_id)
                payload = splice_responses_body(payload, files)
                raw = json.dumps(payload).encode("utf-8")
                headers["content-type"] = "application/json"
                logger.info(
                    "llm-pass splice run_id=%s n=%s bytes=%s",
                    run_id,
                    len(files),
                    sum(len(item.data) for item in files),
                )
        except Exception:
            logger.exception("llm-pass splice skipped run_id=%s", run_id)
    if request.method == "POST":
        raw = gemini_thinking_body(path, raw)
    if "session_id" not in headers:
        # Pi talking here without the run proxy: same session rule (pico#1344).
        session = session_of(raw)
        if session:
            headers["session_id"] = session
    auth = headers.get("authorization") or headers.get("Authorization") or ""
    # One door, one retry layer (pico#1271): the run proxy already raced this
    # step and marked it; Pi talking here directly (no box) is raced here.
    raced = headers.pop(DOOR_HEADER, None)  # starlette keys are lower-case
    if raced:
        call, hedge = door.Call("pi_pass", budget=1), []
    else:
        call = door.Call("pi_step", run_id=run_id)
        hedge = model_hedge(raw, run_id) if request.method == "POST" else []
    return await _stream(
        request.method,
        target,
        headers,
        raw,
        hedge=hedge,
        call=call,
        key=auth.removeprefix("Bearer ").strip() or "llm-pass",
        run_id=None if raced else run_id,
    )
