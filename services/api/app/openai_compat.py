"""OpenAI-compatible /v1/chat/completions for LibreChat and API clients."""

from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from collections.abc import AsyncIterator
from contextlib import suppress
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException
from fastapi.responses import StreamingResponse
from pico_orchestrator.edu_sidebar import (
    SIDEBAR_WEB_SYSTEM,
    SIDEBAR_WORKBENCH_HINT,
    asked_from_sidebar_prompt,
    honest_miss_json,
    inject_web_hits,
    is_json_only_propose,
    shape_web_hits,
)
from pico_orchestrator.gateway import ToolError as ChannelToolError
from pico_orchestrator.sse_keepalive import (
    SSE_COMMENT_KEEPALIVE,
    SSE_KEEPALIVE_SECONDS,
    SSE_STREAM_HEADERS,
    iter_with_idle_ticks,
)
from pico_orchestrator.user_errors import user_message_for_error
from pydantic import BaseModel

from app.auth import (
    LEGACY_PROXY_MEMBERSHIP_ID,
    Principal,
    decode_token,
    enforce_scope,
    payer_for,
    prompt_membership_conflicts_header,
    require_billed_identity,
    scope_proxy_principal,
)
from app.channel_rates import require_rate
from app.db import RunRow, TaskRow, append_event, new_id, session_factory
from app.settings import Settings, get_settings

router = APIRouter(tags=["openai-compat"])
logger = logging.getLogger(__name__)


class ChatMessage(BaseModel):
    role: str
    content: str | list[Any] | None = ""
    # LibreChat AgentClient may put vision parts on the message instead of
    # (or as well as) content[]. Extra fields were previously dropped.
    image_urls: list[Any] | None = None
    files: list[Any] | None = None
    attachments: list[Any] | None = None


class ChatCompletionRequest(BaseModel):
    model: str | None = None
    messages: list[ChatMessage]
    stream: bool = False
    temperature: float | None = None
    max_tokens: int | None = None
    user: str | None = None  # LibreChat may pass conversation id
    metadata: dict[str, Any] | None = None
    web_search: bool = False
    pico_plan: bool = False
    tools: list[Any] | None = None
    allowed_tools: list[str] | None = None


EDU_SIDEBAR_MARK = "附属，不是用户要求"


def _part_filename(part: dict[str, Any]) -> str:
    nested = part.get("file") if isinstance(part.get("file"), dict) else {}
    return str(
        part.get("filename") or nested.get("filename") or part.get("name") or ""
    ).strip()[:180]


def _content_text(content: str | list[Any] | None) -> str:
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    # Keep text. File / input_file parts were dropped (LibreChat native PDF
    # encode); harvest filenames so the model sees the attachment arrived.
    # Image parts stay via last_user_images → RunCaps.images.
    parts: list[str] = []
    for p in content:
        if isinstance(p, str):
            parts.append(p)
            continue
        if not isinstance(p, dict):
            continue
        if p.get("type") == "text":
            parts.append(str(p.get("text") or ""))
            continue
        name = _part_filename(p)
        if name:
            parts.append(name)
    return "\n".join(parts)


def _sibling_file_names(message: ChatMessage) -> str:
    names: list[str] = []
    seen: set[str] = set()
    for blob in (message.files, message.attachments):
        if not isinstance(blob, list):
            continue
        for part in blob:
            if not isinstance(part, dict):
                continue
            name = _part_filename(part)
            if name and name not in seen:
                seen.add(name)
                names.append(name)
    return "\n".join(names)


def _client_system_from_messages(messages: list[ChatMessage] | None) -> str:
    for msg in messages or []:
        if getattr(msg, "role", None) == "system":
            return _content_text(getattr(msg, "content", "")).strip()
    return ""


def _is_edu_sidebar_system(text: str | None) -> bool:
    return EDU_SIDEBAR_MARK in str(text or "")


def _sidebar_chat_only(*, edu_sidebar: bool, json_only: bool) -> bool:
    """Edu sidebar is Cherry-style chat: never force_agent, never land artifacts."""
    return bool(json_only or edu_sidebar)


def _workbench_tool_step_line(tool: str) -> str:
    """One human step for workbench tools. Empty only when the tool name is empty."""
    from pico_orchestrator.workbench_progress import workbench_tool_step_line

    return workbench_tool_step_line(tool)


def _normalize_allowed_tools(raw: list[Any] | None) -> list[str] | None:
    if raw is None:
        return None
    out: list[str] = []
    seen: set[str] = set()
    for item in raw:
        name = ""
        if isinstance(item, str):
            name = item.strip()
        elif isinstance(item, dict):
            fn = item.get("function") if isinstance(item.get("function"), dict) else {}
            name = str(item.get("name") or fn.get("name") or "").strip()
        if name and name not in seen:
            seen.add(name)
            out.append(name)
    return out


def _resolve_allowed_tools(
    skill_snapshot: dict[str, Any] | None,
    request_tools: list[str] | None,
) -> list[str] | None:
    """Request list is a ceiling. Empty intersection falls back to the request list."""
    skill_tools: list[str] | None = None
    if skill_snapshot and skill_snapshot.get("tools"):
        skill_tools = [str(t) for t in skill_snapshot.get("tools") or [] if t]
    if request_tools is None:
        return skill_tools
    if not skill_tools:
        return request_tools
    inter = [t for t in skill_tools if t in set(request_tools)]
    return inter or request_tools


def _model_preference_from_prompt(prompt: str) -> str | None:
    """Resolve the workbench model preference from a strict allowlist."""
    import re

    match = re.search(r"【模型偏好：([^】]+)】", prompt or "")
    if not match:
        return None
    requested = match.group(1).strip()
    aliases = {
        "pico": "pico-agent",
        "pico agent": "pico-agent",
        "pico fast": "pico-fast",
        "pico 快速": "pico-fast",
        "pico deep": "pico-deep",
        "pico 深度": "pico-deep",
        "kimi-k3": "kimi-k3",
        "deepseek": "deepseek-v4-flash",
        "deepseek-chat": "deepseek-chat",
        "deepseek-reasoner": "deepseek-reasoner",
    }
    normalized = aliases.get(requested.lower(), requested)
    if normalized.lower() == "auto":
        return None

    from pico_orchestrator.provider import KNOWN_DEEPSEEK_MODELS, KNOWN_KIMI_MODELS

    allowed = {"pico-agent", "pico-fast", "pico-deep", *KNOWN_DEEPSEEK_MODELS, *KNOWN_KIMI_MODELS}
    return normalized if normalized in allowed else None


def _dev_proxy_keys(settings: Settings) -> set[str]:
    """Explicit dev/proxy keys only — never KIMI_API_KEY or JWT secret."""
    keys = {"pico-dev", "sk-pico-dev"}
    extra = (settings.pico_openai_proxy_key or "").strip()
    if extra:
        keys.add(extra)
    return keys


def _production_proxy_key(settings: Settings) -> str | None:
    key = (settings.pico_openai_proxy_key or "").strip()
    if len(key) < 32 or key in {"pico-dev", "sk-pico-dev"}:
        return None
    return key


def _principal_from_auth(
    authorization: str | None,
    settings: Settings,
) -> Principal:
    """Accept Pico JWT or a scoped OpenAI-compat proxy credential.

    Production accepts only a strong explicit internal proxy credential. Model
    keys and JWT signing secrets are never treated as Bearer credentials.
    """
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="missing bearer")
    token = authorization.split(" ", 1)[1].strip()
    if not token:
        raise HTTPException(status_code=401, detail="empty bearer")

    env = (settings.pico_env or "development").lower()
    production = env in {"production", "prod"}

    # Prefer real JWT always
    try:
        return decode_token(token, settings)
    except HTTPException as jwt_err:
        # Dev defaults stay non-production; production accepts only the strong
        # explicit internal proxy credential.
        if (not production and token in _dev_proxy_keys(settings)) or (
            production and token == _production_proxy_key(settings)
        ):
            return Principal(
                school_id="school-a",
                membership_id=LEGACY_PROXY_MEMBERSHIP_ID,
                scopes=["ai:run", "ai:read", "ai:confirm"],
                iss=settings.pico_jwt_iss,
                aud=settings.pico_jwt_aud,
                exp=int(time.time()) + 3600,
                raw={"proxy": True},
            )
        if production and token in _dev_proxy_keys(settings):
            raise HTTPException(
                status_code=401,
                detail="proxy keys disabled in production; use Pico JWT",
            ) from jwt_err
        raise


def _normalized_model(model: str) -> str:
    normalized = model.strip()
    return normalized.split("/")[-1] if "/" in normalized else normalized


