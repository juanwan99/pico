"""Pico allowlist tools + OpenAI schemas for the multi-step agent loop."""

from __future__ import annotations

import ast
import asyncio
import base64
import logging
import math
import operator
import re
import time
from pathlib import Path
from typing import Any

from pico_orchestrator.artifact_types import (
    is_valid_ooxml_package,
    reject_fake_protected_write_message,
    title_protected_extension,
)
from pico_orchestrator.document_generators import (
    KNOWN_CALC_CELL,
    build_docx_document,
    build_html_document,
    build_pptx_document,
    build_xlsx_document,
    require_docx_body,
    require_pptx_body,
)
from pico_orchestrator.edu_adapter import EduAdapterError, list_classes
from pico_orchestrator.gateway import (
    AllowlistGateway,
    ArtifactStore,
    Principal,
    ToolError,
    ToolSpec,
)
from pico_orchestrator.image_generate import generate_image_bytes
from pico_orchestrator.mcp_bridge import mcp_openai_parameters, mcp_tool_specs
from pico_orchestrator.meili_kb import extract_index_text, meili_configured, search_materials
from pico_orchestrator.office.edit import edit_by_address
from pico_orchestrator.office.inspect import inspect_bytes
from pico_orchestrator.office.qa import verify_bytes
from pico_orchestrator.office.render import render_spec
from pico_orchestrator.office.spec import (
    SpecError,
    attach_image_block,
    body_has_markdown_table,
    parse_spec,
    spec_from_plain_body,
)
from pico_orchestrator.office_editors import edit_docx_bytes, edit_pptx_title_bytes
from pico_orchestrator.sandbox_s1 import (
    MAX_CONTENT_CHARS,
    assert_content_caps,
    assert_same_run,
    attach_preview_meta,
    current_run_id,
    deny_non_preview_url,
    deny_secret_filename,
    extract_title_h1,
    html_from_artifact_row,
    light_exec_with_timeout,
    materialize_workspace_html,
    safe_segment,
    try_parse_artifact_preview_url,
    verify_preview_sig,
    with_io_timeout,
    workspace_id_for,
)
from pico_orchestrator.sandbox_s2 import PNG_MAGIC, raster_html_isolated, raster_meta_from_write
from pico_orchestrator.sandbox_sidecar import sidecar_json
from pico_orchestrator.usage_hook import emit_sandbox_usage
from pico_orchestrator.web_guard import parse_public_http_url
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
_EDIT_TIMEOUT_S = 20.0
_IMAGE_TIMEOUT_S = 45.0

logger = logging.getLogger(__name__)


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


def _optional_int(args: dict[str, Any], key: str, *, default: int | None = None) -> int | None:
    value = args.get(key)
    if value is None or value == "":
        return default
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise ToolError("tool.invalid_arguments", f"{key} 必须是整数") from exc


def _artifact_bytes(row: dict[str, Any]) -> bytes:
    b64 = row.get("content_base64")
    if isinstance(b64, str) and b64.strip():
        try:
            return base64.b64decode(b64.encode("ascii"), validate=False)
        except Exception as exc:
            raise ToolError("artifact.corrupt", "文件内容损坏，打不开。") from exc
    body = row.get("content")
    if isinstance(body, bytes) and body:
        return body
    raise ToolError("artifact.not_binary", "这份不是可改的 Word/PPT 原件。请先在工作台上传原件。")


