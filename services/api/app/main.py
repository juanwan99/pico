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
from fastapi.responses import HTMLResponse, JSONResponse, Response
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
from app.edu_files import router as edu_files_router
from app.edu_kb_ingest import router as edu_kb_ingest_router
from app.edu_school import router as edu_school_router
from app.edu_sso import router as edu_sso_router
from app.kb_rebuild import rebuild_materials
from app.my_files import router as my_files_router
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
        "DEEPSEEK_BASE_URL": s.deepseek_base_url,
        "DEEPSEEK_MODEL": s.deepseek_model,
        "PICO_MODEL_PROVIDER": s.pico_model_provider,
        "PICO_EDU_MODE": s.pico_edu_mode,
        "PICO_EDU_BASE_URL": s.pico_edu_base_url,
        "PICO_EDU_SERVICE_TOKEN": s.pico_edu_service_token,
        "PICO_EDU_TIMEOUT_SECONDS": str(s.pico_edu_timeout_seconds),
        "PICO_EDU_HANDOFF_ENABLED": "true" if s.pico_edu_handoff_enabled else "false",
        "PICO_SANDBOX_URL": s.pico_sandbox_url,
        "PICO_SANDBOX_TOKEN": s.pico_sandbox_token,
        "PICO_MEILI_URL": s.pico_meili_url,
        "MEILI_MASTER_KEY": s.meili_master_key,
        "SILICONFLOW_API_KEY": s.siliconflow_api_key,
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
        # B1 soft drain: give in-process owners a short window before hard kill
        # (docker stop_grace_period must be ≥ this). Then reconcile leftovers.
        drain = await run_service.drain_inflight_runs(timeout_s=45.0)
        try:
            async with factory() as session:
                recon = await run_service.reconcile_orphaned_runs(session)
        except Exception as exc:  # noqa: BLE001 — shutdown must not block process exit
            recon = {"error": 1, "type": type(exc).__name__}
        # Structured one-liner for deploy logs (no secrets).
        print(
            f"[pico] shutdown drain waited={drain.get('waited')} "
            f"remaining={drain.get('remaining')} recon={recon}",
            flush=True,
        )


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
app.include_router(edu_files_router)
app.include_router(edu_kb_ingest_router)
app.include_router(edu_sso_router)
app.include_router(edu_school_router)
app.include_router(my_files_router)


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


def _resolve_default_runtime(settings: Settings) -> str | None:
    """Honest multi-step default label (true-Pi when enabled, else hosted)."""
    if not settings.pico_pi_agent_runtime:
        return "kimi-agent" if settings.legacy_kimi_enabled else None
    try:
        from pico_orchestrator.true_pi.config import default_runtime_for_health

        return default_runtime_for_health()
    except Exception:  # noqa: BLE001
        return "pi-agent"



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
    pi_canary = settings.pi_agent_canary_membership_count
    pi_batch = (settings.pico_pi_agent_canary_batch or "").strip()
    kimi_canary = settings.kimi_agent_canary_membership_count
    kimi_batch = (settings.pico_kimi_agent_canary_batch or "").strip()
    body: dict = {
        "ok": True,
        "service": "pico-api",
        "git_sha": _resolve_git_sha(),
        "edu_mode": settings.pico_edu_mode,
        # Product default multi-step kernel (HANDOFF-WB-PI / true-Pi phase-2)
        "default_runtime": _resolve_default_runtime(settings),
        "pi_agent_runtime_enabled": settings.pico_pi_agent_runtime,
        "pi_agent_scope": settings.pi_agent_scope,
        "pi_agent_canary_configured": pi_canary > 0,
        "pi_agent_canary_membership_count": pi_canary,
        # Legacy Kimi fields (rollback observability; not product default)
        "kimi_agent_runtime_enabled": settings.legacy_kimi_enabled,
        "kimi_agent_scope": settings.kimi_agent_scope,
        "kimi_agent_canary_configured": kimi_canary > 0,
        "kimi_agent_canary_membership_count": kimi_canary,
        # KA-4 HARD: transitional self-built loop remains unavailable
        "legacy_loop_unavailable": True,
        "rate_limit": {
            "chat_rpm": settings.pico_chat_rpm,
            "chat_max_concurrent": settings.pico_chat_max_concurrent,
            "key_scope": "membership_or_ip",
        },
    }
    # P2 MCP allowlist observability (tool names only — no secrets)
    from pico_orchestrator.mcp_bridge import mcp_health_fields

    body.update(mcp_health_fields(settings.pico_mcp_allowlist))
    # True-Pi observability (shadow / canary / default / rollback flags).
    from pico_orchestrator.true_pi.config import health_fields as true_pi_health_fields

    body.update(true_pi_health_fields())
    from pico_orchestrator.meili_kb import health_fields as meili_health_fields

    body.update(meili_health_fields())
    if pi_batch:
        body["pi_agent_canary_batch"] = pi_batch
    if kimi_batch:
        body["kimi_agent_canary_batch"] = kimi_batch
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


