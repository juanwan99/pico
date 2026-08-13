"""Pico allowlist tools + OpenAI schemas for the multi-step agent loop."""

from __future__ import annotations

import ast
import math
import operator
import re
from typing import Any

from pico_orchestrator.artifact_types import (
    reject_fake_protected_write_message,
    title_protected_extension,
)
from pico_orchestrator.document_generators import (
    build_docx_document,
    build_html_document,
    build_pptx_document,
)
from pico_orchestrator.edu_adapter import EduAdapterError, list_classes
from pico_orchestrator.gateway import (
    AllowlistGateway,
    ArtifactStore,
    Principal,
    ToolError,
    ToolSpec,
)
from pico_orchestrator.mcp_bridge import mcp_openai_parameters, mcp_tool_specs
from pico_orchestrator.web_tools import web_fetch_handler, web_search_handler

_MAX_ARTIFACT_CONTENT = 200_000
_MAX_CALC_ABS = 1e100
_MAX_CALC_EXPRESSION = 200
_MAX_OUTLINE_TEXT = 100_000
_MAX_DOC_BODY = 50_000
_MAX_MARKER = 200
_MAX_KB_QUERY = 500
_MAX_KB_EXCERPT = 280
_SKIP_KB_TITLES = frozenset({"回复摘要"})


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


def _optional_text(args: dict[str, Any], key: str, *, maximum: int) -> str | None:
    value = args.get(key)
    if value is None:
        return None
    if not isinstance(value, str):
        raise ToolError("tool.invalid_arguments", f"{key} must be a string")
    if len(value) > maximum:
        raise ToolError("tool.invalid_arguments", f"{key} exceeds {maximum} characters")
    return value


def _marker_arg(args: dict[str, Any]) -> str:
    # Marker is an internal traceability tag. Auto-generate one when the model
    # omits it — hard-failing here made the true-Pi agent retry the same tool
    # call forever (message_update flood → OOM). A unique tag keeps deliveries
    # traceable without requiring the model to know the internal field.
    value = args.get("marker")
    if value is None:
        value = ""
    if not isinstance(value, str):
        raise ToolError("tool.invalid_arguments", "marker must be a string")
    value = value.strip()
    if not value:
        import uuid

        value = f"pico-{uuid.uuid4().hex[:12]}"
    if len(value) > _MAX_MARKER:
        raise ToolError("tool.invalid_arguments", f"marker exceeds {_MAX_MARKER} characters")
    return value


def _ensure_extension(title: str, ext: str) -> str:
    lower = title.lower()
    if lower.endswith(ext):
        return title
    # Strip a wrong extension then append the real one — never rename text to OOXML.
    base = title.rsplit(".", 1)[0] if "." in title.split("/")[-1] else title
    return f"{base}{ext}"


