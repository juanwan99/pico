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
from pico_orchestrator.user_errors import user_message_for_error
from pydantic import BaseModel

from app.auth import (
    LEGACY_PROXY_MEMBERSHIP_ID,
    Principal,
    decode_token,
    enforce_scope,
    scope_proxy_principal,
)
from app.db import RunRow, TaskRow, append_event, new_id, session_factory
from app.settings import Settings, get_settings

router = APIRouter(tags=["openai-compat"])


class ChatMessage(BaseModel):
    role: str
    content: str | list[Any] | None = ""


class ChatCompletionRequest(BaseModel):
    model: str | None = None
    messages: list[ChatMessage]
    stream: bool = False
    temperature: float | None = None
    max_tokens: int | None = None
    user: str | None = None  # LibreChat may pass conversation id
    metadata: dict[str, Any] | None = None


def _content_text(content: str | list[Any] | None) -> str:
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    # multimodal array — take text parts
    parts: list[str] = []
    for p in content:
        if isinstance(p, dict) and p.get("type") == "text":
            parts.append(str(p.get("text") or ""))
        elif isinstance(p, str):
            parts.append(p)
    return "\n".join(parts)


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
        "kimi-k3": "kimi-k3",
        "deepseek": "deepseek-chat",
        "deepseek-chat": "deepseek-chat",
        "deepseek-reasoner": "deepseek-reasoner",
    }
    normalized = aliases.get(requested.lower(), requested)
    if normalized.lower() == "auto":
        return None

    from pico_orchestrator.provider import KNOWN_DEEPSEEK_MODELS, KNOWN_KIMI_MODELS

    allowed = {"pico-agent", *KNOWN_DEEPSEEK_MODELS, *KNOWN_KIMI_MODELS}
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
    allowed = {_normalized_model(item) for item in settings.allowed_model_list}
    if _normalized_model(model) not in allowed:
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
        target = (settings.deepseek_model or "deepseek-chat").strip() or "deepseek-chat"
        if not allowed or _normalized_model(target) in allowed:
            return target
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
        text = _content_text(m.content).strip()
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
        r"```(?:file:)?([A-Za-z0-9._\-]+\.[A-Za-z0-9]{1,12})\s*\n([\s\S]*?)```",
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
        r"(?:创建|生成|写|保存).{0,40}?([A-Za-z0-9._\-]+\.(?:txt|md|csv|json))",
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


def _wants_deliverable_document(prompt: str) -> bool:
    """Detect teacher NL asking for HTML / Word / PPT deliverables.

    Must catch plain Chinese phrasing without tool names or .docx suffixes
    (S1.5 / S2.2: 「重新生成可下载 Word」 must not fall into direct-chat fake success).
    """
    import re

    text = prompt or ""
    if not text.strip():
        return False
    return bool(
        re.search(
            r"\.(?:html?|docx|pptx)\b|"
            r"\b(?:html|docx|pptx|powerpoint)\b|"
            r"幻灯片|课件|网页文件|word\s*文档|PPT|Power\s*Point|"
            # 生成 + type (allow longer Chinese fillers between verb and type)
            r"生成.{0,40}(?:html|网页|word|docx|ppt|pptx|幻灯片|文档)|"
            # 可下载/下载/导出/改版 + Word/文档
            r"(?:可下载|下载|导出|重新生成|改一版|改版|一页).{0,24}"
            r"(?:Word|word|WORD|文档|docx|PPT|pptx|html|幻灯片|课件)|"
            # Word/docx 文件|文档|下载
            r"(?:Word|word|WORD|docx|PPT|pptx).{0,16}(?:文件|文档|下载)|"
            # bare “方案/说明/通知 Word” without 生成 immediately nearby
            r"(?:方案|说明|通知|报告|小结).{0,8}(?:Word|word|docx|PPT|pptx)",
            text,
            re.IGNORECASE,
        )
    )


