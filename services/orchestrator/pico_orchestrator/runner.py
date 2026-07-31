"""Server-side multi-step tool loop: Kimi model API + Pico allowlist gateway.

Host Shell/File/Web/MCP remain off (agent pin + gateway). Tools exposed to the
model are ONLY the Pico allowlist. Not a home-grown agent OS — thin control
plane around the pinned Kimi HTTPS API tool-calling path.
"""

from __future__ import annotations

import asyncio
import json
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from openai import AsyncOpenAI

from pico_orchestrator.gateway import (
    AllowlistGateway,
    ArtifactStore,
    Principal,
    ToolError,
)
from pico_orchestrator.provider import ProviderConfig, resolve_provider
from pico_orchestrator.tools_builtin import build_default_gateway, openai_tool_schemas
from pico_orchestrator.user_errors import enrich_fail_payload

EventEmitter = Callable[[str, dict[str, Any]], Awaitable[None]]


@dataclass
class RunCaps:
    max_seconds: int = 120
    max_tokens: int = 8000
    max_retries: int = 2
    max_steps: int = 8
    allowed_tools: list[str] | None = None
    skill_instruction: str = ""


@dataclass
class RunResult:
    status: str  # succeeded|failed|cancelled
    final_text: str
    error: str | None = None
    token_usage: dict[str, int] | None = None
    artifact_markdown: str | None = None
    change_proposal: dict[str, Any] | None = None


class CancelledError(Exception):
    pass


