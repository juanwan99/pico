"""Pico allowlist tools + OpenAI schemas for the multi-step agent loop."""

from __future__ import annotations

import ast
import math
import operator
import re
from typing import Any

from pico_orchestrator.edu_adapter import EduAdapterError, list_classes
from pico_orchestrator.gateway import (
    AllowlistGateway,
    ArtifactStore,
    Principal,
    ToolError,
    ToolSpec,
)

_MAX_ARTIFACT_CONTENT = 200_000
_MAX_CALC_ABS = 1e100
_MAX_CALC_EXPRESSION = 200
_MAX_OUTLINE_TEXT = 100_000


class _UnavailableArtifactStore:
    async def write(self, *_args: Any, **_kwargs: Any) -> dict[str, Any]:
        raise ToolError("artifact.store_unavailable", "Artifact ledger is unavailable")

    async def read(self, *_args: Any, **_kwargs: Any) -> dict[str, Any] | None:
        raise ToolError("artifact.store_unavailable", "Artifact ledger is unavailable")

    async def list(self, *_args: Any, **_kwargs: Any) -> list[dict[str, Any]]:
        raise ToolError("artifact.store_unavailable", "Artifact ledger is unavailable")


def _required_text(args: dict[str, Any], key: str, *, maximum: int) -> str:
    value = args.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ToolError("tool.invalid_arguments", f"{key} must be a non-empty string")
    if len(value) > maximum:
        raise ToolError("tool.invalid_arguments", f"{key} exceeds {maximum} characters")
    return value.strip() if key == "title" else value


def _artifact_title(args: dict[str, Any]) -> str:
    title = _required_text(args, "title", maximum=512)
    if any(ord(char) < 32 for char in title):
        raise ToolError("tool.invalid_arguments", "title contains control characters")
    return title


async def _echo(principal: Principal, args: dict[str, Any]) -> dict[str, Any]:
    # Never echo raw tenant IDs into model/tool transcripts (stage #265 T11).
    return {
        "echo": args.get("text", ""),
        "scope": "current_user",
        "ok": True,
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
    # Proposal is bound to principal in the ledger; do not surface raw IDs to the model/UI.
    return {
        "proposal": {
            "title": args.get("title") or "未命名变更提案",
            "summary": args.get("summary") or "",
            "payload": args.get("payload") or {},
            "status": "proposed",
            "note": "需教师确认后才会写回（S7）。",
        }
    }


def _workspace_handlers(
    store: ArtifactStore,
) -> tuple[Any, Any, Any]:
    async def write_file(principal: Principal, args: dict[str, Any]) -> dict[str, Any]:
        title = _artifact_title(args)
        content = _required_text(args, "content", maximum=_MAX_ARTIFACT_CONTENT)
        kind = str(args.get("kind") or "file").strip().lower()
        if kind not in {"doc", "file", "json", "outline", "text"}:
            raise ToolError("tool.invalid_arguments", "unsupported artifact kind")
        return await store.write(
            principal,
            title=title,
            content=content,
            kind=kind,
        )

    async def read_file(principal: Principal, args: dict[str, Any]) -> dict[str, Any]:
        artifact_id = args.get("artifact_id")
        title = args.get("title")
        artifact_id = str(artifact_id).strip() if artifact_id is not None else None
        title = str(title).strip() if title is not None else None
        if not artifact_id and not title:
            raise ToolError(
                "tool.invalid_arguments", "artifact_id or title is required"
            )
        result = await store.read(
            principal,
            artifact_id=artifact_id or None,
            title=title or None,
        )
        if result is None:
            raise ToolError("artifact.not_found", "Artifact not found")
        return {"artifact": result}

    async def list_files(principal: Principal, args: dict[str, Any]) -> dict[str, Any]:
        try:
            limit = int(args.get("limit") or 20)
        except (TypeError, ValueError) as exc:
            raise ToolError("tool.invalid_arguments", "limit must be an integer") from exc
        if not 1 <= limit <= 100:
            raise ToolError("tool.invalid_arguments", "limit must be between 1 and 100")
        artifacts = await store.list(principal, limit=limit)
        return {"artifacts": artifacts, "count": len(artifacts)}

    return write_file, read_file, list_files


def _outline_heading(line: str) -> tuple[int, str] | None:
    markdown = re.match(r"^(#{1,6})\s+(.+?)\s*$", line)
    if markdown:
        return len(markdown.group(1)), markdown.group(2).strip()

    bullet = re.match(r"^(\s*)(?:[-*+] |\d+[.)]\s+)(.+?)\s*$", line)
    if bullet:
        indent = len(bullet.group(1).expandtabs(2))
        return 1 + indent // 2, bullet.group(2).strip()
    return None


async def _structured_outline(
    _principal: Principal, args: dict[str, Any]
) -> dict[str, Any]:
    text = _required_text(args, "text", maximum=_MAX_OUTLINE_TEXT)
    nodes: list[dict[str, Any]] = []
    stack: list[tuple[int, dict[str, Any]]] = []
    for raw_line in text.splitlines():
        parsed = _outline_heading(raw_line.rstrip())
        if not parsed:
            continue
        level, title = parsed
        node: dict[str, Any] = {"title": title, "children": []}
        while stack and stack[-1][0] >= level:
            stack.pop()
        if stack:
            stack[-1][1]["children"].append(node)
        else:
            nodes.append(node)
        stack.append((level, node))
    if not nodes:
        nodes = [
            {"title": line.strip(), "children": []}
            for line in text.splitlines()
            if line.strip()
        ]
    return {"outline": nodes, "item_count": _outline_count(nodes)}


def _outline_count(nodes: list[dict[str, Any]]) -> int:
    return sum(1 + _outline_count(node["children"]) for node in nodes)


_BINARY_OPERATORS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
}
_UNARY_OPERATORS = {ast.UAdd: operator.pos, ast.USub: operator.neg}


