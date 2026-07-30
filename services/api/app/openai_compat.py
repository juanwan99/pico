"""OpenAI-compatible /v1/chat/completions — so OSS UIs (NextChat etc.) plug in."""

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

from app.auth import Principal, decode_token, enforce_scope, scope_proxy_principal
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


def _principal_from_auth(
    authorization: str | None,
    settings: Settings,
) -> Principal:
    """Accept Pico JWT, or (non-production) explicit OpenAI-compat proxy keys.

    Rejects arbitrary sk-*, and does not treat model keys / JWT secrets as Bearer.
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
        # Dev proxy keys for NextChat OPENAI_API_KEY — disabled in production
        if not production and token in _dev_proxy_keys(settings):
            return Principal(
                school_id="school-a",
                membership_id="nextchat-user",
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
    from app.db import init_db

    await init_db()
    factory = session_factory()
    task_id = new_id()
    run_id = new_id()
    title = prompt[:80]
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
                token_usage_json=json.dumps(
                    {"skill_snapshot": skill_snapshot} if skill_snapshot else {},
                    ensure_ascii=False,
                ),
            )
        )
        await session.commit()
    return task_id, run_id


def _extract_file_artifacts(text: str) -> list[tuple[str, str]]:
    """Parse fenced file blocks into (filename, body)."""
    import re

    out: list[tuple[str, str]] = []
    if not text:
        return out
    for m in re.finditer(
        r"```(?:file:)?([A-Za-z0-9._\-]+\.[A-Za-z0-9]{1,12})\s*\n([\s\S]*?)```",
        text,
    ):
        name = m.group(1).strip()
        body = m.group(2).rstrip()
        if name:
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


async def _finalize_run(
    run_id: str,
    *,
    status: str,
    error: str | None = None,
    final_text: str | None = None,
    task_id: str | None = None,
    user_prompt: str | None = None,
) -> None:
    from sqlalchemy import select, update

    from app.db import ArtifactRow, ChangeProposalRow, EventRow, _utcnow
    from app.run_service import _json_dict, _skill_s7_payload

    terminal = ("succeeded", "failed", "cancelled")
    if status not in terminal:
        raise ValueError(f"invalid terminal run status: {status}")

    factory = session_factory()
    async with factory() as session:
        claimed = await session.execute(
            update(RunRow)
            .where(
                RunRow.id == run_id,
                RunRow.status.not_in(terminal),
            )
            .values(
                status=status,
                error=error,
                ended_at=_utcnow(),
            )
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

        if final_text and status == "succeeded":
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
                artifact = ArtifactRow(
                    id=new_id(),
                    task_id=run.task_id,
                    run_id=run_id,
                    kind="file",
                    title=name,
                    inline=body,
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
    from pico_orchestrator.runner import RunCaps, run_agent_loop
    from pico_orchestrator.skill_policy import instruction_for_snapshot

    factory = session_factory()

    async def emit(event_type: str, payload: dict[str, Any]) -> None:
        async with factory() as session:
            await append_event(session, run_id, event_type, payload)

    async def is_cancelled() -> bool:
        return False

    caps = RunCaps(
        max_seconds=settings.pico_run_max_seconds,
        max_tokens=settings.pico_run_max_tokens,
        max_retries=settings.pico_run_max_retries,
        allowed_tools=list(skill_snapshot.get("tools") or []) if skill_snapshot else None,
        skill_instruction=instruction_for_snapshot(skill_snapshot),
    )
    if skill_snapshot:
        await emit("skill.snapshot", skill_snapshot)
    result = await run_agent_loop(
        prompt=prompt,
        principal=principal,  # structural Principal protocol
        emit=emit,
        is_cancelled=is_cancelled,
        caps=caps,
        history=history,
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
    history = _history_for_agent(body.messages)
    model = _model_preference_from_prompt(raw_prompt) or body.model or settings.kimi_model or "pico-agent"
    if skill_snapshot and skill_snapshot.get("tools"):
        model = "pico-agent"
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
                "若用户要求创建或生成文件（如 hello.txt），请在回复中用代码块输出完整内容，格式为 ```file:文件名 换行 正文 换行```；中文说明可附在代码块外。"
            )
            if project_instruction:
                system = system + "\n【项目约束】" + project_instruction
            if skill_snapshot:
                system = system + "\n" + instruction_for_snapshot(skill_snapshot)
            parts: list[str] = []
            try:
                async for piece in stream_chat(
                    prompt,
                    max_tokens=body.max_tokens or 2048,
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
            "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
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
                "若用户要求创建或生成文件（如 hello.txt），请在回复中用代码块输出完整内容，格式为 ```file:文件名 换行 正文 换行```；中文说明可附在代码块外。"
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
                    max_tokens=body.max_tokens or 2048,
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
        from pico_orchestrator.runner import RunCaps, run_agent_loop

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
            session.add(
                RunRow(
                    id=run_id,
                    task_id=task_id,
                    status="running",
                    prompt=prompt,
                    model=model,
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
            return False

        async def run() -> None:
            try:
                caps = RunCaps(
                    max_seconds=settings.pico_run_max_seconds,
                    max_tokens=settings.pico_run_max_tokens,
                    max_retries=settings.pico_run_max_retries,
                    allowed_tools=list(skill_snapshot.get("tools") or []) if skill_snapshot else None,
                    skill_instruction=instruction_for_snapshot(skill_snapshot),
                )
                if skill_snapshot:
                    await emit("skill.snapshot", skill_snapshot)
                result = await run_agent_loop(
                    prompt=prompt,
                    principal=principal,
                    emit=emit,
                    is_cancelled=is_cancelled,
                    caps=caps,
                    history=history,
                )
                await _finalize_run(
                    run_id,
                    status=result.status,
                    error=result.error,
                    final_text=result.final_text,
                    task_id=task_id,
                    user_prompt=prompt,
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
