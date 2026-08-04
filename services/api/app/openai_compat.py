"""OpenAI-compatible /v1/chat/completions for LibreChat and API clients."""

from __future__ import annotations

import asyncio
import json
import time
import uuid
from collections.abc import AsyncIterator
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
    }
    normalized = aliases.get(requested.lower(), requested)
    if normalized.lower() == "auto":
        return None

    from pico_orchestrator.provider import KNOWN_KIMI_MODELS

    allowed = {"pico-agent", *KNOWN_KIMI_MODELS}
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
    """Detect teacher NL asking for HTML / Word / PPT deliverables."""
    import re

    text = prompt or ""
    return bool(
        re.search(
            r"\.(?:html?|docx|pptx)\b|"
            r"\b(?:html|docx|pptx|powerpoint)\b|"
            r"幻灯片|课件|网页文件|word\s*文档|PPT|Power\s*Point|"
            r"生成\s*(?:html|网页|word|docx|ppt|pptx|幻灯片)",
            text,
            re.IGNORECASE,
        )
    )


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

    from app.db import ArtifactRow, ChangeProposalRow, EventRow, _utcnow
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
        await session.commit()


async def _run_and_collect(
    prompt: str,
    principal: Principal,
    settings: Settings,
    *,
    run_id: str,
    history: list[dict[str, Any]] | None = None,
    skill_snapshot: dict[str, Any] | None = None,
) -> Any:
    from pico_orchestrator.runner import RunCaps
    from pico_orchestrator.runtime import run_agent_runtime
    from pico_orchestrator.skill_policy import instruction_for_snapshot

    from app.artifact_store import LedgerArtifactStore

    factory = session_factory()

    async def emit(event_type: str, payload: dict[str, Any]) -> None:
        async with factory() as session:
            await append_event(session, run_id, event_type, payload)

    async def is_cancelled() -> bool:
        async with factory() as session:
            run = await session.get(RunRow, run_id)
            return bool(run and (run.cancel_requested or run.status == "cancelled"))

    caps = RunCaps(
        max_seconds=settings.pico_run_max_seconds,
        max_tokens=settings.pico_run_max_tokens,
        max_retries=settings.pico_run_max_retries,
        allowed_tools=list(skill_snapshot.get("tools") or []) if skill_snapshot else None,
        skill_instruction=instruction_for_snapshot(skill_snapshot),
    )
    if skill_snapshot:
        await emit("skill.snapshot", skill_snapshot)
    result = await run_agent_runtime(
        use_kimi_agent=settings.pico_kimi_agent_runtime,
        kimi_agent_canary_principals=(
            settings.kimi_agent_runtime_canary_entries
        ),
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
    from pico_orchestrator.provider import DEFAULT_KIMI_MODEL, KNOWN_KIMI_MODELS

    default = settings.kimi_model or DEFAULT_KIMI_MODEL
    ids = []
    for mid in [default, *KNOWN_KIMI_MODELS, "pico-agent"]:
        if mid not in ids:
            ids.append(mid)
    return {
        "object": "list",
        "data": [
            {"id": mid, "object": "model", "owned_by": "pico-kimi" if mid != "pico-agent" else "pico"}
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
        instruction_for_snapshot,
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
    # Teacher NL asking for HTML/Word/PPT → force tool path (generate_*), not direct chat.
    if not skill_snapshot and _wants_deliverable_document(raw_prompt):
        skill_snapshot = snapshot_for_skill("skill-deliverable")
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
    model = _model_preference_from_prompt(raw_prompt) or body.model or settings.kimi_model or "pico-agent"
    if skill_snapshot and skill_snapshot.get("tools"):
        model = "pico-agent"
    _assert_model_allowed(model, settings)
    effective_max_tokens = _effective_max_tokens(body.max_tokens, settings.pico_run_max_tokens)
    completion_id = f"chatcmpl-{uuid.uuid4().hex[:24]}"
    created = int(time.time())

    # Direct Kimi (or DeepSeek) for non-agent models — real HTTPS API, not mock
    use_direct = model not in {"pico-agent", "pico"} and not model.startswith("pico-")
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
            if skill_snapshot:
                system = system + "\n" + instruction_for_snapshot(skill_snapshot)
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
            if skill_snapshot:
                system = system + "\n" + instruction_for_snapshot(skill_snapshot)
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
        from pico_orchestrator.runner import RunCaps
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
            if event_type == "message.delta":
                text = str(payload.get("text") or "")
                if text:
                    await q.put(("delta", text))
            elif event_type == "agent.step" and payload.get("phase") == "model":
                # light status for first step only — avoid spam
                if payload.get("step") == 1:
                    await q.put(("status", "正在思考…\n"))
            elif event_type == "tool.call":
                name = payload.get("name") or payload.get("tool") or "tool"
                await q.put(("status", f"\n〔调用工具 {name}〕\n"))
            elif event_type == "tool.result":
                await q.put(("status", "〔工具完成〕\n"))

        async def is_cancelled() -> bool:
            async with factory() as session:
                run = await session.get(RunRow, run_id)
                return bool(run and (run.cancel_requested or run.status == "cancelled"))

        async def run() -> None:
            try:
                from app.artifact_store import LedgerArtifactStore

                caps = RunCaps(
                    max_seconds=settings.pico_run_max_seconds,
                    max_tokens=settings.pico_run_max_tokens,
                    max_retries=settings.pico_run_max_retries,
                    allowed_tools=list(skill_snapshot.get("tools") or []) if skill_snapshot else None,
                    skill_instruction=instruction_for_snapshot(skill_snapshot),
                )
                if skill_snapshot:
                    await emit("skill.snapshot", skill_snapshot)
                result = await run_agent_runtime(
                    use_kimi_agent=settings.pico_kimi_agent_runtime,
                    kimi_agent_canary_principals=(
                        settings.kimi_agent_runtime_canary_entries
                    ),
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
                await asyncio.shield(
                    _finalize_run(
                        run_id,
                        status="cancelled",
                        error="stream disconnected",
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
                    await q.put(("done", type("R", (), {"final_text": "", "error": None, "status": "cancelled"})()))
                else:
                    await _finalize_run(
                        run_id,
                        status="failed",
                        error=str(e),
                        task_id=task_id,
                    )
                    await q.put(("error", e))

        task = asyncio.create_task(run())
        saw_text = False
        interrupted = False
        try:
            while True:
                kind, payload = await q.get()
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
                        text = getattr(result, "final_text", None) or getattr(result, "error", None) or ""
                        # small pieces if only final blob
                        step = 32
                        for i in range(0, len(text), step):
                            yield chunk({"content": text[i : i + step]})
                    break
        finally:
            if not task.done():
                interrupted = True
                task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
            except Exception as wait_err:  # noqa: BLE001
                # runner already reported; avoid breaking the SSE trailer
                _ = wait_err
            if interrupted:
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

    return StreamingResponse(event_stream(), media_type="text/event-stream")
