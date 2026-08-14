"""HTTP surface for the pico-sandbox sidecar. Internal docker/loopback only."""

from __future__ import annotations

import os
from typing import Any

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import Response
from pico_orchestrator.gateway import ToolError
from pydantic import BaseModel, Field

from sandbox_worker.browser import ENGINE_NAME, VIEWPORT_HEIGHT, VIEWPORT_WIDTH
from sandbox_worker.ports import SANDBOX_DEFAULT_PORT, assert_listen_port
from sandbox_worker.runtime import HUMAN_LOGIN_COPY, RUNTIME, redact_secrets

app = FastAPI(title="pico-sandbox", version="0.1.0")


def _token_ok(header: str | None) -> bool:
    expected = (os.environ.get("PICO_SANDBOX_TOKEN") or "").strip()
    if not expected:
        return True
    return (header or "").strip() == expected


def _require_token(x_pico_sandbox_token: str | None) -> None:
    if not _token_ok(x_pico_sandbox_token):
        raise HTTPException(status_code=401, detail={"code": "sandbox.denied", "message": "sidecar token mismatch"})


class OpenBody(BaseModel):
    school_id: str
    membership_id: str
    run_id: str | None = None
    url: str = ""
    kind: str = ""
    filename: str = ""
    document_base64: str = ""


class InputBody(BaseModel):
    school_id: str
    membership_id: str
    click_x: int | None = None
    click_y: int | None = None
    text: str | None = None
    password: bool = False
    field: str = Field(default="input", max_length=64)


class FocusBody(BaseModel):
    school_id: str
    membership_id: str
    window_id: str = ""
    kind: str = ""


def _tool_http(exc: ToolError) -> HTTPException:
    status = 404 if exc.code in {"sandbox.session_not_found", "artifact.not_found"} else 400
    return HTTPException(status_code=status, detail={"code": exc.code, "message": exc.message})


@app.get("/health")
async def health() -> dict[str, Any]:
    port = assert_listen_port(int(os.environ.get("PICO_SANDBOX_PORT") or SANDBOX_DEFAULT_PORT))
    return {
        "ok": True,
        "service": "pico-sandbox",
        "listen_port": port,
        "binds_product_ui": False,
        "engine": ENGINE_NAME,
        "real_browser": True,
        "viewport": {"width": VIEWPORT_WIDTH, "height": VIEWPORT_HEIGHT},
        "human_copy": HUMAN_LOGIN_COPY,
        "claim_wb": "NO",
    }


@app.post("/v1/internal/sessions/open")
async def open_session(
    body: OpenBody,
    x_pico_sandbox_token: str | None = Header(default=None),
) -> dict[str, Any]:
    _require_token(x_pico_sandbox_token)
    try:
        document = None
        if body.document_base64.strip():
            import base64

            try:
                document = base64.b64decode(body.document_base64, validate=False)
            except Exception as exc:
                raise HTTPException(
                    status_code=400,
                    detail={"code": "tool.invalid_arguments", "message": "document_base64 无效"},
                ) from exc
        return await RUNTIME.open_session(
            school_id=body.school_id,
            membership_id=body.membership_id,
            run_id=body.run_id,
            url=body.url,
            kind=body.kind,
            filename=body.filename,
            document=document,
        )
    except ToolError as exc:
        raise _tool_http(exc) from exc


@app.get("/v1/internal/sessions/{session_id}")
async def get_session(
    session_id: str,
    school_id: str,
    membership_id: str,
    x_pico_sandbox_token: str | None = Header(default=None),
) -> dict[str, Any]:
    _require_token(x_pico_sandbox_token)
    try:
        sess = RUNTIME.require_owner(
            session_id, school_id=school_id, membership_id=membership_id
        )
        return await RUNTIME.screenshot(sess)
    except ToolError as exc:
        raise _tool_http(exc) from exc


@app.get("/v1/internal/sessions/{session_id}/png")
async def get_png(
    session_id: str,
    school_id: str,
    membership_id: str,
    x_pico_sandbox_token: str | None = Header(default=None),
) -> Response:
    _require_token(x_pico_sandbox_token)
    try:
        sess = RUNTIME.require_owner(
            session_id, school_id=school_id, membership_id=membership_id
        )
        await RUNTIME._sync(sess)
    except ToolError as exc:
        raise _tool_http(exc) from exc
    return Response(content=sess.screenshot_png, media_type="image/png")


@app.post("/v1/internal/sessions/{session_id}/input")
async def post_input(
    session_id: str,
    body: InputBody,
    request: Request,
    x_pico_sandbox_token: str | None = Header(default=None),
) -> dict[str, Any]:
    _require_token(x_pico_sandbox_token)
    # Do not log request body (may contain a password typed on the view).
    _ = request
    try:
        sess = RUNTIME.require_owner(
            session_id, school_id=body.school_id, membership_id=body.membership_id
        )
        return await RUNTIME.apply_input(
            sess,
            click_x=body.click_x,
            click_y=body.click_y,
            text=body.text,
            password=body.password,
            field=body.field,
        )
    except ToolError as exc:
        raise _tool_http(exc) from exc


@app.post("/v1/internal/sessions/{session_id}/focus")
async def focus_window(
    session_id: str,
    body: FocusBody,
    x_pico_sandbox_token: str | None = Header(default=None),
) -> dict[str, Any]:
    _require_token(x_pico_sandbox_token)
    try:
        sess = RUNTIME.require_owner(
            session_id, school_id=body.school_id, membership_id=body.membership_id
        )
        return await RUNTIME.focus(sess, window_id=body.window_id, kind=body.kind)
    except ToolError as exc:
        raise _tool_http(exc) from exc


@app.post("/v1/internal/sessions/{session_id}/destroy")
async def destroy_session(
    session_id: str,
    school_id: str,
    membership_id: str,
    x_pico_sandbox_token: str | None = Header(default=None),
) -> dict[str, Any]:
    _require_token(x_pico_sandbox_token)
    try:
        RUNTIME.require_owner(session_id, school_id=school_id, membership_id=membership_id)
    except ToolError as exc:
        raise _tool_http(exc) from exc
    await RUNTIME.destroy(session_id)
    return redact_secrets({"ok": True, "destroyed": True, "session_id": session_id})
