"""「我的接口」(pico#1331): teacher's own OpenAI-compatible model endpoint.

Only the authenticated membership can read/write its own row — identity is
always ``Principal.school_id`` / ``Principal.membership_id`` from the
request, never a value the caller supplies. The key is Fernet-encrypted
(``PICO_ENDPOINT_SECRET``); this module never stores or logs a plaintext
key, and the API never returns more than ``sk-…`` + the last 4 characters.

Model switching for the turn itself lives in ``pico_orchestrator.provider``
(``personal_provider_scope`` contextvar); this module only owns storage,
the teacher-facing CRUD/test endpoints, and the lookup helper the chat
entry point calls.
"""

from __future__ import annotations

import base64
import hashlib
import logging
import os
import time
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import Principal, require_person
from app.db import UserModelEndpointRow, get_session, session_factory

logger = logging.getLogger(__name__)

router = APIRouter(tags=["model-endpoint"], dependencies=[Depends(require_person)])

ENDPOINT_SECRET_ENV = "PICO_ENDPOINT_SECRET"
_TEST_TIMEOUT_S = 10.0


# ---------------------------------------------------------------------------
# Crypto: Fernet keyed by PICO_ENDPOINT_SECRET. Never store plaintext.
# ---------------------------------------------------------------------------


def _fernet() -> Any | None:
    secret = os.environ.get(ENDPOINT_SECRET_ENV, "").strip()
    if not secret:
        return None
    from cryptography.fernet import Fernet

    key = base64.urlsafe_b64encode(hashlib.sha256(secret.encode("utf-8")).digest())
    return Fernet(key)


def secret_configured() -> bool:
    return bool(os.environ.get(ENDPOINT_SECRET_ENV, "").strip())


def encrypt_api_key(raw: str) -> str:
    """Raises RuntimeError when PICO_ENDPOINT_SECRET is unset.

    Callers must turn that into a clear teacher-facing error and must never
    fall back to storing the plaintext key (pico#1331 contract).
    """
    f = _fernet()
    if f is None:
        raise RuntimeError(f"{ENDPOINT_SECRET_ENV} not configured")
    return f.encrypt(raw.encode("utf-8")).decode("ascii")


def decrypt_api_key(enc: str) -> str:
    f = _fernet()
    if f is None:
        raise RuntimeError(f"{ENDPOINT_SECRET_ENV} not configured")
    return f.decrypt(enc.encode("ascii")).decode("utf-8")


def mask_key(raw: str) -> str:
    tail = raw[-4:] if len(raw) >= 4 else raw
    return f"sk-…{tail}"


# ---------------------------------------------------------------------------
# Storage helpers
# ---------------------------------------------------------------------------


async def _get_row(
    session: AsyncSession, principal: Principal
) -> UserModelEndpointRow | None:
    return await session.get(
        UserModelEndpointRow, (principal.school_id, principal.membership_id)
    )


