"""Phase 1 allowlist tools + OpenAI tool schemas for multi-step loop."""

from __future__ import annotations

from typing import Any

from pico_orchestrator.gateway import AllowlistGateway, Principal, ToolSpec


async def _echo(principal: Principal, args: dict[str, Any]) -> dict[str, Any]:
    return {
        "echo": args.get("text", ""),
        "school_id": principal.school_id,
        "membership_id": principal.membership_id,
    }


async def _fake_edu_list_classes(
    principal: Principal, args: dict[str, Any]
) -> dict[str, Any]:
    school_id = principal.school_id
    catalog = {
        "school-a": [
            {"id": "cls-a1", "name": "一年级 1 班"},
            {"id": "cls-a2", "name": "一年级 2 班"},
        ],
        "school-b": [
            {"id": "cls-b1", "name": "二年级 1 班"},
        ],
    }
    classes = catalog.get(school_id, [])
    limit = int(args.get("limit") or 20)
    return {"school_id": school_id, "classes": classes[:limit]}


async def _propose_change(principal: Principal, args: dict[str, Any]) -> dict[str, Any]:
    """Propose a business change — does NOT write school DB (S7)."""
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
                "List classes for the caller's school (FakeEdu Phase 1). "
                "Optional school_id must match token or is rejected."
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


def openai_tool_schemas(gw: AllowlistGateway | None = None) -> list[dict[str, Any]]:
    gw = gw or build_default_gateway()
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