@app.get("/v1/meta/tip")
async def meta_tip() -> dict:
    """Minimal public tip probe — full 40-char git_sha only (G4).

    Product UI exposes the same shape at GET /api/pico/tip (no JWT).
    See docs/TIP-PROBE.md.
    """
    return {
        "ok": True,
        "service": "pico-api",
        "git_sha": _resolve_git_sha(),
    }


def _ops_reindex_peer_allowed(host: str) -> bool:
    """pico-api binds 127.0.0.1 only; host-network hairpin may present eth0, not 127.0.0.1."""
    peer = (host or "").strip().lower()
    if peer in {"127.0.0.1", "::1", "localhost"}:
        return True
    try:
        import ipaddress

        ip = ipaddress.ip_address(peer)
    except ValueError:
        return False
    # Reachable peers are already local to the loopback bind; allow RFC1918 / link-local / loopback.
    return bool(ip.is_loopback or ip.is_private or ip.is_link_local)


@app.post("/v1/kb/reindex")
async def kb_reindex(
    principal: Principal = Depends(require_any_scope("ai:run", "ai:read")),
) -> dict:
    """Rebuild this membership's Meili projection from the ledger."""
    return await rebuild_materials(principal)


@app.post("/v1/kb/reindex-all")
async def kb_reindex_all(request: Request) -> dict:
    """Ops rebuild. pico-api is loopback-bound; peer may be eth0 under host-network hairpin."""
    host = request.client.host if request.client else ""
    if not _ops_reindex_peer_allowed(host):
        raise HTTPException(status_code=403, detail={"code": "forbidden", "message": "loopback only"})
    return await rebuild_materials(None)


@app.get("/v1/meta/freeze")
async def freeze_meta(settings: Settings = Depends(get_settings)) -> dict:
    from pico_orchestrator.pins import AGENT_PINS, installed_versions
    from pico_orchestrator.provider import resolve_provider

    cfg = resolve_provider()
    return {
        "plan": "MVP-3DAY v1.2 FIXED",
        "agent_pins": AGENT_PINS,
        "installed": installed_versions(),
        "spend_caps": settings.spend_caps_dict(),
        "dangerous_tools_enabled_setting": settings.pico_dangerous_tools_enabled,
        "model_ready": cfg is not None,
        "model_provider": cfg.name if cfg else None,
        "model_name": cfg.model if cfg else None,
    }


