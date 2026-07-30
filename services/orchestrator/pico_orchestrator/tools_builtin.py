"""Phase 1–3 allowlist tools + OpenAI tool schemas for multi-step loop."""

from __future__ import annotations

from typing import Any

from pico_orchestrator.edu_adapter import EduAdapterError, list_classes
from pico_orchestrator.gateway import AllowlistGateway, Principal, ToolError, ToolSpec


async def _echo(principal: Principal, args: dict[str, Any]) -> dict[str, Any]:
    return {
        "echo": args.get("text", ""),
        "school_id": principal.school_id,
        "membership_id": principal.membership_id,
    }


async def _fake_edu_list_classes(
    principal: Principal, args: dict[str, Any]
) -> dict[str, Any]:
    """Name kept for contract stability; implementation swaps via PICO_EDU_MODE."""
    try:
        return await list_classes(
            principal.school_id, limit=int(args.get("limit") or 20)
        )
    except EduAdapterError as e:
        raise ToolError(e.code, e.message) from e


async def _propose_change(principal: Principal, args: dict[str, Any]) -> dict[str, Any]:
    return {
        "proposal": {
            "title": args.get("title") or "未命名变更提案",
            "summary": args.get("summary") or "",
            "payload": args.get("payload") or {},
            "school_id": principal.school_id,
            "membership_id": principal.membership_id,
            "status": "proposed",
            "note": "Requires human confirm before any edu write-back (Phase 3).",
        }
    }


def build_default_gateway() -> AllowlistGateway:
    gw = AllowlistGateway()
    gw.register(
        ToolSpec(
            name="pico_echo",
            description="Echo text bound to the verified principal (smoke tool).",
            handler=_echo,
            school_scoped=False,
        )
    )
    gw.register(
        ToolSpec(
            name="fake_edu_list_classes",
            description=(
                "List classes for the caller's school. "
                "Phase 1 FakeEdu; Phase 3 live edu adapter (same name)."
            ),
            handler=_fake_edu_list_classes,
            school_scoped=True,
        )
    )
    gw.register(
        ToolSpec(
            name="pico_propose_change",
            description=(
                "Propose a school data change for human confirmation. "
                "Does not write business data. Args: title, summary, payload."
            ),
            handler=_propose_change,
            school_scoped=False,
        )
    )
    return gw


def openai_tool_schemas(
    gw: AllowlistGateway | None = None,
    *,
    allowed_tools: list[str] | tuple[str, ...] | None = None,
) -> list[dict[str, Any]]:
    gw = gw or build_default_gateway()
    if allowed_tools is not None:
        gw = gw.restricted_to(allowed_tools)
    schemas: list[dict[str, Any]] = []
    for name, spec in gw.tools.items():
        if name == "pico_echo":
            params = {
                "type": "object",
                "properties": {"text": {"type": "string"}},
                "required": ["text"],
            }
        elif name == "fake_edu_list_classes":
            params = {
                "type": "object",
                "properties": {
                    "school_id": {
                        "type": "string",
                        "description": "Must equal token school_id",
                    },
                    "limit": {"type": "integer"},
                },
            }
        elif name == "pico_propose_change":
            params = {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "summary": {"type": "string"},
                    "payload": {"type": "object"},
                },
                "required": ["title", "summary"],
            }
        else:
            params = {"type": "object", "properties": {}}
        schemas.append(
            {
                "type": "function",
                "function": {
                    "name": name,
                    "description": spec.description,
                    "parameters": params,
                },
            }
        )
    return schemas
