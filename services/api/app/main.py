"""Pico API control plane and AI ledger."""

from __future__ import annotations

import asyncio
import json
import mimetypes
import re
import sys
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import quote

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sse_starlette.sse import EventSourceResponse

_ROOT = Path(__file__).resolve().parents[3]
_ORCH = _ROOT / "services" / "orchestrator"
for p in (str(_ORCH),):
    if p not in sys.path:
        sys.path.insert(0, p)

# Load repo-root .env before settings (keys never shipped in git)
try:
    from dotenv import load_dotenv

    load_dotenv(_ROOT / ".env", override=False)
except ImportError:
    pass

from app import run_service
from app.auth import (
    Principal,
    issue_test_token,
    require_any_scope,
    require_scope,
    require_scoped_principal,
    require_service_token,
)
from app.db import EventRow, RunRow, WorkspaceRow, get_session, init_db, new_id
from app.openai_compat import router as openai_compat_router
from app.rate_limit import ChatRateLimitMiddleware
from app.settings import Settings, get_settings


def _sync_settings_to_environ() -> None:
    """Bridge pydantic settings into os.environ for orchestrator adapters."""
    import os

    s = get_settings()
    mapping = {
        "KIMI_API_KEY": s.kimi_api_key,
        "KIMI_BASE_URL": s.kimi_base_url,
        "KIMI_MODEL": s.kimi_model,
        "DEEPSEEK_API_KEY": s.deepseek_api_key,
        "PICO_EDU_MODE": s.pico_edu_mode,
        "PICO_EDU_BASE_URL": s.pico_edu_base_url,
        "PICO_EDU_SERVICE_TOKEN": s.pico_edu_service_token,
        "PICO_EDU_TIMEOUT_SECONDS": str(s.pico_edu_timeout_seconds),
        "PICO_EDU_HANDOFF_ENABLED": "true" if s.pico_edu_handoff_enabled else "false",
    }
    for k, v in mapping.items():
        if v and not os.environ.get(k):
            os.environ[k] = str(v)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    get_settings().validate_production()
    _sync_settings_to_environ()
    await init_db()
    factory = run_service.session_factory()
    async with factory() as session:
        await run_service.reconcile_orphaned_runs(session)
    from app import automation_service

    automation_service.start_scheduler()
    try:
        yield
    finally:
        await automation_service.stop_scheduler()


app = FastAPI(
    title="Pico API",
    version="0.4.0",
    description="Pico control plane and AI ledger",
    lifespan=lifespan,
)

_settings = get_settings()
app.add_middleware(ChatRateLimitMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=_settings.cors_origin_list or ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(openai_compat_router)


# ----- meta / auth -----


class TokenRequest(BaseModel):
    school_id: str = Field(examples=["school-a"])
    membership_id: str = Field(examples=["member-1"])
    scopes: list[str] = Field(
        default_factory=lambda: ["ai:run", "ai:read", "ai:confirm"]
    )


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    claims_shape: dict




def _resolve_git_sha() -> str:
    """Best-effort code identity for version self-proof."""
    import os
    import subprocess

    env = (os.environ.get("PICO_GIT_SHA") or os.environ.get("GITHUB_SHA") or "").strip()
    if env:
        return env
    try:
        out = subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            cwd=str(_ROOT),
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=2,
        )
        return out.strip()
    except (OSError, subprocess.SubprocessError):
        return "unknown"



@app.get("/")
async def root_info() -> dict:
    """Avoid bare FastAPI Not Found when preview probes API root."""
    return {
        "ok": True,
        "service": "pico-api",
        "message": "Pico API. Product UI is on the preview host (LibreChat via product UI :8080).",
        "health": "/health",
        "version": "/v1/meta/version",
        "chat": "/v1/chat/completions",
    }


@app.get("/health")
async def health(settings: Settings = Depends(get_settings)) -> dict:
    # Never echo canary principal IDs — only counts / opaque batch labels.
    canary_count = settings.kimi_agent_canary_membership_count
    batch = (settings.pico_kimi_agent_canary_batch or "").strip()
    body: dict = {
        "ok": True,
        "service": "pico-api",
        "git_sha": _resolve_git_sha(),
        "edu_mode": settings.pico_edu_mode,
        "kimi_agent_runtime_enabled": settings.pico_kimi_agent_runtime,
        "kimi_agent_scope": settings.kimi_agent_scope,
        "kimi_agent_canary_configured": canary_count > 0,
        "kimi_agent_canary_membership_count": canary_count,
        "rate_limit": {
            "chat_rpm": settings.pico_chat_rpm,
            "chat_max_concurrent": settings.pico_chat_max_concurrent,
            "key_scope": "membership_or_ip",
        },
    }
    if batch:
        body["kimi_agent_canary_batch"] = batch
    return body