def _assert_model_allowed(model: str, settings: Settings) -> None:
    if not settings.is_production:
        return
    normalized = _normalized_model(model)
    allowed = {_normalized_model(item) for item in settings.allowed_model_list}
    product_surface = {"pico-fast", "pico-deep", "pico-agent", "pico"}
    deepseek_aliases = {"deepseek-v4-flash", "deepseek-chat", "deepseek-reasoner"}
    if normalized in allowed:
        return
    if product_surface.intersection(allowed) and normalized in deepseek_aliases:
        return
    if normalized in {"pico-fast", "pico-deep"} and {"pico-fast", "pico-deep"}.intersection(allowed):
        return
    # Product delivery name. Host allowlist is often pico-fast,pico-deep only.
    if normalized in {"pico-agent", "pico"} and {"pico-fast", "pico-deep"}.intersection(
        allowed
    ):
        return
    raise HTTPException(status_code=400, detail="model is not allowed")


def _coerce_default_model(model: str, settings: Settings) -> str:
    """Rewrite legacy broken Kimi defaults onto DeepSeek when allowlist moved.

    Owner E2E-DEFAULT: new chats must work without manually picking DeepSeek.
    Old browser prefs that still hold ``kimi-k2.x`` should not dead-end when
    production allowlist is ``deepseek-chat,pico-agent`` only.
    """
    from pico_orchestrator.provider import is_kimi_model

    bare = _normalized_model(model or "")
    if not bare or not is_kimi_model(bare):
        return model
    allowed = {_normalized_model(item) for item in settings.allowed_model_list}
    if allowed and bare in allowed:
        return model  # Kimi still explicitly allowed
    # Prefer product DeepSeek default when key/provider says so.
    prefer_deepseek = (
        settings.deepseek_api_key.strip()
        and settings.pico_model_provider.strip().lower() != "kimi"
    )
    if prefer_deepseek or (settings.deepseek_api_key.strip() and not settings.kimi_api_key.strip()):
        target = (settings.deepseek_model or "deepseek-v4-flash").strip() or "deepseek-v4-flash"
        if not allowed or _normalized_model(target) in allowed:
            return target
        if {"pico-fast", "pico-deep"}.intersection(allowed):
            return "deepseek-v4-flash"
    return model


def _effective_max_tokens(requested: int | None, cap: int) -> int:
    default = min(2048, cap)
    return min(requested if requested and requested > 0 else default, cap)


def _compat_usage_payload(
    prompt: str, completion: str, provider_usage: dict[str, Any] | None
) -> dict[str, int] | None:
    """OpenAI-compat shell must not expose token numbers to teachers.

    Native usage still lands on the Pico ledger. Formula stays in points_meter.
    """
    del prompt, completion, provider_usage
    return None



def _all_message_text(messages: list[ChatMessage]) -> str:
    parts: list[str] = []
    for message in messages or []:
        parts.append(_content_text(message.content))
    return "\n".join(parts)


def _is_title_generation_request(prompt: str, messages: list[ChatMessage]) -> bool:
    """Detect LibreChat *automatic* title prompts only (high precision).

    Must never create durable Task/Run for shell auto-title traffic (stage #260).
    Must NOT swallow real user tasks such as「请生成一个短标题」/「write a short title for …」.
    Match multi-signal LibreChat scaffolds only — never a single short phrase.
    """
    blob = f"{_all_message_text(messages)}\n{prompt or ''}".lower()

    # @librechat/agents createTitleRunnable default (language + title structured)
    if (
        "analyze this conversation and provide" in blob
        and "detected language" in blob
        and (
            "concise title in the detected language" in blob
            or ("5 words or less" in blob and "no punctuation" in blob)
        )
    ):
        return True

    # @librechat/agents createCompletionTitleRunnable default
    if (
        "provide a concise, 5-word-or-less title for the conversation" in blob
        and "only return the title itself" in blob
        and ("title case" in blob or "conversation:" in blob)
    ):
        return True

    # assistants endpoint title.js scaffold
    if (
        "please generate a concise title (max 40 characters) for a conversation that starts with"
        in blob
    ):
        return True

    # Same assistants scaffold with User:/Assistant:/Title: layout (no single-phrase match)
    return (
        "concise title" in blob
        and "conversation that starts with" in blob
        and "user:" in blob
        and "title:" in blob
    )


def _synthetic_title_from_messages(messages: list[ChatMessage], prompt: str) -> str:
    """Local title only — no model call, no ledger, no tools."""
    import re

    blob = _all_message_text(messages) or (prompt or "")
    # Prefer embedded user turn if title prompt quoted it.
    for pattern in (
        r"(?im)^\s*user\s*:\s*(.+)$",
        r"(?im)conversation:\s*(.+)$",
        r"(?is)\{convo\}\s*(.+)$",
    ):
        match = re.search(pattern, blob)
        if match:
            blob = match.group(1).strip()
            break
    # Drop instruction scaffolding lines.
    cleaned_lines: list[str] = []
    for line in blob.splitlines():
        low = line.strip().lower()
        if not line.strip():
            continue
        if any(
            skip in low
            for skip in (
                "analyze this conversation",
                "provide a concise",
                "please generate",
                "only return the title",
                "detected language",
                "title case",
                "title:",
            )
        ):
            continue
        cleaned_lines.append(line.strip())
    seed = cleaned_lines[0] if cleaned_lines else (prompt or "新对话")
    seed = re.sub(r"\s+", " ", seed).strip(" \"'`，。；：,.!?")
    if not seed:
        seed = "新对话"
    if len(seed) > 40:
        seed = seed[:37].rstrip() + "…"
    return seed


def _title_completion_payload(
    *,
    completion_id: str,
    created: int,
    model: str,
    title: str,
    prompt: str,
) -> dict[str, Any]:
    del prompt
    return {
        "id": completion_id,
        "object": "chat.completion",
        "created": created,
        "model": model,
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": title},
                "finish_reason": "stop",
            }
        ],
    }


def _strip_pico_markers(text: str) -> str:
    """Remove Pico-internal ledger markers before the model sees the user turn."""
    import re

    t = str(text or "")
    t = re.sub(r"【Pico-Convo:[^】]+】", "", t)
    t = re.sub(r"【Pico-User:[^】]+】", "", t)
    t = re.sub(r"【工作空间：[^】]+】", "", t)
    t = re.sub(r"【权限：[^】]+】", "", t)
    t = re.sub(r"【模型偏好：[^】]+】", "", t)
    t = re.sub(r"【项目指令：[^】]+】", "", t)
    return t


def _last_user_prompt(messages: list[ChatMessage]) -> str:
    for m in reversed(messages):
        if m.role == "user":
            t = _content_text(m.content).strip()
            extra = _sibling_file_names(m)
            if extra:
                t = f"{t}\n{extra}".strip() if t else extra
            if t:
                return t
    return "\n".join(
        f"{m.role}: {_content_text(m.content)}" for m in messages
    ).strip() or "hello"


def _history_for_agent(messages: list[ChatMessage]) -> list[dict[str, Any]]:
    """Prior turns only (exclude the latest user message — runner appends it)."""
    if not messages:
        return []
    # drop trailing user message(s) that form current prompt
    trimmed = list(messages)
    while trimmed and trimmed[-1].role == "user":
        trimmed.pop()
    out: list[dict[str, Any]] = []
    for m in trimmed[-20:]:  # cap context
        if m.role not in ("user", "assistant"):
            continue
        text = _strip_pico_markers(_content_text(m.content)).strip()
        if text:
            out.append({"role": m.role, "content": text})
    return out



def _conversation_id_from(
    body: ChatCompletionRequest,
    x_conversation_id: str | None,
) -> str | None:
    if x_conversation_id and x_conversation_id.strip():
        return x_conversation_id.strip()[:128]
    if body.metadata:
        for k in ("conversation_id", "conversationId", "convo_id"):
            v = body.metadata.get(k)
            if v:
                return str(v)[:128]
    # parse 【Pico-Convo:xxx】 from latest user message
    import re
    prompt = _last_user_prompt(body.messages)
    m = re.search(r"【Pico-Convo:([^】]+)】", prompt)
    if m:
        return m.group(1).strip()[:128]
    if body.user and body.user.strip() and body.user not in {"default", "user"}:
        return body.user.strip()[:128]
    return None


def _workspace_id_from(
    body: ChatCompletionRequest,
    x_workspace_id: str | None,
) -> str | None:
    if x_workspace_id and x_workspace_id.strip():
        return x_workspace_id.strip()[:36]
    if body.metadata:
        v = body.metadata.get("workspace_id") or body.metadata.get("workspaceId")
        if v:
            return str(v)[:36]
    return None


async def _day_use_system_block(
    principal: Principal, display_header: str | None
) -> str:
    """SSO name + recent ledger titles → SYSTEM appendix. Fail soft; never a memory OS."""
    from pico_orchestrator.day_use import build_day_use_block, decode_display_name_header

    name = decode_display_name_header(display_header)
    titles: list[str] = []
    try:
        from app.run_service import list_artifacts_for_principal

        factory = session_factory()
        async with factory() as session:
            rows = await list_artifacts_for_principal(session, principal, limit=12)
        titles = [str(getattr(row, "title", "") or "") for row in rows]
    except Exception:  # noqa: BLE001 — missing ledger must not block chat
        titles = []
    return build_day_use_block(display_name=name, recent_titles=titles)


