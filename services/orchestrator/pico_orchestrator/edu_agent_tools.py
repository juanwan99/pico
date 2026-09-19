"""Thin HTTP adapter: edu catalog + run_pack as Pi tools.

Membership JWT only (same person). No service account. Etag cache is per-run.
500 catalog_budget_exceeded is passed through, never swallowed.
"""

from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
import jwt

from pico_orchestrator.gateway import Principal, ToolError, ToolSpec

CATALOG_FIND = "edu_catalog_find"
CATALOG_DESCRIBE = "edu_catalog_describe"
CATALOG_COMMAND = "edu_catalog_command"
RUN_PACK = "edu_run_pack"
EDU_AGENT_TOOLS: tuple[str, ...] = (
    CATALOG_FIND,
    CATALOG_DESCRIBE,
    CATALOG_COMMAND,
    RUN_PACK,
)

_ETAG_CACHE: dict[tuple[str, str, str], tuple[str, dict[str, Any]]] = {}


class EduHttpError(Exception):
    def __init__(self, status: int, code: str, message: str) -> None:
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message


def _edu_root() -> str:
    base = (os.environ.get("PICO_EDU_BASE_URL") or "").rstrip("/")
    if not base and (os.environ.get("PICO_ENV") or "").strip().lower() == "production":
        base = "https://edu.weiyuji.cn"
    if not base:
        return ""
    return base if base.endswith("/api") else f"{base}/api"


def _mint(principal: Principal, *, scopes: list[str]) -> str | None:
    iss = (os.environ.get("PICO_EDU_ISS") or "").strip()
    secret = (os.environ.get("PICO_EDU_JWT_SECRET") or "").strip()
    school = str(getattr(principal, "school_id", "") or "").strip()
    member = str(getattr(principal, "membership_id", "") or "").strip()
    if not iss or not secret or not school or not member:
        return None
    now = datetime.now(UTC)
    payload = {
        "iss": iss,
        "aud": "pico-api",
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(seconds=90)).timestamp()),
        "school_id": school,
        "membership_id": member,
        "scopes": scopes,
        "sub": f"{school}:{member}",
        "purpose": "edu-agent",
    }
    return jwt.encode(payload, secret, algorithm="HS256")


def _message_from(resp: httpx.Response) -> tuple[str, str]:
    try:
        data = resp.json()
    except ValueError:
        return "edu.error", "学校拒绝了这次调用"
    if not isinstance(data, dict):
        return "edu.error", "学校拒绝了这次调用"
    code = str(data.get("code") or "edu.error")
    message = str(data.get("error") or data.get("message") or "学校拒绝了这次调用")
    return code, message


async def edu_request(
    principal: Principal,
    method: str,
    path: str,
    *,
    params: dict[str, str] | None = None,
    body: dict[str, Any] | None = None,
    scopes: list[str] | None = None,
    timeout: float = 20,
) -> dict[str, Any]:
    root = _edu_root()
    token = _mint(principal, scopes=scopes or ["ai:read"])
    if not root or not token:
        raise ToolError("edu.unconfigured", "学校目录未接通（缺学校登录或 edu 基址）")
    url = f"{root}{path}"
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.request(
                method, url, params=params, json=body, headers=headers
            )
    except httpx.HTTPError as exc:
        raise ToolError("edu.unreachable", f"学校现在连不上（{exc}）") from exc
    if response.status_code >= 400:
        code, message = _message_from(response)
        if response.status_code >= 500:
            raise ToolError(code or "edu.error", message)
        raise ToolError(code or "edu.error", message)
    try:
        data = response.json()
    except ValueError as exc:
        raise ToolError("edu.contract_error", "学校返回不是 JSON") from exc
    if not isinstance(data, dict):
        raise ToolError("edu.contract_error", "学校返回不是对象")
    return data


def _cache_key(principal: Principal, kind: str, extra: str) -> tuple[str, str, str]:
    return (
        str(getattr(principal, "membership_id", "") or ""),
        kind,
        extra,
    )


