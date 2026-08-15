"""Thin HTTP client from pico-api → pico-sandbox sidecar.

Execution lives in the sidecar process. This module only maps identity,
never runs a second agent loop, and never stores cookies.
"""

from __future__ import annotations

import os
from typing import Any

import httpx

from pico_orchestrator.gateway import ToolError

_TIMEOUT_S = 90.0


def sandbox_url() -> str:
    raw = (os.environ.get("PICO_SANDBOX_URL") or "").strip()
    return raw or "http://127.0.0.1:18767"


def sandbox_token() -> str:
    return (os.environ.get("PICO_SANDBOX_TOKEN") or "").strip()


def _headers() -> dict[str, str]:
    token = sandbox_token()
    if not token:
        return {}
    return {"X-Pico-Sandbox-Token": token}


def _raise_detail(resp: httpx.Response) -> None:
    code = "sandbox.unavailable"
    message = "隔离沙箱侧车不可用（不是 LibreChat 进程）。请稍后重试。"
    try:
        body = resp.json()
        detail = body.get("detail") if isinstance(body, dict) else None
        if isinstance(detail, dict):
            code = str(detail.get("code") or code)
            message = str(detail.get("message") or message)
        elif isinstance(detail, str) and detail.strip():
            message = detail.strip()
    except Exception:  # noqa: BLE001 — sidecar error body is optional JSON
        message = f"隔离沙箱返回 HTTP {resp.status_code}"
    raise ToolError(code, message)


async def _embedded_call(
    method: str,
    path: str,
    *,
    json_body: dict[str, Any] | None = None,
    params: dict[str, Any] | None = None,
) -> Any:
    from sandbox_worker.runtime import RUNTIME

    parts = [p for p in path.strip("/").split("/") if p]
    # /v1/internal/sessions/...
    if method == "GET" and path.rstrip("/").endswith("/disk"):
        params = params or {}
        from pico_orchestrator.sandbox_persist import owner_disk_meta

        return owner_disk_meta(
            str(params.get("school_id") or ""),
            str(params.get("membership_id") or ""),
        )
    if method == "POST" and path.rstrip("/").endswith("/disk/clear"):
        body = json_body or {}
        if not body.get("confirm"):
            raise ToolError("tool.invalid_arguments", "清空老师盘需要 confirm=true")
        from pico_orchestrator.sandbox_persist import clear_owner_disk

        out = clear_owner_disk(
            str(body.get("school_id") or ""),
            str(body.get("membership_id") or ""),
        )
        out["human_copy"] = "已按你的要求清空这台老师盘。"
        return out
    if method == "POST" and path.endswith("/sessions/open"):
        body = json_body or {}
        document = None
        raw_b64 = str(body.get("document_base64") or "").strip()
        if raw_b64:
            import base64

            document = base64.b64decode(raw_b64, validate=False)
        return await RUNTIME.open_session(
            school_id=str(body.get("school_id") or ""),
            membership_id=str(body.get("membership_id") or ""),
            run_id=body.get("run_id"),
            url=str(body.get("url") or ""),
            kind=str(body.get("kind") or ""),
            filename=str(body.get("filename") or ""),
            document=document,
        )
    if len(parts) >= 4 and parts[0] == "v1" and parts[2] == "sessions":
        session_id = parts[3]
        school = str((json_body or params or {}).get("school_id") or "")
        member = str((json_body or params or {}).get("membership_id") or "")
        sess = RUNTIME.require_owner(session_id, school_id=school, membership_id=member)
        if method == "GET" and path.endswith("/png"):
            await RUNTIME._sync(sess)
            return sess.screenshot_png
        if method == "POST" and path.endswith("/input"):
            body = json_body or {}
            return await RUNTIME.apply_input(
                sess,
                click_x=body.get("click_x"),
                click_y=body.get("click_y"),
                text=body.get("text"),
                password=bool(body.get("password")),
                field=str(body.get("field") or "input"),
            )
        if method == "POST" and path.endswith("/focus"):
            body = json_body or {}
            return await RUNTIME.focus(
                sess,
                window_id=str(body.get("window_id") or ""),
                kind=str(body.get("kind") or ""),
            )
        if method == "POST" and path.endswith("/destroy"):
            await RUNTIME.destroy(session_id)
            return {"ok": True, "destroyed": True, "session_id": session_id}
        if method == "GET":
            return await RUNTIME.screenshot(sess)
    raise ToolError("sandbox.unavailable", "隔离沙箱内部路径未知")


async def sidecar_json(
    method: str,
    path: str,
    *,
    json_body: dict[str, Any] | None = None,
    params: dict[str, Any] | None = None,
) -> Any:
    base = sandbox_url()
    if base == "embedded":
        return await _embedded_call(method, path, json_body=json_body, params=params)
    url = base.rstrip("/") + path
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT_S, trust_env=False) as client:
            resp = await client.request(
                method,
                url,
                json=json_body,
                params=params,
                headers=_headers(),
            )
    except httpx.HTTPError as exc:
        raise ToolError(
            "sandbox.unavailable",
            "隔离沙箱侧车未运行。浏览器画面不在 LibreChat / pico-api 进程内。",
        ) from exc
    if resp.status_code >= 400:
        _raise_detail(resp)
    if path.endswith("/png"):
        return resp.content
    try:
        return resp.json()
    except Exception as exc:
        raise ToolError("sandbox.unavailable", "隔离沙箱返回了无法解析的响应") from exc