async def _ledger_task_run(
    *,
    principal: Principal,
    prompt: str,
    model: str,
    conversation_id: str | None,
    workspace_id: str | None,
    skill_snapshot: dict[str, Any] | None = None,
    status: str = "running",
) -> tuple[str, str]:
    """Create Task+Run rows for any chat completion path."""
    from app.db import _utcnow, init_db

    await init_db()
    factory = session_factory()
    task_id = new_id()
    run_id = new_id()
    title = prompt[:80]
    # Running rows must stamp started_at so A5/G9 overlap timelines are auditable.
    started = _utcnow() if status == "running" else None
    async with factory() as session:
        session.add(
            TaskRow(
                id=task_id,
                school_id=principal.school_id,
                membership_id=principal.membership_id,
                title=title,
                conversation_id=conversation_id,
                workspace_id=workspace_id,
            )
        )
        session.add(
            RunRow(
                id=run_id,
                task_id=task_id,
                status=status,
                prompt=prompt,
                model=model or "",
                started_at=started,
                token_usage_json=json.dumps(
                    {"skill_snapshot": skill_snapshot} if skill_snapshot else {},
                    ensure_ascii=False,
                ),
            )
        )
        await session.commit()
    return task_id, run_id


def _extract_file_artifacts(text: str) -> list[tuple[str, str]]:
    """Parse fenced file blocks into (filename, body).

    Protected extensions (.html/.docx/.pptx) are never accepted from fences —
    those must come from generate_*_document tools (fail-closed anti-fake).
    """
    import re

    from pico_orchestrator.artifact_types import title_protected_extension

    out: list[tuple[str, str]] = []
    if not text:
        return out
    for m in re.finditer(
        r"```(?:file:)?([\w.\-]+\.[A-Za-z0-9]{1,12})\s*\n([\s\S]*?)```",
        text,
    ):
        name = m.group(1).strip()
        body = m.group(2).rstrip()
        if not name:
            continue
        if title_protected_extension(name):
            # Drop pseudo Office/HTML fences rather than storing fake bytes.
            continue
        out.append((name[:200], body[:50000]))
    return out


def _file_from_user_prompt(user_prompt: str | None) -> list[tuple[str, str]]:
    """Synthesize file when user explicitly asks to create name.ext with content."""
    import re

    if not user_prompt:
        return []
    um = re.search(
        r"(?:创建|生成|写|保存).{0,40}?([\w.\-]+\.(?:txt|md|csv|json))",
        user_prompt,
        re.IGNORECASE,
    )
    if not um:
        return []
    name = um.group(1)
    cm = re.search(r"内容\s*[为是:=：]\s*([^\n，,。；;]{1,200})", user_prompt)
    body = "hi"
    if cm:
        body = cm.group(1).strip().strip("\"'「」")
    return [(name, body or "hi")]


def _this_round_delivery_plan(
    raw_prompt: str,
    *,
    prior_artifact_titles: list[str] | None = None,
) -> Any:
    """Never set min_artifacts / force_agent from a user-prompt word list.

    Tools stay mounted. The post-run gate only fails a chat-only *claim*.
    """
    del raw_prompt, prior_artifact_titles
    from pico_orchestrator.delivery_policy import no_guess_plan

    return no_guess_plan()


def _sticky_delivery_plan(
    raw_prompt: str,
    history: list[dict[str, Any]] | None,
    *,
    prior_artifact_titles: list[str] | None = None,
) -> Any:
    """T-GROK-PATH: no prior-turn force_agent; no prompt word table."""
    del history
    return _this_round_delivery_plan(
        raw_prompt, prior_artifact_titles=prior_artifact_titles
    )


def _resolve_skill_for_prompt(
    raw_prompt: str,
    skill_snapshot: dict[str, Any] | None,
    *,
    prior_artifact_titles: list[str] | None = None,
    history: list[dict[str, Any]] | None = None,
) -> tuple[dict[str, Any] | None, Any]:
    """Keep an explicit hung skill. Do not guess-and-attach deliverable/engineering.

    Returns (skill_snapshot, DeliveryPlan). Tools stay on the allowlist either way.
    """
    plan = _sticky_delivery_plan(
        raw_prompt,
        history,
        prior_artifact_titles=prior_artifact_titles,
    )
    return skill_snapshot, plan


def _caps_with_landing_min(caps: Any, delivery_plan: Any, skill_snapshot: dict | None) -> Any:
    """Post-run min_artifacts only. Do not floor because a skill name was guessed."""
    from dataclasses import replace as _dc_replace

    del skill_snapshot
    need = 0
    if delivery_plan is not None:
        need = int(getattr(delivery_plan, "min_artifacts", 0) or 0)
    if need > 0:
        return _dc_replace(caps, min_artifacts=need)
    return caps


def _caps_with_images(caps: Any, images: list[dict[str, Any]] | None) -> Any:
    """Keep chat image parts; switch backend to a vision model when present."""
    from pico_orchestrator.vision import apply_images_to_caps

    return apply_images_to_caps(caps, images or [])


def _caps_with_dual_mode(caps: Any, model: str | None) -> Any:
    """Apply the dual-mode runtime policy onto RunCaps (Pico 快速 / Pico 深度).

    LAW #865: lanes do not hard-cap the upstream window. GPT brain thinks.
    """
    from dataclasses import replace as _dc_replace

    from pico_orchestrator.provider import runtime_policy_for_model

    low = (model or "").strip().lower()
    if low not in {"pico-fast", "pico-deep"}:
        return caps
    policy = runtime_policy_for_model(low)
    fields: dict[str, Any] = {
        "max_steps": int(policy.get("max_steps", caps.max_steps)),
        "max_tokens": int(policy.get("max_tokens", caps.max_tokens)),
        "thinking_on": bool(policy.get("thinking", False)),
        "ui_model": low,
        "backend_model": str(policy.get("backend_model") or ""),
    }
    if hasattr(caps, "max_context"):
        fields["max_context"] = int(policy.get("max_context", caps.max_context))
    return _dc_replace(caps, **fields)


def _caps_with_sidebar_thinking(caps: Any, *, edu_sidebar: bool) -> Any:
    """Edu rail only paints `content`. Thinking stays in reasoning_content, so
    the school placeholder 正在想 never clears. Sidebar turns thinking off;
    workbench GPT still thinks (LAW #865).
    """
    if not edu_sidebar or not getattr(caps, "thinking_on", False):
        return caps
    from dataclasses import replace as _dc_replace

    return _dc_replace(caps, thinking_on=False)


def _request_plan_on(body: ChatCompletionRequest, header: str | None = None) -> bool:
    """Teacher 先计划 toggle. Header / body / metadata; never default on."""
    # Direct calls (integration tests) pass FastAPI's Header() sentinel, not a str.
    raw = header.strip().lower() if isinstance(header, str) else ""
    if raw in {"1", "true", "yes", "on"}:
        return True
    if bool(getattr(body, "pico_plan", False)):
        return True
    meta = body.metadata if isinstance(body.metadata, dict) else None
    return bool(meta and meta.get("pico_plan"))


def _caps_with_plan(caps: Any, plan_on: bool) -> Any:
    from dataclasses import replace as _dc_replace

    if not plan_on:
        return caps
    return _dc_replace(caps, plan_on=True)


def _instruction_with_delivery(
    skill_snapshot: dict[str, Any] | None,
    prompt: str,
    plan: Any | None = None,
    *,
    prior_artifact_titles: list[str] | None = None,
) -> str:
    """Explicit hung-skill catalog text only. Do not weld per-turn Landing N into it."""
    from pico_orchestrator.skill_policy import instruction_for_snapshot

    del prompt, plan, prior_artifact_titles
    return instruction_for_snapshot(skill_snapshot)