async def catalog_find(principal: Principal, args: dict[str, Any]) -> dict[str, Any]:
    q = str(args.get("q") or args.get("intent") or "").strip()
    school = str(getattr(principal, "school_id", "") or "").strip()
    path = f"/v1/schools/{school}/agent/catalog/find" if school else "/v1/pico/membership/catalog/find"
    params = {"q": q} if q else {}
    if school:
        return await edu_request(principal, "GET", path, params=params)
    return await edu_request(principal, "GET", "/v1/pico/membership/catalog/find", params=params)


async def catalog_describe(principal: Principal, args: dict[str, Any]) -> dict[str, Any]:
    domain = str(args.get("domain") or "HOME").strip() or "HOME"
    school = str(getattr(principal, "school_id", "") or "").strip()
    path = (
        f"/v1/schools/{school}/agent/catalog/describe"
        if school
        else "/v1/pico/membership/catalog/describe"
    )
    key = _cache_key(principal, "describe", domain)
    cached = _ETAG_CACHE.get(key)
    if cached:
        return {**cached[1], "cache": "etag"}
    data = await edu_request(principal, "GET", path, params={"domain": domain})
    etag = str(data.get("etag") or "")
    _ETAG_CACHE[key] = (etag, data)
    return data


async def catalog_command(principal: Principal, args: dict[str, Any]) -> dict[str, Any]:
    cid = str(args.get("id") or args.get("command") or "").strip()
    school = str(getattr(principal, "school_id", "") or "").strip()
    path = (
        f"/v1/schools/{school}/agent/catalog/command"
        if school
        else "/v1/pico/membership/catalog/command"
    )
    return await edu_request(principal, "GET", path, params={"id": cid})


async def run_pack(principal: Principal, args: dict[str, Any]) -> dict[str, Any]:
    school = str(getattr(principal, "school_id", "") or "").strip()
    if not school:
        raise ToolError("edu.unconfigured", "没有学校登录，不能按票执行")
    grant_id = str(args.get("grant_id") or "").strip()
    steps = args.get("steps")
    if not grant_id or not isinstance(steps, list):
        raise ToolError("tool.invalid_arguments", "grant_id 和 steps 必填")
    path = f"/v1/schools/{school}/agent/run-packs"
    return await edu_request(
        principal,
        "POST",
        path,
        body={
            "grant_id": grant_id,
            "run_id": str(args.get("run_id") or "")[:80],
            "steps": steps,
        },
        scopes=["ai:read", "ai:delegate"],
        timeout=30,
    )


def register_edu_agent_tools(gateway: Any) -> None:
    gateway.register(
        ToolSpec(
            name=CATALOG_FIND,
            description=(
                "Ask the school workbench catalog what hands exist for an intent. "
                "Progressive: summaries only. Args: q."
            ),
            handler=catalog_find,
            school_scoped=True,
        )
    )
    gateway.register(
        ToolSpec(
            name=CATALOG_DESCRIBE,
            description=(
                "Describe one school domain (default HOME). Command names without "
                "parameter schemas. Args: domain?"
            ),
            handler=catalog_describe,
            school_scoped=True,
        )
    )
    gateway.register(
        ToolSpec(
            name=CATALOG_COMMAND,
            description="Fetch one school command contract including params_schema. Args: id.",
            handler=catalog_command,
            school_scoped=True,
        )
    )
    gateway.register(
        ToolSpec(
            name=RUN_PACK,
            description=(
                "Submit a school work pack under the teacher's grant. "
                "Drafts allowed; publish/submit will be rejected. "
                "Args: grant_id, steps, run_id?"
            ),
            handler=run_pack,
            school_scoped=True,
        )
    )


def catalog_command_id(raw: str) -> bool:
    aid = str(raw or "").strip()
    return bool(aid) and "." in aid and " " not in aid and len(aid) < 80