async def run_agent_loop(
    *,
    prompt: str,
    principal: Principal,
    emit: EventEmitter,
    is_cancelled: Callable[[], Awaitable[bool]],
    caps: RunCaps | None = None,
    force_tools: list[str] | None = None,
    history: list[dict[str, Any]] | None = None,
    artifact_store: ArtifactStore | None = None,
) -> RunResult:
    """Execute multi-step tool loop; emit ordered events via callback.

    Underlying agent = pinned Kimi model HTTPS API + allowlist tool gateway
    (not a custom agent OS). Optional `history` is prior OpenAI-style messages.
    """
    caps = caps or RunCaps()
    cfg = resolve_provider()
    if cfg is None:
        reason = "尚未配置 Kimi 密钥：请设置 KIMI_API_KEY（或 DEEPSEEK_API_KEY）"
        await emit(
            "run.status",
            enrich_fail_payload({"status": "failed", "reason": reason, "code": "model.unconfigured"}),
        )
        return RunResult(
            status="failed",
            final_text="",
            error=reason,
        )

    gw = build_default_gateway(artifact_store).restricted_to(caps.allowed_tools)
    tools = openai_tool_schemas(gw)
    client = AsyncOpenAI(api_key=cfg.api_key, base_url=cfg.base_url)

    await emit(
        "run.status",
        {"status": "running", "provider": cfg.name, "model": cfg.model},
    )
    await emit(
        "agent.step",
        {"step": 0, "message": "multi-step tool loop started (allowlist only)"},
    )

    system = (
        "你是 Pico，面向学校师生的 AI 工作台助手。"
        "底层是大模型 HTTPS API + 白名单工具；没有 Shell、本机文件、随意联网、MCP。"
        "只能使用已提供的工具；文件写入、读取、列举必须使用 workspace_* 工具，"
        "它们只操作当前成员的 Artifact 账本，不是宿主机文件；"
        "计算使用 calculator，整理层级使用 structured_outline；"
        "查班级等只读数据用 fake_edu_list_classes；"
        "业务变更只能 pico_propose_change（提案，禁止假装已写库）。"
        f"当前租户 school_id={principal.school_id}，禁止编造其它学校数据。"
        "回答：先给结论，再补必要步骤；中文优先；结构清晰；不要空话套话。"
        "普通问答直接回答，不必强行调工具。"
    )
    if caps.skill_instruction:
        system = f"{system}\n{caps.skill_instruction}"

    messages: list[dict[str, Any]] = [{"role": "system", "content": system}]
    # prior turns (user/assistant only; drop system from client)
    for h in history or []:
        role = h.get("role")
        content = h.get("content")
        if role in ("user", "assistant") and content:
            messages.append({"role": role, "content": str(content)})
    # current user prompt (if not already last)
    if not messages or messages[-1].get("role") != "user" or messages[-1].get("content") != prompt:
        messages.append({"role": "user", "content": prompt})

    # Optional scripted first tool for deterministic demos / tests
    if force_tools:
        for name in force_tools:
            await _invoke_tool(gw, principal, name, {}, emit)

    started = time.monotonic()
    final_text_parts: list[str] = []
    total_tokens = 0
    artifact_md: str | None = None
    change_proposal: dict[str, Any] | None = None
    retries = 0

    for step in range(1, caps.max_steps + 1):
        if await is_cancelled():
            await emit("run.status", {"status": "cancelled"})
            return RunResult(status="cancelled", final_text="".join(final_text_parts))

        if time.monotonic() - started > caps.max_seconds:
            await emit(
                "run.status",
                enrich_fail_payload(
                    {
                        "status": "failed",
                        "reason": f"timeout after {caps.max_seconds}s",
                        "code": "timeout",
                    }
                ),
            )
            return RunResult(
                status="failed",
                final_text="".join(final_text_parts),
                error=f"timeout after {caps.max_seconds}s",
            )

        await emit("agent.step", {"step": step, "phase": "model"})

        try:
            request: dict[str, Any] = {
                "model": cfg.model,
                "messages": messages,
                "max_tokens": min(1024, caps.max_tokens),
            }
            if tools:
                request.update(tools=tools, tool_choice="auto")
            resp = await client.chat.completions.create(**request)
        except Exception as e:  # noqa: BLE001
            retries += 1
            await emit(
                "run.error",
                enrich_fail_payload({"error": str(e), "retry": retries}),
            )
            if retries > caps.max_retries:
                await emit(
                    "run.status",
                    enrich_fail_payload({"status": "failed", "reason": str(e)}),
                )
                return RunResult(
                    status="failed",
                    final_text="".join(final_text_parts),
                    error=str(e),
                )
            await asyncio.sleep(0.5 * retries)
            continue

        # A cancel can arrive while the provider request is in flight. Honor it
        # before applying terminal caps or dispatching any returned tool calls.
        if await is_cancelled():
            await emit("run.status", {"status": "cancelled"})
            return RunResult(status="cancelled", final_text="".join(final_text_parts))

        usage = getattr(resp, "usage", None)
        if usage:
            total_tokens += int(getattr(usage, "total_tokens", 0) or 0)
            if total_tokens > caps.max_tokens:
                await emit(
                    "run.status",
                    enrich_fail_payload(
                        {
                            "status": "failed",
                            "reason": "token_cap",
                            "code": "token_cap",
                            "tokens": total_tokens,
                        }
                    ),
                )
                return RunResult(
                    status="failed",
                    final_text="".join(final_text_parts),
                    error=f"token cap {caps.max_tokens}",
                    token_usage={"total_tokens": total_tokens},
                )

        choice = resp.choices[0]
        msg = choice.message
        tool_calls = msg.tool_calls or []

        assistant_msg: dict[str, Any] = {"role": "assistant", "content": msg.content or ""}
        if tool_calls:
            assistant_msg["tool_calls"] = [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {
                        "name": tc.function.name,
                        "arguments": tc.function.arguments or "{}",
                    },
                }
                for tc in tool_calls
            ]
        messages.append(assistant_msg)

        if msg.content:
            final_text_parts.append(msg.content)
            await emit("message.delta", {"text": msg.content})

        if not tool_calls:
            break

        for tc in tool_calls:
            if await is_cancelled():
                await emit("run.status", {"status": "cancelled"})
                return RunResult(status="cancelled", final_text="".join(final_text_parts))

            name = tc.function.name
            try:
                args = json.loads(tc.function.arguments or "{}")
            except json.JSONDecodeError:
                args = {}

            await emit(
                "tool.call",
                {"tool": name, "arguments": args, "call_id": tc.id},
            )
            try:
                result = await gw.invoke(principal, name, args)
                await emit(
                    "tool.result",
                    {"tool": name, "ok": True, "result": result, "call_id": tc.id},
                )
                if name == "fake_edu_list_classes":
                    artifact_md = _classes_artifact(result)
                if name == "pico_propose_change":
                    change_proposal = result
                body = json.dumps(result, ensure_ascii=False)
            except ToolError as e:
                await emit(
                    "tool.result",
                    {
                        "tool": name,
                        "ok": False,
                        "code": e.code,
                        "message": e.message,
                        "call_id": tc.id,
                    },
                )
                if e.code == "tenant.cross_school":
                    await emit(
                        "auth.deny",
                        {
                            "code": e.code,
                            "message": e.message,
                            "token_school_id": principal.school_id,
                            "tool": name,
                            "arguments": args,
                        },
                    )
                body = json.dumps({"error": e.code, "message": e.message})

            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": body,
                }
            )

    # Cancellation can arrive after the final provider response (or the last
    # tool result) but before terminal success is emitted. Give the durable
    # cancel request one final chance to win that race.
    if await is_cancelled():
        await emit("run.status", {"status": "cancelled"})
        return RunResult(status="cancelled", final_text="".join(final_text_parts))

    text = "".join(final_text_parts).strip()
    if not text and artifact_md:
        text = "已完成工具调用。"
    # Surface tool trail for chat UIs that only show assistant text
    tool_notes: list[str] = []
    if artifact_md:
        tool_notes.append("【工具产物 · 班级列表】\n" + artifact_md)
    if change_proposal:
        tool_notes.append(
            "【变更提案 · 待人工确认】\n"
            + json.dumps(change_proposal, ensure_ascii=False, indent=2)
        )
    if tool_notes:
        text = (text + "\n\n" if text else "") + "\n\n".join(tool_notes)

    await emit(
        "run.status",
        {
            "status": "succeeded",
            "tokens": total_tokens,
            "provider": cfg.name,
            "model": cfg.model,
        },
    )
    return RunResult(
        status="succeeded",
        final_text=text,
        token_usage={"total_tokens": total_tokens},
        artifact_markdown=artifact_md,
        change_proposal=change_proposal,
    )


