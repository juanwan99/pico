"""Overlay workdir/exec for PICO_WORKENV=exec.

Pi stays on pico-api. Overlay is the remote computer (files + python).
Not a new tool name. Not a second kernel.
"""

from __future__ import annotations

import base64
from typing import Any

from pico_orchestrator.gateway import Principal
from pico_orchestrator.sandbox_s1 import current_run_id
from pico_orchestrator.true_pi.workenv_http import WorkenvHttpError, workenv_post


def overlay_exec_on() -> bool:
    from pico_orchestrator.capability_loading import workenv_mode

    return workenv_mode() == "exec"


def overlay_workspace_id(principal: Principal, store: Any) -> str | None:
    rid = current_run_id(principal, store)
    if rid:
        return str(rid)
    store_rid = getattr(store, "_run_id", None) if store is not None else None
    if store_rid:
        return str(store_rid)
    extra = getattr(principal, "extra", None)
    if isinstance(extra, dict) and extra.get("run_id"):
        return str(extra.get("run_id"))
    return None


async def ensure_overlay_run(
    workspace_id: str,
    *,
    principal: Principal,
    conversation_id: str | None = None,
) -> dict[str, Any]:
    return await workenv_post(
        "/v1/internal/workenv/create",
        {
            "run_id": workspace_id,
            "workspace_id": workspace_id,
            "conversation_id": conversation_id or workspace_id,
            "school_id": str(getattr(principal, "school_id", "") or ""),
            "membership_id": str(getattr(principal, "membership_id", "") or ""),
            "mode": "workdir",
        },
        timeout=15.0,
    )


async def overlay_write_file(workspace_id: str, name: str, raw: bytes) -> dict[str, Any]:
    return await workenv_post(
        "/v1/internal/workenv/attach",
        {
            "workspace_id": workspace_id,
            "files": [
                {
                    "name": name,
                    "bytes_b64": base64.b64encode(raw).decode("ascii"),
                }
            ],
        },
    )


async def overlay_list_files(workspace_id: str) -> list[dict[str, Any]]:
    body = await workenv_post(
        "/v1/internal/workenv/ls",
        {"workspace_id": workspace_id},
    )
    rows = body.get("files") if isinstance(body, dict) else []
    return rows if isinstance(rows, list) else []


async def overlay_read_file(workspace_id: str, name: str) -> bytes:
    body = await workenv_post(
        "/v1/internal/workenv/read",
        {"workspace_id": workspace_id, "name": name},
    )
    raw_b64 = str((body or {}).get("bytes_b64") or "")
    return base64.b64decode(raw_b64) if raw_b64 else b""


async def overlay_exec(
    workspace_id: str,
    *,
    source: str | None = None,
    timeout: int = 30,
) -> dict[str, Any]:
    payload: dict[str, Any] = {"workspace_id": workspace_id, "timeout": timeout}
    if source:
        payload["source"] = source
    try:
        return await workenv_post("/v1/internal/workenv/exec", payload, timeout=float(timeout + 5))
    except WorkenvHttpError as exc:
        return {"ok": False, "error": str(exc.body)[:400], "executed": False}