def _resolve_skill_for_prompt(
    raw_prompt: str,
    skill_snapshot: dict[str, Any] | None,
    *,
    prior_artifact_titles: list[str] | None = None,
) -> tuple[dict[str, Any] | None, Any]:
    """Attach auto skill for engineering delivery without overriding explicit skills.

    Returns (skill_snapshot, DeliveryPlan).
    """
    from pico_orchestrator.delivery_policy import (
        ENGINEERING_SKILL_ID,
        analyze_delivery,
    )
    from pico_orchestrator.skill_policy import snapshot_for_skill

    plan = analyze_delivery(
        raw_prompt, prior_artifact_titles=prior_artifact_titles
    )
    if skill_snapshot is not None:
        return skill_snapshot, plan
    # Multi-file / pipeline / runnable → engineering package (includes workspace_write).
    if plan.force_agent:
        return snapshot_for_skill(ENGINEERING_SKILL_ID), plan
    # Single Office/HTML deliverable → classic deliverable skill.
    if _wants_deliverable_document(raw_prompt):
        return snapshot_for_skill("skill-deliverable"), plan
    return None, plan


def _instruction_with_delivery(
    skill_snapshot: dict[str, Any] | None,
    prompt: str,
    plan: Any | None = None,
    *,
    prior_artifact_titles: list[str] | None = None,
) -> str:
    """Merge skill catalog instruction with generic engineering-delivery discipline."""
    from pico_orchestrator.delivery_policy import analyze_delivery
    from pico_orchestrator.skill_policy import instruction_for_snapshot

    base = instruction_for_snapshot(skill_snapshot)
    plan = (
        plan
        if plan is not None
        else analyze_delivery(prompt, prior_artifact_titles=prior_artifact_titles)
    )
    extra = getattr(plan, "instruction", "") or ""
    if not extra or not getattr(plan, "engineering", False):
        return base
    if base:
        return f"{base}\n{extra}"
    return extra


async def _prior_artifact_titles_for_principal(principal: Any) -> list[str]:
    """Session artifact graph for revision binding (D2). Best-effort, never raises."""
    try:
        from pico_orchestrator.delivery_policy import is_bookkeeping_title
        from sqlalchemy import select

        from app.db import ArtifactRow, TaskRow

        factory = session_factory()
        async with factory() as session:
            rows = await session.execute(
                select(ArtifactRow.title)
                .join(TaskRow, ArtifactRow.task_id == TaskRow.id)
                .where(
                    TaskRow.school_id == principal.school_id,
                    TaskRow.membership_id == principal.membership_id,
                )
                .order_by(ArtifactRow.created_at.desc())
                .limit(40)
            )
            titles: list[str] = []
            seen: set[str] = set()
            for (title,) in rows.all():
                t = str(title or "").strip()
                if not t or is_bookkeeping_title(t):
                    continue
                key = t.lower()
                if key in seen:
                    continue
                seen.add(key)
                titles.append(t)
            return titles
    except Exception:  # noqa: BLE001 — policy must not fail chat
        return []