def _safe_number(value: Any) -> int | float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ToolError("calculator.invalid_expression", "only numeric literals are allowed")
    if not math.isfinite(float(value)) or abs(value) > _MAX_CALC_ABS:
        raise ToolError("calculator.out_of_range", "numeric result is out of range")
    return value


def _evaluate(node: ast.AST) -> int | float:
    if isinstance(node, ast.Expression):
        return _evaluate(node.body)
    if isinstance(node, ast.Constant):
        return _safe_number(node.value)
    if isinstance(node, ast.UnaryOp) and type(node.op) in _UNARY_OPERATORS:
        return _safe_number(_UNARY_OPERATORS[type(node.op)](_evaluate(node.operand)))
    if isinstance(node, ast.BinOp) and type(node.op) in _BINARY_OPERATORS:
        left = _evaluate(node.left)
        right = _evaluate(node.right)
        if isinstance(node.op, ast.Pow) and abs(right) > 100:
            raise ToolError("calculator.out_of_range", "exponent is out of range")
        try:
            return _safe_number(_BINARY_OPERATORS[type(node.op)](left, right))
        except ZeroDivisionError as exc:
            raise ToolError("calculator.division_by_zero", "division by zero") from exc
        except OverflowError as exc:
            raise ToolError("calculator.out_of_range", "numeric result is out of range") from exc
    raise ToolError(
        "calculator.invalid_expression",
        "only numbers, parentheses, and + - * / // % ** are allowed",
    )


async def _calculator(_principal: Principal, args: dict[str, Any]) -> dict[str, Any]:
    expression = _required_text(args, "expression", maximum=_MAX_CALC_EXPRESSION)
    try:
        tree = ast.parse(expression, mode="eval")
    except (SyntaxError, ValueError) as exc:
        raise ToolError("calculator.invalid_expression", "invalid expression") from exc
    result = _evaluate(tree)
    return {"expression": expression, "result": result}


def build_default_gateway(
    artifact_store: ArtifactStore | None = None,
) -> AllowlistGateway:
    gw = AllowlistGateway()
    store = artifact_store or _UnavailableArtifactStore()
    write_file, read_file, list_files = _workspace_handlers(store)
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
    gw.register(
        ToolSpec(
            name="workspace_write_file",
            description="Write text to the caller's Artifact ledger; never writes a host path.",
            handler=write_file,
            school_scoped=False,
        )
    )
    gw.register(
        ToolSpec(
            name="workspace_read_file",
            description="Read one Artifact owned by the current membership by id or title.",
            handler=read_file,
            school_scoped=False,
        )
    )
    gw.register(
        ToolSpec(
            name="workspace_list_files",
            description="List Artifacts owned by the current membership.",
            handler=list_files,
            school_scoped=False,
        )
    )
    gw.register(
        ToolSpec(
            name="structured_outline",
            description="Turn headings or bullet text into a nested JSON outline.",
            handler=_structured_outline,
            school_scoped=False,
        )
    )
    gw.register(
        ToolSpec(
            name="calculator",
            description="Safely evaluate a numeric expression without shell or code execution.",
            handler=_calculator,
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
    parameters: dict[str, dict[str, Any]] = {
        "pico_echo": {
            "type": "object",
            "properties": {"text": {"type": "string"}},
            "required": ["text"],
        },
        "fake_edu_list_classes": {
            "type": "object",
            "properties": {
                "school_id": {
                    "type": "string",
                    "description": "Must equal token school_id",
                },
                "limit": {"type": "integer", "minimum": 1, "maximum": 100},
            },
        },
        "pico_propose_change": {
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "summary": {"type": "string"},
                "payload": {"type": "object"},
            },
            "required": ["title", "summary"],
        },
        "workspace_write_file": {
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "Artifact title or filename"},
                "content": {"type": "string"},
                "kind": {
                    "type": "string",
                    "enum": ["doc", "file", "json", "outline", "text"],
                },
            },
            "required": ["title", "content"],
        },
        # Moonshot rejects object schemas that combine top-level "type"
        # with "anyOf"/"oneOf". Both keys optional; handler enforces one-of.
        "workspace_read_file": {
            "type": "object",
            "properties": {
                "artifact_id": {
                    "type": "string",
                    "description": "Artifact id (provide this or title)",
                },
                "title": {
                    "type": "string",
                    "description": "Exact artifact title (provide this or artifact_id)",
                },
            },
        },
        "workspace_list_files": {
            "type": "object",
            "properties": {
                "limit": {"type": "integer", "minimum": 1, "maximum": 100}
            },
        },
        "structured_outline": {
            "type": "object",
            "properties": {"text": {"type": "string"}},
            "required": ["text"],
        },
        "calculator": {
            "type": "object",
            "properties": {"expression": {"type": "string"}},
            "required": ["expression"],
        },
    }
    schemas: list[dict[str, Any]] = []
    for name, spec in gw.tools.items():
        schemas.append(
            {
                "type": "function",
                "function": {
                    "name": name,
                    "description": spec.description,
                    "parameters": parameters.get(
                        name, {"type": "object", "properties": {}}
                    ),
                },
            }
        )
    return schemas
