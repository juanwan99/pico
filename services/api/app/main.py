"""Pico API — D1 scaffold (health, test token, safety proof, model hello)."""

from __future__ import annotations

import sys
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

# Allow importing orchestrator package when running from repo root / app-dir
_ROOT = Path(__file__).resolve().parents[3]
_ORCH = _ROOT / "services" / "orchestrator"
for p in (str(_ORCH),):
    if p not in sys.path:
        sys.path.insert(0, p)

from app.auth import Principal, issue_test_token, require_principal
from app.settings import Settings, get_settings

app = FastAPI(title="Pico API", version="0.1.0", description="Phase 1 MVP control plane")

_settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=_settings.cors_origin_list or ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class TokenRequest(BaseModel):
    school_id: str = Field(examples=["school-a"])
    membership_id: str = Field(examples=["member-1"])
    scopes: list[str] = Field(default_factory=lambda: ["ai:run", "ai:read"])


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    claims_shape: dict


@app.get("/health")
async def health() -> dict:
    return {"ok": True, "service": "pico-api", "phase": "1-d1"}


@app.get("/v1/meta/freeze")
async def freeze_meta(settings: Settings = Depends(get_settings)) -> dict:
    from pico_orchestrator.pins import AGENT_PINS, installed_versions

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
    }


@app.get("/v1/meta/agent-safety")
async def agent_safety(settings: Settings = Depends(get_settings)) -> dict:
    from pico_orchestrator.safety import assert_dangerous_tools_off

    agent_path = Path(settings.pico_agent_file)
    if not agent_path.is_absolute():
        agent_path = _ROOT / agent_path
    if settings.pico_dangerous_tools_enabled:
        raise HTTPException(
            status_code=500,
            detail="PICO_DANGEROUS_TOOLS_ENABLED must be false",
        )
    try:
        proof = assert_dangerous_tools_off(agent_path)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e
    return {"ok": True, "proof": proof}


@app.post("/v1/dev/token", response_model=TokenResponse)
async def dev_token(
    body: TokenRequest, settings: Settings = Depends(get_settings)
) -> TokenResponse:
    """Phase 1 test issuer — claim shape matches future edu issuance."""
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
async def me(principal: Principal = Depends(require_principal)) -> dict:
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
    principal: Principal = Depends(require_principal),
    settings: Settings = Depends(get_settings),
) -> dict:
    """Real model API smoke (S1). Fails honestly if no key — never mock-pass."""
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


@app.get("/v1/tools")
async def list_tools(principal: Principal = Depends(require_principal)) -> dict:
    from pico_orchestrator.tools_builtin import build_default_gateway

    gw = build_default_gateway()
    return {"tools": gw.list_tools(), "school_id": principal.school_id}


class ToolInvokeRequest(BaseModel):
    name: str
    arguments: dict = Field(default_factory=dict)


@app.post("/v1/tools/invoke")
async def invoke_tool(
    body: ToolInvokeRequest,
    principal: Principal = Depends(require_principal),
) -> dict:
    from pico_orchestrator.gateway import ToolError
    from pico_orchestrator.tools_builtin import build_default_gateway

    gw = build_default_gateway()
    try:
        result = await gw.invoke(principal, body.name, dict(body.arguments))
    except ToolError as e:
        code = 403 if e.code == "tenant.cross_school" else 400
        raise HTTPException(
            status_code=code, detail={"code": e.code, "message": e.message}
        ) from e
    return {"ok": True, "result": result}
