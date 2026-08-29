"""Kimi callable tools that can execute only through Pico's allowlist gateway."""

from __future__ import annotations

import json
from collections.abc import Awaitable, Callable, Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from typing import Any, ClassVar, Literal

from kimi_agent_sdk import CallableTool2, ToolOk, ToolReturnValue
from kimi_agent_sdk import ToolError as KimiToolError
from pydantic import BaseModel, Field

from pico_orchestrator.gateway import AllowlistGateway, Principal, ToolError

AuditEmitter = Callable[[str, dict[str, Any]], Awaitable[None]]


@dataclass(slots=True)
class GatewayToolContext:
    gateway: AllowlistGateway
    principal: Principal
    emit: AuditEmitter | None = None
    results: list[tuple[str, dict[str, Any]]] = field(default_factory=list)


_TOOL_CONTEXT: ContextVar[GatewayToolContext | None] = ContextVar(
    "pico_kimi_gateway_context", default=None
)


@contextmanager
def bind_gateway_tools(
    gateway: AllowlistGateway,
    principal: Principal,
    emit: AuditEmitter | None = None,
) -> Iterator[GatewayToolContext]:
    """Bind request-scoped authority for Kimi-created tool tasks."""

    context = GatewayToolContext(gateway=gateway, principal=principal, emit=emit)
    token = _TOOL_CONTEXT.set(context)
    try:
        yield context
    finally:
        _TOOL_CONTEXT.reset(token)


class _GatewayTool(CallableTool2[BaseModel]):
    name: ClassVar[str]
    description: ClassVar[str]
    params: ClassVar[type[BaseModel]]

    async def __call__(self, params: BaseModel) -> ToolReturnValue:
        context = _TOOL_CONTEXT.get()
        if context is None:
            return KimiToolError(
                message="Pico gateway context is unavailable",
                brief="Tool unavailable",
            )
        arguments = params.model_dump(exclude_none=True)
        try:
            result = await context.gateway.invoke(context.principal, self.name, arguments)
        except ToolError as exc:
            if exc.code == "tenant.cross_school" and context.emit is not None:
                await context.emit(
                    "auth.deny",
                    {
                        "code": exc.code,
                        "message": "跨校访问已被拒绝（租户隔离）。",
                        "tool": self.name,
                        # Never put raw school/membership IDs in events (stage #265 T11).
                    },
                )
            return KimiToolError(
                message=f"{exc.code}: {exc.message}",
                brief=exc.message,
            )
        context.results.append((self.name, result))
        return ToolOk(
            output=json.dumps(result, ensure_ascii=False),
            message=f"{self.name} completed through Pico allowlist gateway",
            brief="Tool completed",
        )


class EchoParams(BaseModel):
    text: str


class PicoEcho(_GatewayTool):
    name = "pico_echo"
    description = "Echo text bound to the verified Pico principal."
    params = EchoParams


class ListClassesParams(BaseModel):
    school_id: str | None = None
    limit: int | None = Field(default=None, ge=1, le=100)


class FakeEduListClasses(_GatewayTool):
    name = "fake_edu_list_classes"
    description = "List classes for the verified principal's school."
    params = ListClassesParams


class ProposeChangeParams(BaseModel):
    title: str
    summary: str
    payload: dict[str, Any] = Field(default_factory=dict)


class PicoProposeChange(_GatewayTool):
    name = "pico_propose_change"
    description = "Create a Pico change proposal that still requires human confirmation."
    params = ProposeChangeParams


class WorkspaceWriteParams(BaseModel):
    title: str
    content: str
    kind: Literal["doc", "file", "json", "outline", "text"] | None = None


class WorkspaceWriteFile(_GatewayTool):
    name = "workspace_write_file"
    description = (
        "Write plain text to the Artifact ledger. "
        "Do NOT use for .html/.docx/.pptx — use generate_*_document tools instead."
    )
    params = WorkspaceWriteParams


class WorkspaceReadParams(BaseModel):
    artifact_id: str | None = None
    title: str | None = None


class WorkspaceReadFile(_GatewayTool):
    name = "workspace_read_file"
    description = "Read one Artifact owned by the current Pico membership."
    params = WorkspaceReadParams


class WorkspaceListParams(BaseModel):
    limit: int | None = Field(default=None, ge=1, le=100)


class WorkspaceListFiles(_GatewayTool):
    name = "workspace_list_files"
    description = "List Artifacts owned by the current Pico membership."
    params = WorkspaceListParams


class StructuredOutlineParams(BaseModel):
    text: str


class StructuredOutline(_GatewayTool):
    name = "structured_outline"
    description = "Turn headings or bullet text into a nested JSON outline."
    params = StructuredOutlineParams


class CalculatorParams(BaseModel):
    expression: str


class Calculator(_GatewayTool):
    name = "calculator"
    description = "Safely evaluate a numeric expression without shell or code execution."
    params = CalculatorParams


class GenerateDocParams(BaseModel):
    title: str
    marker: str
    body: str | None = None


class GenerateHtmlDocument(_GatewayTool):
    name = "generate_html_document"
    description = (
        "Create a real .html Artifact with a unique visible marker "
        "(offline HTML: inline CSS/JS/canvas, no CDN, no window.THREE)."
    )
    params = GenerateDocParams


class GenerateDocxDocument(_GatewayTool):
    name = "generate_docx_document"
    description = (
        "Create a real OOXML .docx Artifact (ZIP with Content_Types + word/document.xml) "
        "containing a unique marker."
    )
    params = GenerateDocParams


class GeneratePptxDocument(_GatewayTool):
    name = "generate_pptx_document"
    description = (
        "Create a real OOXML .pptx Artifact (presentation + ≥1 slide) "
        "containing a unique marker."
    )
    params = GenerateDocParams