@app.get("/v1/meta/agent-safety")
async def agent_safety(settings: Settings = Depends(get_settings)) -> dict:
    """Prove dangerous tools are off for default agent file (and legacy Kimi yaml if present).

    Pi default path uses Pico allowlist tools only (no host shell / unrestricted crawl).
    Legacy Kimi yaml is still checked when the file exists.
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
    paths: list[Path] = [agent_path]
    # Only enforce Kimi yaml when legacy path enabled or file coexists for safety proof.
    if settings.legacy_kimi_enabled and kimi_path.is_file() and kimi_path.resolve() != agent_path.resolve() or kimi_path.is_file() and kimi_path.resolve() != agent_path.resolve():
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


# ----- usage ledger (statistics only — no billing) -----


def _usage_html(principal: Principal, summary: dict, events: list[dict]) -> str:
    import html as html_lib

    rows = []
    for ev in events:
        tok = (
            "unknown"
            if ev.get("tokens_unknown")
            else str(ev.get("total_tokens") if ev.get("total_tokens") is not None else "—")
        )
        if ev.get("estimated") and tok != "unknown":
            tok = f"{tok} (est.)"
        rows.append(
            "<tr>"
            f"<td>{html_lib.escape(str(ev.get('created_at') or ''))}</td>"
            f"<td>{html_lib.escape(str(ev.get('kind') or ''))}</td>"
            f"<td>{html_lib.escape(str(ev.get('model') or '—'))}</td>"
            f"<td>{html_lib.escape(tok)}</td>"
            f"<td>{html_lib.escape(str(ev.get('run_id') or '—'))}</td>"
            "</tr>"
        )
    body_rows = "\n".join(rows) or (
        "<tr><td colspan='5'>暂无用量记录（空态诚实）</td></tr>"
    )
    day_bits = []
    for d in summary.get("days") or []:
        day_bits.append(
            f"<li>{html_lib.escape(str(d.get('day')))} · {html_lib.escape(str(d.get('kind')))} · "
            f"{int(d.get('event_count') or 0)} 次 · tokens="
            f"{html_lib.escape(str(d.get('total_tokens') if d.get('total_tokens') is not None else 'unknown'))}"
            f"</li>"
        )
    days_html = "\n".join(day_bits) or "<li>暂无汇总</li>"
    school = html_lib.escape(principal.school_id)
    member = html_lib.escape(principal.membership_id)
    return f"""<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><title>我的用量</title>
