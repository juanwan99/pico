"""OpenAI-compatible /v1/chat/completions — so OSS UIs (NextChat etc.) plug in."""

from __future__ import annotations

import json
import time
import uuid
from collections.abc import AsyncIterator
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.auth import Principal, decode_token
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


async def _run_and_collect(
    prompt: str,
    principal: Principal,
    settings: Settings,
    *,
    history: list[dict[str, Any]] | None = None,
) -> str:
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
            )
        )
        session.add(
            RunRow(
                id=run_id,
                task_id=task_id,
                status="running",
                prompt=prompt,
                model="",
            )
        )
        await session.commit()

    async def emit(event_type: str, payload: dict[str, Any]) -> None:
        async with factory() as session:
            await append_event(session, run_id, event_type, payload)

    async def is_cancelled() -> bool:
        return False

    caps = RunCaps(
        max_seconds=settings.pico_run_max_seconds,
        max_tokens=settings.pico_run_max_tokens,
        max_retries=settings.pico_run_max_retries,
    )
    result = await run_agent_loop(
        prompt=prompt,
        principal=principal,  # structural Principal protocol
        emit=emit,
        is_cancelled=is_cancelled,
        caps=caps,
        history=history,
    )
    async with factory() as session:
        run = await session.get(RunRow, run_id)
        if run:
            run.status = result.status
            run.error = result.error
            await session.commit()
    return result.final_text or result.error or "(empty)"


def _sse_chunk(data: dict[str, Any]) -> str:
    return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"


@router.get("/v1/models")
async def list_models(
    authorization: str | None = Header(default=None),
    settings: Settings = Depends(get_settings),
) -> dict:
    _principal_from_auth(authorization, settings)
    model = settings.kimi_model or "moonshot-v1-8k"
    return {
        "object": "list",
        "data": [
            {"id": model, "object": "model", "owned_by": "pico"},
            {"id": "pico-agent", "object": "model", "owned_by": "pico"},
        ],
    }


@router.post("/v1/chat/completions")
async def chat_completions(
    body: ChatCompletionRequest,
    authorization: str | None = Header(default=None),
    settings: Settings = Depends(get_settings),
):
    principal = _principal_from_auth(authorization, settings)
    prompt = _last_user_prompt(body.messages)
    history = _history_for_agent(body.messages)
    model = body.model or settings.kimi_model or "pico-agent"
    completion_id = f"chatcmpl-{uuid.uuid4().hex[:24]}"
    created = int(time.time())

    if not body.stream:
        text = await _run_and_collect(prompt, principal, settings, history=history)
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
        if use_direct or model in {"moonshot-v1-8k", "moonshot-v1-32k", "moonshot-v1-128k"}:
            from pico_orchestrator.provider import stream_chat

            system = (
                "你是 Pico，面向学校场景的 AI 助手。"
                "回答准确、结构清晰；需要分点时用简洁列表；中文优先。"
                "不要编造不存在的学校数据。"
            )
            try:
                async for piece in stream_chat(
                    prompt,
                    max_tokens=body.max_tokens or 2048,
                    history=history,
                    system=system,
                ):
                    if piece:
                        yield chunk({"content": piece})
            except Exception as e:  # noqa: BLE001
                yield chunk({"content": f"【错误】{e}"})
            yield chunk({}, finish="stop")
            yield b"data: [DONE]\n\n"
            return

        # pico-agent: progressive deltas from agent loop (not wait-then-fake-chunk)
        import asyncio

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
                )
            )
            session.add(
                RunRow(
                    id=run_id,
                    task_id=task_id,
                    status="running",
                    prompt=prompt,
                    model=model,
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
                )
                result = await run_agent_loop(
                    prompt=prompt,
                    principal=principal,
                    emit=emit,
                    is_cancelled=is_cancelled,
                    caps=caps,
                    history=history,
                )
                async with factory() as session:
                    run_row = await session.get(RunRow, run_id)
                    if run_row:
                        run_row.status = result.status
                        run_row.error = result.error
                        await session.commit()
                await q.put(("done", result))
            except Exception as e:  # noqa: BLE001
                await q.put(("error", e))

        task = asyncio.create_task(run())
        saw_text = False
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
                    yield chunk({"content": f"【错误】{payload}"})
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
                task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
            except Exception as wait_err:  # noqa: BLE001
                # runner already reported; avoid breaking the SSE trailer
                _ = wait_err

        yield chunk({}, finish="stop")
        yield b"data: [DONE]\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")