async def _finalize_run(
    run_id: str,
    *,
    status: str,
    error: str | None = None,
    final_text: str | None = None,
    task_id: str | None = None,
    user_prompt: str | None = None,
    change_proposal: dict | None = None,
    token_usage: dict[str, Any] | None = None,
    bill_to: str | None = None,
) -> None:
    from sqlalchemy import case, select, update

    from app.db import ArtifactRow, ChangeProposalRow, EventRow, TaskRow, _utcnow
    from app.run_service import _json_dict, _skill_s7_payload

    terminal = ("succeeded", "failed", "cancelled")
    if status not in terminal:
        raise ValueError(f"invalid terminal run status: {status}")

    factory = session_factory()
    async with factory() as session:
        requested_status = status
        mark_cancel = status == "cancelled"
        values: dict = {
            "status": case(
                (RunRow.cancel_requested != 0, "cancelled"),
                else_=status,
            ),
            "error": case(
                (RunRow.cancel_requested != 0, None),
                else_=error,
            ),
            "ended_at": _utcnow(),
        }
        if mark_cancel:
            values["cancel_requested"] = case(
                (RunRow.cancel_requested != 0, RunRow.cancel_requested),
                else_=1,
            )

        claimed = await session.execute(
            update(RunRow)
            .where(
                RunRow.id == run_id,
                RunRow.status.not_in(terminal),
            )
            .values(**values)
        )
        if claimed.rowcount != 1:
            await session.rollback()
            return

        run = await session.get(RunRow, run_id)
        if not run:
            await session.rollback()
            return
        if task_id is not None and task_id != run.task_id:
            await session.rollback()
            raise ValueError("run/task mismatch during finalize")
        status = run.status
        if status == "cancelled":
            # Honest ledger when stop only tears down the stream.
            await append_event(
                session,
                run_id,
                "run.cancel_requested",
                {
                    "source": (
                        "stream_or_finalize"
                        if requested_status == "cancelled"
                        else "flag_before_finalize"
                    )
                },
                commit=False,
            )
            await append_event(
                session,
                run_id,
                "run.status",
                {"status": "cancelled"},
                commit=False,
            )

        usage = _json_dict(run.token_usage_json)
        if token_usage:
            snapshot = usage.get("skill_snapshot")
            usage.update({k: v for k, v in token_usage.items() if k != "skill_snapshot"})
            for key in list(usage):
                if str(key).lower() in {
                    "cost",
                    "price",
                    "currency",
                    "charge",
                    "amount",
                    "billing",
                    "millipoints",
                    "rate",
                    "scale",
                    "formula",
                    "per_token",
                    "multiplier",
                }:
                    usage.pop(key, None)
            if isinstance(snapshot, dict):
                usage["skill_snapshot"] = snapshot
            run.token_usage_json = json.dumps(usage, ensure_ascii=False)
        skill_snapshot = usage.get("skill_snapshot")
        if isinstance(skill_snapshot, dict) and status == "succeeded":
            existing_skill_event = await session.execute(
                select(EventRow.id)
                .where(EventRow.run_id == run_id, EventRow.type == "skill.snapshot")
                .limit(1)
            )
            if existing_skill_event.scalar_one_or_none() is None:
                await append_event(
                    session,
                    run_id,
                    "skill.snapshot",
                    skill_snapshot,
                    commit=False,
                )

        unknown_skill = (
            isinstance(skill_snapshot, dict)
            and skill_snapshot.get("name") == "skill.unknown"
        )
        if final_text and status == "succeeded" and not unknown_skill:
            existing = await session.execute(
                select(ArtifactRow.kind, ArtifactRow.title).where(
                    ArtifactRow.run_id == run_id
                )
            )
            existing_keys = {(kind, title) for kind, title in existing.all()}
            files = _extract_file_artifacts(final_text)
            if not files:
                files = _file_from_user_prompt(user_prompt)
            for name, body in files:
                key = ("file", name)
                if key in existing_keys:
                    continue
                import hashlib

                raw_bytes = body.encode("utf-8")
                artifact = ArtifactRow(
                    id=new_id(),
                    task_id=run.task_id,
                    run_id=run_id,
                    kind="file",
                    title=name,
                    inline=body,
                    content_encoding="utf8",
                    content_sha256=hashlib.sha256(raw_bytes).hexdigest(),
                    byte_size=len(raw_bytes),
                )
                session.add(artifact)
                existing_keys.add(key)
                await append_event(
                    session,
                    run_id,
                    "artifact.created",
                    {
                        "artifact_id": artifact.id,
                        "title": name,
                        "user_label": name,
                        "kind": "file",
                        "download_path": (
                            f"/v1/artifacts/{artifact.id}/content?download=true"
                        ),
                    },
                    commit=False,
                )

            # T-GROK-PATH: 回复摘要 stays in run.final_text (bookkeeping), not
            # a result-area Artifact. Do not mint a downloadable 回复摘要 chip.
        if (
            isinstance(skill_snapshot, dict)
            and skill_snapshot.get("requires_s7")
            and status == "succeeded"
        ):
            existing_change = await session.execute(
                select(ChangeProposalRow.id).where(ChangeProposalRow.run_id == run_id).limit(1)
            )
            if existing_change.scalar_one_or_none() is None:
                task_row = await session.get(TaskRow, run.task_id)
                if task_row is None:
                    await session.rollback()
                    return
                prop = _skill_s7_payload(
                    prompt=run.prompt,
                    final_text=final_text,
                    snapshot=skill_snapshot,
                )
                change = ChangeProposalRow(
                    id=new_id(),
                    school_id=task_row.school_id,
                    membership_id=task_row.membership_id,
                    task_id=run.task_id,
                    run_id=run.id,
                    title=prop["title"],
                    summary=prop["summary"],
                    payload_json=json.dumps(prop["payload"], ensure_ascii=False),
                    status="proposed",
                )
                session.add(change)
                await append_event(
                    session,
                    run_id,
                    "change.proposed",
                    {"change_id": change.id, "title": change.title},
                    commit=False,
                )
        # Tool-path S7: persist pico_propose_change even when skill does not require_s7.
        if change_proposal and status in ("succeeded", "failed"):
            existing_tool_change = await session.execute(
                select(ChangeProposalRow.id).where(ChangeProposalRow.run_id == run_id).limit(1)
            )
            if existing_tool_change.scalar_one_or_none() is None:
                task_row = await session.get(TaskRow, run.task_id)
                if task_row is not None:
                    prop = change_proposal.get("proposal") or change_proposal
                    if isinstance(prop, dict):
                        change = ChangeProposalRow(
                            id=new_id(),
                            school_id=task_row.school_id,
                            membership_id=task_row.membership_id,
                            task_id=run.task_id,
                            run_id=run.id,
                            title=str(prop.get("title") or "变更提案"),
                            summary=str(prop.get("summary") or ""),
                            payload_json=json.dumps(
                                prop.get("payload") or {}, ensure_ascii=False
                            ),
                            status="proposed",
                        )
                        session.add(change)
                        await append_event(
                            session,
                            run_id,
                            "change.proposed",
                            {"change_id": change.id, "title": change.title},
                            commit=False,
                        )

        # Fail-closed delivery: real artifacts required when intent demands them.
        # Shared gate (app.delivery_gate.apply_delivery_gate) — same gate is
        # applied by the retry / REST / automation path (_execute_run) so re-runs
        # cannot bypass #375 fail-closed semantics. Single source of truth.
        from app.delivery_gate import apply_delivery_gate

        await apply_delivery_gate(
            session,
            run,
            final_text=final_text,
            user_prompt=user_prompt,
        )

        await session.commit()

    # Usage meter is best-effort and must never roll back the Run path.
    from app.usage_ledger import emit_llm_usage_after_run

    await emit_llm_usage_after_run(
        run_id,
        token_usage=token_usage,
        prompt=user_prompt,
        completion=final_text,
        source="openai_compat",
        bill_to=bill_to,
    )


async def _run_and_collect(
    prompt: str,
    principal: Principal,
    settings: Settings,
    *,
    run_id: str,
    model: str | None = None,
    history: list[dict[str, Any]] | None = None,
    skill_snapshot: dict[str, Any] | None = None,
    delivery_plan: Any | None = None,
    allowed_tools: list[str] | None = None,
    system_prompt: str = "",
    conversation_id: str | None = None,
    images: list[dict[str, Any]] | None = None,
    day_use: str = "",
    plan_on: bool = False,
    native_files: list | None = None,
    edu_sidebar: bool = False,
) -> Any:
    from pico_orchestrator.llm_file_pass import remember_turn_files
    from pico_orchestrator.runtime import run_agent_runtime

    from app.artifact_store import LedgerArtifactStore

    remember_turn_files(run_id, list(native_files or []))
    factory = session_factory()

    async def emit(event_type: str, payload: dict[str, Any]) -> None:
        async with factory() as session:
            await append_event(session, run_id, event_type, payload)

    async def is_cancelled() -> bool:
        async with factory() as session:
            run = await session.get(RunRow, run_id)
            return bool(run and (run.cancel_requested or run.status == "cancelled"))

    caps = settings.delivery_run_caps(
        allowed_tools=_resolve_allowed_tools(skill_snapshot, allowed_tools),
        skill_instruction=_instruction_with_delivery(
            skill_snapshot, prompt, delivery_plan
        ),
    )
    # Dual-mode: Pico 快速 / Pico 深度 set their own steps/tokens/thinking.
    caps = _caps_with_dual_mode(caps, model)
    caps = _caps_with_sidebar_thinking(caps, edu_sidebar=edu_sidebar)
    caps = _caps_with_plan(caps, plan_on)
    caps = _caps_with_images(caps, images)
    # Landing gate: force min_artifacts into Pi so chat-only "done" cannot succeed.
    caps = _caps_with_landing_min(caps, delivery_plan, skill_snapshot)
    if system_prompt:
        from dataclasses import replace as _dc_replace_sys

        caps = _dc_replace_sys(caps, system_prompt=system_prompt)
    if day_use:
        from dataclasses import replace as _dc_replace_day

        caps = _dc_replace_day(caps, day_use=day_use)
    if skill_snapshot:
        await emit("skill.snapshot", skill_snapshot)
    if delivery_plan is not None and getattr(delivery_plan, "engineering", False):
        await emit(
            "delivery.plan",
            {
                "multi_deliverable": delivery_plan.multi_deliverable,
                "pipeline": delivery_plan.pipeline,
                "revision": delivery_plan.revision,
                "runnable_html": delivery_plan.runnable_html,
                "min_artifacts": delivery_plan.min_artifacts,
                "implicit_package": bool(
                    getattr(delivery_plan, "implicit_package", False)
                ),
                "structure_item_count": int(
                    getattr(delivery_plan, "structure_item_count", 0) or 0
                ),
                "prior_artifact_count": int(
                    getattr(delivery_plan, "prior_artifact_count", 0) or 0
                ),
            },
        )
    result = await run_agent_runtime(
        use_pi_agent=settings.pico_pi_agent_runtime,
        pi_agent_canary_principals=settings.pi_agent_canary_principal_set,
        pi_agent_allow_all=settings.pi_agent_default_all,
        use_kimi_agent=settings.legacy_kimi_enabled,
        kimi_agent_canary_principals=(
            settings.kimi_agent_canary_principal_set
        ),
        kimi_agent_allow_all=settings.kimi_agent_default_all,
        legacy_agent_loop_emergency=settings.pico_legacy_agent_loop_emergency,
        prompt=prompt,
        principal=principal,  # structural Principal protocol
        emit=emit,
        is_cancelled=is_cancelled,
        caps=caps,
        history=history,
        artifact_store=LedgerArtifactStore(
            factory, run_id=run_id, conversation_id=conversation_id
        ),
        conversation_id=conversation_id,
        persist_pi_session=True,
        run_id=run_id,
    )
    return result