async def _finalize_run(
    run_id: str,
    *,
    status: str,
    error: str | None = None,
    final_text: str | None = None,
    task_id: str | None = None,
    user_prompt: str | None = None,
    change_proposal: dict | None = None,
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
                        "kind": "file",
                    },
                    commit=False,
                )

            summary_key = ("doc", "回复摘要")
            if summary_key not in existing_keys:
                artifact = ArtifactRow(
                    id=new_id(),
                    task_id=run.task_id,
                    run_id=run_id,
                    kind="doc",
                    title="回复摘要",
                    inline=final_text[:8000],
                )
                session.add(artifact)
                await append_event(
                    session,
                    run_id,
                    "artifact.created",
                    {
                        "artifact_id": artifact.id,
                        "title": "回复摘要",
                        "kind": "doc",
                    },
                    commit=False,
                )
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
        from pico_orchestrator.delivery_policy import (
            analyze_delivery,
            count_user_artifacts,
            is_bookkeeping_title,
        )

        prompt_for_plan = user_prompt or run.prompt or ""
        # Prefer principal-scoped prior titles when available on the run's school/membership.
        prior_titles: list[str] = []
        try:
            task = await session.get(TaskRow, run.task_id) if run.task_id else None
            if task is not None:

                class _P:
                    school_id = task.school_id
                    membership_id = task.membership_id

                prior_titles = await _prior_artifact_titles_for_principal(_P())
        except Exception:  # noqa: BLE001
            prior_titles = []
        plan = analyze_delivery(
            prompt_for_plan, prior_artifact_titles=prior_titles
        )
        art_rows = await session.execute(
            select(ArtifactRow.kind, ArtifactRow.title, ArtifactRow.byte_size).where(
                ArtifactRow.run_id == run_id
            )
        )
        art_list = list(art_rows.all())
        titles = [
            str(title or "")
            for _kind, title, _bs in art_list
            if title and not is_bookkeeping_title(str(title))
        ]
        user_art_count = count_user_artifacts(art_list)

        # G5 observability: machine-readable delivery summary (always, when we have a plan).
        if status in ("succeeded", "failed", "cancelled"):
            await append_event(
                session,
                run_id,
                "delivery.summary",
                {
                    "status": status,
                    "artifact_count": user_art_count,
                    "min_required": plan.min_artifacts,
                    "titles": titles[:40],
                    "multi_deliverable": plan.multi_deliverable,
                    "pipeline": plan.pipeline,
                    "revision": plan.revision,
                    "runnable_html": plan.runnable_html,
                    "implicit_package": bool(
                        getattr(plan, "implicit_package", False)
                    ),
                    "structure_item_count": int(
                        getattr(plan, "structure_item_count", 0) or 0
                    ),
                    "prior_artifact_count": int(
                        getattr(plan, "prior_artifact_count", 0) or 0
                    ),
                    "ok": (
                        user_art_count >= plan.min_artifacts
                        if plan.min_artifacts > 0
                        else True
                    ),
                    "human_titles": titles[:40],
                    "note": (
                        "Prefer run.status + delivery.summary + artifact list over "
                        "client stream timeout alone. "
                        "Scripts: scripts/wait_delivery_summary.py. "
                        "Human lens: open files in app/browser; L0≠人类可用."
                    ),
                },
                commit=False,
            )

        # S2.2: classic Office/HTML deliverable skill without a real protected file.
        skill_name = (
            skill_snapshot.get("name") if isinstance(skill_snapshot, dict) else None
        )
        if (
            skill_name in {"skill.deliverable", "skill.engineering_delivery"}
            and status == "succeeded"
            and (
                _wants_deliverable_document(prompt_for_plan)
                or plan.runnable_html
            )
            and plan.min_artifacts <= 1
            and not plan.multi_deliverable
            and not plan.pipeline
        ):
            has_real_file = False
            for kind, title, byte_size in art_list:
                title_s = str(title or "")
                kind_s = str(kind or "").lower()
                if is_bookkeeping_title(title_s):
                    continue
                if kind_s in {"docx", "html", "htm", "pptx"}:
                    has_real_file = True
                    break
                lower = title_s.lower()
                if lower.endswith((".docx", ".html", ".htm", ".pptx")) and (
                    byte_size or 0
                ) > 0:
                    has_real_file = True
                    break
            if not has_real_file:
                run.status = "failed"
                run.error = (
                    "交件未生成可下载的真文件（HTML/Word/PPT）。"
                    "请点「再跑一次」或重新描述「生成可下载 Word/HTML」；"
                    "纯文字摘要不能当作文件交付。"
                )
                await append_event(
                    session,
                    run_id,
                    "run.status",
                    {
                        "status": "failed",
                        "reason": "deliverable_missing_artifact",
                        "runtime": "fail-closed",
                    },
                    commit=False,
                )
                status = "failed"

        # G1/G2/G4: multi-artifact / pipeline / revision min count fail-closed.
        if status == "succeeded" and plan.min_artifacts > 0 and user_art_count < plan.min_artifacts:
            run.status = "failed"
            run.error = (
                f"工程交付未满足多产物要求：需要至少 {plan.min_artifacts} 个独立文件，"
                f"本轮仅 {user_art_count} 个。"
                "请分文件写入（禁止单长文多标题冒充），再跑一次。"
            )
            await append_event(
                session,
                run_id,
                "run.status",
                {
                    "status": "failed",
                    "reason": "delivery_min_artifacts",
                    "min_required": plan.min_artifacts,
                    "artifact_count": user_art_count,
                    "runtime": "fail-closed",
                },
                commit=False,
            )

        await session.commit()