def _row_payload(row: UserModelEndpointRow | None) -> dict[str, Any]:
    if row is None:
        return {
            "configured": False,
            "enabled": False,
            "base_url": "",
            "model": "",
            "masked_key": "",
            "updated_at": None,
        }
    masked = ""
    try:
        masked = mask_key(decrypt_api_key(row.api_key_enc)) if row.api_key_enc else ""
    except Exception:  # noqa: BLE001 — secret rotated/missing; never 500 the GET
        logger.warning("model_endpoint: could not decrypt key for masked display")
        masked = "sk-…????"
    return {
        "configured": True,
        "enabled": bool(row.enabled),
        "base_url": row.base_url,
        "model": row.model,
        "masked_key": masked,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


async def personal_provider_config_for(principal: Principal) -> Any | None:
    """``ProviderConfig`` for this membership's own endpoint, or None.

    None (→ school model, exactly as if nothing were ever saved) **only**
    when there is no row, it is disabled, or the DB/session itself is not
    reachable (e.g. not yet initialized — some unit tests call
    chat_completions directly without the app lifespan). That last branch
    is deliberately narrow: it is a lookup/environment failure, not a
    judgement about the saved row's content.

    An **enabled** row that cannot actually be used — incomplete fields,
    a base_url that is no longer safe (DNS can change after save; this
    re-checks the SSRF guard every turn, not only at PUT time), or a key
    that fails to decrypt (secret rotated) — raises a tagged
    ``RuntimeError`` instead (``user_errors.PERSONAL_ENDPOINT_ERROR_TAG``).
    The card forbids a silent fall back to the school model (and the Pico
    points that would imply) just because the teacher's own config broke;
    the turn must fail with a teacher-facing 「你的接口出错了：…」 instead.
    """
    from pico_orchestrator.gateway import ToolError
    from pico_orchestrator.provider import PERSONAL_PROVIDER_NAME, ProviderConfig
    from pico_orchestrator.user_errors import PERSONAL_ENDPOINT_ERROR_TAG
    from pico_orchestrator.web_guard import assert_public_http_url

    try:
        factory = session_factory()
        async with factory() as session:
            row = await _get_row(session, principal)
    except Exception:  # noqa: BLE001 — DB/session only; narrow on purpose
        logger.warning(
            "model_endpoint: lookup failed for %s/%s (DB not reachable) — turn falls back to school model",
            principal.school_id,
            principal.membership_id,
        )
        return None
    if row is None or not row.enabled:
        return None
    if not row.base_url or not row.model or not row.api_key_enc:
        logger.warning(
            "model_endpoint: enabled row for %s/%s is incomplete — failing the turn, not falling back",
            principal.school_id,
            principal.membership_id,
        )
        raise RuntimeError(f"{PERSONAL_ENDPOINT_ERROR_TAG}endpoint_config_incomplete")
    try:
        await assert_public_http_url(row.base_url)
    except ToolError as exc:
        logger.warning(
            "model_endpoint: base_url no longer safe at use time for %s/%s — failing the turn",
            principal.school_id,
            principal.membership_id,
        )
        raise RuntimeError(f"{PERSONAL_ENDPOINT_ERROR_TAG}{exc.message}") from exc
    try:
        api_key = decrypt_api_key(row.api_key_enc)
    except Exception as exc:
        logger.warning(
            "model_endpoint: decrypt failed for %s/%s — failing the turn, not falling back",
            principal.school_id,
            principal.membership_id,
        )
        raise RuntimeError(
            f"{PERSONAL_ENDPOINT_ERROR_TAG}endpoint_key_undecryptable"
        ) from exc
    return ProviderConfig(
        name=PERSONAL_PROVIDER_NAME,
        api_key=api_key,
        base_url=row.base_url,
        model=row.model,
    )


# ---------------------------------------------------------------------------
# SSRF guard (reuse the sandbox/web-fetch egress rule — pico#1331 contract)
# ---------------------------------------------------------------------------


async def _assert_endpoint_url_safe(base_url: str) -> None:
    from pico_orchestrator.gateway import ToolError
    from pico_orchestrator.web_guard import assert_public_http_url

    try:
        await assert_public_http_url(base_url)
    except ToolError as exc:
        raise HTTPException(
            status_code=400,
            detail={"code": "endpoint.denied", "message": exc.message},
        ) from exc


# ---------------------------------------------------------------------------
# Request bodies
# ---------------------------------------------------------------------------


class ModelEndpointBody(BaseModel):
    base_url: str = ""
    model: str = ""
    api_key: str = ""  # blank on PUT = keep the saved key
    enabled: bool = True


class ModelEndpointTestBody(BaseModel):
    base_url: str = ""
    model: str = ""
    api_key: str = ""  # blank = use the already-saved key


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.get("/v1/me/model-endpoint")
async def get_model_endpoint(
    principal: Principal = Depends(require_person),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    row = await _get_row(session, principal)
    return _row_payload(row)


@router.put("/v1/me/model-endpoint")
async def put_model_endpoint(
    body: ModelEndpointBody,
    principal: Principal = Depends(require_person),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    base_url = body.base_url.strip()
    model = body.model.strip()
    api_key = body.api_key.strip()
    if not base_url or not model:
        raise HTTPException(
            status_code=400,
            detail={"code": "endpoint.invalid", "message": "接口地址和模型名都要填"},
        )
    await _assert_endpoint_url_safe(base_url)

    row = await _get_row(session, principal)
    if api_key:
        try:
            api_key_enc = encrypt_api_key(api_key)
        except RuntimeError as exc:
            raise HTTPException(
                status_code=503,
                detail={
                    "code": "endpoint.secret_unconfigured",
                    "message": "服务器还没配好密钥保险箱，暂时不能保存，请告诉管理员",
                },
            ) from exc
    elif row is not None and row.api_key_enc:
        api_key_enc = row.api_key_enc  # unchanged: edit address/model, keep the key
    else:
        raise HTTPException(
            status_code=400,
            detail={"code": "endpoint.key_required", "message": "请填写密钥"},
        )

    if row is None:
        row = UserModelEndpointRow(
            school_id=principal.school_id,
            membership_id=principal.membership_id,
            base_url=base_url,
            model=model,
            api_key_enc=api_key_enc,
            enabled=1 if body.enabled else 0,
        )
        session.add(row)
    else:
        row.base_url = base_url
        row.model = model
        row.api_key_enc = api_key_enc
        row.enabled = 1 if body.enabled else 0
    await session.commit()
    return _row_payload(row)


@router.delete("/v1/me/model-endpoint")
async def delete_model_endpoint(
    principal: Principal = Depends(require_person),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    row = await _get_row(session, principal)
    if row is not None:
        await session.delete(row)
        await session.commit()
    return {"ok": True}


@router.post("/v1/me/model-endpoint/test")
async def test_model_endpoint(
    body: ModelEndpointTestBody,
    principal: Principal = Depends(require_person),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    base_url = body.base_url.strip()
    model = body.model.strip()
    api_key = body.api_key.strip()
    if not base_url or not api_key or not model:
        row = await _get_row(session, principal)
        if row is not None:
            base_url = base_url or row.base_url
            model = model or row.model
            if not api_key and row.api_key_enc:
                try:
                    api_key = decrypt_api_key(row.api_key_enc)
                except RuntimeError:
                    return {
                        "ok": False,
                        "reason": "服务器还没配好密钥保险箱，暂时不能测试",
                    }
    if not base_url or not model or not api_key:
        return {"ok": False, "reason": "接口地址、密钥、模型名都要填"}

    try:
        await _assert_endpoint_url_safe(base_url)
    except HTTPException as exc:
        detail = exc.detail if isinstance(exc.detail, dict) else {}
        return {"ok": False, "reason": str(detail.get("message") or "这个地址不能用")}

    return await _probe(base_url=base_url, api_key=api_key, model=model)


async def _probe(*, base_url: str, api_key: str, model: str) -> dict[str, Any]:
    from openai import AsyncOpenAI
    from pico_orchestrator.user_errors import personal_endpoint_reason

    client = AsyncOpenAI(
        api_key=api_key, base_url=base_url, timeout=_TEST_TIMEOUT_S, max_retries=0
    )
    started = time.monotonic()
    try:
        resp = await client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": "ping"}],
            max_tokens=4,
        )
    except Exception as exc:  # noqa: BLE001 — classify, never leak raw vendor text
        return {"ok": False, "reason": personal_endpoint_reason(str(exc))}
    latency_ms = int((time.monotonic() - started) * 1000)
    answered_model = str(getattr(resp, "model", "") or model)
    return {"ok": True, "model": answered_model, "latency_ms": latency_ms}