def _sse_chunk(data: dict[str, Any]) -> str:
    return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"


@router.get("/v1/models")
async def list_models(
    authorization: str | None = Header(default=None),
    settings: Settings = Depends(get_settings),
) -> dict:
    enforce_scope(_principal_from_auth(authorization, settings), "ai:read")
    from pico_orchestrator.provider import (
        DEFAULT_DEEPSEEK_MODEL,
        KNOWN_DEEPSEEK_MODELS,
        KNOWN_KIMI_MODELS,
        owned_by_for_model,
    )

    # Product default = DeepSeek first (LibreChat uses first OPENAI_MODELS entry;
    # API list order stays aligned for honest branding).
    if settings.deepseek_api_key.strip() and settings.pico_model_provider.strip().lower() != "kimi":
        default = settings.deepseek_model or DEFAULT_DEEPSEEK_MODEL
        known = list(KNOWN_DEEPSEEK_MODELS) + list(KNOWN_KIMI_MODELS)
    else:
        default = settings.kimi_model or settings.deepseek_model or DEFAULT_DEEPSEEK_MODEL
        known = list(KNOWN_KIMI_MODELS) + list(KNOWN_DEEPSEEK_MODELS)
    # Production allowlist (first entry = shell default) wins when set.
    allow = settings.allowed_model_list
    if allow:
        ids: list[str] = []
        for mid in allow:
            bare = _normalized_model(mid)
            if bare and bare not in ids:
                ids.append(bare)
    else:
        ids = []
        for mid in [default, *known, "pico-agent"]:
            if mid not in ids:
                ids.append(mid)
    # Pico UI exposes ONLY the two product modes (F4). Any legacy/raw SKU that
    # leaked in (deepseek-chat / deepseek-reasoner / kimi-* / pico-agent) is
    # filtered out — the product surface is exactly {pico-fast, pico-deep}.
    # This also makes /v1/models deterministic regardless of allowlist breadth.
    ids = [mid for mid in ids if _normalized_model(mid) in {"pico-fast", "pico-deep"}]
    if "pico-fast" not in ids:
        ids.insert(0, "pico-fast")
    if "pico-deep" not in ids:
        ids.insert(1 if "pico-fast" in ids else 0, "pico-deep")
    return {
        "object": "list",
        "data": [
            {
                "id": mid,
                "object": "model",
                "owned_by": owned_by_for_model(mid),
            }
            for mid in ids
        ],
    }


