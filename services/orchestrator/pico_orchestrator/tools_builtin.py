"""Phase 1 allowlist tools (shapes only — FakeEdu expands on D2)."""

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
    # Synthetic school data — contract shape for future edu read adapter.
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


def build_default_gateway() -> AllowlistGateway:
    gw = AllowlistGateway()
    gw.register(
        ToolSpec(
            name="pico.echo",
            description="Echo text bound to the verified principal (smoke tool).",
            handler=_echo,
            school_scoped=False,
        )
    )
    gw.register(
        ToolSpec(
            name="fake_edu.list_classes",
            description="List classes for the caller's school (FakeEdu Phase 1).",
            handler=_fake_edu_list_classes,
            school_scoped=True,
        )
    )
    return gw
