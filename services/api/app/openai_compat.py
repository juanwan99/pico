"""OpenAI-compatible /v1/chat/completions for LibreChat and API clients."""

from __future__ import annotations

import asyncio
import json
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
from pico_orchestrator.day_use import apply_day_use
from pico_orchestrator.user_errors import user_message_for_error
from pydantic import BaseModel

from app.auth import (
    LEGACY_PROXY_MEMBERSHIP_ID,
    Principal,
    decode_token,
    enforce_scope,
    prompt_membership_conflicts_header,
    scope_proxy_principal,
)
from app.db import RunRow, TaskRow, append_event, new_id, session_factory
from app.settings import Settings, get_settings

router = APIRouter(tags=["openai-compat"])


class ChatMessage(BaseModel):
    role: str
    content: str | list[Any] | None = ""
    # LibreChat AgentClient may put vision parts on the message instead of
    # (or as well as) content[]. Extra fields were previously dropped.
    image_urls: list[Any] | None = None


class ChatCompletionRequest(BaseModel):
    model: str | None = None
    messages: list[ChatMessage]
    stream: bool = False
    temperature: float | None = None
    max_tokens: int | None = None
    user: str | None = None  # LibreChat may pass conversation id
    metadata: dict[str, Any] | None = None
    web_search: bool = False
    tools: list[Any] | None = None
    allowed_tools: list[str] | None = None


EDU_SIDEBAR_MARK = "附属，不是用户要求"


def _content_text(content: str | list[Any] | None) -> str:
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    # Text only. Image parts are kept via last_user_images → RunCaps.images.
    parts: list[str] = []
    for p in content:
        if isinstance(p, dict) and p.get("type") == "text":
            parts.append(str(p.get("text") or ""))
        elif isinstance(p, str):
            parts.append(p)
    return "\n".join(parts)


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


def _estimated_usage(prompt: str, completion: str) -> dict[str, int | bool]:
    # Upstream streaming adapters do not expose provider usage yet. This is an
    # explicit estimate rather than the previous misleading constant zero.
    prompt_tokens = max(1, (len(prompt) + 3) // 4)
    completion_tokens = max(1, (len(completion) + 3) // 4)
    return {
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": prompt_tokens + completion_tokens,
        "estimated": True,
    }



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
        "usage": _estimated_usage(prompt, title),
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

    - pico-fast: deepseek-v4-flash, thinking off, tighter steps/tokens.
    - pico-deep: deepseek-reasoner, thinking on + circuit breaker armed.
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
    )