@router.post("/v1/chat/completions")
async def chat_completions(
    body: ChatCompletionRequest,
    authorization: str | None = Header(default=None),
    x_conversation_id: str | None = Header(default=None, alias="X-Conversation-Id"),
    x_workspace_id: str | None = Header(default=None, alias="X-Workspace-Id"),
    x_pico_membership_id: str | None = Header(default=None, alias="X-Pico-Membership-Id"),
    x_pico_display_name: str | None = Header(default=None, alias="X-Pico-Display-Name"),
    x_pico_output: str | None = Header(default=None, alias="X-Pico-Output"),
    x_pico_plan: str | None = Header(default=None, alias="X-Pico-Plan"),
    settings: Settings = Depends(get_settings),
):
    import re

    principal = _principal_from_auth(authorization, settings)
    from pico_orchestrator.vision import (
        conversation_images,
        last_user_images,
        merge_images,
    )

    turn_images = last_user_images(body.messages)
    from app.edu_files import images_from_native_pdf_parts

    turn_images = merge_images(turn_images, images_from_native_pdf_parts(body.messages))
    raw_for_user = _last_user_prompt(body.messages)
    m_user = re.search(r"【Pico-User:([^】]+)】", raw_for_user)
    marker_membership = m_user.group(1).strip() if m_user else None
    if principal.raw.get("proxy") and prompt_membership_conflicts_header(
        marker_membership, x_pico_membership_id
    ):
        raise HTTPException(status_code=403, detail="proxy membership mismatch")
    principal = scope_proxy_principal(principal, x_pico_membership_id)
    enforce_scope(principal, "ai:run")
    require_billed_identity(principal, settings)
    try:
        require_rate(kind="llm", model=(body.model or "").strip() or "gpt-5.6-sol")
    except ChannelToolError as exc:
        raise HTTPException(
            status_code=403,
            detail={"code": exc.code, "message": str(exc.message)},
        ) from exc
    day_use_block = await _day_use_system_block(principal, x_pico_display_name)
    raw_prompt_with_skill = _last_user_prompt(body.messages)
    from pico_orchestrator.skill_policy import (
        snapshot_for_skill,
        snapshot_from_prompt,
    )

    raw_prompt, skill_snapshot = snapshot_from_prompt(raw_prompt_with_skill)
    if body.metadata and not skill_snapshot:
        skill_snapshot = snapshot_for_skill(
            body.metadata.get("pico_skill_id")
            or body.metadata.get("skill_id")
            or body.metadata.get("skillId")
        )
    json_only = is_json_only_propose(raw_prompt_with_skill, output_header=x_pico_output)
    native_files: list = []
    client_system = _client_system_from_messages(body.messages)
    edu_sidebar = _is_edu_sidebar_system(client_system)
    request_tools = _normalize_allowed_tools(body.allowed_tools)
    if request_tools is None:
        request_tools = _normalize_allowed_tools(body.tools)
    plan_on = _request_plan_on(body, x_pico_plan)
    conversation_id = _conversation_id_from(body, x_conversation_id)
    turn_images = merge_images(turn_images, conversation_images(conversation_id))
    workspace_id = _workspace_id_from(body, x_workspace_id)
    # T-HARNESS-SLIM: do not fetch prior titles to guess a delivery plan.
    # strip ledger markers from model-visible prompt; project instruction → system
    m_proj = re.search(r"【项目指令：([^】]+)】", raw_prompt)
    project_instruction = m_proj.group(1).strip() if m_proj else ""
    prompt = _strip_pico_markers(raw_prompt).strip() or raw_prompt
    try:
        # Use the module-level session_factory. A local `from app.db import
        # session_factory` here makes it a cell of chat_completions; the
        # nested event_stream then NameErrors on edu sidebar (this import
        # is skipped) when the Pi path calls session_factory().
        from app.edu_school import excerpts_for_conversation, inject_named_school_materials

        factory = session_factory()
        async with factory() as named_session:
            named_items = await excerpts_for_conversation(
                principal, conversation_id or "", named_session, settings
            )
            from app.edu_files import uploads_for_conversation

            upload_items = await uploads_for_conversation(
                named_session, principal, conversation_id or ""
            )
            from app.edu_files import (
                ensure_paperclip_pdf_pages,
                images_from_upload_rows,
                native_files_from_rows,
            )

            await ensure_paperclip_pdf_pages(
                named_session, principal, conversation_id or "", upload_items
            )
            native_files = await native_files_from_rows(
                named_session, list(upload_items) + list(named_items or [])
            )
            turn_images = merge_images(
                turn_images,
                await images_from_upload_rows(named_session, upload_items),
            )
        if not edu_sidebar:
            prompt = inject_named_school_materials(prompt, named_items)
            from app.edu_files import inject_conversation_uploads

            prompt = inject_conversation_uploads(prompt, upload_items)
    except Exception:
        logger.exception("named school materials inject failed")
    turn_images = merge_images(turn_images, conversation_images(conversation_id))
    max_chars = int(getattr(settings, "pico_chat_max_prompt_chars", 100000) or 100000)
    # Sidebar propose packs a whitelist JSON. Cap the asked field only; the
    # marker is explicit so this must not 400 a legal affordance table.
    length_basis = prompt
    if json_only:
        try:
            parsed_ask = json.loads(prompt)
            if isinstance(parsed_ask, dict) and parsed_ask.get("asked") is not None:
                length_basis = str(parsed_ask.get("asked") or "")
        except json.JSONDecodeError:
            length_basis = prompt
    if len(length_basis) > max_chars:
        # Explicit reject — never silent-truncate then execute (stage #260 A1).
        raise HTTPException(
            status_code=400,
            detail=(
                f"输入过长（{len(length_basis)} 字，上限 {max_chars} 字）。"
                "请缩短问题后重试；系统不会静默截断后继续执行。"
            ),
        )

    # LibreChat auto-title / auxiliary requests: answer without durable Task/Run.
    if _is_title_generation_request(prompt, body.messages):
        title = _synthetic_title_from_messages(body.messages, prompt)
        completion_id = f"chatcmpl-{uuid.uuid4().hex[:24]}"
        created = int(time.time())
        model = body.model or "pico-agent"
        if body.stream:

            async def title_event_stream() -> AsyncIterator[bytes]:
                def chunk(delta: dict, *, finish: str | None = None) -> bytes:
                    return _sse_chunk(
                        {
                            "id": completion_id,
                            "object": "chat.completion.chunk",
                            "created": created,
                            "model": model,
                            "choices": [
                                {
                                    "index": 0,
                                    "delta": delta,
                                    "finish_reason": finish,
                                }
                            ],
                        }
                    ).encode()

                yield chunk({"role": "assistant"})
                if title:
                    yield chunk({"content": title})
                yield chunk({}, finish="stop")
                yield b"data: [DONE]\n\n"

            return StreamingResponse(
                title_event_stream(),
                media_type="text/event-stream",
                headers=dict(SSE_STREAM_HEADERS),
            )
        return _title_completion_payload(
            completion_id=completion_id,
            created=created,
            model=model,
            title=title,
            prompt=prompt,
        )

    history = _history_for_agent(body.messages)
    # edu sidebar (附属标记) is chat, not delivery — never land files.
    # Routing does not guess min_artifacts / force_agent from the prompt.
    chat_only = _sidebar_chat_only(edu_sidebar=edu_sidebar, json_only=json_only)
    sidebar_system = client_system or None
    sidebar_web_hits: dict[str, Any] | None = None
    if chat_only:
        skill_snapshot = None
        delivery_plan = None
        if json_only and not sidebar_system:
            sidebar_system = (
                "只输出一个 JSON 对象，不要文件或 Markdown 解释："
                '{"summary":"一句话","mutations":[{"affordanceId":"id","params":{},"label":"短标签"}]}'
            )
        if edu_sidebar:
            sidebar_system = (
                f"{sidebar_system}\n{SIDEBAR_WORKBENCH_HINT}"
                if sidebar_system
                else SIDEBAR_WORKBENCH_HINT
            )
        if body.web_search is True:
            from pico_orchestrator.web_tools import web_search_handler

            query = asked_from_sidebar_prompt(prompt)
            if not query:
                raw_hits = {
                    "retrieved": False,
                    "honest_miss": True,
                    "message": "未检索：没有可搜的问句",
                    "sources": [],
                }
            else:
                try:
                    from pico_orchestrator.usage_hook import (
                        bind_usage_context,
                        reset_usage_context,
                    )

                    _search_tok = bind_usage_context(
                        school_id=principal.school_id,
                        membership_id=principal.membership_id,
                        bill_to=payer_for(principal),
                        scopes=principal.scopes,
                    )
                    try:
                        raw_hits = await web_search_handler(
                            principal, {"query": query}
                        )
                    finally:
                        reset_usage_context(_search_tok)
                except Exception as exc:  # noqa: BLE001
                    raw_hits = {
                        "retrieved": False,
                        "honest_miss": True,
                        "message": f"未检索：网搜引擎不可用（{exc}）",
                        "sources": [],
                    }
            sidebar_web_hits = shape_web_hits(raw_hits)
            prompt = inject_web_hits(prompt, sidebar_web_hits)
            sidebar_system = sidebar_system + "\n" + SIDEBAR_WEB_SYSTEM
    else:
        skill_snapshot, delivery_plan = _resolve_skill_for_prompt(
            prompt,
            skill_snapshot,
            history=history,
        )
    model = (
        _model_preference_from_prompt(raw_prompt)
        or body.model
        or settings.deepseek_model
        or settings.kimi_model
        or "pico-fast"
    )
    # Skill/tool path: preserve explicit dual-mode choice (pico-fast keeps thinking
    # off + tight budget; pico-deep keeps thinking on + breaker). Only remap
    # legacy agent SKUs / unknown ids onto pico-deep when a skill was hung.
    if skill_snapshot and skill_snapshot.get("tools"):
        low = str(model or "").strip().lower()
        if low not in {"pico-fast", "pico-deep"}:
            model = "pico-deep"
    # Residual LibreChat prefs may still say kimi-k2.x after product default
    # moved to DeepSeek. Remount onto the product brain when Kimi is not in the
    # production allowlist so default-path chat does not 400.
    model = _coerce_default_model(model, settings)
    _assert_model_allowed(model, settings)
    # Direct model = short tier; pico-agent = delivery tier for token ceiling.
    # json_only / edu sidebar must not enter pi-agent even when the SKU is pico-fast.
    use_direct = chat_only or (
        model not in {"pico-agent", "pico"} and not model.startswith("pico-")
    )
    if native_files and not json_only:
        use_direct = False
    token_ceiling = (
        settings.pico_run_short_max_tokens if use_direct else settings.pico_run_max_tokens
    )
    effective_max_tokens = _effective_max_tokens(body.max_tokens, token_ceiling)
    completion_id = f"chatcmpl-{uuid.uuid4().hex[:24]}"
    created = int(time.time())

    # Direct Kimi (or DeepSeek) for non-agent models — real HTTPS API, not mock
    if not body.stream:
        task_id, run_id = await _ledger_task_run(
            principal=principal,
            prompt=prompt,
            model=model,
            conversation_id=conversation_id,
            workspace_id=workspace_id,
            skill_snapshot=skill_snapshot,
        )
        if use_direct:
            from pico_orchestrator.provider import stream_chat

            system = (
                sidebar_system
                if (json_only or edu_sidebar) and sidebar_system
                else (
                    "你是 Pico，面向学校场景的 AI 助手。"
                    "回答准确、结构清晰；需要分点时用简洁列表；中文优先。"
                    "不要编造不存在的学校数据。"
                    "若用户要求创建或生成纯文本文件（如 hello.txt），请在回复中用代码块输出完整内容，"
                    "格式为 ```file:文件名 换行 正文 换行```；中文说明可附在代码块外。"
                    "禁止用代码块或改后缀冒充 .html / .docx / .pptx；此类交付须走专用生成工具路径。"
                )
            )
            if project_instruction:
                system = system + "\n【项目约束】" + project_instruction
            delivery_instr = _instruction_with_delivery(
                skill_snapshot, prompt, delivery_plan
            )
            if delivery_instr:
                system = system + "\n" + delivery_instr
            if day_use_block:
                system = system + "\n\n" + day_use_block
            parts: list[str] = []
            direct_usage: dict[str, Any] = {}
            try:
                if json_only and sidebar_web_hits and sidebar_web_hits.get("honest_miss"):
                    text = honest_miss_json(sidebar_web_hits)
                else:
                    async for piece in stream_chat(
                        prompt,
                        max_tokens=effective_max_tokens,
                        history=history,
                        system=system,
                        model=model,
                        thinking=False if json_only else None,
                        usage_out=direct_usage,
                    ):
                        if piece:
                            parts.append(piece)
                    text = "".join(parts) or "(empty)"
                await _finalize_run(
                    run_id,
                    status="succeeded",
                    final_text=text,
                    task_id=task_id,
                    user_prompt=prompt,
                    token_usage=direct_usage or None,
                    bill_to=payer_for(principal),
                )
            except Exception as e:  # noqa: BLE001
                text = f"【错误】{user_message_for_error(str(e))}"
                await _finalize_run(
                    run_id,
                    status="failed",
                    error=str(e),
                    task_id=task_id,
                    bill_to=payer_for(principal),
                )
        else:
            result = await _run_and_collect(
                prompt,
                principal,
                settings,
                run_id=run_id,
                model=model,
                history=history,
                skill_snapshot=skill_snapshot,
                delivery_plan=delivery_plan,
                allowed_tools=request_tools,
                system_prompt=client_system if edu_sidebar else "",
                conversation_id=conversation_id,
                images=turn_images,
                day_use=day_use_block,
                plan_on=plan_on,
                native_files=native_files,
                edu_sidebar=edu_sidebar,
            )
            text = result.final_text or result.error or "(empty)"
            await _finalize_run(
                run_id,
                status=result.status,
                error=result.error,
                final_text=result.final_text,
                task_id=task_id,
                user_prompt=prompt,
                change_proposal=getattr(result, "change_proposal", None),
                token_usage=getattr(result, "token_usage", None),
                bill_to=payer_for(principal),
            )
        payload = {
            "id": completion_id,
            "object": "chat.completion",
            "created": created,
            "model": model,
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": text},
                    "finish_reason": "stop",
                }
            ],
        }
        usage = _compat_usage_payload(
            prompt,
            text,
            (direct_usage if use_direct else getattr(result, "token_usage", None)),
        )
        if usage:
            payload["usage"] = usage
        if sidebar_web_hits is not None:
            payload["pico_web_search"] = sidebar_web_hits
        return payload

    async def event_stream() -> AsyncIterator[bytes]:
        def chunk(delta: dict, *, finish: str | None = None, usage: dict | None = None) -> bytes:
            body: dict[str, Any] = {
                "id": completion_id,
                "object": "chat.completion.chunk",
                "created": created,
                "model": model,
                "choices": [
                    {
                        "index": 0,
                        "delta": delta,
                        "finish_reason": finish,
                    }
                ],
            }
            if usage:
                body["usage"] = usage
            return _sse_chunk(body).encode()

        yield chunk({"role": "assistant"})

        # Direct model (moonshot/deepseek/*) → real token stream (GPT-like handfeel)
        use_direct = chat_only or (
            model not in {"pico-agent", "pico"} and not model.startswith("pico-")
        )
        if native_files and not json_only:
            use_direct = False
        if use_direct:
            from pico_orchestrator.provider import stream_chat

            task_id, run_id = await _ledger_task_run(
                principal=principal,
                prompt=prompt,
                model=model,
                conversation_id=conversation_id,
                workspace_id=workspace_id,
                skill_snapshot=skill_snapshot,
            )
            system = (
                sidebar_system
                if (json_only or edu_sidebar) and sidebar_system
                else (
                    "你是 Pico，面向学校场景的 AI 助手。"
                    "回答准确、结构清晰；需要分点时用简洁列表；中文优先。"
                    "不要编造不存在的学校数据。"
                    "若用户要求创建或生成纯文本文件（如 hello.txt），请在回复中用代码块输出完整内容，"
                    "格式为 ```file:文件名 换行 正文 换行```；中文说明可附在代码块外。"
                    "禁止用代码块或改后缀冒充 .html / .docx / .pptx；此类交付须走专用生成工具路径。"
                )
            )
            if project_instruction:
                system = system + "\n【项目约束】" + project_instruction
            delivery_instr = _instruction_with_delivery(
                skill_snapshot, prompt, delivery_plan
            )
            if delivery_instr:
                system = system + "\n" + delivery_instr
            if day_use_block:
                system = system + "\n\n" + day_use_block
            parts: list[str] = []
            stream_usage: dict[str, Any] = {}
            finalized = False
            try:
                async for piece in iter_with_idle_ticks(
                    stream_chat(
                        prompt,
                        max_tokens=effective_max_tokens,
                        history=history,
                        system=system,
                        model=model,
                        thinking=False if json_only else None,
                        usage_out=stream_usage,
                    )
                ):
                    if piece is None:
                        yield SSE_COMMENT_KEEPALIVE
                        continue
                    if piece:
                        parts.append(piece)
                        yield chunk({"content": piece})
                await _finalize_run(
                    run_id,
                    status="succeeded",
                    final_text="".join(parts),
                    task_id=task_id,
                    user_prompt=prompt,
                    token_usage=stream_usage or None,
                    bill_to=payer_for(principal),
                )
                finalized = True
            except (asyncio.CancelledError, GeneratorExit):
                await asyncio.shield(
                    _finalize_run(
                        run_id,
                        status="cancelled",
                        error="stream disconnected",
                        task_id=task_id,
                        bill_to=payer_for(principal),
                    )
                )
                finalized = True
                raise
            except Exception as e:  # noqa: BLE001
                yield chunk({"content": f"【错误】{user_message_for_error(str(e))}"})
                await _finalize_run(
                    run_id,
                    status="failed",
                    error=str(e),
                    task_id=task_id,
                    bill_to=payer_for(principal),
                )
                finalized = True
            finally:
                if not finalized:
                    await asyncio.shield(
                        _finalize_run(
                            run_id,
                            status="cancelled",
                            error="stream disconnected",
                            task_id=task_id,
                            bill_to=payer_for(principal),
                        )
                    )
            yield chunk(
                {},
                finish="stop",
                usage=_compat_usage_payload(prompt, "".join(parts), stream_usage or None),
            )
            yield b"data: [DONE]\n\n"
            return

        # pico-agent: progressive deltas from agent loop (not wait-then-fake-chunk)
        from pico_orchestrator.runtime import run_agent_runtime

        from app.db import init_db

        await init_db()
        factory = session_factory()
        task_id = new_id()
        run_id = new_id()
        async with factory() as session:
            session.add(
                TaskRow(
                    id=task_id,
                    school_id=principal.school_id,
                    membership_id=principal.membership_id,
                    title=prompt[:80],
                    conversation_id=conversation_id,
                    workspace_id=workspace_id,
                )
            )
            from app.db import _utcnow

            session.add(
                RunRow(
                    id=run_id,
                    task_id=task_id,
                    status="running",
                    prompt=prompt,
                    model=model,
                    started_at=_utcnow(),
                    token_usage_json=json.dumps(
                        {"skill_snapshot": skill_snapshot} if skill_snapshot else {},
                        ensure_ascii=False,
                    ),
                )
            )
            await session.commit()

        q: asyncio.Queue[tuple[str, object]] = asyncio.Queue()

        async def emit(event_type: str, payload: dict[str, Any]) -> None:
            if event_type == "thinking.delta":
                # Token-level thoughts: stream only. Do not flood the ledger.
                text = str(payload.get("text") or "")
                if text:
                    await q.put(("think", text))
                return
            async with factory() as session:
                await append_event(session, run_id, event_type, payload)
                # Checkpoint survives client detach (package B).
                if event_type == "tool.result":
                    tool_name = payload.get("name") or payload.get("tool") or "tool"
                    await append_event(
                        session,
                        run_id,
                        "run.checkpoint",
                        {
                            "kind": "tool.result",
                            "tool": tool_name,
                            "summary": str(
                                payload.get("summary") or payload.get("ok") or ""
                            )[:200],
                        },
                    )
            if event_type == "message.delta":
                text = str(payload.get("text") or "")
                if text:
                    await q.put(("delta", text))
            elif event_type in {
                "compaction.begin",
                "compaction.end",
                "compaction.failed",
                "ui.prompt.begin",
                "ui.prompt.end",
            }:
                # Process chrome only. 在整理上文 / 已压缩 / 在等你选 must not become the bubble.
                text = str(payload.get("text") or "").strip()
                if not text:
                    text = {
                        "compaction.begin": "在整理上文",
                        "compaction.end": "已压缩",
                        "compaction.failed": "压缩失败",
                        "ui.prompt.begin": "在等你选",
                        "ui.prompt.end": "已选",
                    }.get(event_type, "")
                if text:
                    await q.put(("status", f"{text}\n"))
            elif event_type == "plan.progress":
                from pico_orchestrator.human_package import public_progress_delta

                text = public_progress_delta(payload)
                if text:
                    await q.put(("delta", f"{text}\n"))
            elif event_type == "agent.step" and payload.get("phase") == "model":
                # G2: user main channel stays human-package only.
                # Tool/step process lives in ledger + ResultPanel timeline, not bubble.
                if payload.get("step") == 1:
                    await q.put(("status", "正在准备…\n"))
            elif event_type == "tool.call":
                # Ledger + TaskRunBar / ResultPanel already show 正在画/正在写.
                # Streaming those lines as content leaves them in the settled bubble.
                pass
            elif event_type == "tool.result":
                pass
            elif event_type == "run.heartbeat":
                elapsed = payload.get("elapsed_seconds")
                if elapsed is not None:
                    await q.put(("status", f"\n仍在处理…（已用时 {elapsed}s）\n"))
                else:
                    await q.put(("status", "\n仍在处理…\n"))
            elif event_type == "run.checkpoint":
                # Checkpoint is engineer state — do not spam the user bubble.
                pass

        async def is_cancelled() -> bool:
            async with factory() as session:
                run = await session.get(RunRow, run_id)
                return bool(run and (run.cancel_requested or run.status == "cancelled"))

        async def run() -> None:
            try:
                from app.artifact_store import LedgerArtifactStore

                # Detach-on mode uses durable wall so leave-and-return jobs can exceed 900s.
                skill_instr = _instruction_with_delivery(
                    skill_snapshot, prompt, delivery_plan
                )
                if settings.pico_run_detach_on_disconnect:
                    caps = settings.durable_run_caps(
                        allowed_tools=_resolve_allowed_tools(skill_snapshot, request_tools),
                        skill_instruction=skill_instr,
                    )
                else:
                    caps = settings.delivery_run_caps(
                        allowed_tools=_resolve_allowed_tools(skill_snapshot, request_tools),
                        skill_instruction=skill_instr,
                    )
                # Stream path must apply the same dual-mode policy as non-stream.
                caps = _caps_with_dual_mode(caps, model)
                caps = _caps_with_sidebar_thinking(caps, edu_sidebar=edu_sidebar)
                caps = _caps_with_plan(caps, plan_on)
                caps = _caps_with_images(caps, turn_images)
                # Stream path must apply the same landing min as non-stream.
                caps = _caps_with_landing_min(caps, delivery_plan, skill_snapshot)
                if edu_sidebar and client_system:
                    from dataclasses import replace as _dc_replace_sys_stream

                    caps = _dc_replace_sys_stream(caps, system_prompt=client_system)
                if day_use_block:
                    from dataclasses import replace as _dc_replace_day_stream

                    caps = _dc_replace_day_stream(caps, day_use=day_use_block)
                if skill_snapshot:
                    await emit("skill.snapshot", skill_snapshot)
                if delivery_plan is not None and getattr(
                    delivery_plan, "engineering", False
                ):
                    await emit(
                        "delivery.plan",
                        {
                            "multi_deliverable": delivery_plan.multi_deliverable,
                            "pipeline": delivery_plan.pipeline,
                            "revision": delivery_plan.revision,
                            "runnable_html": delivery_plan.runnable_html,
                            "min_artifacts": delivery_plan.min_artifacts,
                            "implicit_package": bool(
                                getattr(delivery_plan, "implicit_package", False)
                            ),
                            "structure_item_count": int(
                                getattr(delivery_plan, "structure_item_count", 0) or 0
                            ),
                            "prior_artifact_count": int(
                                getattr(delivery_plan, "prior_artifact_count", 0) or 0
                            ),
                        },
                    )
                await emit(
                    "run.durable",
                    {
                        "detach_on_disconnect": settings.pico_run_detach_on_disconnect,
                        "max_seconds": caps.max_seconds,
                        "policy": "client_is_subscriber",
                    },
                )
                from pico_orchestrator.llm_file_pass import remember_turn_files

                remember_turn_files(run_id, native_files)
                result = await run_agent_runtime(
                    use_pi_agent=settings.pico_pi_agent_runtime,
                    pi_agent_canary_principals=settings.pi_agent_canary_principal_set,
                    pi_agent_allow_all=settings.pi_agent_default_all,
                    use_kimi_agent=settings.legacy_kimi_enabled,
                    kimi_agent_canary_principals=(
                        settings.kimi_agent_canary_principal_set
                    ),
                    kimi_agent_allow_all=settings.kimi_agent_default_all,
                    legacy_agent_loop_emergency=settings.pico_legacy_agent_loop_emergency,
                    prompt=prompt,
                    principal=principal,
                    emit=emit,
                    is_cancelled=is_cancelled,
                    caps=caps,
                    history=history,
                    artifact_store=LedgerArtifactStore(
                        factory,
                        task_id=task_id,
                        run_id=run_id,
                        conversation_id=conversation_id,
                    ),
                    conversation_id=conversation_id,
                    persist_pi_session=True,
                    run_id=run_id,
                )
                await _finalize_run(
                    run_id,
                    status=result.status,
                    error=result.error,
                    final_text=result.final_text,
                    task_id=task_id,
                    user_prompt=prompt,
                    change_proposal=getattr(result, "change_proposal", None),
                    token_usage=getattr(result, "token_usage", None),
                    bill_to=payer_for(principal),
                )
                await q.put(("done", result))
            except asyncio.CancelledError:
                # Only explicit task.cancel() (legacy kill path) lands here.
                await asyncio.shield(
                    _finalize_run(
                        run_id,
                        status="cancelled",
                        error="run cancelled",
                        task_id=task_id,
                        bill_to=payer_for(principal),
                    )
                )
                raise
            except Exception as e:  # noqa: BLE001
                # If stop already requested, do not report failed+sqlite noise.
                factory_local = session_factory()
                cancel_hit = False
                async with factory_local() as session:
                    run = await session.get(RunRow, run_id)
                    cancel_hit = bool(run and (run.cancel_requested or run.status == "cancelled"))
                if cancel_hit:
                    await _finalize_run(
                        run_id,
                        status="cancelled",
                        error=None,
                        task_id=task_id,
                        bill_to=payer_for(principal),
                    )
                    await q.put(
                        (
                            "done",
                            type(
                                "R",
                                (),
                                {"final_text": "", "error": None, "status": "cancelled"},
                            )(),
                        )
                    )
                else:
                    await _finalize_run(
                        run_id,
                        status="failed",
                        error=str(e),
                        task_id=task_id,
                        bill_to=payer_for(principal),
                    )
                    await q.put(("error", e))

        bg_task = asyncio.create_task(run())
        # Share drain set with run_service so deploy SIGTERM can soft-wait.
        from app.run_service import _track_inflight

        _track_inflight(bg_task)
        saw_text = False
        pending_status: list[str] = []
        native_usage: dict[str, int] | None = None
        detach = settings.pico_run_detach_on_disconnect
        last_wire = time.monotonic()
        try:
            while True:
                try:
                    kind, payload = await asyncio.wait_for(q.get(), timeout=1.0)
                except TimeoutError:
                    if bg_task.done():
                        # Drain any terminal item that raced the timeout.
                        if not q.empty():
                            kind, payload = q.get_nowait()
                        else:
                            break
                    else:
                        if time.monotonic() - last_wire >= SSE_KEEPALIVE_SECONDS:
                            last_wire = time.monotonic()
                            yield SSE_COMMENT_KEEPALIVE
                        continue
                if kind == "delta":
                    saw_text = True
                    # Drop buffered system chrome (「正在准备…」/heartbeat) —
                    # never leak it into the settled bubble (#461 L1).
                    pending_status.clear()
                    last_wire = time.monotonic()
                    yield chunk({"content": str(payload)})
                elif kind == "think":
                    # Official Pi thinking_delta → OpenAI reasoning_content.
                    # Must not become the product bubble (`content`).
                    last_wire = time.monotonic()
                    yield chunk(
                        {
                            "reasoning_content": str(payload),
                            "reasoning": str(payload),
                        }
                    )
                elif kind == "status":
                    # Buffer status chrome; only flush on the failure path where
                    # no product text ever arrives (user still sees progress).
                    if not saw_text:
                        pending_status.append(str(payload))
                elif kind == "error":
                    if not saw_text and pending_status:
                        for p in pending_status:
                            last_wire = time.monotonic()
                            yield chunk({"content": p})
                    last_wire = time.monotonic()
                    yield chunk({"content": f"【错误】{user_message_for_error(str(payload))}"})
                    break
                elif kind == "done":
                    result = payload
                    native_usage = _compat_usage_payload(
                        prompt,
                        getattr(result, "final_text", None) or "",
                        getattr(result, "token_usage", None),
                    )
                    if not saw_text:
                        # final_text is already complete + human-package cleaned;
                        # buffered chrome must NOT be prepended (would re-pollute
                        # the bubble with「正在准备…」).
                        text = getattr(result, "final_text", None) or ""
                        if not text and getattr(result, "status", None) == "failed":
                            # Prefer Chinese user_message for timeout / max_steps / token_cap
                            text = user_message_for_error(getattr(result, "error", None))
                        if not text:
                            text = getattr(result, "error", None) or ""
                        if not str(text).strip():
                            text = user_message_for_error(
                                "Pi agent received empty model response",
                                code="pi.empty_response",
                            )
                        # small pieces if only final blob
                        step = 32
                        for i in range(0, len(text), step):
                            last_wire = time.monotonic()
                            yield chunk({"content": text[i : i + step]})
                    break
        except (asyncio.CancelledError, GeneratorExit):
            # Client closed the SSE. Durable default: keep bg_task alive.
            if detach and not bg_task.done():
                await asyncio.shield(
                    emit(
                        "run.client_detached",
                        {
                            "reason": "sse_disconnect",
                            "message": "客户端已断开；任务在云端继续。",
                            "run_id": run_id,
                            "task_id": task_id,
                        },
                    )
                )
                # Do not cancel bg_task — ledger remains source of truth.
                return
            if not bg_task.done():
                bg_task.cancel()
            raise
        finally:
            if not detach:
                # Legacy: stream lifetime owns the job.
                if not bg_task.done():
                    bg_task.cancel()
                try:
                    await bg_task
                except asyncio.CancelledError:
                    pass
                except Exception as wait_err:  # noqa: BLE001
                    _ = wait_err
            elif bg_task.done():
                # Detach mode but job already finished while client was connected.
                with suppress(Exception):
                    await bg_task

        if detach and not bg_task.done():
            # Client left the generator normally without consuming done — keep job.
            await emit(
                "run.client_detached",
                {
                    "reason": "stream_end_while_running",
                    "message": "客户端流结束；任务在云端继续。",
                    "run_id": run_id,
                    "task_id": task_id,
                },
            )
            return

        yield chunk({}, finish="stop", usage=native_usage)
        yield b"data: [DONE]\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers=dict(SSE_STREAM_HEADERS),
    )