<style>
body {{ font-family: sans-serif; margin: 1.5rem; color: #111; }}
table {{ border-collapse: collapse; width: 100%; }}
th, td {{ border: 1px solid #ccc; padding: 0.4rem 0.6rem; text-align: left; }}
.note {{ color: #555; }}
</style></head><body>
<h1>我的用量</h1>
<p class="note">统计/管理 · <strong>不做钱</strong>（无价格、无扣款）。账号 {school} / {member}</p>
<h2>按日汇总</h2>
<ul>{days_html}</ul>
<h2>明细</h2>
<table>
<thead><tr><th>时间</th><th>kind</th><th>模型</th><th>tokens</th><th>run</th></tr></thead>
<tbody>
{body_rows}
</tbody>
</table>
</body></html>
"""


@app.get("/v1/usage/summary")
async def usage_summary(
    kind: str | None = None,
    day: str | None = None,
    membership_id: str | None = None,
    principal: Principal = Depends(require_scope("ai:read")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    from app.usage_ledger import summarize_usage

    return await summarize_usage(
        session, principal, kind=kind, day=day, membership_id=membership_id
    )


@app.get("/v1/usage/events")
async def usage_events(
    kind: str | None = None,
    day: str | None = None,
    membership_id: str | None = None,
    limit: int = 50,
    offset: int = 0,
    principal: Principal = Depends(require_scope("ai:read")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    from app.usage_ledger import list_usage_events, usage_event_dict

    rows = await list_usage_events(
        session,
        principal,
        kind=kind,
        day=day,
        membership_id=membership_id,
        limit=limit,
        offset=offset,
    )
    return {
        "billing": False,
        "school_id": principal.school_id,
        "events": [usage_event_dict(r) for r in rows],
    }


@app.get("/v1/usage/events/{event_id}")
async def usage_event_detail(
    event_id: str,
    principal: Principal = Depends(require_scope("ai:read")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    from app.usage_ledger import get_usage_event_for_principal, usage_event_dict

    row = await get_usage_event_for_principal(session, event_id, principal)
    if row is None:
        raise HTTPException(status_code=404, detail="usage event not found")
    return {"billing": False, "event": usage_event_dict(row)}


@app.get("/v1/usage")
async def my_usage_page(
    principal: Principal = Depends(require_scope("ai:read")),
    session: AsyncSession = Depends(get_session),
) -> HTMLResponse:
    from app.usage_ledger import list_usage_events, summarize_usage, usage_event_dict

    summary = await summarize_usage(session, principal)
    rows = await list_usage_events(session, principal, limit=50, offset=0)
    html = _usage_html(principal, summary, [usage_event_dict(r) for r in rows])
    return HTMLResponse(html)


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
    from pico_orchestrator.usage_hook import bind_usage_context, reset_usage_context

    token = bind_usage_context(
        school_id=principal.school_id,
        membership_id=principal.membership_id,
    )
    try:
        result = await gw.invoke(principal, body.name, dict(body.arguments))
    except ToolError as e:
        code = 403 if e.code == "tenant.cross_school" else 400
        raise HTTPException(
            status_code=code, detail={"code": e.code, "message": e.message}
        ) from e
    finally:
        reset_usage_context(token)
    return {"ok": True, "result": result}


class OpenSandboxSessionRequest(BaseModel):
    url: str | None = Field(default=None, max_length=2048)
    artifact_id: str | None = Field(default=None, max_length=128)
    filename: str | None = Field(default=None, max_length=512)
    kind: str | None = Field(default=None, max_length=32)
    body: str | None = Field(default=None, max_length=50_000)


@app.post("/v1/sandbox/sessions")
async def open_sandbox_session(
    body: OpenSandboxSessionRequest,
    principal: Principal = Depends(require_scope("ai:run")),
) -> dict:
    """Teacher/result-pane open: browser URL or LibreOffice document. Same sidecar."""
    from pico_orchestrator.gateway import ToolError
    from pico_orchestrator.tools_builtin import build_default_gateway
    from pico_orchestrator.usage_hook import bind_usage_context, reset_usage_context

    from app.artifact_store import LedgerArtifactStore
    from app.db import session_factory

    gw = build_default_gateway(LedgerArtifactStore(session_factory()))
    token = bind_usage_context(
        school_id=principal.school_id,
        membership_id=principal.membership_id,
    )
    url = (body.url or "").strip()
    kind = (body.kind or "").strip().lower()
    artifact_id = (body.artifact_id or "").strip()
    filename = (body.filename or "").strip()
    try:
        if url and not artifact_id and kind in {"", "browser"}:
            result = await gw.invoke(principal, "sandbox_browser_open", {"url": url})
        else:
            result = await gw.invoke(
                principal,
                "sandbox_document_open",
                {
                    "artifact_id": artifact_id or None,
                    "filename": filename or None,
                    "kind": kind or "writer",
                    "body": body.body,
                },
            )
    except ToolError as e:
        if e.code == "tenant.cross_school" or e.code == "sandbox.forbidden":
            code = 403
        elif e.code == "sandbox.quota":
            code = 429
        elif e.code in {"sandbox.session_not_found", "sandbox.file_not_found"}:
            code = 404
        else:
            code = 400
        raise HTTPException(
            status_code=code, detail={"code": e.code, "message": e.message}
        ) from e
    finally:
        reset_usage_context(token)
    if not isinstance(result, dict):
        raise HTTPException(status_code=502, detail={"code": "sandbox.unavailable"})
    session_id = str(result.get("session_id") or "")
    return _sandbox_public_meta(session_id, result)


# ----- sandbox B2 human-in-the-loop view (sidecar; not LibreChat) -----


def _sandbox_public_meta(session_id: str, meta: dict) -> dict:
    from pico_orchestrator.sandbox_session_event import sandbox_session_payload

    payload = sandbox_session_payload({**meta, "session_id": session_id}) or {
        "session_id": session_id,
        "url": str(meta.get("url") or ""),
        "title": str(meta.get("title") or ""),
        "view_path": f"/v1/sandbox/sessions/{session_id}/view",
        "human_copy": str(meta.get("human_copy") or ""),
        "engine": str(meta.get("engine") or ""),
        "workspace_id": str(meta.get("workspace_id") or ""),
    }
    return {"ok": True, **payload}


@app.get("/v1/sandbox/sessions/{session_id}")
async def sandbox_session_meta(
    session_id: str,
    principal: Principal = Depends(require_scope("ai:read")),
) -> JSONResponse:
    from pico_orchestrator.gateway import ToolError
    from pico_orchestrator.sandbox_sidecar import sidecar_json

    try:
        meta = await sidecar_json(
            "GET",
            f"/v1/internal/sessions/{session_id}",
            params={
                "school_id": principal.school_id,
                "membership_id": principal.membership_id,
            },
        )
    except ToolError as exc:
        if exc.code == "sandbox.forbidden":
            status = 403
        elif exc.code == "sandbox.session_not_found":
            status = 404
        else:
            status = 400
        raise HTTPException(
            status_code=status, detail={"code": exc.code, "message": exc.message}
        ) from exc
    if not isinstance(meta, dict):
        raise HTTPException(status_code=502, detail={"code": "sandbox.unavailable"})
    return JSONResponse(
        content=_sandbox_public_meta(session_id, meta),
        headers={"Cache-Control": "no-store"},
    )


@app.get("/v1/sandbox/sessions/{session_id}/view")
async def sandbox_session_view(
    session_id: str,
    principal: Principal = Depends(require_scope("ai:read")),
) -> HTMLResponse:
    from pico_orchestrator.gateway import ToolError
    from pico_orchestrator.sandbox_sidecar import sidecar_json
    from pico_orchestrator.sandbox_view import render_session_view_html

    try:
        meta = await sidecar_json(
            "GET",
            f"/v1/internal/sessions/{session_id}",
            params={
                "school_id": principal.school_id,
                "membership_id": principal.membership_id,
            },
        )
    except ToolError as exc:
        if exc.code == "sandbox.forbidden":
            status = 403
        elif exc.code == "sandbox.session_not_found":
            status = 404
        else:
            status = 400
        raise HTTPException(
            status_code=status, detail={"code": exc.code, "message": exc.message}
        ) from exc
    if not isinstance(meta, dict):
        raise HTTPException(status_code=502, detail={"code": "sandbox.unavailable"})
    html = render_session_view_html(
        session_id=session_id,
        screenshot_path=f"/v1/sandbox/sessions/{session_id}/screenshot",
        page_url=str(meta.get("url") or ""),
        workspace_id=str(meta.get("workspace_id") or ""),
        input_path=f"/v1/sandbox/sessions/{session_id}/input",
    )
    return HTMLResponse(
        content=html,
        headers={"Cache-Control": "no-store", "X-Pico-Sandbox-Human": "b2"},
    )


@app.get("/v1/sandbox/sessions/{session_id}/screenshot")
async def sandbox_session_screenshot(
    session_id: str,
    principal: Principal = Depends(require_scope("ai:read")),
) -> Response:
    from pico_orchestrator.gateway import ToolError
    from pico_orchestrator.sandbox_sidecar import sidecar_json

    try:
        png = await sidecar_json(
            "GET",
            f"/v1/internal/sessions/{session_id}/png",
            params={
                "school_id": principal.school_id,
                "membership_id": principal.membership_id,
            },
        )
    except ToolError as exc:
        if exc.code == "sandbox.forbidden":
            status = 403
        elif exc.code == "sandbox.session_not_found":
            status = 404
        else:
            status = 400
        raise HTTPException(
            status_code=status, detail={"code": exc.code, "message": exc.message}
        ) from exc
    if not isinstance(png, (bytes, bytearray)) or not bytes(png).startswith(b"\x89PNG"):
        raise HTTPException(status_code=502, detail={"code": "sandbox.unavailable"})
    return Response(
        content=bytes(png),
        media_type="image/png",
        headers={"Cache-Control": "no-store"},
    )


@app.post("/v1/sandbox/sessions/{session_id}/focus")
async def sandbox_session_focus(
    session_id: str,
    request: Request,
    principal: Principal = Depends(require_scope("ai:read")),
) -> JSONResponse:
    from pico_orchestrator.gateway import ToolError
    from pico_orchestrator.sandbox_sidecar import sidecar_json

    window_id = ""
    kind = ""
    try:
        body = await request.json()
    except ValueError:
        body = {}
    if isinstance(body, dict):
        window_id = str(body.get("window_id") or "")
        kind = str(body.get("kind") or "")
    try:
        meta = await sidecar_json(
            "POST",
            f"/v1/internal/sessions/{session_id}/focus",
            json_body={
                "school_id": principal.school_id,
                "membership_id": principal.membership_id,
                "window_id": window_id,
                "kind": kind,
            },
        )
    except ToolError as exc:
        status = 404 if exc.code == "sandbox.session_not_found" else 400
        raise HTTPException(
            status_code=status, detail={"code": exc.code, "message": exc.message}
        ) from exc
    if not isinstance(meta, dict):
        raise HTTPException(status_code=502, detail={"code": "sandbox.unavailable"})
    return JSONResponse(
        content=_sandbox_public_meta(session_id, meta),
        headers={"Cache-Control": "no-store"},
    )


@app.post("/v1/sandbox/sessions/{session_id}/input")
async def sandbox_session_input(
    session_id: str,
    request: Request,
    principal: Principal = Depends(require_scope("ai:read")),
) -> Response:
    """Forward click/type into the isolated browser. Never log the body."""
    from pico_orchestrator.gateway import ToolError
    from pico_orchestrator.sandbox_sidecar import sidecar_json

    ctype = (request.headers.get("content-type") or "").lower()
    click_x = click_y = None
    text = None
    password = False
    try:
        if "application/json" in ctype:
            body = await request.json()
            if not isinstance(body, dict):
                body = {}
            click_x = body.get("click_x")
            click_y = body.get("click_y")
            secret = body.get("secret") or body.get("password")
            visible = body.get("text")
            if secret:
                text = str(secret)
                password = True
            elif visible:
                text = str(visible)
        else:
            form = await request.form()
            cx = form.get("click_x")
            cy = form.get("click_y")
            click_x = int(str(cx)) if cx not in {None, ""} else None
            click_y = int(str(cy)) if cy not in {None, ""} else None
            secret = form.get("secret")
            visible = form.get("text")
            if secret:
                text = str(secret)
                password = True
            elif visible:
                text = str(visible)
    except Exception as exc:
        raise HTTPException(
            status_code=400,
            detail={"code": "tool.invalid_arguments", "message": "无法读取画面输入"},
        ) from exc
    try:
        applied = await sidecar_json(
            "POST",
            f"/v1/internal/sessions/{session_id}/input",
            json_body={
                "school_id": principal.school_id,
                "membership_id": principal.membership_id,
                "click_x": click_x,
                "click_y": click_y,
                "text": text,
                "password": password,
                "field": "password" if password else "input",
            },
        )
    except ToolError as exc:
        status = 404 if exc.code == "sandbox.session_not_found" else 400
        raise HTTPException(
            status_code=status, detail={"code": exc.code, "message": exc.message}
        ) from exc
    accept = (request.headers.get("accept") or "").lower()
    if "application/json" in ctype or "application/json" in accept:
        meta = applied if isinstance(applied, dict) else {}
        body = _sandbox_public_meta(session_id, meta)
        body["clicked"] = bool(meta.get("clicked"))
        body["typed"] = bool(meta.get("typed"))
        return JSONResponse(content=body, headers={"Cache-Control": "no-store"})
    return HTMLResponse(
        status_code=303,
        headers={"Location": f"/v1/sandbox/sessions/{session_id}/view"},
        content="",
    )


@app.delete("/v1/sandbox/sessions/{session_id}")
async def destroy_sandbox_session(
    session_id: str,
    principal: Principal = Depends(require_scope("ai:run")),
) -> dict:
    """Close Chromium/LibreOffice. Owner disk stays."""
    from pico_orchestrator.gateway import ToolError
    from pico_orchestrator.sandbox_persist import PERSIST_COPY
    from pico_orchestrator.sandbox_sidecar import sidecar_json

    try:
        out = await sidecar_json(
            "POST",
            f"/v1/internal/sessions/{session_id}/destroy",
            json_body={
                "school_id": principal.school_id,
                "membership_id": principal.membership_id,
            },
            params={
                "school_id": principal.school_id,
                "membership_id": principal.membership_id,
            },
        )
    except ToolError as exc:
        if exc.code == "sandbox.forbidden":
            status = 403
        elif exc.code == "sandbox.session_not_found":
            status = 404
        else:
            status = 400
        raise HTTPException(
            status_code=status, detail={"code": exc.code, "message": exc.message}
        ) from exc
    if not isinstance(out, dict):
        out = {}
    return {
        "ok": True,
        "destroyed": True,
        "session_id": session_id,
        "persist": True,
        "human_copy": str(out.get("human_copy") or PERSIST_COPY),
    }


@app.get("/v1/sandbox/disk")
async def get_sandbox_disk(
    principal: Principal = Depends(require_scope("ai:read")),
) -> dict:
    from pico_orchestrator.gateway import ToolError
    from pico_orchestrator.sandbox_sidecar import sidecar_json

    try:
        out = await sidecar_json(
            "GET",
            "/v1/internal/disk",
            params={
                "school_id": principal.school_id,
                "membership_id": principal.membership_id,
            },
        )
    except ToolError as exc:
        raise HTTPException(
            status_code=400, detail={"code": exc.code, "message": exc.message}
        ) from exc
    if not isinstance(out, dict):
        raise HTTPException(status_code=502, detail={"code": "sandbox.unavailable"})
    return out


class ClearSandboxDiskRequest(BaseModel):
    confirm: bool = False


@app.post("/v1/sandbox/disk/clear")
async def clear_sandbox_disk(
    body: ClearSandboxDiskRequest,
    principal: Principal = Depends(require_scope("ai:run")),
) -> dict:
    from pico_orchestrator.gateway import ToolError
    from pico_orchestrator.sandbox_sidecar import sidecar_json

    try:
        out = await sidecar_json(
            "POST",
            "/v1/internal/disk/clear",
            json_body={
                "school_id": principal.school_id,
                "membership_id": principal.membership_id,
                "confirm": bool(body.confirm),
            },
        )
    except ToolError as exc:
        raise HTTPException(
            status_code=400, detail={"code": exc.code, "message": exc.message}
        ) from exc
    if not isinstance(out, dict):
        raise HTTPException(status_code=502, detail={"code": "sandbox.unavailable"})
    return out


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
            # user_message: teacher list must not depend on client-side English mapping alone.
            from pico_orchestrator.user_errors import user_message_for_error

            user_msg = None
            if run.status == "failed" and run.error:
                user_msg = user_message_for_error(run.error)
            item["latest_run"] = {
                "id": run.id,
                "status": run.status,
                "cancel_requested": bool(run.cancel_requested),
                "model": run.model,
                "error": run.error,
                "user_message": user_msg,
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
                "user_label": a.title,
                "inline": inline_value,
                "run_id": a.run_id,
                "content_encoding": encoding,
                "byte_size": byte_size,
                "content_sha256": sha,
                "download_path": f"/v1/artifacts/{a.id}/content?download=true",
            }
        )
    return {
        "task": _task_dict(task),
        "artifacts": artifacts_out,
    }


@app.get("/v1/artifacts")
async def list_conversation_artifacts(
    conversation_id: str = "",
    mine: bool = False,
    folder_id: str | None = None,
    principal: Principal = Depends(require_scope("ai:read")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    if mine:
        arts = await run_service.list_artifacts_for_principal(
            session, principal, folder_id=folder_id
        )
    else:
        cid = str(conversation_id or "").strip()
        if not cid:
            raise HTTPException(status_code=400, detail={"code": "conversation_required", "message": "conversation_id required"})
        arts = await run_service.list_artifacts_for_conversation(session, principal, cid)
    return {
        "count": len(arts),
        "artifacts": [
            {
                "id": a.id,
                "title": a.title,
                "kind": a.kind,
                "folder_id": getattr(a, "folder_id", "") or "",
                "created_at": a.created_at.isoformat() if a.created_at else None,
                "download_path": f"/v1/artifacts/{a.id}/content?download=true",
            }
            for a in arts
        ],
    }


@app.delete("/v1/artifacts")
async def clear_conversation_artifacts(
    conversation_id: str = "",
    principal: Principal = Depends(require_scope("ai:run")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    cid = str(conversation_id or "").strip()
    if not cid:
        raise HTTPException(status_code=400, detail={"code": "conversation_required", "message": "conversation_id required"})
    deleted = await run_service.delete_artifacts_for_conversation(session, principal, cid)
    return {"ok": True, "deleted": deleted}


@app.get("/v1/artifacts/{artifact_id}/content")
async def get_artifact_content(
    artifact_id: str,
    download: bool = False,
    preview: bool = False,
    exp: int | None = None,
    sig: str | None = None,
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

    # Security: non-download HTML must not be navigable as active content via API
    # unless this is an owner preview (?preview=1) with CSP sandbox.
    # Owner isolation already applied by get_artifact_for_principal (other accounts 404).
    extra_headers: dict[str, str] = {}
    if ext in {".html", ".htm"} and not download:
        if preview:
            if sig:
                from pico_orchestrator.sandbox_s1 import verify_preview_sig

                err = verify_preview_sig(
                    artifact_id=artifact.id,
                    school_id=principal.school_id,
                    membership_id=principal.membership_id,
                    run_id=getattr(artifact, "run_id", None),
                    exp=int(exp or 0),
                    sig=sig,
                )
                if err:
                    raise HTTPException(
                        status_code=404,
                        detail={"code": err, "message": "预览无效或已过期"},
                    )
            media_type = "text/html; charset=utf-8"
            extra_headers["Content-Security-Policy"] = (
                "default-src 'none'; img-src data:; style-src 'unsafe-inline'; "
                "script-src 'unsafe-inline'; base-uri 'none'; form-action 'none'; "
                "frame-ancestors 'none'; sandbox allow-scripts"
            )
        else:
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
            **extra_headers,
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


class DurableJobRequest(BaseModel):
    """Start a server-owned staged durable job (package B)."""

    wall_seconds: int = Field(default=1800, ge=5, le=3600)
    stages: int | None = Field(default=None, ge=2, le=120)
    title: str | None = None
    conversation_id: str | None = None


@app.post("/v1/durable-jobs")
async def create_durable_job(
    body: DurableJobRequest,
    principal: Principal = Depends(require_scope("ai:run")),
) -> dict:
    """Create a durable staged job that continues after client disconnect.

    Gold path: wall_seconds>=1800 with checkpoints. Not a substitute for HA.
    """
    from app.durable_job import start_durable_job

    try:
        info = await start_durable_job(
            principal=principal,
            wall_seconds=body.wall_seconds,
            stages=body.stages,
            title=body.title,
            conversation_id=body.conversation_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"job": info, "policy": "detach_on_disconnect_default"}


@app.post("/v1/runs/{run_id}/continue-durable")
async def continue_durable_run(
    run_id: str,
    principal: Principal = Depends(require_scope("ai:run")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Continue a terminal durable_job from its last checkpoint stage."""
    from app.durable_job import start_durable_job

    source = await run_service.get_run_for_principal(session, run_id, principal)
    if not source:
        raise HTTPException(status_code=404, detail="run not found")
    try:
        info = await start_durable_job(
            principal=principal,
            wall_seconds=1800,
            resume_from_run_id=source.id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {"job": info, "continued_from_run_id": source.id}


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