@app.get("/v1/meta/version")
async def meta_version(settings: Settings = Depends(get_settings)) -> dict:
    """Runtime version self-proof — which code + which product shell."""
    from pico_orchestrator.pins import AGENT_PINS, installed_versions
    from pico_orchestrator.provider import resolve_provider

    librechat = _ROOT / "apps" / "librechat" / "package.json"
    product_ui = "librechat" if librechat.is_file() else "missing"
    cfg = resolve_provider()
    return {
        "ok": True,
        "service": "pico-api",
        "git_sha": _resolve_git_sha(),
        "api_version": app.version,
        "product_ui": product_ui,
        "product_ui_ok": product_ui == "librechat",
        "agent_pins": AGENT_PINS,
        "installed": installed_versions(),
        "dangerous_tools_enabled": settings.pico_dangerous_tools_enabled,
        "model_ready": cfg is not None,
        "model_provider": cfg.name if cfg else None,
        "model_name": cfg.model if cfg else None,
        "plan": "MVP-3DAY v1.2 FIXED",
    }


@app.get("/v1/meta/freeze")
async def freeze_meta(settings: Settings = Depends(get_settings)) -> dict:
    from pico_orchestrator.pins import AGENT_PINS, installed_versions
    from pico_orchestrator.provider import resolve_provider

    cfg = resolve_provider()
    return {
        "plan": "MVP-3DAY v1.2 FIXED",
        "agent_pins": AGENT_PINS,
        "installed": installed_versions(),
        "spend_caps": {
            "max_seconds": settings.pico_run_max_seconds,
            "max_tokens": settings.pico_run_max_tokens,
            "max_retries": settings.pico_run_max_retries,
        },
        "dangerous_tools_enabled_setting": settings.pico_dangerous_tools_enabled,
        "model_ready": cfg is not None,
        "model_provider": cfg.name if cfg else None,
        "model_name": cfg.model if cfg else None,
    }


@app.get("/v1/meta/agent-safety")
async def agent_safety(settings: Settings = Depends(get_settings)) -> dict:
    """Prove dangerous tools are off for the default agent file AND the Kimi runtime file.

    Canary/KA path loads ``pico-kimi-runtime.yaml``; checking only ``pico.yaml`` is misleading.
    """
    from pico_orchestrator.safety import assert_dangerous_tools_off

    if settings.pico_dangerous_tools_enabled:
        raise HTTPException(status_code=500, detail="PICO_DANGEROUS_TOOLS_ENABLED must be false")

    agent_path = Path(settings.pico_agent_file)
    if not agent_path.is_absolute():
        agent_path = _ROOT / agent_path

    kimi_path = (
        Path(__file__).resolve().parents[2]
        / "orchestrator"
        / "agents"
        / "pico-kimi-runtime.yaml"
    )
    # main.py is services/api/app/main.py → parents[2] = services
    paths: list[Path] = [agent_path]
    if kimi_path.is_file() and kimi_path.resolve() != agent_path.resolve():
        paths.append(kimi_path)

    proofs: list[dict] = []
    try:
        for path in paths:
            proofs.append(assert_dangerous_tools_off(path))
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={
                "message": "安全配置校验失败，危险工具必须保持关闭。",
                "code": "safety.check_failed",
                "detail": str(e),
            },
        ) from e
    return {
        "ok": True,
        # backward compatible single proof = last checked (Kimi file when present)
        "proof": proofs[-1],
        "proofs": proofs,
        "agent_files_checked": [str(p) for p in paths],
    }


@app.post("/v1/dev/token", response_model=TokenResponse)
async def dev_token(
    body: TokenRequest, settings: Settings = Depends(get_settings)
) -> TokenResponse:
    if settings.pico_env == "production":
        raise HTTPException(status_code=404, detail="not available in production")
    token = issue_test_token(
        school_id=body.school_id,
        membership_id=body.membership_id,
        scopes=body.scopes,
        settings=settings,
    )
    return TokenResponse(
        access_token=token,
        expires_in=settings.pico_jwt_ttl_seconds,
        claims_shape={
            "iss": settings.pico_jwt_iss,
            "aud": settings.pico_jwt_aud,
            "school_id": body.school_id,
            "membership_id": body.membership_id,
            "scopes": body.scopes,
            "exp": "unix",
        },
    )