async def _run_and_collect(
    prompt: str,
    principal: Principal,
    settings: Settings,
    *,
    run_id: str,
    history: list[dict[str, Any]] | None = None,
    skill_snapshot: dict[str, Any] | None = None,
    delivery_plan: Any | None = None,
) -> Any:
    from pico_orchestrator.runtime import run_agent_runtime

    from app.artifact_store import LedgerArtifactStore

    factory = session_factory()

    async def emit(event_type: str, payload: dict[str, Any]) -> None:
        async with factory() as session:
            await append_event(session, run_id, event_type, payload)

    async def is_cancelled() -> bool:
        async with factory() as session:
            run = await session.get(RunRow, run_id)
            return bool(run and (run.cancel_requested or run.status == "cancelled"))

    caps = settings.delivery_run_caps(
        allowed_tools=list(skill_snapshot.get("tools") or []) if skill_snapshot else None,
        skill_instruction=_instruction_with_delivery(
            skill_snapshot, prompt, delivery_plan
        ),
    )
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
        artifact_store=LedgerArtifactStore(factory, run_id=run_id),
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
    settings: Settings = Depends(get_settings),
):
    import re

    principal = _principal_from_auth(authorization, settings)
    raw_for_user = _last_user_prompt(body.messages)
    m_user = re.search(r"【Pico-User:([^】]+)】", raw_for_user)
    marker_membership = m_user.group(1).strip() if m_user else None
    if (
        principal.raw.get("proxy")
        and marker_membership
        and marker_membership != (x_pico_membership_id or "").strip()
    ):
        raise HTTPException(status_code=403, detail="proxy membership mismatch")
    principal = scope_proxy_principal(principal, x_pico_membership_id)
    enforce_scope(principal, "ai:run")
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
    # D2: bind revision to session artifact graph (prior deliverables).
    prior_titles = await _prior_artifact_titles_for_principal(principal)
    # Engineering multi/pipeline/runnable OR classic Office/HTML → force agent tool path.
    skill_snapshot, delivery_plan = _resolve_skill_for_prompt(
        raw_prompt, skill_snapshot, prior_artifact_titles=prior_titles
    )
    conversation_id = _conversation_id_from(body, x_conversation_id)
    workspace_id = _workspace_id_from(body, x_workspace_id)
    # strip ledger markers from model-visible prompt; project instruction → system
    m_proj = re.search(r"【项目指令：([^】]+)】", raw_prompt)
    project_instruction = m_proj.group(1).strip() if m_proj else ""
    prompt = re.sub(r"【Pico-Convo:[^】]+】", "", raw_prompt)
    prompt = re.sub(r"【Pico-User:[^】]+】", "", prompt)
    prompt = re.sub(r"【工作空间：[^】]+】", "", prompt)
    prompt = re.sub(r"【权限：[^】]+】", "", prompt)
    prompt = re.sub(r"【模型偏好：[^】]+】", "", prompt)
    prompt = re.sub(r"【项目指令：[^】]+】", "", prompt).strip() or raw_prompt
    max_chars = int(getattr(settings, "pico_chat_max_prompt_chars", 12000) or 12000)
    if len(prompt) > max_chars:
        # Explicit reject — never silent-truncate then execute (stage #260 A1).
        raise HTTPException(
            status_code=400,
            detail=(
                f"输入过长（{len(prompt)} 字，上限 {max_chars} 字）。"
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

            return StreamingResponse(title_event_stream(), media_type="text/event-stream")
        return _title_completion_payload(
            completion_id=completion_id,
            created=created,
            model=model,
            title=title,
            prompt=prompt,
        )

    history = _history_for_agent(body.messages)
    model = _model_preference_from_prompt(raw_prompt) or body.model or settings.deepseek_model or settings.kimi_model or "pico-agent"
    if skill_snapshot and skill_snapshot.get("tools"):
        model = "pico-agent"
    # Residual LibreChat prefs may still say kimi-k2.x after product default
    # moved to DeepSeek. Remount onto the product brain when Kimi is not in the
    # production allowlist so default-path chat does not 400.
    model = _coerce_default_model(model, settings)
    _assert_model_allowed(model, settings)
    # Direct model = short tier; pico-agent = delivery tier for token ceiling.
    use_direct = model not in {"pico-agent", "pico"} and not model.startswith("pico-")
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
                "你是 Pico，面向学校场景的 AI 助手。"
                "回答准确、结构清晰；需要分点时用简洁列表；中文优先。"
                "不要编造不存在的学校数据。"
                "若用户要求创建或生成纯文本文件（如 hello.txt），请在回复中用代码块输出完整内容，"
                "格式为 ```file:文件名 换行 正文 换行```；中文说明可附在代码块外。"
                "禁止用代码块或改后缀冒充 .html / .docx / .pptx；此类交付须走专用生成工具路径。"
            )
            if project_instruction:
                system = system + "\n【项目约束】" + project_instruction
            delivery_instr = _instruction_with_delivery(
                skill_snapshot, prompt, delivery_plan
            )
            if delivery_instr:
                system = system + "\n" + delivery_instr
            parts: list[str] = []
            try:
                async for piece in stream_chat(
                    prompt,
                    max_tokens=effective_max_tokens,
                    history=history,
                    system=system,
                    model=model,
                ):
                    if piece:
                        parts.append(piece)
                text = "".join(parts) or "(empty)"
                await _finalize_run(run_id, status="succeeded", final_text=text, task_id=task_id, user_prompt=prompt)
            except Exception as e:  # noqa: BLE001
                text = f"【错误】{user_message_for_error(str(e))}"
                await _finalize_run(run_id, status="failed", error=str(e), task_id=task_id)
        else:
            result = await _run_and_collect(
                prompt,
                principal,
                settings,
                run_id=run_id,
                history=history,
                skill_snapshot=skill_snapshot,
                delivery_plan=delivery_plan,
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
            )
        return {
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
            "usage": _estimated_usage(prompt, text),
        }

    async def event_stream() -> AsyncIterator[bytes]:
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

        # Direct model (moonshot/deepseek/*) → real token stream (GPT-like handfeel)
        use_direct = model not in {"pico-agent", "pico"} and not model.startswith("pico-")
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
                "你是 Pico，面向学校场景的 AI 助手。"
                "回答准确、结构清晰；需要分点时用简洁列表；中文优先。"
                "不要编造不存在的学校数据。"
                "若用户要求创建或生成纯文本文件（如 hello.txt），请在回复中用代码块输出完整内容，"
                "格式为 ```file:文件名 换行 正文 换行```；中文说明可附在代码块外。"
                "禁止用代码块或改后缀冒充 .html / .docx / .pptx；此类交付须走专用生成工具路径。"
            )
            if project_instruction:
                system = system + "\n【项目约束】" + project_instruction
            delivery_instr = _instruction_with_delivery(
                skill_snapshot, prompt, delivery_plan
            )
            if delivery_instr:
                system = system + "\n" + delivery_instr
            parts: list[str] = []
            finalized = False
            try:
                async for piece in stream_chat(
                    prompt,
                    max_tokens=effective_max_tokens,
                    history=history,
                    system=system,
                    model=model,
                ):
                    if piece:
                        parts.append(piece)
                        yield chunk({"content": piece})
                await _finalize_run(
                    run_id,
                    status="succeeded",
                    final_text="".join(parts),
                    task_id=task_id,
                    user_prompt=prompt,
                )
                finalized = True
            except (asyncio.CancelledError, GeneratorExit):
                await asyncio.shield(
                    _finalize_run(
                        run_id,
                        status="cancelled",
                        error="stream disconnected",
                        task_id=task_id,
                    )
                )
                finalized = True
                raise
            except Exception as e:  # noqa: BLE001
                yield chunk({"content": f"【错误】{user_message_for_error(str(e))}"})
                await _finalize_run(run_id, status="failed", error=str(e), task_id=task_id)
                finalized = True
            finally:
                if not finalized:
                    await asyncio.shield(
                        _finalize_run(
                            run_id,
                            status="cancelled",
                            error="stream disconnected",
                            task_id=task_id,
                        )
                    )
            yield chunk({}, finish="stop")
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
            elif event_type == "agent.step" and payload.get("phase") == "model":
                # light status for first step only — avoid spam
                if payload.get("step") == 1:
                    await q.put(("status", "正在思考…\n"))
                elif isinstance(payload.get("step"), int) and payload["step"] > 1:
                    await q.put(("status", f"\n〔步骤 {payload['step']}〕\n"))
            elif event_type == "tool.call":
                name = payload.get("name") or payload.get("tool") or "tool"
                await q.put(("status", f"\n〔调用工具 {name}〕\n"))
            elif event_type == "tool.result":
                await q.put(("status", "〔工具完成〕\n"))
            elif event_type == "run.heartbeat":
                elapsed = payload.get("elapsed_seconds")
                if elapsed is not None:
                    await q.put(("status", f"\n〔仍在处理… 已用时 {elapsed}s〕\n"))
                else:
                    await q.put(("status", "\n〔仍在处理…〕\n"))
            elif event_type == "run.checkpoint":
                await q.put(("status", "\n〔检查点已保存〕\n"))

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
                        allowed_tools=(
                            list(skill_snapshot.get("tools") or []) if skill_snapshot else None
                        ),
                        skill_instruction=skill_instr,
                    )
                else:
                    caps = settings.delivery_run_caps(
                        allowed_tools=(
                            list(skill_snapshot.get("tools") or []) if skill_snapshot else None
                        ),
                        skill_instruction=skill_instr,
                    )
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
                    ),
                )
                await _finalize_run(
                    run_id,
                    status=result.status,
                    error=result.error,
                    final_text=result.final_text,
                    task_id=task_id,
                    user_prompt=prompt,
                    change_proposal=getattr(result, "change_proposal", None),
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
                    )
                    await q.put(("error", e))

        bg_task = asyncio.create_task(run())
        saw_text = False
        detach = settings.pico_run_detach_on_disconnect
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
                        continue
                if kind == "delta":
                    saw_text = True
                    yield chunk({"content": str(payload)})
                elif kind == "status":
                    # only show status if no answer yet (tool path UX)
                    if not saw_text:
                        yield chunk({"content": str(payload)})
                elif kind == "error":
                    yield chunk({"content": f"【错误】{user_message_for_error(str(payload))}"})
                    break
                elif kind == "done":
                    result = payload
                    if not saw_text:
                        text = getattr(result, "final_text", None) or ""
                        if not text and getattr(result, "status", None) == "failed":
                            # Prefer Chinese user_message for timeout / max_steps / token_cap
                            text = user_message_for_error(getattr(result, "error", None))
                        if not text:
                            text = getattr(result, "error", None) or ""
                        # small pieces if only final blob
                        step = 32
                        for i in range(0, len(text), step):
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

        yield chunk({}, finish="stop")
        yield b"data: [DONE]\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")
