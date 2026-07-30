"""Allowlist tool gateway — only registered tools may execute."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any, Protocol


class ToolError(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class Principal(Protocol):
    school_id: str
    membership_id: str
    scopes: list[str]


ToolHandler = Callable[[Principal, dict[str, Any]], Awaitable[dict[str, Any]]]


@dataclass
class ToolSpec:
    name: str
    description: str
    handler: ToolHandler
    school_scoped: bool = True


@dataclass
class AllowlistGateway:
    """Server-side intercept: only allowlisted tools run."""

    tools: dict[str, ToolSpec] = field(default_factory=dict)

    def register(self, spec: ToolSpec) -> None:
        self.tools[spec.name] = spec

    def list_tools(self) -> list[dict[str, str]]:
        return [
            {"name": t.name, "description": t.description} for t in self.tools.values()
        ]

    def restricted_to(self, names: list[str] | tuple[str, ...] | None) -> AllowlistGateway:
        if names is None:
            return self
        allowed = set(names)
        return AllowlistGateway(
            tools={name: spec for name, spec in self.tools.items() if name in allowed}
        )

    async def invoke(
        self,
        principal: Principal,
        name: str,
        arguments: dict[str, Any],
    ) -> dict[str, Any]:
        spec = self.tools.get(name)
        if spec is None:
            raise ToolError("tool.not_allowlisted", f"Tool not allowlisted: {name}")
        if spec.school_scoped:
            target = arguments.get("school_id")
            if target is not None and str(target) != principal.school_id:
                raise ToolError(
                    "tenant.cross_school",
                    f"Cross-school deny: token={principal.school_id} tool={target}",
                )
            # Default school_id from token when omitted
            arguments = {**arguments, "school_id": principal.school_id}
        return await spec.handler(principal, arguments)