async def _invoke_tool(
    gw: AllowlistGateway,
    principal: Principal,
    name: str,
    args: dict[str, Any],
    emit: EventEmitter,
) -> None:
    await emit("tool.call", {"tool": name, "arguments": args, "call_id": "forced"})
    try:
        result = await gw.invoke(principal, name, args)
        await emit("tool.result", {"tool": name, "ok": True, "result": result})
    except ToolError as e:
        await emit(
            "tool.result",
            {"tool": name, "ok": False, "code": e.code, "message": e.message},
        )
        if e.code == "tenant.cross_school":
            await emit(
                "auth.deny",
                {
                    "code": e.code,
                    "message": e.message,
                    "token_school_id": principal.school_id,
                    "tool": name,
                    "arguments": args,
                },
            )


def _classes_artifact(result: dict[str, Any]) -> str:
    lines = [
        f"# 班级列表（{result.get('school_id', '')}）",
        "",
        "| ID | 名称 |",
        "|----|------|",
    ]
    for c in result.get("classes") or []:
        lines.append(f"| {c.get('id', '')} | {c.get('name', '')} |")
    return "\n".join(lines)


def provider_label(cfg: ProviderConfig | None = None) -> str:
    c = cfg or resolve_provider()
    if not c:
        return ""
    return f"{c.name}:{c.model}"