async def _run_bounded(awaitable: Any, *, seconds: float, code: str, message: str) -> Any:
    try:
        return await asyncio.wait_for(awaitable, timeout=seconds)
    except TimeoutError as exc:
        raise ToolError(code, message) from exc


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
) -> tuple[Any, ...]:
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
        assert_content_caps(content)
        deny_secret_filename(title)
        kind = str(args.get("kind") or "file").strip().lower()
        if kind not in {"doc", "file", "json", "outline", "text"}:
            raise ToolError("tool.invalid_arguments", "unsupported artifact kind")
        result = await with_io_timeout(
            store.write(
                principal,
                title=title,
                content=content,
                kind=kind,
            ),
            what="workspace_write_file",
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
        result = await with_io_timeout(
            store.read(
                principal,
                artifact_id=artifact_id or None,
                title=title or None,
            ),
            what="workspace_read_file",
        )
        if result is None:
            raise ToolError("artifact.not_found", "Artifact not found")
        body = result.get("content")
        if isinstance(body, str) and len(body) > MAX_CONTENT_CHARS:
            result = dict(result)
            result["content"] = body[:MAX_CONTENT_CHARS]
            result["truncated"] = True
        return {"artifact": result}

    async def list_files(principal: Principal, args: dict[str, Any]) -> dict[str, Any]:
        try:
            limit = int(args.get("limit") or 20)
        except (TypeError, ValueError) as exc:
            raise ToolError("tool.invalid_arguments", "limit must be an integer") from exc
        if not 1 <= limit <= 100:
            raise ToolError("tool.invalid_arguments", "limit must be between 1 and 100")
        artifacts = await with_io_timeout(
            store.list(principal, limit=limit),
            what="workspace_list_files",
        )
        return {"artifacts": artifacts, "count": len(artifacts)}

    async def _scan_kb_hits(
        principal: Principal, query: str, limit: int
    ) -> list[dict[str, Any]]:
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
            raw = None
            b64 = full.get("content_base64")
            if isinstance(b64, str) and b64:
                try:
                    raw = base64.b64decode(b64)
                except Exception:  # noqa: BLE001
                    raw = None
            text = extract_index_text(
                title=title,
                kind=str(full.get("kind") or ""),
                content=content if isinstance(content, str) else None,
                raw=raw,
            )
            if not text:
                if q_low not in title.lower():
                    continue
                hits.append(
                    {
                        "artifact_id": art_id,
                        "title": title,
                        "kind": full.get("kind"),
                        "excerpt": f"（材料未能抽出正文，标题命中：{title}）",
                        "match": "title",
                    }
                )
                continue
            title_hit = q_low in title.lower()
            body_hit = q_low in text.lower()
            if not title_hit and not body_hit:
                continue
            hits.append(
                {
                    "artifact_id": art_id,
                    "title": title,
                    "kind": full.get("kind"),
                    "excerpt": _excerpt_around(text if body_hit else title, query),
                    "match": "title+body" if title_hit and body_hit else (
                        "title" if title_hit else "body"
                    ),
                }
            )
            if len(hits) >= limit:
                break
        return hits

    async def kb_search(principal: Principal, args: dict[str, Any]) -> dict[str, Any]:
        """Search membership materials via Meili projection; scan fallback if Meili is down."""
        query = _required_text(args, "query", maximum=_MAX_KB_QUERY)
        try:
            limit = int(args.get("limit") or 20)
        except (TypeError, ValueError) as exc:
            raise ToolError("tool.invalid_arguments", "limit must be an integer") from exc
        if not 1 <= limit <= 50:
            raise ToolError("tool.invalid_arguments", "limit must be between 1 and 50")
        # Client filter strings are ignored. Tenant filter is server-injected in Meili.

        degraded = False
        mode = "scan"
        hits: list[dict[str, Any]] = []
        if meili_configured():
            try:
                result = search_materials(
                    query,
                    school_id=principal.school_id,
                    membership_id=principal.membership_id,
                    limit=limit,
                )
                mode = "hybrid" if result.get("hybrid") else "keyword"
                for row in result.get("hits") or []:
                    if not isinstance(row, dict):
                        continue
                    art_id = str(row.get("artifact_id") or "")
                    title = str(row.get("title") or "")
                    text = str(row.get("text") or "")
                    row_school = str(row.get("school_id") or "").strip()
                    row_member = str(row.get("membership_id") or "").strip()
                    if row_school and row_school != principal.school_id:
                        continue
                    if row_member and row_member != principal.membership_id:
                        continue
                    if not art_id or title in _SKIP_KB_TITLES:
                        continue
                    hits.append(
                        {
                            "artifact_id": art_id,
                            "title": title,
                            "kind": row.get("kind"),
                            "excerpt": _excerpt_around(text or title, query),
                            "match": "index",
                        }
                    )
            except Exception:  # noqa: BLE001 — Meili down: honest scan fallback
                degraded = True
                mode = "scan"
                hits = await _scan_kb_hits(principal, query, limit)
        else:
            hits = await _scan_kb_hits(principal, query, limit)

        sources = [
            {
                "title": str(h.get("title") or "材料"),
                "artifact_id": str(h.get("artifact_id") or ""),
                "snippet": str(h.get("excerpt") or ""),
                "url": "",
            }
            for h in hits
            if h.get("artifact_id")
        ]
        if not hits:
            return {
                "hits": [],
                "count": 0,
                "honest_miss": True,
                "degraded": degraded,
                "mode": mode,
                "retrieved": False,
                "sources": [],
                "user_message": (
                    "未在已入库材料中命中该问题。"
                    "请先把材料写入账本（可重建进 Meili）后再问，或换关键词。"
                ),
            }
        engine = (
            "语义检索"
            if mode == "hybrid"
            else "关键词检索" if mode == "keyword" else "账本扫描"
        )
        if degraded:
            engine = "检索降级为账本扫描"
        return {
            "hits": hits,
            "count": len(hits),
            "honest_miss": False,
            "degraded": degraded,
            "mode": mode,
            "retrieved": True,
            "sources": sources,
            "user_message": f"命中 {len(hits)} 条材料依据（{engine}，含出处）。",
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
        result = await with_io_timeout(
            store.write(
                principal,
                title=title,
                content=content,
                kind="html",
            ),
            what="generate_html_document",
        )
        result["format"] = "html"
        result["marker"] = marker
        result = attach_preview_meta(result, principal, store=store)
        run_id = current_run_id(principal, store) or result.get("run_id")
        if isinstance(content, str):
            materialize_workspace_html(
                principal,
                run_id=str(run_id) if run_id else None,
                title=title,
                content=content,
            )
        school = result.get("school") if isinstance(result.get("school"), dict) else {}
        if school.get("landed") is True:
            result["school_landed"] = True
        elif school:
            result["school_landed"] = False
            note = str(school.get("user_message") or school.get("error") or "").strip()
            if note:
                result["user_message"] = note
        await emit_sandbox_usage(
            principal,
            extra={
                "duration_ms": 0,
                "artifact_id": result.get("artifact_id"),
                "workspace_id": result.get("workspace_id"),
                "phase": "write",
                "tool": "generate_html_document",
            },
            ok=True,
        )
        return result

    async def _office_images_from_spec(
        principal: Principal, spec: dict[str, Any]
    ) -> dict[str, bytes]:
        ids: list[str] = []
        for block in spec.get("blocks") or []:
            if not isinstance(block, dict):
                continue
            if block.get("type") == "image":
                aid = str(block.get("artifact_id") or "").strip()
                if aid:
                    ids.append(aid)
            image = block.get("image")
            if isinstance(image, dict):
                aid = str(image.get("artifact_id") or "").strip()
                if aid:
                    ids.append(aid)
        out: dict[str, bytes] = {}
        for aid in ids:
            row = await store.read(principal, artifact_id=aid)
            if row is None:
                raise ToolError(
                    "artifact.not_found",
                    f"找不到图 {aid}。请先 generate_image，再把 artifact_id 写进 spec。",
                )
            try:
                out[aid] = _artifact_bytes(row)
            except ToolError as exc:
                raise ToolError(
                    "artifact.not_image",
                    f"artifact {aid} 不是可插入的图。",
                ) from exc
        return out

    def _spec_arg(args: dict[str, Any]) -> dict[str, Any] | None:
        raw = args.get("spec")
        if raw is None or raw == "":
            return None
        try:
            return parse_spec(raw)
        except SpecError as exc:
            raise ToolError("tool.invalid_arguments", str(exc)) from exc

    async def generate_docx(principal: Principal, args: dict[str, Any]) -> dict[str, Any]:
        title = _ensure_extension(_artifact_title(args), ".docx")
        marker = _marker_arg(args)
        body = _optional_text(args, "body", maximum=_MAX_DOC_BODY)
        spec = _spec_arg(args)
        image_id = args.get("image_artifact_id")
        image_id = str(image_id).strip() if image_id is not None else ""
        try:
            if spec is None:
                if not body_has_markdown_table(body) and not image_id:
                    require_docx_body(body)
                spec = spec_from_plain_body(
                    kind="docx", title=title, marker=marker, body=body
                )
            if image_id:
                spec = attach_image_block(spec, artifact_id=image_id)
            images = await _office_images_from_spec(principal, spec)
            raw = build_docx_document(
                title=title, marker=marker, spec=spec, images=images
            )
        except (ValueError, SpecError) as exc:
            raise ToolError("tool.invalid_arguments", str(exc)) from exc
        result = await store.write(
            principal,
            title=title,
            content=raw,
            kind="docx",
        )
        result["format"] = "docx"
        result["marker"] = marker
        result["spec_version"] = spec.get("version")
        return result

    async def generate_pptx(principal: Principal, args: dict[str, Any]) -> dict[str, Any]:
        title = _ensure_extension(_artifact_title(args), ".pptx")
        marker = _marker_arg(args)
        body = _optional_text(args, "body", maximum=_MAX_DOC_BODY)
        spec = _spec_arg(args)
        image_id = args.get("image_artifact_id")
        image_id = str(image_id).strip() if image_id is not None else ""
        try:
            if spec is None:
                require_pptx_body(body)
                spec = spec_from_plain_body(
                    kind="pptx", title=title, marker=marker, body=body
                )
            if image_id:
                spec = attach_image_block(spec, artifact_id=image_id)
            images = await _office_images_from_spec(principal, spec)
            raw = build_pptx_document(
                title=title, marker=marker, spec=spec, images=images
            )
        except (ValueError, SpecError) as exc:
            raise ToolError("tool.invalid_arguments", str(exc)) from exc
        result = await store.write(
            principal,
            title=title,
            content=raw,
            kind="pptx",
        )
        result["format"] = "pptx"
        result["marker"] = marker
        result["spec_version"] = spec.get("version")
        return result

    async def inspect_document(principal: Principal, args: dict[str, Any]) -> dict[str, Any]:
        row, raw, ext = await _load_office_any(principal, args)
        try:
            outline = inspect_bytes(raw, ext)
        except ValueError as exc:
            raise ToolError("tool.invalid_arguments", str(exc)) from exc
        outline["artifact_id"] = row.get("artifact_id")
        outline["title"] = row.get("title")
        return outline

    async def render_document(principal: Principal, args: dict[str, Any]) -> dict[str, Any]:
        spec = _spec_arg(args)
        if spec is None:
            raise ToolError("tool.invalid_arguments", "render_document 需要 spec（pico.office.spec/v1）。")
        marker = _marker_arg(args)
        image_id = args.get("image_artifact_id")
        image_id = str(image_id).strip() if image_id is not None else ""
        try:
            if image_id:
                spec = attach_image_block(spec, artifact_id=image_id)
            images = await _office_images_from_spec(principal, spec)
            raw = render_spec(spec, images=images)
        except (ValueError, SpecError) as exc:
            raise ToolError("tool.invalid_arguments", str(exc)) from exc
        kind = spec["kind"]
        default_title = spec.get("title") or ("文档.docx" if kind == "docx" else "课件.pptx")
        title = _ensure_extension(
            str(args.get("title") or default_title),
            f".{kind}",
        )
        result = await store.write(principal, title=title, content=raw, kind=kind)
        result["format"] = kind
        result["marker"] = marker
        result["spec_version"] = spec.get("version")
        return result

    async def edit_document(principal: Principal, args: dict[str, Any]) -> dict[str, Any]:
        row, raw, ext = await _load_office_any(principal, args)
        address = args.get("address")
        address = str(address).strip() if address is not None else ""
        if not address:
            para_i = _optional_int(args, "paragraph_index")
            slide_i = _optional_int(args, "slide_index")
            if para_i is not None:
                address = f"p:{para_i}"
            elif slide_i is not None:
                address = f"s:{slide_i}.title"
        text = args.get("text")
        if text is None:
            text = args.get("new_title")
        text = str(text).strip() if text is not None else ""
        try:
            edited = await _run_bounded(
                asyncio.to_thread(
                    edit_by_address, raw, ext=ext, address=address, text=text
                ),
                seconds=_EDIT_TIMEOUT_S,
                code="office.timeout",
                message="改文档超时（20 秒）。请换更小的文件或稍后再试。",
            )
        except ValueError as exc:
            raise ToolError("tool.invalid_arguments", str(exc)) from exc
        kind = "docx" if ext == ".docx" else "pptx"
        out_title = _ensure_extension(
            str(args.get("output_title") or row.get("title") or f"已改.{kind}"),
            f".{kind}",
        )
        result = await store.write(principal, title=out_title, content=edited, kind=kind)
        result["format"] = kind
        result["edited"] = True
        result["address"] = address
        result["source_artifact_id"] = row.get("artifact_id")
        return result

    async def verify_document(principal: Principal, args: dict[str, Any]) -> dict[str, Any]:
        row, raw, ext = await _load_office_any(principal, args)
        report = verify_bytes(raw, ext)
        report["artifact_id"] = row.get("artifact_id")
        report["title"] = row.get("title")
        if not report.get("ok"):
            return report
        return report

    async def _load_office_any(
        principal: Principal, args: dict[str, Any]
    ) -> tuple[dict[str, Any], bytes, str]:
        artifact_id = args.get("artifact_id")
        title = args.get("title")
        artifact_id = str(artifact_id).strip() if artifact_id is not None else None
        title = str(title).strip() if title is not None else None
        if not artifact_id and not title:
            raise ToolError(
                "tool.invalid_arguments",
                "请提供已上传文件的 artifact_id 或 title。",
            )
        row = await store.read(
            principal,
            artifact_id=artifact_id or None,
            title=title or None,
        )
        if row is None:
            raise ToolError(
                "artifact.not_found",
                "找不到这份文件。请先在工作台上传或生成原件。",
            )
        raw = _artifact_bytes(row)
        kind = str(row.get("kind") or "").lower()
        title_name = str(row.get("title") or "")
        if kind == "docx" or title_name.lower().endswith(".docx"):
            ext = ".docx"
        elif kind == "pptx" or title_name.lower().endswith(".pptx"):
            ext = ".pptx"
        else:
            raise ToolError("artifact.not_ooxml", "这份不是 Word/PPT，不能 inspect/edit/verify。")
        return row, raw, ext

    async def _load_office(
        principal: Principal,
        args: dict[str, Any],
        *,
        ext: str,
    ) -> tuple[dict[str, Any], bytes]:
        artifact_id = args.get("artifact_id")
        title = args.get("title")
        artifact_id = str(artifact_id).strip() if artifact_id is not None else None
        title = str(title).strip() if title is not None else None
        if not artifact_id and not title:
            raise ToolError(
                "tool.invalid_arguments",
                "请提供已上传文件的 artifact_id 或 title。",
            )
        row = await store.read(
            principal,
            artifact_id=artifact_id or None,
            title=title or None,
        )
        if row is None:
            raise ToolError(
                "artifact.not_found",
                "找不到这份文件。请先在工作台上传原件再改。",
            )
        raw = _artifact_bytes(row)
        if not is_valid_ooxml_package(raw, ext):
            raise ToolError(
                "artifact.not_ooxml",
                f"这份不是真 {ext} 原件，不能当改稿保存。",
            )
        return row, raw

    async def edit_docx(principal: Principal, args: dict[str, Any]) -> dict[str, Any]:
        row, raw = await _load_office(principal, args, ext=".docx")
        index = _optional_int(args, "paragraph_index")
        if index is None:
            raise ToolError("tool.invalid_arguments", "请指定 paragraph_index（从 1 起）。")
        text = _required_text(args, "text", maximum=_MAX_DOC_BODY)
        try:
            edited = await _run_bounded(
                asyncio.to_thread(
                    edit_docx_bytes, raw, paragraph_index=index, text=text
                ),
                seconds=_EDIT_TIMEOUT_S,
                code="office.timeout",
                message="改文档超时（20 秒）。请换更小的文件或稍后再试。",
            )
        except ValueError as exc:
            raise ToolError("tool.invalid_arguments", str(exc)) from exc
        out_title = _ensure_extension(
            str(args.get("output_title") or row.get("title") or "已改.docx"),
            ".docx",
        )
        result = await store.write(
            principal,
            title=out_title,
            content=edited,
            kind="docx",
        )
        result["format"] = "docx"
        result["edited"] = True
        result["paragraph_index"] = index
        result["source_artifact_id"] = row.get("artifact_id")
        return result

    async def edit_pptx(principal: Principal, args: dict[str, Any]) -> dict[str, Any]:
        row, raw = await _load_office(principal, args, ext=".pptx")
        index = _optional_int(args, "slide_index", default=1) or 1
        new_title = _required_text(args, "new_title", maximum=500)
        try:
            edited = await _run_bounded(
                asyncio.to_thread(
                    edit_pptx_title_bytes, raw, slide_index=index, new_title=new_title
                ),
                seconds=_EDIT_TIMEOUT_S,
                code="office.timeout",
                message="改文档超时（20 秒）。请换更小的文件或稍后再试。",
            )
        except ValueError as exc:
            raise ToolError("tool.invalid_arguments", str(exc)) from exc
        out_title = _ensure_extension(
            str(args.get("output_title") or row.get("title") or "已改.pptx"),
            ".pptx",
        )
        result = await store.write(
            principal,
            title=out_title,
            content=edited,
            kind="pptx",
        )
        result["format"] = "pptx"
        result["edited"] = True
        result["slide_index"] = index
        result["source_artifact_id"] = row.get("artifact_id")
        return result

    async def generate_image(principal: Principal, args: dict[str, Any]) -> dict[str, Any]:
        prompt = _required_text(args, "prompt", maximum=2000)
        title_raw = args.get("title")
        title_hint = str(title_raw).strip() if isinstance(title_raw, str) else ""
        raw, ext = await _run_bounded(
            generate_image_bytes(prompt),
            seconds=_IMAGE_TIMEOUT_S,
            code="image.timeout",
            message="出图超时（45 秒）。请稍后重试，不能编造图片。",
        )
        title = _ensure_extension(title_hint or "课堂示意图", f".{ext}")
        kind = "png" if ext == "png" else "jpg"
        result = await store.write(
            principal,
            title=title,
            content=raw,
            kind=kind,
        )
        result["format"] = ext
        result["user_message"] = "图已生成，可在结果区下载。"
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

    async def inspect_preview(principal: Principal, args: dict[str, Any]) -> dict[str, Any]:
        """S2 see-page: title/h1 plus PNG raster of THIS run's HTML. Never fetches URLs."""
        started = time.perf_counter()
        artifact_id = args.get("artifact_id")
        artifact_id = str(artifact_id).strip() if artifact_id is not None else None
        preview_url = args.get("preview_url") or args.get("url")
        preview_url = str(preview_url).strip() if preview_url is not None else None
        run_id = current_run_id(principal, store)
        phase_extra: dict[str, Any] = {
            "tool": "sandbox_preview_inspect",
            "phase": "inspect",
            "workspace_id": workspace_id_for(
                principal.school_id, principal.membership_id, run_id
            ),
        }

        async def _emit(ok: bool, extra: dict[str, Any]) -> None:
            duration_ms = int((time.perf_counter() - started) * 1000)
            payload = {**phase_extra, **extra, "duration_ms": duration_ms}
            await emit_sandbox_usage(principal, extra=payload, ok=ok)

        try:
            if not artifact_id and preview_url:
                parsed = try_parse_artifact_preview_url(preview_url)
                from urllib.parse import urlparse as _urlparse

                host_present = bool(
                    _urlparse(preview_url).scheme in {"http", "https"}
                    and _urlparse(preview_url).hostname
                )
                if parsed and parsed.get("has_sig"):
                    err = verify_preview_sig(
                        artifact_id=str(parsed["artifact_id"]),
                        school_id=principal.school_id,
                        membership_id=principal.membership_id,
                        run_id=run_id,
                        exp=int(parsed.get("exp") or 0),
                        sig=str(parsed.get("sig") or ""),
                    )
                    if err:
                        if host_present:
                            deny_non_preview_url(preview_url)
                        raise ToolError(err, "预览签名无效或已过期")
                    artifact_id = str(parsed["artifact_id"])
                elif parsed and not host_present:
                    artifact_id = str(parsed["artifact_id"])
                else:
                    deny_non_preview_url(preview_url)
            if not artifact_id:
                raise ToolError(
                    "tool.invalid_arguments",
                    "artifact_id or preview_url is required",
                )
            row = await with_io_timeout(
                store.read(principal, artifact_id=artifact_id, title=None),
                what="sandbox_preview_inspect",
            )
            if row is None:
                raise ToolError("artifact.not_found", "Artifact not found")
            assert_same_run(row, run_id)
            html = html_from_artifact_row(row)
            title_text, h1_text = extract_title_h1(html)
            seen = bool(title_text or h1_text)
            meta = attach_preview_meta(
                {
                    "artifact_id": row.get("artifact_id") or artifact_id,
                    "run_id": row.get("run_id") or run_id,
                    "title": row.get("title"),
                    "kind": row.get("kind"),
                },
                principal,
                store=store,
            )
            raster_fields: dict[str, Any] = {}
            screenshot_id = None
            try:
                png = await raster_html_isolated(html)
                if png and png.startswith(PNG_MAGIC):
                    shot_title = (
                        f"inspect-{safe_segment(str(meta.get('artifact_id') or 'page'), fallback='page')}.png"
                    )
                    deny_secret_filename(shot_title)
                    shot = await with_io_timeout(
                        store.write(
                            principal,
                            title=shot_title,
                            content=png,
                            kind="image",
                        ),
                        what="sandbox_preview_inspect_raster",
                    )
                    raster_fields = raster_meta_from_write(shot, byte_size=len(png))
                    screenshot_id = raster_fields.get("screenshot", {}).get("artifact_id")
                    seen = True
            except Exception:  # noqa: BLE001 — raster must not drop title/h1
                raster_fields = {}
            out = {
                "ok": True,
                "seen": seen,
                "title": title_text,
                "h1": h1_text,
                "artifact_id": meta.get("artifact_id"),
                "preview_path": meta.get("preview_path"),
                "preview_url": meta.get("preview_url"),
                "workspace_id": meta.get("workspace_id"),
                "message": (
                    f"已看见页面 title={title_text or '（无）'} h1={h1_text or '（无）'}"
                    if (title_text or h1_text)
                    else "已打开本次预览，但文档没有 title/h1"
                ),
                **raster_fields,
            }
            extra_ok: dict[str, Any] = {
                "artifact_id": out["artifact_id"],
                "workspace_id": out["workspace_id"],
                "seen": seen,
            }
            if screenshot_id:
                extra_ok["screenshot_artifact_id"] = screenshot_id
            await _emit(True, extra_ok)
            return out
        except ToolError as exc:
            await _emit(False, {"error_code": exc.code, "artifact_id": artifact_id})
            raise

    async def workspace_exec(principal: Principal, args: dict[str, Any]) -> dict[str, Any]:
        """Optional light exec: parse HTML/Python inside the isolation dir. No bash."""
        started = time.perf_counter()
        source = args.get("source") or args.get("code")
        html = args.get("html")
        run_id = current_run_id(principal, store)
        ws = workspace_id_for(principal.school_id, principal.membership_id, run_id)
        try:
            if isinstance(html, str) and html.strip():
                assert_content_caps(html)
                title_text, h1_text = extract_title_h1(html)
                materialize_workspace_html(
                    principal,
                    run_id=run_id,
                    title=str(args.get("title") or "exec.html"),
                    content=html,
                )
                out = {
                    "ok": True,
                    "parsed": True,
                    "executed": False,
                    "title": title_text,
                    "h1": h1_text,
                    "workspace_id": ws,
                }
            elif isinstance(source, str) and source.strip():
                parsed = await light_exec_with_timeout(source)
                out = {**parsed, "workspace_id": ws}
            else:
                raise ToolError(
                    "tool.invalid_arguments",
                    "source or html is required",
                )
            duration_ms = int((time.perf_counter() - started) * 1000)
            await emit_sandbox_usage(
                principal,
                extra={
                    "duration_ms": duration_ms,
                    "workspace_id": ws,
                    "phase": "exec",
                    "tool": "sandbox_workspace_exec",
                },
                ok=True,
            )
            return out
        except ToolError as exc:
            duration_ms = int((time.perf_counter() - started) * 1000)
            await emit_sandbox_usage(
                principal,
                extra={
                    "duration_ms": duration_ms,
                    "workspace_id": ws,
                    "phase": "exec",
                    "tool": "sandbox_workspace_exec",
                    "error_code": exc.code,
                },
                ok=False,
            )
            raise

    async def browser_open(principal: Principal, args: dict[str, Any]) -> dict[str, Any]:
        """B2: open a public page in the isolated sidecar. Human-in-the-loop login."""
        started = time.perf_counter()
        url = args.get("url")
        if not isinstance(url, str) or not url.strip():
            raise ToolError("tool.invalid_arguments", "url 必须是非空字符串")
        url = url.strip()
        run_id = current_run_id(principal, store)
        ws = workspace_id_for(principal.school_id, principal.membership_id, run_id)
        extra_base: dict[str, Any] = {
            "tool": "sandbox_browser_open",
            "phase": "browser_open",
            "workspace_id": ws,
        }

        async def _emit(ok: bool, extra: dict[str, Any]) -> None:
            duration_ms = int((time.perf_counter() - started) * 1000)
            await emit_sandbox_usage(
                principal,
                extra={**extra_base, **extra, "duration_ms": duration_ms},
                ok=ok,
            )

        try:
            parse_public_http_url(url)
            out = await sidecar_json(
                "POST",
                "/v1/internal/sessions/open",
                json_body={
                    "school_id": principal.school_id,
                    "membership_id": principal.membership_id,
                    "run_id": run_id,
                    "url": url,
                },
            )
            if not isinstance(out, dict):
                raise ToolError("sandbox.unavailable", "隔离沙箱返回异常")
            extra_ok = {
                "workspace_id": out.get("workspace_id") or ws,
                "session_id": out.get("session_id"),
            }
            await _emit(True, extra_ok)
            return out
        except ToolError as exc:
            await _emit(False, {"error_code": exc.code, "workspace_id": ws})
            raise

    async def browser_screenshot(principal: Principal, args: dict[str, Any]) -> dict[str, Any]:
        started = time.perf_counter()
        session_id = str(args.get("session_id") or "").strip()
        if not session_id:
            raise ToolError("tool.invalid_arguments", "session_id 必须是非空字符串")
        run_id = current_run_id(principal, store)
        ws = workspace_id_for(principal.school_id, principal.membership_id, run_id)

        async def _emit(ok: bool, extra: dict[str, Any]) -> None:
            duration_ms = int((time.perf_counter() - started) * 1000)
            await emit_sandbox_usage(
                principal,
                extra={
                    "tool": "sandbox_browser_screenshot",
                    "phase": "browser_screenshot",
                    "workspace_id": ws,
                    "session_id": session_id,
                    "duration_ms": duration_ms,
                    **extra,
                },
                ok=ok,
            )

        try:
            out = await sidecar_json(
                "GET",
                f"/v1/internal/sessions/{session_id}",
                params={
                    "school_id": principal.school_id,
                    "membership_id": principal.membership_id,
                },
            )
            if not isinstance(out, dict):
                raise ToolError("sandbox.unavailable", "隔离沙箱返回异常")
            await _emit(True, {"workspace_id": out.get("workspace_id") or ws})
            return out
        except ToolError as exc:
            await _emit(False, {"error_code": exc.code})
            raise

    async def document_open(principal: Principal, args: dict[str, Any]) -> dict[str, Any]:
        """Open a real Office file in sidecar LibreOffice (Writer/Calc/Impress)."""
        import base64

        started = time.perf_counter()
        kind = str(args.get("kind") or "writer").strip().lower() or "writer"
        filename = str(args.get("filename") or args.get("title") or "").strip()
        artifact_id = str(args.get("artifact_id") or "").strip()
        body_text = _optional_text(args, "body", maximum=_MAX_DOC_BODY)
        run_id = current_run_id(principal, store)
        ws = workspace_id_for(principal.school_id, principal.membership_id, run_id)
        extra_base: dict[str, Any] = {
            "tool": "sandbox_document_open",
            "phase": "document_open",
            "workspace_id": ws,
        }

        async def _emit(ok: bool, extra: dict[str, Any]) -> None:
            duration_ms = int((time.perf_counter() - started) * 1000)
            await emit_sandbox_usage(
                principal,
                extra={**extra_base, **extra, "duration_ms": duration_ms},
                ok=ok,
            )

        try:
            if kind == "files":
                out = await sidecar_json(
                    "POST",
                    "/v1/internal/sessions/open",
                    json_body={
                        "school_id": principal.school_id,
                        "membership_id": principal.membership_id,
                        "run_id": run_id,
                        "kind": "files",
                    },
                )
                if not isinstance(out, dict):
                    raise ToolError("sandbox.unavailable", "隔离沙箱返回异常")
                await _emit(True, {"session_id": out.get("session_id"), "workspace_id": out.get("workspace_id") or ws})
                return out
            raw: bytes | None = None
            if artifact_id:
                row = await store.read(principal, artifact_id=artifact_id, title=None)
                if not row:
                    raise ToolError("artifact.not_found", "找不到该文档产物")
                filename = filename or str(row.get("title") or row.get("user_label") or "document.docx")
                encoding = str(row.get("content_encoding") or "utf8").lower()
                if encoding == "base64" and row.get("content_base64"):
                    raw = base64.b64decode(str(row.get("content_base64") or ""), validate=False)
                elif isinstance(row.get("content"), (bytes, bytearray)):
                    raw = bytes(row.get("content"))
                elif isinstance(row.get("content"), str) and row.get("content"):
                    # Binary artifacts should be base64; refuse to treat UTF-8 as OOXML.
                    raise ToolError(
                        "tool.invalid_arguments",
                        "该产物不是二进制 Office 包，拒绝当 Word 打开",
                    )
            if raw is None and filename and not body_text:
                listing = await sidecar_json(
                    "GET",
                    "/v1/internal/disk",
                    params={
                        "school_id": principal.school_id,
                        "membership_id": principal.membership_id,
                    },
                )
                names: list[str] = []
                if isinstance(listing, dict):
                    for item in listing.get("files") or []:
                        if isinstance(item, dict) and item.get("name"):
                            names.append(str(item["name"]))
                want = Path(filename).name
                if want and want in names:
                    out = await sidecar_json(
                        "POST",
                        "/v1/internal/sessions/open",
                        json_body={
                            "school_id": principal.school_id,
                            "membership_id": principal.membership_id,
                            "run_id": run_id,
                            "kind": kind or "writer",
                            "filename": want,
                        },
                    )
                    if not isinstance(out, dict):
                        raise ToolError("sandbox.unavailable", "隔离沙箱返回异常")
                    await _emit(
                        True,
                        {"session_id": out.get("session_id"), "workspace_id": out.get("workspace_id") or ws},
                    )
                    return out
            if raw is None:
                name = (filename or "").lower()
                if kind in {"calc"} or name.endswith((".xlsx", ".xls", ".ods", ".csv")):
                    title = filename or "课堂成绩.xlsx"
                    filename = _ensure_extension(title, ".xlsx")
                    kind = "calc"
                    raw = build_xlsx_document(
                        title=title,
                        marker=_marker_arg({"marker": args.get("marker")}),
                        body=body_text or KNOWN_CALC_CELL,
                    )
                elif kind in {"impress"} or name.endswith((".pptx", ".ppt", ".odp")):
                    title = filename or "课堂演示.pptx"
                    filename = _ensure_extension(title, ".pptx")
                    kind = "impress"
                    raw = build_pptx_document(
                        title=title,
                        marker=_marker_arg({"marker": args.get("marker")}),
                        body=body_text or "NIGHT-P4-SLIDE-ALPHA",
                    )
                else:
                    title = filename or "课堂笔记.docx"
                    filename = _ensure_extension(title, ".docx")
                    kind = "writer"
                    raw = build_docx_document(
                        title=title,
                        marker=_marker_arg({"marker": args.get("marker")}),
                        body=body_text or "沙箱里的这份 Word 正文。打开 = Writer 窗口，不是 PDF。",
                    )
            out = await sidecar_json(
                "POST",
                "/v1/internal/sessions/open",
                json_body={
                    "school_id": principal.school_id,
                    "membership_id": principal.membership_id,
                    "run_id": run_id,
                    "kind": kind or "writer",
                    "filename": filename or "document.docx",
                    "document_base64": base64.b64encode(raw).decode("ascii"),
                },
            )
            if not isinstance(out, dict):
                raise ToolError("sandbox.unavailable", "隔离沙箱返回异常")
            await _emit(True, {"session_id": out.get("session_id"), "workspace_id": out.get("workspace_id") or ws})
            return out
        except ToolError as exc:
            await _emit(False, {"error_code": exc.code, "workspace_id": ws})
            raise

    return (
        write_file,
        read_file,
        list_files,
        kb_search,
        generate_html,
        generate_docx,
        generate_pptx,
        inspect_document,
        render_document,
        edit_document,
        verify_document,
        edit_docx,
        edit_pptx,
        generate_image,
        verify_html,
        inspect_preview,
        workspace_exec,
        browser_open,
        browser_screenshot,
        document_open,
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
        inspect_document,
        render_document,
        edit_document,
        verify_document,
        edit_docx,
        edit_pptx,
        generate_image,
        verify_html,
        inspect_preview,
        workspace_exec,
        browser_open,
        browser_screenshot,
        document_open,
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
                "Search this membership's indexed materials (Meili projection of the "
                "artifact ledger; keyword or hybrid). Call only when the teacher asks "
                "about school materials. Being listed does not mean you must call. "
                "Returns excerpts + sources (title/artifact_id/snippet) or honest_miss. "
                "Never invent content. Args: query, limit?"
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
            name="sandbox_preview_inspect",
            description=(
                "See THIS run's HTML preview: given artifact_id or this-run preview_url, "
                "return title, h1, and a PNG screenshot artifact of the same-run HTML. "
                "Does not fetch public sites or intranet (127.0.0.1 / pico.aivia.asia admin denied). "
                "Args: artifact_id? | preview_url?"
            ),
            handler=inspect_preview,
            school_scoped=False,
        )
    )
    gw.register(
        ToolSpec(
            name="sandbox_workspace_exec",
            description=(
                "Optional light exec inside the isolated workspace: parse HTML or Python "
                "(ast only, timeout-killed). Cannot run bash, host shell, or leave the workspace. "
                "Args: html? | source?"
            ),
            handler=workspace_exec,
            school_scoped=False,
        )
    )
    gw.register(
        ToolSpec(
            name="sandbox_browser_open",
            description=(
                "Open a PUBLIC http(s) page in sidecar Chromium (Playwright; not LibreChat). "
                "The page appears in the result-area 网页 pane (not an iframe browser). "
                "Teacher completes login on the viewport; never send passwords in chat. "
                "Denies intranet, loopback, metadata, pico-api 18765, and pico.aivia.asia. "
                "WeChat/教务 are not required to succeed — if they block automation, the tool "
                "fails in human language. Args: url."
            ),
            handler=browser_open,
            school_scoped=False,
        )
    )
    gw.register(
        ToolSpec(
            name="sandbox_browser_screenshot",
            description=(
                "Return metadata for the current isolated browser screen (PNG on the view path). "
                "Args: session_id."
            ),
            handler=browser_screenshot,
            school_scoped=False,
        )
    )
    gw.register(
        ToolSpec(
            name="sandbox_document_open",
            description=(
                "Open a Word/Calc/Impress file in sidecar LibreOffice (the sandbox screen). "
                "Word is Word — do not convert to PDF or HTML, do not ask the teacher to download. "
                "Args: artifact_id? | filename? | kind?=writer | body?"
            ),
            handler=document_open,
            school_scoped=False,
        )
    )
    gw.register(
        ToolSpec(
            name="generate_docx_document",
            description=(
                "Create a real OOXML .docx via pico.office.spec/v1 (python-docx). "
                "Use spec.blocks for heading/para/table/image so tables are tables. "
                "Or pass body (blank-line paragraphs; markdown pipe tables become real tables). "
                "Args: title, marker?, body?, spec?, image_artifact_id?"
            ),
            handler=generate_docx,
            school_scoped=False,
        )
    )
    gw.register(
        ToolSpec(
            name="generate_pptx_document",
            description=(
                "Create a real OOXML .pptx via pico.office.spec/v1 (python-pptx). "
                "Use spec slides with title/bullets/image so pictures sit on the slide. "
                "Or pass body (--- / blank line = pages). "
                "Args: title, marker?, body?, spec?, image_artifact_id?"
            ),
            handler=generate_pptx,
            school_scoped=False,
        )
    )
    gw.register(
        ToolSpec(
            name="inspect_document",
            description=(
                "Read structure of an existing Word/PPT: addresses p:N / t:N / s:N.title. "
                "Does not write a file. Call before edit_document. "
                "Args: artifact_id | title"
            ),
            handler=inspect_document,
            school_scoped=False,
        )
    )
    gw.register(
        ToolSpec(
            name="render_document",
            description=(
                "Render pico.office.spec/v1 into a real .docx or .pptx Artifact. "
                "Path A: edit spec then render the whole file. "
                "Args: spec (required), title?, marker?, image_artifact_id?"
            ),
            handler=render_document,
            school_scoped=False,
        )
    )
    gw.register(
        ToolSpec(
            name="edit_document",
            description=(
                "Path B: change one inspect address on an uploaded Word/PPT. "
                "Other parts stay. Never invent a blank template. "
                "Args: artifact_id|title, address (p:N / t:N.rR.cC / s:N.title / s:N.b:M), text, output_title?"
            ),
            handler=edit_document,
            school_scoped=False,
        )
    )
    gw.register(
        ToolSpec(
            name="verify_document",
            description=(
                "Fail-closed OOXML check: package parts + python-docx/pptx can open. "
                "LibreOffice sandbox_document_open is preview only — do not treat it as verify. "
                "Args: artifact_id | title"
            ),
            handler=verify_document,
            school_scoped=False,
        )
    )
    gw.register(
        ToolSpec(
            name="edit_docx_document",
            description=(
                "Edit an already uploaded .docx in the Pico ledger with python-docx. "
                "Original other paragraphs stay. Never create a blank template. "
                "Args: artifact_id|title, paragraph_index (1-based), text, output_title?"
            ),
            handler=edit_docx,
            school_scoped=False,
        )
    )
    gw.register(
        ToolSpec(
            name="edit_pptx_document",
            description=(
                "Edit an already uploaded .pptx in the Pico ledger with python-pptx. "
                "Change one slide title; other slides stay. Never create a blank deck. "
                "Args: artifact_id|title, slide_index? (default 1), new_title, output_title?"
            ),
            handler=edit_pptx,
            school_scoped=False,
        )
    )
    gw.register(
        ToolSpec(
            name="generate_image",
            description=(
                "Create one downloadable png/jpg via SiliconFlow HTTPS images API. "
                "On missing key, timeout, or 4xx: honest Chinese failure; never invent pixels. "
                "Args: prompt, title?"
            ),
            handler=generate_image,
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
                    "description": "Keyword or question fragment to find in school materials",
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
        "sandbox_preview_inspect": {
            "type": "object",
            "properties": {
                "artifact_id": {
                    "type": "string",
                    "description": "This-run HTML artifact id (or preview_url)",
                },
                "preview_url": {
                    "type": "string",
                    "description": "Signed this-run preview path/URL, not a public site",
                },
            },
        },
        "sandbox_workspace_exec": {
            "type": "object",
            "properties": {
                "html": {
                    "type": "string",
                    "description": "HTML to parse inside the isolated workspace",
                },
                "source": {
                    "type": "string",
                    "description": "Python source to parse only (no bash, no imports of os/subprocess)",
                },
                "title": {"type": "string", "description": "Optional workspace filename"},
            },
        },
        "sandbox_browser_open": {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "Public http(s) URL (example.com demo). Not intranet or 18765.",
                },
            },
            "required": ["url"],
        },
        "sandbox_browser_screenshot": {
            "type": "object",
            "properties": {
                "session_id": {
                    "type": "string",
                    "description": "Isolated sandbox session id from sandbox_browser_open",
                },
            },
            "required": ["session_id"],
        },
        "sandbox_document_open": {
            "type": "object",
            "properties": {
                "artifact_id": {
                    "type": "string",
                    "description": "Existing .docx/.xlsx/.pptx artifact to open in LibreOffice",
                },
                "filename": {
                    "type": "string",
                    "description": "Document filename shown in the Writer window",
                },
                "kind": {
                    "type": "string",
                    "description": "writer | calc | impress (default writer)",
                },
                "body": {
                    "type": "string",
                    "description": "If no artifact, body text for a newly created .docx",
                },
            },
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
                "body": {
                    "type": "string",
                    "description": (
                        "题面正文. Blank lines separate paragraphs. "
                        "Markdown pipe tables become real Word tables. "
                        "Short body without a table/spec fails — no filler padding."
                    ),
                },
                "spec": {
                    "description": "pico.office.spec/v1 object or JSON (kind=docx, blocks=heading|para|table|image)",
                },
                "image_artifact_id": {
                    "type": "string",
                    "description": "generate_image artifact_id to insert as a real picture",
                },
            },
            "required": ["title"],
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
                "body": {
                    "type": "string",
                    "description": (
                        "题面页稿. Separate slides with a blank line or ---. "
                        "At least three titled pages from the prompt unless spec is provided. "
                        "Fewer pages fail — the tool will not invent 说明 slides."
                    ),
                },
                "spec": {
                    "description": "pico.office.spec/v1 object or JSON (kind=pptx, blocks=slide)",
                },
                "image_artifact_id": {
                    "type": "string",
                    "description": "generate_image artifact_id to place on the last slide",
                },
            },
            "required": ["title"],
        },
        "inspect_document": {
            "type": "object",
            "properties": {
                "artifact_id": {"type": "string"},
                "title": {"type": "string"},
            },
        },
        "render_document": {
            "type": "object",
            "properties": {
                "spec": {
                    "description": "pico.office.spec/v1 object or JSON string",
                },
                "title": {"type": "string"},
                "marker": {"type": "string"},
                "image_artifact_id": {"type": "string"},
            },
            "required": ["spec"],
        },
        "edit_document": {
            "type": "object",
            "properties": {
                "artifact_id": {"type": "string"},
                "title": {"type": "string"},
                "address": {
                    "type": "string",
                    "description": "p:N / t:N.rR.cC / s:N.title / s:N.b:M from inspect_document",
                },
                "text": {"type": "string"},
                "new_title": {"type": "string"},
                "paragraph_index": {"type": "integer"},
                "slide_index": {"type": "integer"},
                "output_title": {"type": "string"},
            },
        },
        "verify_document": {
            "type": "object",
            "properties": {
                "artifact_id": {"type": "string"},
                "title": {"type": "string"},
            },
        },
        "edit_docx_document": {
            "type": "object",
            "properties": {
                "artifact_id": {
                    "type": "string",
                    "description": "Uploaded .docx artifact id (or title)",
                },
                "title": {
                    "type": "string",
                    "description": "Uploaded .docx title (or artifact_id)",
                },
                "paragraph_index": {
                    "type": "integer",
                    "description": "1-based nonempty paragraph to replace",
                },
                "text": {"type": "string", "description": "New paragraph text"},
                "output_title": {
                    "type": "string",
                    "description": "Optional download filename",
                },
            },
            "required": ["paragraph_index", "text"],
        },
        "edit_pptx_document": {
            "type": "object",
            "properties": {
                "artifact_id": {
                    "type": "string",
                    "description": "Uploaded .pptx artifact id (or title)",
                },
                "title": {
                    "type": "string",
                    "description": "Uploaded .pptx title (or artifact_id)",
                },
                "slide_index": {
                    "type": "integer",
                    "description": "1-based slide to edit (default 1)",
                },
                "new_title": {"type": "string", "description": "New title for that slide"},
                "output_title": {
                    "type": "string",
                    "description": "Optional download filename",
                },
            },
            "required": ["new_title"],
        },
        "generate_image": {
            "type": "object",
            "properties": {
                "prompt": {
                    "type": "string",
                    "description": "What to draw (Chinese or English)",
                },
                "title": {
                    "type": "string",
                    "description": "Optional download filename ending .png/.jpg",
                },
            },
            "required": ["prompt"],
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