@app.get("/v1/me")
async def me(principal: Principal = Depends(require_scoped_principal)) -> dict:
    return {
        "school_id": principal.school_id,
        "membership_id": principal.membership_id,
        "scopes": principal.scopes,
        "iss": principal.iss,
        "aud": principal.aud,
        "exp": principal.exp,
    }


class HelloRequest(BaseModel):
    prompt: str = Field(default="Say hello in one short sentence.")


@app.post("/v1/dev/model-hello")
async def model_hello(
    body: HelloRequest,
    principal: Principal = Depends(require_scope("ai:run")),
    settings: Settings = Depends(get_settings),
) -> dict:
    from pico_orchestrator.provider import resolve_provider, stream_chat

    cfg = resolve_provider()
    if cfg is None:
        return {
            "status": "BLOCKED",
            "standard": "S1",
            "reason": "missing KIMI_API_KEY (and no DEEPSEEK_API_KEY fallback)",
            "principal": {
                "school_id": principal.school_id,
                "membership_id": principal.membership_id,
            },
        }
    chunks: list[str] = []
    max_tokens = min(256, settings.pico_run_max_tokens)
    async for delta in stream_chat(body.prompt, max_tokens=max_tokens):
        chunks.append(delta)
    return {
        "status": "ok",
        "provider": cfg.name,
        "model": cfg.model,
        "text": "".join(chunks),
        "principal": {
            "school_id": principal.school_id,
            "membership_id": principal.membership_id,
        },
    }


# ----- tools -----


@app.get("/v1/tools")
async def list_tools(
    principal: Principal = Depends(require_scope("ai:read")),
) -> dict:
    from pico_orchestrator.tools_builtin import build_default_gateway

    gw = build_default_gateway()
    return {"tools": gw.list_tools(), "school_id": principal.school_id}


@app.get("/v1/skills/catalog")
async def list_skill_catalog(
    _principal: Principal = Depends(require_scope("ai:read")),
) -> dict:
    """Expose controlled skill/tool bindings without editable policy fields."""
    from pico_orchestrator.skill_policy import skill_catalog

    return {"skills": skill_catalog()}


class ToolInvokeRequest(BaseModel):
    name: str
    arguments: dict = Field(default_factory=dict)


@app.post("/v1/tools/invoke")
async def invoke_tool(
    body: ToolInvokeRequest,
    principal: Principal = Depends(require_scope("ai:run")),
) -> dict:
    from pico_orchestrator.gateway import ToolError
    from pico_orchestrator.tools_builtin import build_default_gateway

    from app.artifact_store import LedgerArtifactStore
    from app.db import session_factory

    gw = build_default_gateway(LedgerArtifactStore(session_factory()))
    try:
        result = await gw.invoke(principal, body.name, dict(body.arguments))
    except ToolError as e:
        code = 403 if e.code == "tenant.cross_school" else 400
        raise HTTPException(
            status_code=code, detail={"code": e.code, "message": e.message}
        ) from e
    return {"ok": True, "result": result}




# ----- workspaces (managed boundary) -----


class CreateWorkspaceRequest(BaseModel):
    name: str
    note: str = ""
    kind: str = "managed"