def _excerpt_around(text: str, query: str, *, width: int = _MAX_KB_EXCERPT) -> str:
    low = text.lower()
    q = query.lower()
    idx = low.find(q)
    if idx < 0:
        snippet = text.strip().replace("\n", " ")
        return snippet[:width] + ("…" if len(snippet) > width else "")
    start = max(0, idx - width // 4)
    end = min(len(text), idx + len(query) + width // 2)
    snippet = text[start:end].strip().replace("\n", " ")
    if start > 0:
        snippet = "…" + snippet
    if end < len(text):
        snippet = snippet + "…"
    return snippet[:width]


def _static_html_checks(content: str) -> list[dict[str, Any]]:
    """Structure-only HTML checks (no browser). Honest statuses: pass|fail|not_verified."""
    text = content or ""
    low = text.lower()
    checks: list[dict[str, Any]] = []

    def add(name: str, status: str, detail: str) -> None:
        checks.append({"name": name, "status": status, "detail": detail})

    has_doc = bool(
        re.search(r"<!doctype\s+html|<html[\s>]|<body[\s>]", low)
        or ("<html" in low)
    )
    add(
        "document_shell",
        "pass" if has_doc else "fail",
        "has doctype/html/body" if has_doc else "missing html document shell",
    )

    # Interactive surfaces commonly needed for "local runnable" pages.
    has_input = bool(re.search(r"<input[\s>]|<textarea[\s>]|<select[\s>]", low))
    has_button = bool(
        re.search(r"<button[\s>]|type\s*=\s*[\"']submit[\"']|onclick\s*=", low)
    )
    has_script = "<script" in low
    if has_input or has_button or has_script:
        add(
            "interactive_surface",
            "pass" if (has_input or has_button) else "fail",
            f"input={has_input} button={has_button} script={has_script}",
        )
    else:
        add(
            "interactive_surface",
            "not_verified",
            "no form controls found — static page may be intentional",
        )

    # Empty submit / required fields: only structural signal.
    has_required = "required" in low or "aria-required" in low
    if has_input:
        add(
            "empty_submit_guard",
            "pass" if (has_required or has_script) else "not_verified",
            "required attr or script present"
            if (has_required or has_script)
            else "no required/script guard detected (static check only)",
        )
    else:
        add(
            "empty_submit_guard",
            "not_verified",
            "no inputs to validate",
        )

    # Persistence hints (localStorage / sessionStorage).
    if "localstorage" in low or "sessionstorage" in low:
        add(
            "refresh_persistence_hint",
            "pass",
            "storage API referenced (runtime not executed)",
        )
    else:
        add(
            "refresh_persistence_hint",
            "not_verified",
            "no localStorage/sessionStorage — refresh persistence not proven",
        )

    # Dangerous remote script loads (soft warning).
    remote_script = bool(
        re.search(r"<script[^>]+src\s*=\s*[\"']https?://", low)
    )
    add(
        "no_remote_script",
        "fail" if remote_script else "pass",
        "external script src found" if remote_script else "no external script src",
    )

    return checks


def _workspace_handlers(
    store: ArtifactStore,
) -> tuple[Any, Any, Any, Any, Any, Any, Any, Any]:
    async def write_file(principal: Principal, args: dict[str, Any]) -> dict[str, Any]:
        from pico_orchestrator.delivery_policy import normalize_artifact_title

        title = _artifact_title(args)
        title, ext_fix = normalize_artifact_title(title)
        protected = title_protected_extension(title)
        if protected:
            raise ToolError(
                "tool.invalid_arguments",
                reject_fake_protected_write_message(protected),
            )
        content = _required_text(args, "content", maximum=_MAX_ARTIFACT_CONTENT)
        kind = str(args.get("kind") or "file").strip().lower()
        if kind not in {"doc", "file", "json", "outline", "text"}:
            raise ToolError("tool.invalid_arguments", "unsupported artifact kind")
        result = await store.write(
            principal,
            title=title,
            content=content,
            kind=kind,
        )
        if ext_fix:
            result = dict(result)
            result["extension_corrected"] = ext_fix
        return result

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

    async def kb_search(principal: Principal, args: dict[str, Any]) -> dict[str, Any]:
        """P2 KB pilot: full-text scan of membership Artifact materials (no vector DB)."""
        query = _required_text(args, "query", maximum=_MAX_KB_QUERY)
        try:
            limit = int(args.get("limit") or 20)
        except (TypeError, ValueError) as exc:
            raise ToolError("tool.invalid_arguments", "limit must be an integer") from exc
        if not 1 <= limit <= 50:
            raise ToolError("tool.invalid_arguments", "limit must be between 1 and 50")
        listed = await store.list(principal, limit=min(100, max(limit * 3, 20)))
        hits: list[dict[str, Any]] = []
        q_low = query.lower()
        for meta in listed:
            title = str(meta.get("title") or "")
            if title in _SKIP_KB_TITLES:
                continue
            art_id = str(meta.get("artifact_id") or meta.get("id") or "")
            if not art_id:
                continue
            full = await store.read(principal, artifact_id=art_id, title=None)
            if not full:
                continue
            content = full.get("content")
            if not isinstance(content, str):
                # Binary materials: title-only match
                if q_low not in title.lower():
                    continue
                hits.append(
                    {
                        "artifact_id": art_id,
                        "title": title,
                        "kind": full.get("kind"),
                        "excerpt": f"（二进制材料，标题命中：{title}）",
                        "match": "title",
                    }
                )
                continue
            title_hit = q_low in title.lower()
            body_hit = q_low in content.lower()
            if not title_hit and not body_hit:
                continue
            hits.append(
                {
                    "artifact_id": art_id,
                    "title": title,
                    "kind": full.get("kind"),
                    "excerpt": _excerpt_around(content if body_hit else title, query),
                    "match": "title+body" if title_hit and body_hit else (
                        "title" if title_hit else "body"
                    ),
                }
            )
            if len(hits) >= limit:
                break
        if not hits:
            return {
                "hits": [],
                "count": 0,
                "honest_miss": True,
                "user_message": (
                    "未在已挂载的工作区材料中命中该问题。"
                    "请先生成或上传材料到产物账本后再问，或换关键词。"
                ),
            }
        return {
            "hits": hits,
            "count": len(hits),
            "honest_miss": False,
            "user_message": f"命中 {len(hits)} 条材料依据（Artifact 账本全文检索试点，非向量库）。",
        }

    async def generate_html(principal: Principal, args: dict[str, Any]) -> dict[str, Any]:
        title = _ensure_extension(_artifact_title(args), ".html")
        marker = _marker_arg(args)
        body = _optional_text(args, "body", maximum=_MAX_DOC_BODY)
        try:
            raw = build_html_document(title=title, marker=marker, body=body)
        except ValueError as exc:
            raise ToolError("tool.invalid_arguments", str(exc)) from exc
        # Store HTML as UTF-8 text so verify_html + human open can read it.
        # build_html_document returns bytes; base64 storage made L0 self-check
        # fail closed and models recited engineer walls into the main bubble (#394 Y1).
        content: str | bytes = raw
        if isinstance(raw, bytes):
            content = raw.decode("utf-8")
        result = await store.write(
            principal,
            title=title,
            content=content,
            kind="html",
        )
        result["format"] = "html"
        result["marker"] = marker
        return result

    async def generate_docx(principal: Principal, args: dict[str, Any]) -> dict[str, Any]:
        title = _ensure_extension(_artifact_title(args), ".docx")
        marker = _marker_arg(args)
        body = _optional_text(args, "body", maximum=_MAX_DOC_BODY)
        try:
            raw = build_docx_document(title=title, marker=marker, body=body)
        except ValueError as exc:
            raise ToolError("tool.invalid_arguments", str(exc)) from exc
        result = await store.write(
            principal,
            title=title,
            content=raw,
            kind="docx",
        )
        result["format"] = "docx"
        result["marker"] = marker
        return result

    async def generate_pptx(principal: Principal, args: dict[str, Any]) -> dict[str, Any]:
        title = _ensure_extension(_artifact_title(args), ".pptx")
        marker = _marker_arg(args)
        body = _optional_text(args, "body", maximum=_MAX_DOC_BODY)
        try:
            raw = build_pptx_document(title=title, marker=marker, body=body)
        except ValueError as exc:
            raise ToolError("tool.invalid_arguments", str(exc)) from exc
        result = await store.write(
            principal,
            title=title,
            content=raw,
            kind="pptx",
        )
        result["format"] = "pptx"
        result["marker"] = marker
        return result

    async def verify_html(principal: Principal, args: dict[str, Any]) -> dict[str, Any]:
        """Static HTML self-check — never claims runtime PASS without evidence."""
        artifact_id = args.get("artifact_id")
        title = args.get("title")
        artifact_id = str(artifact_id).strip() if artifact_id is not None else None
        title = str(title).strip() if title is not None else None
        inline = args.get("content")
        content: str | None = None
        source = "inline"
        art_meta: dict[str, Any] = {}
        if isinstance(inline, str) and inline.strip():
            content = inline
            if len(content) > _MAX_ARTIFACT_CONTENT:
                raise ToolError(
                    "tool.invalid_arguments",
                    f"content exceeds {_MAX_ARTIFACT_CONTENT} characters",
                )
        else:
            if not artifact_id and not title:
                raise ToolError(
                    "tool.invalid_arguments",
                    "artifact_id, title, or content is required",
                )
            result = await store.read(
                principal,
                artifact_id=artifact_id or None,
                title=title or None,
            )
            if result is None:
                raise ToolError("artifact.not_found", "Artifact not found")
            art_meta = {
                "artifact_id": result.get("artifact_id"),
                "title": result.get("title"),
                "kind": result.get("kind"),
            }
            body = result.get("content")
            if not isinstance(body, str) or not body.strip():
                # Legacy base64 HTML (bytes write path) — decode for structure only.
                b64 = result.get("content_base64")
                if isinstance(b64, str) and b64.strip():
                    import base64

                    try:
                        body = base64.b64decode(b64.encode("ascii"), validate=False).decode(
                            "utf-8", errors="replace"
                        )
                    except Exception:  # noqa: BLE001 — corrupt payload → fail check
                        body = None
            if not isinstance(body, str) or not body.strip():
                return {
                    "ok": False,
                    "overall": "fail",
                    "checks": [
                        {
                            "name": "content_readable",
                            "status": "fail",
                            "detail": "artifact is binary or empty text",
                        }
                    ],
                    # Machine-only note — never user-facing prose (human_package strips echoes).
                    "honest_note": "internal_only: content_unreadable; fix artifact, do not narrate to user",
                    **art_meta,
                }
            content = body
            source = "artifact"
        assert content is not None
        checks = _static_html_checks(content)
        statuses = {c["status"] for c in checks}
        if "fail" in statuses:
            overall = "fail"
        elif statuses == {"pass"} or statuses <= {"pass"}:
            overall = "pass"
        else:
            overall = "partial"
        # H3: layered verification — L0 structure only; L1 interaction never claimed here.
        # honest_note is control-plane only; models must not paste it into main bubble.
        verification_level = "L0_structure"
        interaction_status = "not_run"
        honest = (
            "internal_only: structure_ok; user reply = filename + open/download only; no L0/L1 dump"
            if overall != "fail"
            else "internal_only: structure_fail; fix or honest short failure; no field table to user"
        )
        return {
            "ok": overall != "fail",
            "overall": overall,
            "source": source,
            "checks": checks,
            "honest_note": honest,
            "verification_level": verification_level,
            "interaction_status": interaction_status,
            "levels": {
                "L0": {
                    "name": "structure",
                    "status": overall,
                    "ran": True,
                },
                "L1": {
                    "name": "browser_interaction",
                    "status": "not_run",
                    "ran": False,
                    "note": "internal_only: no headless browser in this tool",
                },
            },
            **art_meta,
        }

    return (
        write_file,
        read_file,
        list_files,
        kb_search,
        generate_html,
        generate_docx,
        generate_pptx,
        verify_html,
    )


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
    (
        write_file,
        read_file,
        list_files,
        kb_search,
        generate_html,
        generate_docx,
        generate_pptx,
        verify_html,
    ) = _workspace_handlers(store)
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
            name="kb_search",
            description=(
                "P2 knowledge pilot: search membership Artifact materials by keyword "
                "(full-text on ledger text, no vector DB). Returns excerpts + artifact_id "
                "citations, or honest_miss when nothing matches. Args: query, limit?"
            ),
            handler=kb_search,
            school_scoped=False,
        )
    )
    gw.register(
        ToolSpec(
            name="generate_html_document",
            description=(
                "Create a real .html Artifact with a unique visible marker. "
                "Safe for sandbox preview (no external scripts). Args: title, marker, body?"
            ),
            handler=generate_html,
            school_scoped=False,
        )
    )
    gw.register(
        ToolSpec(
            name="generate_docx_document",
            description=(
                "Create a real OOXML .docx Artifact (ZIP with Content_Types + word/document.xml) "
                "containing a unique marker. Args: title, marker, body?"
            ),
            handler=generate_docx,
            school_scoped=False,
        )
    )
    gw.register(
        ToolSpec(
            name="generate_pptx_document",
            description=(
                "Create a real OOXML .pptx Artifact (presentation + ≥1 slide) "
                "containing a unique marker. Args: title, marker, body?"
            ),
            handler=generate_pptx,
            school_scoped=False,
        )
    )
    gw.register(
        ToolSpec(
            name="verify_html_document",
            description=(
                "System-side static HTML structure self-check (artifact or inline content). "
                "Returns machine JSON for the control plane (overall/checks). "
                "Do NOT paste field names (verification_level, interaction_status, L0/L1) "
                "into the user chat — use results only to decide fix-or-honest-failure. "
                "Never claims browser/human usability. "
                "Args: artifact_id? | title? | content?"
            ),
            handler=verify_html,
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
    gw.register(
        ToolSpec(
            name="web_search",
            description=(
                "Search the public web via DeepSeek official server-side web_search. "
                "Use for current events, public facts, curriculum names, or anything "
                "that needs retrieval. Returns sources (title+url+snippet) or honest "
                "未检索. Args: query. Never invent citations."
            ),
            handler=web_search_handler,
            school_scoped=False,
        )
    )
    gw.register(
        ToolSpec(
            name="web_fetch",
            description=(
                "Read one public http(s) page into truncated text. "
                "Use when the user pasted a specific URL. Denies intranet, loopback, "
                "link-local, cloud metadata, and Pico/edu admin hosts. Args: url."
            ),
            handler=web_fetch_handler,
            school_scoped=False,
        )
    )
    # P2 MCP allowlist bridge (safe tools only; empty allowlist → none registered)
    for spec in mcp_tool_specs(store):
        gw.register(spec)
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
        "kb_search": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Keyword or question fragment to find in mounted materials",
                },
                "limit": {"type": "integer", "minimum": 1, "maximum": 50},
            },
            "required": ["query"],
        },
        "verify_html_document": {
            "type": "object",
            "properties": {
                "artifact_id": {
                    "type": "string",
                    "description": "Artifact id to verify (or title or content)",
                },
                "title": {
                    "type": "string",
                    "description": "Exact artifact title to verify",
                },
                "content": {
                    "type": "string",
                    "description": "Inline HTML to check when no artifact id/title",
                },
            },
        },
        "generate_html_document": {
            "type": "object",
            "properties": {
                "title": {
                    "type": "string",
                    "description": "Filename, preferably ending with .html",
                },
                "marker": {
                    "type": "string",
                    "description": "Unique visible marker string required in the HTML body",
                },
                "body": {"type": "string", "description": "Optional extra body text"},
            },
            "required": ["title", "marker"],
        },
        "generate_docx_document": {
            "type": "object",
            "properties": {
                "title": {
                    "type": "string",
                    "description": "Filename, preferably ending with .docx",
                },
                "marker": {
                    "type": "string",
                    "description": "Unique visible marker string required in the document",
                },
                "body": {"type": "string", "description": "Optional extra paragraph text"},
            },
            "required": ["title", "marker"],
        },
        "generate_pptx_document": {
            "type": "object",
            "properties": {
                "title": {
                    "type": "string",
                    "description": "Filename, preferably ending with .pptx",
                },
                "marker": {
                    "type": "string",
                    "description": "Unique visible marker string required on the slide",
                },
                "body": {"type": "string", "description": "Optional extra slide text"},
            },
            "required": ["title", "marker"],
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
        "web_search": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search query for DeepSeek official web_search",
                }
            },
            "required": ["query"],
        },
        "web_fetch": {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "Public http(s) URL to read (no intranet)",
                }
            },
            "required": ["url"],
        },
        **mcp_openai_parameters(),
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
