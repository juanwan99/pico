"""Thin HTTP adapter: edu catalog + run_pack + read-only queries as Pi tools.

Membership JWT only (same person). No service account. Etag cache is per-run.
500 catalog_budget_exceeded is passed through, never swallowed.
"""

from __future__ import annotations

import os
import re
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
import jwt

from pico_orchestrator.gateway import Principal, ToolError, ToolSpec

CATALOG_FIND = "edu_catalog_find"
CATALOG_DESCRIBE = "edu_catalog_describe"
CATALOG_COMMAND = "edu_catalog_command"
RUN_PACK = "edu_run_pack"
STEWARD_CORPUS = "edu_steward_public_corpus"
QUERY_LIST = "edu_query_list"
QUERY_RUN = "edu_query"
# School /agent/catalog/* is teacher-session only. Pico membership JWT
# uses the existing /v1/pico/membership/catalog/* mouths (edu-core #1636).
MEMBERSHIP_CATALOG = "/v1/pico/membership/catalog"
# Read-only data as the teacher (edu-core #5140/#5147): the list is edu's
# registry, fetched live, so a query edu registers shows up without a Pico change.
MEMBERSHIP_QUERY = "/v1/pico/membership/query"
_QUERY_ID = re.compile(r"^[a-z]+(\.[a-z_]+)+$")
EDU_AGENT_TOOLS: tuple[str, ...] = (
    CATALOG_FIND,
    CATALOG_DESCRIBE,
    CATALOG_COMMAND,
    RUN_PACK,
    QUERY_LIST,
    QUERY_RUN,
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


def _mint_steward(school: str) -> str | None:
    iss = (os.environ.get("PICO_EDU_ISS") or "").strip()
    secret = (os.environ.get("PICO_EDU_JWT_SECRET") or "").strip()
    school_id = str(school or "").strip()
    if not iss or not secret or not school_id:
        return None
    now = datetime.now(UTC)
    payload = {
        "iss": iss,
        "aud": "pico-api",
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(seconds=90)).timestamp()),
        "school_id": school_id,
        "scopes": ["ai:steward-public"],
        "purpose": "steward-public",
        "sub": f"{school_id}:steward-public",
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
    params = {"q": q} if q else {}
    return await edu_request(principal, "GET", f"{MEMBERSHIP_CATALOG}/find", params=params)


async def catalog_describe(principal: Principal, args: dict[str, Any]) -> dict[str, Any]:
    domain = str(args.get("domain") or "HOME").strip() or "HOME"
    key = _cache_key(principal, "describe", domain)
    cached = _ETAG_CACHE.get(key)
    if cached:
        return {**cached[1], "cache": "etag"}
    data = await edu_request(
        principal, "GET", f"{MEMBERSHIP_CATALOG}/describe", params={"domain": domain}
    )
    etag = str(data.get("etag") or "")
    _ETAG_CACHE[key] = (etag, data)
    return data


async def catalog_command(principal: Principal, args: dict[str, Any]) -> dict[str, Any]:
    cid = str(args.get("id") or args.get("command") or "").strip()
    return await edu_request(
        principal, "GET", f"{MEMBERSHIP_CATALOG}/command", params={"id": cid}
    )


async def query_list(principal: Principal, args: dict[str, Any]) -> dict[str, Any]:
    del args
    return await edu_request(principal, "GET", MEMBERSHIP_QUERY)


async def query_run(principal: Principal, args: dict[str, Any]) -> dict[str, Any]:
    qid = str(args.get("id") or "").strip()
    if not _QUERY_ID.match(qid):
        raise ToolError("tool.invalid_arguments", "id 必填，取 edu_query_list 里的 id")
    params = args.get("params")
    if params is None:
        # Models sometimes flatten params next to id; edu keeps only registered keys.
        params = {k: v for k, v in args.items() if k not in ("id", "params")}
    if not isinstance(params, dict):
        raise ToolError("tool.invalid_arguments", "params 要是对象")
    return await edu_request(principal, "POST", f"{MEMBERSHIP_QUERY}/{qid}", body=params)


async def run_pack(principal: Principal, args: dict[str, Any]) -> dict[str, Any]:
    school = str(getattr(principal, "school_id", "") or "").strip()
    if not school:
        raise ToolError("edu.unconfigured", "没有学校登录，不能按票执行")
    grant_id = str(args.get("grant_id") or "").strip()
    steps = args.get("steps")
    if not isinstance(steps, list):
        raise ToolError("tool.invalid_arguments", "steps 必填")
    path = f"/v1/schools/{school}/agent/run-packs"
    body: dict[str, Any] = {
        "run_id": str(args.get("run_id") or "")[:80],
        "steps": steps,
    }
    if grant_id:
        body["grant_id"] = grant_id
    return await edu_request(
        principal,
        "POST",
        path,
        body=body,
        scopes=["ai:read", "ai:delegate"],
        timeout=30,
    )


async def steward_public_corpus(principal: Principal, args: dict[str, Any]) -> dict[str, Any]:
    school = str(getattr(principal, "school_id", "") or "").strip()
    if not school:
        raise ToolError("edu.unconfigured", "没有学校，不能读公开语料")
    root = _edu_root()
    token = _mint_steward(school)
    if not root or not token:
        raise ToolError("edu.unconfigured", "学校公开语料未接通（缺 edu 基址或密钥）")
    url = f"{root}/v1/pico/steward/public-corpus"
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.get(url, headers=headers)
    except httpx.HTTPError as exc:
        raise ToolError("edu.unreachable", f"学校现在连不上（{exc}）") from exc
    if response.status_code >= 400:
        code, message = _message_from(response)
        raise ToolError(code or "edu.error", message)
    try:
        data = response.json()
    except ValueError as exc:
        raise ToolError("edu.contract_error", "学校返回不是 JSON") from exc
    if not isinstance(data, dict):
        raise ToolError("edu.contract_error", "学校返回不是对象")
    return data


QUERY_LIST_DESCRIPTION = (
    "List the school's read-only data queries for this teacher: who am I / which week, "
    "timetable, school calendar, bell schedule, a student's roster card, name to id. "
    "Call it when the teacher asks for school data and the edu attachment has no queries list "
    "(edu-core#5227: the sidebar sends the same list there). Returns id, summary, params. No args."
)
QUERY_RUN_DESCRIPTION = (
    "Run one read-only school query as the teacher; the result is what the teacher can see "
    "on the school pages, nothing more. Args: id (from the attachment's queries list "
    "or edu_query_list), params (object). "
    "Turn class / teacher / student names into ids with id=lookup.name first. "
    "Answer from the result; a 403/404 means the teacher cannot see it, say so."
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
                "Submit school work under the teacher's live grant. "
                "grant_id optional when a live ticket exists. "
                "For field.display.draft put a short 拟写 in steps[].params.body_md. "
                "Drafts allowed; publish/submit rejected. "
                "Args: steps, grant_id?, run_id?"
            ),
            handler=run_pack,
            school_scoped=True,
        )
    )
    gateway.register(
        ToolSpec(
            name=QUERY_LIST,
            description=QUERY_LIST_DESCRIPTION,
            handler=query_list,
            school_scoped=True,
        )
    )
    gateway.register(
        ToolSpec(
            name=QUERY_RUN,
            description=QUERY_RUN_DESCRIPTION,
            handler=query_run,
            school_scoped=True,
        )
    )


def catalog_command_id(raw: str) -> bool:
    aid = str(raw or "").strip()
    return bool(aid) and "." in aid and " " not in aid and len(aid) < 80