@app.get("/v1/workspaces")
async def list_workspaces(
    principal: Principal = Depends(require_scope("ai:read")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    from sqlalchemy import select

    q = await session.execute(
        select(WorkspaceRow)
        .where(
            WorkspaceRow.school_id == principal.school_id,
            WorkspaceRow.membership_id == principal.membership_id,
        )
        .order_by(WorkspaceRow.created_at.desc())
    )
    rows = list(q.scalars().all())
    return {
        "workspaces": [
            {
                "id": w.id,
                "name": w.name,
                "kind": w.kind,
                "note": w.note,
                "created_at": w.created_at.isoformat() if w.created_at else None,
            }
            for w in rows
        ]
    }


@app.post("/v1/workspaces")
async def create_workspace(
    body: CreateWorkspaceRequest,
    principal: Principal = Depends(require_scope("ai:run")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    name = body.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="name required")
    row = WorkspaceRow(
        id=new_id(),
        school_id=principal.school_id,
        membership_id=principal.membership_id,
        name=name[:256],
        kind=body.kind if body.kind in {"managed", "cloud"} else "managed",
        note=(body.note or "")[:512],
    )
    session.add(row)
    await session.commit()
    return {
        "workspace": {
            "id": row.id,
            "name": row.name,
            "kind": row.kind,
            "note": row.note,
        }
    }


@app.delete("/v1/workspaces/{workspace_id}")
async def delete_workspace(
    workspace_id: str,
    principal: Principal = Depends(require_scope("ai:run")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    row = await session.get(WorkspaceRow, workspace_id)
    if not row or row.school_id != principal.school_id or row.membership_id != principal.membership_id:
        raise HTTPException(status_code=404, detail="workspace not found")
    await session.delete(row)
    await session.commit()
    return {"ok": True}




# ----- automations (server scheduler) -----


class CreateAutomationRequest(BaseModel):
    name: str
    prompt: str
    schedule_kind: str = "periodic"  # periodic|interval|once
    schedule: dict | None = None
    workspace_id: str | None = None


def _auto_dict(a) -> dict:
    import json as _json
    return {
        "id": a.id,
        "name": a.name,
        "prompt": a.prompt,
        "schedule_kind": a.schedule_kind,
        "schedule": _json.loads(a.schedule_json or "{}"),
        "workspace_id": a.workspace_id,
        "enabled": bool(a.enabled),
        "last_run_at": a.last_run_at.isoformat() if a.last_run_at else None,
        "next_run_at": a.next_run_at.isoformat() if a.next_run_at else None,
        "created_at": a.created_at.isoformat() if a.created_at else None,
    }


@app.get("/v1/automations")
async def list_automations(
    principal: Principal = Depends(require_scope("ai:read")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    from app import automation_service

    rows = await automation_service.list_automations(session, principal)
    return {"automations": [_auto_dict(a) for a in rows]}


@app.post("/v1/automations")
async def create_automation(
    body: CreateAutomationRequest,
    principal: Principal = Depends(require_scope("ai:run")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    from app import automation_service

    if not body.prompt.strip() and not body.name.strip():
        raise HTTPException(status_code=400, detail="name/prompt required")
    row = await automation_service.create_automation(
        session,
        principal,
        name=body.name.strip() or body.prompt.strip()[:40],
        prompt=body.prompt.strip() or body.name.strip(),
        schedule_kind=body.schedule_kind,
        schedule=body.schedule or {},
        workspace_id=body.workspace_id,
    )
    return {"automation": _auto_dict(row)}


@app.post("/v1/automations/{auto_id}/enable")
async def enable_automation(
    auto_id: str,
    principal: Principal = Depends(require_scope("ai:run")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    from app import automation_service

    row = await automation_service.set_enabled(session, principal, auto_id, True)
    if not row:
        raise HTTPException(status_code=404, detail="not found")
    return {"automation": _auto_dict(row)}


@app.post("/v1/automations/{auto_id}/disable")
async def disable_automation(
    auto_id: str,
    principal: Principal = Depends(require_scope("ai:run")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    from app import automation_service

    row = await automation_service.set_enabled(session, principal, auto_id, False)
    if not row:
        raise HTTPException(status_code=404, detail="not found")
    return {"automation": _auto_dict(row)}


@app.post("/v1/automations/{auto_id}/run")
async def run_automation_once(
    auto_id: str,
    principal: Principal = Depends(require_scope("ai:run")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    from app import automation_service

    result = await automation_service.run_once(session, principal, auto_id)
    if not result:
        raise HTTPException(status_code=404, detail="not found")
    automation, task, run = result
    return {
        "automation": _auto_dict(automation),
        "task": _task_dict(task),
        "run": _run_dict(run),
    }


@app.delete("/v1/automations/{auto_id}")
async def delete_automation(
    auto_id: str,
    principal: Principal = Depends(require_scope("ai:run")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    from app import automation_service

    ok = await automation_service.delete_automation(session, principal, auto_id)
    if not ok:
        raise HTTPException(status_code=404, detail="not found")
    return {"ok": True}


# ----- tasks / runs / events -----


class CreateTaskRequest(BaseModel):
    title: str = ""
    prompt: str
    skill_id: str | None = None


def _task_dict(t) -> dict:
    return {
        "id": t.id,
        "school_id": t.school_id,
        "membership_id": t.membership_id,
        "title": t.title,
        "conversation_id": getattr(t, "conversation_id", None),
        "workspace_id": getattr(t, "workspace_id", None),
        "created_at": t.created_at.isoformat() if t.created_at else None,
    }


def _run_dict(r) -> dict:
    return {
        "id": r.id,
        "task_id": r.task_id,
        "status": r.status,
        "model": r.model,
        "prompt": r.prompt,
        "error": r.error,
        "cancel_requested": bool(r.cancel_requested),
        "started_at": r.started_at.isoformat() if r.started_at else None,
        "ended_at": r.ended_at.isoformat() if r.ended_at else None,
        "token_usage": json.loads(r.token_usage_json or "{}"),
    }


def _event_dict(e: EventRow) -> dict:
    return {
        "id": e.id,
        "run_id": e.run_id,
        "seq": e.seq,
        "type": e.type,
        "payload": e.payload,
        "created_at": e.created_at.isoformat() if e.created_at else None,
    }


@app.post("/v1/tasks")
async def create_task(
    body: CreateTaskRequest,
    principal: Principal = Depends(require_scope("ai:run")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    if not body.prompt.strip():
        raise HTTPException(status_code=400, detail="prompt required")
    task, run = await run_service.create_task(
        session, principal, body.title, body.prompt.strip(), body.skill_id
    )
    await run_service.start_run_background(run.id, principal)
    return {"task": _task_dict(task), "run": _run_dict(run)}


@app.get("/v1/tasks")
async def tasks(
    conversation_id: str | None = None,
    principal: Principal = Depends(require_scope("ai:read")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    rows = await run_service.list_tasks(
        session,
        principal,
        conversation_id=conversation_id,
    )
    latest = await run_service.latest_runs_for_tasks(session, [t.id for t in rows])
    out = []
    for task in rows:
        item = _task_dict(task)
        run = latest.get(task.id)
        if run is not None:
            # Compact summary for list UIs — no prompt body.
            item["latest_run"] = {
                "id": run.id,
                "status": run.status,
                "cancel_requested": bool(run.cancel_requested),
                "model": run.model,
                "error": run.error,
                "started_at": run.started_at.isoformat() if run.started_at else None,
                "ended_at": run.ended_at.isoformat() if run.ended_at else None,
            }
        else:
            item["latest_run"] = None
        out.append(item)
    return {"tasks": out}


@app.get("/v1/tasks/{task_id}")
async def get_task(
    task_id: str,
    principal: Principal = Depends(require_scope("ai:read")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    task = await run_service.get_task_for_principal(session, task_id, principal)
    if not task:
        raise HTTPException(status_code=404, detail="task not found")
    arts = await run_service.list_artifacts_for_task(session, task_id)
    artifacts_out: list[dict] = []
    for a in arts:
        encoding = getattr(a, "content_encoding", None) or "utf8"
        byte_size = int(getattr(a, "byte_size", 0) or 0)
        sha = getattr(a, "content_sha256", None) or ""
        # Never embed base64 binary into the task JSON as fake text.
        inline_value = a.inline if encoding == "utf8" else None
        if not byte_size and encoding == "utf8":
            byte_size = len((a.inline or "").encode("utf-8"))
        artifacts_out.append(
            {
                "id": a.id,
                "kind": a.kind,
                "title": a.title,
                "inline": inline_value,
                "run_id": a.run_id,
                "content_encoding": encoding,
                "byte_size": byte_size,
                "content_sha256": sha,
            }
        )
    return {
        "task": _task_dict(task),
        "artifacts": artifacts_out,
    }


@app.get("/v1/artifacts/{artifact_id}/content")
async def get_artifact_content(
    artifact_id: str,
    download: bool = False,
    principal: Principal = Depends(require_scope("ai:read")),
    session: AsyncSession = Depends(get_session),
) -> Response:
    from app.artifact_store import decode_artifact_payload

    artifact = await run_service.get_artifact_for_principal(
        session,
        artifact_id,
        principal,
    )
    if artifact is None:
        raise HTTPException(
            status_code=404,
            detail={
                "code": "artifact.not_found",
                "message": (
                    "找不到该产物。请用 GET /v1/artifacts/{id}/content"
                    "（可选 ?download=true）下载，不要用虚构的 /download 尾缀。"
                ),
                "user_message": "找不到该产物。请从任务结果区打开或下载；路径为 /v1/artifacts/{id}/content。",
                "correct_path": f"/v1/artifacts/{artifact_id}/content",
            },
        )

    filename = (artifact.title or f"{artifact.id}.txt").replace("\r", "").replace("\n", "")
    fallback = re.sub(r"[^A-Za-z0-9._-]+", "_", filename).strip("._") or "artifact.bin"
    disposition = "attachment" if download else "inline"
    extension_media_types = {
        ".csv": "text/csv",
        ".json": "application/json",
        ".md": "text/markdown",
        ".txt": "text/plain",
        ".html": "text/html; charset=utf-8",
        ".htm": "text/html; charset=utf-8",
        ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    }
    ext = Path(filename).suffix.lower()
    guessed_media_type = (
        extension_media_types.get(ext)
        or mimetypes.guess_type(filename)[0]
        or "application/octet-stream"
    )
    safe_inline_media_types = {
        "application/json",
        "image/bmp",
        "image/gif",
        "image/jpeg",
        "image/png",
        "image/webp",
        "text/csv",
        "text/markdown",
        "text/plain",
        "text/html",
        "text/html; charset=utf-8",
    }
    encoding = getattr(artifact, "content_encoding", None) or "utf8"
    try:
        raw = decode_artifact_payload(artifact.inline, encoding)
    except Exception as exc:
        raise HTTPException(status_code=500, detail="artifact payload corrupt") from exc

    # Fail-closed: never serve renamed text as legitimate Office packages.
    if ext in {".docx", ".pptx"}:
        from pico_orchestrator.artifact_types import is_valid_ooxml_package

        if not is_valid_ooxml_package(raw, ext):
            raise HTTPException(
                status_code=415,
                detail=(
                    f"产物不是合法的 {ext} OOXML 包（禁止改后缀文本冒充）。"
                    "请使用 generate_docx_document / generate_pptx_document 重新生成。"
                ),
            )
    # HTML claimed but looks like a ZIP/binary package without text markup → reject as html
    if ext in {".html", ".htm"} and raw[:2] == b"PK":
        raise HTTPException(
            status_code=415,
            detail="产物不是合法 HTML（疑似二进制改后缀）。请使用 generate_html_document。",
        )

    # Security: non-download HTML must not be navigable as active content via API.
    # UI sandboxed preview still uses the body bytes; filename drives preview mode.
    # Shell still applies iframe sandbox; do not rely on payload CSP alone.
    if ext in {".html", ".htm"} and not download:
        media_type = "text/plain; charset=utf-8"
    elif download or guessed_media_type in safe_inline_media_types:
        media_type = guessed_media_type
    else:
        media_type = "application/octet-stream"

    digest = getattr(artifact, "content_sha256", None) or ""
    return Response(
        content=raw,
        media_type=media_type,
        headers={
            "Content-Disposition": (
                f'{disposition}; filename="{fallback}"; '
                f"filename*=UTF-8''{quote(filename)}"
            ),
            "X-Content-Type-Options": "nosniff",
            "X-Pico-Content-Encoding": encoding,
            "X-Pico-Content-SHA256": digest,
            "X-Pico-Byte-Size": str(len(raw)),
        },
    )




class RebindConversationRequest(BaseModel):
    from_conversation_id: str
    to_conversation_id: str


@app.post("/v1/tasks/rebind-conversation")
async def rebind_conversation(
    body: RebindConversationRequest,
    principal: Principal = Depends(require_scope("ai:run")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Map pending client convo id → real LibreChat conversation id."""
    src = (body.from_conversation_id or "").strip()[:128]
    dst = (body.to_conversation_id or "").strip()[:128]
    if not src or not dst or src == dst:
        raise HTTPException(status_code=400, detail="invalid conversation ids")
    if dst in {"new", "search"} or src in {"new", "search"}:
        raise HTTPException(status_code=400, detail="reserved conversation id")
    from sqlalchemy import select

    from app.db import TaskRow

    q = await session.execute(
        select(TaskRow).where(
            TaskRow.school_id == principal.school_id,
            TaskRow.membership_id == principal.membership_id,
            TaskRow.conversation_id == src,
        )
    )
    rows = list(q.scalars().all())
    for row in rows:
        row.conversation_id = dst
    await session.commit()
    return {"updated": len(rows), "from": src, "to": dst}


@app.get("/v1/tasks/{task_id}/runs")
async def list_task_runs(
    task_id: str,
    principal: Principal = Depends(require_scope("ai:read")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    task = await run_service.get_task_for_principal(session, task_id, principal)
    if not task:
        raise HTTPException(status_code=404, detail="task not found")
    runs = await run_service.list_runs_for_task(session, task_id)
    return {"runs": [_run_dict(r) for r in runs]}


@app.get("/v1/runs/{run_id}")
async def get_run(
    run_id: str,
    principal: Principal = Depends(require_scope("ai:read")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    run = await run_service.get_run_for_principal(session, run_id, principal)
    if not run:
        raise HTTPException(status_code=404, detail="run not found")
    return {"run": _run_dict(run)}


@app.post("/v1/runs/{run_id}/cancel")
async def cancel_run(
    run_id: str,
    principal: Principal = Depends(require_scope("ai:run")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    from app.db import append_event

    run = await run_service.get_run_for_principal(session, run_id, principal)
    if not run:
        raise HTTPException(status_code=404, detail="run not found")
    try:
        result = await run_service.request_cancel(session, run)
    except ValueError:
        # Already succeeded/failed (not sticky cancelled). Never pretend cancel worked.
        raise HTTPException(
            status_code=409,
            detail={
                "code": "run.already_terminal",
                "message": "该任务已结束，无法再停止。请刷新查看最终状态。",
                "user_message": "该任务已结束，无法再停止。请刷新查看最终状态。",
                "status": run.status,
            },
        ) from None
    # Event allocation may roll the session back on a concurrent seq collision,
    # expiring ORM attributes.  Snapshot the response before appending events so
    # cancellation still returns its durable terminal state.
    run_payload = _run_dict(result.run)
    cancelled_run_id = run_payload["id"]
    if result.request_recorded:
        await append_event(session, cancelled_run_id, "run.cancel_requested", {})
    if result.status_changed:
        await append_event(
            session,
            cancelled_run_id,
            "run.status",
            {"status": "cancelled"},
        )
    # Sticky cancelled: first cancel and idempotent re-cancel both return 200 + cancelled.
    return {"run": run_payload, "cancel": "ok"}


@app.post("/v1/tasks/{task_id}/cancel-active")
async def cancel_task_active_runs(
    task_id: str,
    principal: Principal = Depends(require_scope("ai:run")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    from app.db import append_event

    task = await run_service.get_task_for_principal(session, task_id, principal)
    if not task:
        raise HTTPException(status_code=404, detail="task not found")
    results = await run_service.cancel_active_runs_for_task(session, task_id)
    runs = []
    for result in results:
        # See cancel_run: append_event can expire ORM state after a SQLite
        # sequence collision, so never serialize result.run after event writes.
        run_payload = _run_dict(result.run)
        cancelled_run_id = run_payload["id"]
        if result.request_recorded:
            await append_event(
                session,
                cancelled_run_id,
                "run.cancel_requested",
                {"source": "task_cancel"},
            )
        if result.status_changed:
            await append_event(
                session,
                cancelled_run_id,
                "run.status",
                {"status": "cancelled"},
            )
        runs.append(run_payload)
    return {"runs": runs, "cancelled": len(runs)}


@app.post("/v1/runs/{run_id}/retry")
async def retry_run(
    run_id: str,
    principal: Principal = Depends(require_scope("ai:run")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    source_run = await run_service.get_run_for_principal(session, run_id, principal)
    if not source_run:
        raise HTTPException(status_code=404, detail="run not found")
    try:
        retry = await run_service.retry_failed_run(session, source_run)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    await run_service.start_run_background(retry.id, principal)
    return {
        "run": _run_dict(retry),
        "retried_from_run_id": source_run.id,
    }


@app.get("/v1/runs/{run_id}/events")
async def run_events(
    run_id: str,
    principal: Principal = Depends(require_scope("ai:read")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    run = await run_service.get_run_for_principal(session, run_id, principal)
    if not run:
        raise HTTPException(status_code=404, detail="run not found")
    events = await run_service.list_events(session, run_id)
    return {"events": [_event_dict(e) for e in events]}


@app.get("/v1/runs/{run_id}/stream")
async def stream_run(
    run_id: str,
    request: Request,
    principal: Principal = Depends(require_scope("ai:read")),
    session: AsyncSession = Depends(get_session),
):
    run = await run_service.get_run_for_principal(session, run_id, principal)
    if not run:
        raise HTTPException(status_code=404, detail="run not found")

    async def gen():
        last_seq = 0
        terminal = {"succeeded", "failed", "cancelled"}
        while True:
            if await request.is_disconnected():
                break
            from app.db import session_factory

            factory = session_factory()
            async with factory() as s:
                r = await s.get(RunRow, run_id)
                events = await run_service.list_events(s, run_id)
                for e in events:
                    if e.seq > last_seq:
                        last_seq = e.seq
                        yield {
                            "event": e.type,
                            "data": json.dumps(_event_dict(e), ensure_ascii=False),
                        }
                status = r.status if r else "failed"
            if status in terminal:
                # End even when zero events (failed before emit) — avoid infinite poll.
                yield {
                    "event": "stream.end",
                    "data": json.dumps({"status": status}),
                }
                break
            await asyncio.sleep(0.25)

    return EventSourceResponse(gen())


# ----- changes (S7) -----


class ChangeCreateRequest(BaseModel):
    title: str
    summary: str
    payload: dict = Field(default_factory=dict)
    task_id: str | None = None
    run_id: str | None = None


def _change_dict(row) -> dict:
    return {
        "id": row.id,
        "task_id": row.task_id,
        "run_id": row.run_id,
        "title": row.title,
        "summary": row.summary,
        "payload": json.loads(row.payload_json or "{}"),
        "status": row.status,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "confirmed_by": row.confirmed_by,
        "confirmed_at": row.confirmed_at.isoformat() if row.confirmed_at else None,
        "audit": json.loads(row.audit_json or "[]"),
    }


@app.post("/v1/changes")
async def create_change(
    body: ChangeCreateRequest,
    principal: Principal = Depends(require_scope("ai:run")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    try:
        row = await run_service.create_change(
            session,
            principal,
            title=body.title,
            summary=body.summary,
            payload=body.payload,
            task_id=body.task_id,
            run_id=body.run_id,
        )
    except KeyError:
        raise HTTPException(status_code=404, detail="task or run not found") from None
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return {"change": _change_dict(row)}


@app.get("/v1/changes")
async def changes(
    task_id: str | None = None,
    status: str | None = None,
    principal: Principal = Depends(require_scope("ai:read")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    if status and status not in {"proposed", "confirmed", "rejected"}:
        raise HTTPException(status_code=400, detail="invalid change status")
    rows = await run_service.list_changes(
        session,
        principal,
        task_id=task_id,
        status=status,
    )
    return {"changes": [_change_dict(row) for row in rows]}


@app.get("/v1/changes/{change_id}")
async def get_change(
    change_id: str,
    principal: Principal = Depends(require_scope("ai:read")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    row = await run_service.get_change_for_principal(session, principal, change_id)
    if row is None:
        raise HTTPException(status_code=404, detail="change not found")
    return {"change": _change_dict(row)}


@app.post("/v1/changes/{change_id}/confirm")
async def confirm_change(
    change_id: str,
    principal: Principal = Depends(require_any_scope("ai:confirm", "ai:run")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    try:
        row = await run_service.confirm_change(session, principal, change_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="change not found") from None
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    change = _change_dict(row)
    change["note"] = "Audit only — no school business write in Phase 1"
    return {"change": change}


@app.post("/v1/changes/{change_id}/reject")
async def reject_change(
    change_id: str,
    principal: Principal = Depends(require_any_scope("ai:confirm", "ai:run")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    try:
        row = await run_service.reject_change(session, principal, change_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="change not found") from None
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    change = _change_dict(row)
    change["note"] = "Rejected — no school business write"
    return {"change": change}


# ----- demos -----


@app.post("/v1/demo/cross-school-deny")
async def demo_cross_school(
    principal: Principal = Depends(require_scope("ai:run")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    return await run_service.demo_cross_school_deny(session, principal)


# ----- Phase 3 edu hooks -----


class EduChangeStatusIn(BaseModel):
    pico_change_id: str
    edu_review_id: str = ""
    status: str  # committed | rejected
    detail: dict = Field(default_factory=dict)


@app.post("/v1/hooks/edu/change-status")
async def edu_change_status(
    body: EduChangeStatusIn,
    session: AsyncSession = Depends(get_session),
    _: bool = Depends(require_service_token),
) -> dict:
    """edu → Pico callback after Review/Commit (no school write in Pico)."""
    from app.db import AuditRow, ChangeProposalRow, new_id

    if body.status not in {"committed", "rejected"}:
        raise HTTPException(status_code=400, detail="status must be committed|rejected")
    row = await session.get(ChangeProposalRow, body.pico_change_id)
    if row is None:
        raise HTTPException(status_code=404, detail="change not found")
    history = json.loads(row.audit_json or "[]")
    history.append(
        {
            "action": f"edu_{body.status}",
            "edu_review_id": body.edu_review_id,
            "detail": body.detail,
        }
    )
    row.audit_json = json.dumps(history, ensure_ascii=False)
    if body.status == "rejected" and row.status == "confirmed":
        row.status = "rejected"
    session.add(
        AuditRow(
            id=new_id(),
            school_id=row.school_id,
            membership_id=row.membership_id,
            action=f"change.edu_{body.status}",
            subject_type="change_proposal",
            subject_id=row.id,
            detail_json=json.dumps(
                {"edu_review_id": body.edu_review_id, "detail": body.detail},
                ensure_ascii=False,
            ),
        )
    )
    await session.commit()
    return {"ok": True, "pico_change_id": row.id, "status": row.status}


@app.get("/v1/meta/phase3")
async def phase3_meta(settings: Settings = Depends(get_settings)) -> dict:
    return {
        "edu_mode": settings.pico_edu_mode,
        "edu_base_configured": bool(settings.pico_edu_base_url),
        "edu_issuer_configured": bool(
            settings.pico_edu_iss
            and (settings.pico_edu_jwt_secret or settings.pico_edu_jwt_public_key_pem)
        ),
        "auth_issuer_mode": settings.auth_issuer_mode,
        "accept_test_issuer": settings.pico_accept_test_issuer,
        "handoff_enabled": settings.pico_edu_handoff_enabled,
        "hook_token_configured": bool(settings.pico_hook_service_token),
    }
