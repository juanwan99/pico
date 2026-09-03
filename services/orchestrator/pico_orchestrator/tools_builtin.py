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
from pico_orchestrator.diagram_generate import render_diagram_bytes
from pico_orchestrator.document_generators import (
    build_docx_document,
    build_html_document,
    build_pptx_document,
    build_xlsx_document,
    html_engine_violations,
    html_remote_violations,
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
from pico_orchestrator.image_generate import (
    IMAGE_TIMEOUT_S,
    generate_image_with_usage,
)
from pico_orchestrator.mcp_bridge import mcp_openai_parameters, mcp_tool_specs
from pico_orchestrator.meili_kb import (
    extract_index_text,
    extract_office_text,
    meili_configured,
    search_materials,
)
from pico_orchestrator.office.extract import extract_embedded_images
from pico_orchestrator.office.inspect import inspect_office_bytes
from pico_orchestrator.office.legacy import (
    LEGACY_OFFICE_ERROR,
    LEGACY_OFFICE_EXTS,
    guess_office_ext,
)
from pico_orchestrator.office.qa import verify_office_bytes
from pico_orchestrator.office.render import render_spec
from pico_orchestrator.office.sandbox_lib import (
    PPTX_LIB_MAX_SOURCE,
    run_pptx_lib_source_async,
)
from pico_orchestrator.office.spec import parse_spec
from pico_orchestrator.office_editors import (
    comment_docx_bytes,
    edit_docx_bytes,
    edit_pptx_title_bytes,
    edit_xlsx_cell_bytes,
    fill_office_bytes,
)
from pico_orchestrator.sandbox_persist import read_owner_disk_file
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
from pico_orchestrator.usage_hook import emit_image_usage, emit_sandbox_usage
from pico_orchestrator.vision import remember_conversation_png
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
_IMAGE_TIMEOUT_S = IMAGE_TIMEOUT_S  # align with image_generate (90s)
_DIAGRAM_TIMEOUT_S = 30.0

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


def _attach_write_observation(
    result: dict[str, Any],
    *,
    kind: str,
    title: str,
    raw: bytes | str | None,
) -> dict[str, Any]:
    from pico_orchestrator.tool_observation import observe_write

    result["observation"] = observe_write(
        kind=kind, title=title, raw=raw, extra=result
    )
    if str(kind).lower() == "png" and isinstance(raw, (bytes, bytearray)):
        remember_conversation_png(bytes(raw))
    return result


OFFICE_CONTENT_BOX_COPY = "沙箱内容框：只渲染页面/幻灯片，不是 Writer/Impress 整窗。"


def _office_open_kinds(kind: str, filename: str) -> tuple[str, str, str]:
    """Map open args to (sandbox kind, ledger kind, filename with ext)."""
    name = (filename or "").lower()
    token = (kind or "").strip().lower()
    if token in {"calc", "xlsx"} or name.endswith((".xlsx", ".xls", ".ods", ".csv")):
        title = filename or "sheet.xlsx"
        return "calc", "xlsx", _ensure_extension(title, ".xlsx")
    if token in {"impress", "pptx"} or name.endswith((".pptx", ".ppt", ".odp")):
        title = filename or "deck.pptx"
        return "impress", "pptx", _ensure_extension(title, ".pptx")
    title = filename or "document.docx"
    return "writer", "docx", _ensure_extension(title, ".docx")


def _try_read_owner_office(principal: Principal, filename: str) -> bytes | None:
    want = Path(filename).name
    if not want:
        return None
    try:
        return read_owner_disk_file(principal.school_id, principal.membership_id, want)
    except ToolError as exc:
        if exc.code == "sandbox.file_not_found":
            return None
        raise


async def _observe_document_open(
    out: dict[str, Any], *, filename: str, kind: str
) -> dict[str, Any]:
    saw = False
    sid = str(out.get("session_id") or "")
    if sid.startswith("sbox_"):
        try:
            png = await sidecar_json("GET", f"/v1/internal/sessions/{sid}/png")
            if isinstance(png, (bytes, bytearray)):
                saw = remember_conversation_png(bytes(png))
        except Exception:
            logger.debug("document_open screen skip", exc_info=True)
    out["observation"] = {
        "opened": filename or str(out.get("title") or ""),
        "kind": str(out.get("kind") or kind),
        "saw_screen": saw,
    }
    return out


def _make_sandbox_pptx_lib(store: ArtifactStore):
    async def sandbox_pptx_lib(principal: Principal, args: dict[str, Any]) -> dict[str, Any]:
        source = _required_text(args, "source", maximum=PPTX_LIB_MAX_SOURCE)
        title_raw = args.get("title")
        title = _ensure_extension(
            str(title_raw).strip() if isinstance(title_raw, str) and title_raw.strip() else "沙箱上限.pptx",
            ".pptx",
        )
        deny_secret_filename(title)
        raw_ids = args.get("image_artifact_ids") or args.get("images") or []
        if raw_ids is None:
            raw_ids = []
        if not isinstance(raw_ids, list):
            raise ToolError("tool.invalid_arguments", "image_artifact_ids 必须是数组。")
        images: dict[str, bytes] = {}
        for item in raw_ids:
            aid = str(item or "").strip()
            if not aid:
                continue
            row = await store.read(principal, artifact_id=aid, title=None)
            if row is None:
                continue
            images[aid] = _artifact_bytes(row)
        raw = await run_pptx_lib_source_async(source, images=images)
        result = await store.write(principal, title=title, content=raw, kind="pptx")
        result["format"] = "pptx"
        result["via"] = "sandbox_pptx_lib"
        return _attach_write_observation(result, kind="pptx", title=title, raw=raw)

    return sandbox_pptx_lib


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


_PIXEL_READ_KINDS = frozenset({"png", "jpg", "jpeg", "webp", "gif"})
_PIXEL_READ_EXTS = frozenset({".png", ".jpg", ".jpeg", ".webp", ".gif"})
_OFFICE_READ_KINDS = frozenset({"pdf", "docx", "xlsx", "pptx", "edu_office"})
_OFFICE_READ_EXTS = frozenset(
    {".pdf", ".docx", ".xlsx", ".pptx", ".doc", ".xls", ".ppt"}
)
_TEXT_READ_KINDS = frozenset(
    {"html", "file", "doc", "json", "outline", "text", "md", "markdown"}
)


def _row_suffix(title: str) -> str:
    name = str(title or "").strip()
    if "." not in name:
        return ""
    return "." + name.rsplit(".", 1)[-1].lower()


def _optional_row_bytes(row: dict[str, Any]) -> bytes | None:
    b64 = row.get("content_base64")
    if isinstance(b64, str) and b64.strip():
        try:
            return base64.b64decode(b64.encode("ascii"), validate=False)
        except Exception:  # noqa: BLE001 — unread is honest; do not raise into the model
            return None
    body = row.get("content")
    if isinstance(body, bytes) and body:
        return body
    return None


def _office_unread_message(*, title: str, kind: str) -> str:
    suffix = _row_suffix(title)
    token = f".{kind}" if kind and not kind.startswith(".") else kind
    if suffix in LEGACY_OFFICE_EXTS or token in LEGACY_OFFICE_EXTS:
        return LEGACY_OFFICE_ERROR
    label = title or "文件"
    return f"《{label}》在账本。"


def _clip_text(body: str) -> tuple[str, bool]:
    if len(body) > MAX_CONTENT_CHARS:
        return body[:MAX_CONTENT_CHARS], True
    return body, False


def _read_file_for_model(row: dict[str, Any]) -> dict[str, Any]:
    """Pixels stay metadata. Office/PDF return extracted text, never base64."""
    out = dict(row)
    kind = str(out.get("kind") or "").strip().lower().lstrip(".")
    title = str(out.get("title") or "")
    suffix = _row_suffix(title)
    encoding = str(out.get("content_encoding") or "").strip().lower()

    if (
        kind in {"html", "htm", "page"}
        or suffix in {".html", ".htm"}
        or (isinstance(out.get("content"), str) and "data:image/" in out["content"])
    ):
        body = out.get("content")
        if isinstance(body, str):
            from pico_orchestrator.html_ledger_images import strip_embedded_data_urls

            body = strip_embedded_data_urls(body)
            body, truncated = _clip_text(body)
            out["content"] = body
            if truncated:
                out["truncated"] = True
        out.pop("content_base64", None)
        return out

    if kind in {"edu_excerpt", "kb_text"}:
        out.pop("content_base64", None)
        if kind == "edu_excerpt":
            out.pop("content", None)
            out["unread"] = True
            out["user_message"] = _office_unread_message(title=title, kind=kind)
        return out

    if kind in _PIXEL_READ_KINDS or suffix in _PIXEL_READ_EXTS:
        out.pop("content", None)
        out.pop("content_base64", None)
        out["binary"] = True
        out["user_message"] = (
            f"图片《{title or 'file'}》在账本。"
            "像素不进本工具返回；要用时把 artifact_id 交给文档工具。"
        )
        return out

    if kind in _OFFICE_READ_KINDS or suffix in _OFFICE_READ_EXTS:
        raw = _optional_row_bytes(out)
        text = extract_index_text(
            title=title or "file",
            kind=kind,
            content=out.get("content") if isinstance(out.get("content"), str) else None,
            raw=raw,
        )
        if (not text or not text.strip()) and raw:
            text = extract_office_text(filename=title or "file", data=raw)
        out.pop("content_base64", None)
        if text and text.strip():
            body, truncated = _clip_text(text.strip())
            out["content"] = body
            out["extracted"] = True
            out.pop("binary", None)
            if truncated:
                out["truncated"] = True
            return out
        out.pop("content", None)
        out["unread"] = True
        out["user_message"] = _office_unread_message(title=title, kind=kind)
        return out

    binary = encoding == "base64" and kind not in _TEXT_READ_KINDS and kind != "bin"
    if encoding == "base64" and kind == "bin" and suffix not in _OFFICE_READ_EXTS:
        binary = True
    if not binary:
        body = out.get("content")
        if isinstance(body, str):
            body, truncated = _clip_text(body)
            out["content"] = body
            if truncated:
                out["truncated"] = True
        out.pop("content_base64", None)
        return out
    out.pop("content", None)
    out.pop("content_base64", None)
    out["binary"] = True
    out["user_message"] = (
        f"二进制《{title or 'file'}》在账本。"
        "要用时把 artifact_id 交给文档工具。"
    )
    return out


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

    # Remote engines/assets (CDN import, script src, leftover fonts, img https).
    remote_hits = html_remote_violations(text)
    engine_hits = html_engine_violations(text)
    offline_hits = remote_hits + engine_hits
    add(
        "no_remote_script",
        "fail" if offline_hits else "pass",
        (
            "remote/engine: " + ",".join(offline_hits)
            if offline_hits
            else "no remote script/import/asset load"
        ),
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
        result = _read_file_for_model(result)
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
        from pico_orchestrator.html_ledger_images import (
            canonicalize_pico_artifact_refs,
            collect_pico_artifact_refs,
            is_image_bytes,
            parse_image_artifact_ids,
        )

        try:
            index_ids = parse_image_artifact_ids(args.get("image_artifact_ids"))
        except TypeError as exc:
            raise ToolError("tool.invalid_arguments", str(exc)) from exc
        # Keep pico-artifact:<id> on the ledger. Inlining data: at write turned
        # six PNGs into a 12MB utf8 row; GET /v1/tasks then froze 结果区 chips.
        body = canonicalize_pico_artifact_refs(body or "", index_ids)
        landed: list[str] = []
        skipped: list[str] = []
        for aid in collect_pico_artifact_refs(body, []):
            row = await store.read(principal, artifact_id=aid, title=None)
            if row is None:
                skipped.append(aid)
                continue
            try:
                blob = _artifact_bytes(row)
            except ToolError:
                skipped.append(aid)
                continue
            if is_image_bytes(blob):
                landed.append(aid)
            else:
                skipped.append(aid)
        images_meta = {"landed": landed, "skipped": skipped}
        try:
            raw = build_html_document(
                title=title,
                marker=marker,
                body=body,
                enforce_body_max=False,
            )
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
        result = _attach_write_observation(
            result, kind="html", title=title, raw=content
        )
        if images_meta.get("landed") or images_meta.get("skipped"):
            result["images"] = images_meta
            obs = result.get("observation")
            if isinstance(obs, dict):
                obs["images"] = images_meta
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

    async def _load_spec_images(principal: Principal, spec: object) -> dict[str, bytes]:
        out: dict[str, bytes] = {}
        for aid in getattr(spec, "image_ids", lambda: ())():
            # Production LedgerArtifactStore.read is keyword-only and requires title=.
            # Memory-store tests used to default title=None and hid this miss.
            # Missing id: skip. Do not fail the whole deck (S2 first-write).
            row = await store.read(principal, artifact_id=aid, title=None)
            if row is None:
                continue
            out[str(aid)] = _artifact_bytes(row)
        return out

    def _spec_arg(args: dict[str, Any]) -> object | None:
        spec = args.get("spec")
        blocks = args.get("blocks")
        # Live F4: Pi sent spec={"images": []} (or kpi_table_title) AND sibling
        # top-level blocks. Preferring spec dropped the slides → 不能为空.
        if isinstance(spec, dict):
            have = spec.get("blocks")
            if (not isinstance(have, list) or not have) and isinstance(blocks, list) and blocks:
                return {**spec, "blocks": blocks}
            return spec
        if spec is not None:
            return spec
        if blocks is not None:
            return blocks
        return None

    def _has_new_office_content(args: dict[str, Any]) -> bool:
        return any(args.get(key) is not None for key in ("body", "spec", "blocks"))

    def _docx_is_patch(args: dict[str, Any]) -> bool:
        if _has_new_office_content(args):
            return False
        if args.get("paragraph_index") is not None:
            return True
        if str(args.get("comment") or "").strip():
            return True
        if args.get("values") is not None:
            return True
        return bool(str(args.get("text") or "").strip())

    def _pptx_is_patch(args: dict[str, Any]) -> bool:
        if _has_new_office_content(args):
            return False
        if str(args.get("new_title") or "").strip():
            return True
        if args.get("values") is not None:
            return True
        return args.get("slide_index") is not None

    def _xlsx_is_patch(args: dict[str, Any]) -> bool:
        if _has_new_office_content(args):
            return False
        if str(args.get("cell") or args.get("address") or "").strip():
            return True
        return args.get("values") is not None

    async def generate_docx(principal: Principal, args: dict[str, Any]) -> dict[str, Any]:
        if _docx_is_patch(args):
            return await edit_docx(principal, args)
        title = _ensure_extension(_artifact_title(args), ".docx")
        marker = _marker_arg(args)
        spec_raw = _spec_arg(args)
        try:
            if spec_raw is not None:
                if isinstance(spec_raw, list):
                    spec_raw = {
                        "kind": "docx",
                        "title": title,
                        "marker": marker,
                        "blocks": spec_raw,
                    }
                elif isinstance(spec_raw, dict):
                    spec_raw = {
                        **spec_raw,
                        "kind": spec_raw.get("kind") or "docx",
                        "title": spec_raw.get("title") or title,
                        "marker": spec_raw.get("marker") or marker,
                    }
                spec = parse_spec(spec_raw, default_kind="docx")
                raw = render_spec(spec, images=await _load_spec_images(principal, spec))
            else:
                body = _optional_text(args, "body", maximum=_MAX_DOC_BODY)
                require_docx_body(body)
                raw = build_docx_document(title=title, marker=marker, body=body)
        except (ValueError, TypeError) as exc:
            raise ToolError("tool.invalid_arguments", str(exc)) from exc
        result = await store.write(
            principal,
            title=title,
            content=raw,
            kind="docx",
        )
        result["format"] = "docx"
        result["marker"] = marker
        result["via"] = "spec" if spec_raw is not None else "plain"
        return _attach_write_observation(result, kind="docx", title=title, raw=raw)

    async def generate_pptx(principal: Principal, args: dict[str, Any]) -> dict[str, Any]:
        if _pptx_is_patch(args):
            return await edit_pptx(principal, args)
        title = _ensure_extension(_artifact_title(args), ".pptx")
        marker = _marker_arg(args)
        spec_raw = _spec_arg(args)
        try:
            if spec_raw is not None:
                if isinstance(spec_raw, list):
                    spec_raw = {
                        "kind": "pptx",
                        "title": title,
                        "marker": marker,
                        "blocks": spec_raw,
                    }
                elif isinstance(spec_raw, dict):
                    spec_raw = {
                        **spec_raw,
                        "kind": spec_raw.get("kind") or "pptx",
                        "title": spec_raw.get("title") or title,
                        "marker": spec_raw.get("marker") or marker,
                    }
                spec = parse_spec(spec_raw, default_kind="pptx")
                raw = render_spec(spec, images=await _load_spec_images(principal, spec))
            else:
                body = _optional_text(args, "body", maximum=_MAX_DOC_BODY)
                require_pptx_body(body)
                raw = build_pptx_document(title=title, marker=marker, body=body)
        except (ValueError, TypeError) as exc:
            raise ToolError("tool.invalid_arguments", str(exc)) from exc
        result = await store.write(
            principal,
            title=title,
            content=raw,
            kind="pptx",
        )
        result["format"] = "pptx"
        result["marker"] = marker
        result["via"] = "spec" if spec_raw is not None else "plain"
        return _attach_write_observation(result, kind="pptx", title=title, raw=raw)

    async def generate_xlsx(principal: Principal, args: dict[str, Any]) -> dict[str, Any]:
        if _xlsx_is_patch(args):
            return await edit_xlsx(principal, args)
        title = _ensure_extension(_artifact_title(args), ".xlsx")
        marker = _marker_arg(args)
        spec_raw = _spec_arg(args)
        try:
            if spec_raw is not None:
                if isinstance(spec_raw, list):
                    spec_raw = {
                        "kind": "xlsx",
                        "title": title,
                        "marker": marker,
                        "blocks": spec_raw,
                    }
                elif isinstance(spec_raw, dict):
                    spec_raw = {
                        **spec_raw,
                        "kind": spec_raw.get("kind") or "xlsx",
                        "title": spec_raw.get("title") or title,
                        "marker": spec_raw.get("marker") or marker,
                    }
                spec = parse_spec(spec_raw, default_kind="xlsx")
                raw = render_spec(spec, images=await _load_spec_images(principal, spec))
            else:
                body = _optional_text(args, "body", maximum=_MAX_DOC_BODY)
                raw = build_xlsx_document(title=title, marker=marker, body=body)
        except (ValueError, TypeError) as exc:
            raise ToolError("tool.invalid_arguments", str(exc)) from exc
        result = await store.write(
            principal,
            title=title,
            content=raw,
            kind="xlsx",
        )
        result["format"] = "xlsx"
        result["marker"] = marker
        result["via"] = "spec" if spec_raw is not None else "plain"
        return _attach_write_observation(result, kind="xlsx", title=title, raw=raw)

    async def render_document(principal: Principal, args: dict[str, Any]) -> dict[str, Any]:
        spec_raw = args.get("spec") if args.get("spec") is not None else args
        try:
            spec = parse_spec(spec_raw)
            raw = render_spec(spec, images=await _load_spec_images(principal, spec))
        except (ValueError, TypeError) as exc:
            raise ToolError("tool.invalid_arguments", str(exc)) from exc
        ext = f".{spec.kind}"
        title = _ensure_extension(str(args.get("title") or spec.title or f"pico{ext}"), ext)
        result = await store.write(
            principal,
            title=title,
            content=raw,
            kind=spec.kind,
        )
        result["format"] = spec.kind
        result["via"] = "spec"
        check = verify_office_bytes(raw, ext)
        result["valid_ooxml"] = check.get("valid_ooxml")
        return _attach_write_observation(
            result, kind=spec.kind, title=title, raw=raw
        )

    def _office_ext_from_args(args: dict[str, Any]) -> str:
        try:
            return guess_office_ext(
                kind=str(args.get("kind") or ""),
                title=str(args.get("title") or args.get("filename") or ""),
            )
        except ValueError as exc:
            raise ToolError("tool.invalid_arguments", str(exc)) from exc

    async def inspect_document(principal: Principal, args: dict[str, Any]) -> dict[str, Any]:
        ext = _office_ext_from_args(args)
        row, raw = await _load_office(principal, args, ext=ext)
        try:
            outline = inspect_office_bytes(raw, ext)
        except (ValueError, TypeError) as exc:
            raise ToolError("tool.invalid_arguments", str(exc)) from exc
        outline["artifact_id"] = row.get("artifact_id")
        outline["title"] = row.get("title")
        kept = 0
        for blob in extract_embedded_images(raw, ext):
            if remember_conversation_png(blob):
                kept += 1
        outline["extracted_images"] = kept
        return outline

    async def verify_document(principal: Principal, args: dict[str, Any]) -> dict[str, Any]:
        try:
            ext = guess_office_ext(
                kind=str(args.get("kind") or ""),
                title=str(args.get("title") or ""),
            )
        except ValueError as exc:
            return {
                "ok": False,
                "valid_ooxml": False,
                "error": str(exc),
                "title": args.get("title"),
            }
        row, raw = await _load_office(principal, args, ext=ext)
        check = verify_office_bytes(raw, ext)
        check["artifact_id"] = row.get("artifact_id")
        check["title"] = row.get("title")
        return check

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
        title_name = str(row.get("title") or args.get("title") or "")
        try:
            guess_office_ext(kind=ext.lstrip("."), title=title_name)
        except ValueError as exc:
            raise ToolError("tool.invalid_arguments", str(exc)) from exc
        if not is_valid_ooxml_package(raw, ext):
            raise ToolError(
                "artifact.not_ooxml",
                f"这份不是真 {ext} 原件，不能当改稿保存。",
            )
        return row, raw

    def _values_arg(args: dict[str, Any]) -> dict[str, str] | None:
        raw = args.get("values")
        if raw is None:
            return None
        if not isinstance(raw, dict) or not raw:
            raise ToolError("tool.invalid_arguments", "values 必须是对象，例如 {\"姓名\": \"张三\"}。")
        return {str(k).strip(): str(v) for k, v in raw.items() if str(k).strip()}

    async def edit_docx(principal: Principal, args: dict[str, Any]) -> dict[str, Any]:
        row, raw = await _load_office(principal, args, ext=".docx")
        values = _values_arg(args)
        comment = str(args.get("comment") or "").strip()
        index = _optional_int(args, "paragraph_index")
        text = str(args.get("text") or "").strip()
        if values is None and not comment and not text:
            raise ToolError(
                "tool.invalid_arguments",
                "请指定 text（改一段）、comment（留批注）或 values（套 {{key}}）。",
            )
        if (text or comment) and index is None:
            raise ToolError("tool.invalid_arguments", "请指定 paragraph_index（从 1 起）。")

        def _apply() -> bytes:
            edited = raw
            if values is not None:
                edited = fill_office_bytes(edited, ".docx", values)
            if comment:
                edited = comment_docx_bytes(edited, paragraph_index=index or 1, text=comment)
            if text:
                edited = edit_docx_bytes(edited, paragraph_index=index or 1, text=text)
            return edited

        try:
            edited = await _run_bounded(
                asyncio.to_thread(_apply),
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
        if comment:
            result["commented"] = True
        if values is not None:
            result["filled"] = True
        return _attach_write_observation(result, kind="docx", title=out_title, raw=edited)

    async def edit_pptx(principal: Principal, args: dict[str, Any]) -> dict[str, Any]:
        row, raw = await _load_office(principal, args, ext=".pptx")
        values = _values_arg(args)
        new_title = str(args.get("new_title") or "").strip()
        index = _optional_int(args, "slide_index", default=1) or 1
        if values is None and not new_title:
            raise ToolError(
                "tool.invalid_arguments",
                "请指定 new_title（改页标题）或 values（套 {{key}}）。",
            )

        def _apply() -> bytes:
            edited = raw
            if values is not None:
                edited = fill_office_bytes(edited, ".pptx", values)
            if new_title:
                edited = edit_pptx_title_bytes(
                    edited, slide_index=index, new_title=new_title
                )
            return edited

        try:
            edited = await _run_bounded(
                asyncio.to_thread(_apply),
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
        if values is not None:
            result["filled"] = True
        return _attach_write_observation(result, kind="pptx", title=out_title, raw=edited)

    async def edit_xlsx(principal: Principal, args: dict[str, Any]) -> dict[str, Any]:
        row, raw = await _load_office(principal, args, ext=".xlsx")
        values = _values_arg(args)
        cell = str(args.get("cell") or args.get("address") or "").strip()
        value = args.get("value")
        sheet = args.get("sheet")
        if values is None and not cell:
            raise ToolError(
                "tool.invalid_arguments",
                "请指定 cell（如 D2）和 value，或 values（套 {{key}}）。",
            )

        def _apply() -> bytes:
            edited = raw
            if values is not None:
                edited = fill_office_bytes(edited, ".xlsx", values)
            if cell:
                if value is None:
                    raise ValueError("改格需要 value。")
                edited = edit_xlsx_cell_bytes(
                    edited,
                    cell=cell,
                    value=str(value),
                    sheet=sheet if isinstance(sheet, (str, int)) or sheet is None else str(sheet),
                )
            return edited

        try:
            edited = await _run_bounded(
                asyncio.to_thread(_apply),
                seconds=_EDIT_TIMEOUT_S,
                code="office.timeout",
                message="改文档超时（20 秒）。请换更小的文件或稍后再试。",
            )
        except ValueError as exc:
            raise ToolError("tool.invalid_arguments", str(exc)) from exc
        out_title = _ensure_extension(
            str(args.get("output_title") or row.get("title") or "已改.xlsx"),
            ".xlsx",
        )
        result = await store.write(
            principal,
            title=out_title,
            content=edited,
            kind="xlsx",
        )
        result["format"] = "xlsx"
        result["edited"] = True
        result["cell"] = cell or None
        result["source_artifact_id"] = row.get("artifact_id")
        if values is not None:
            result["filled"] = True
        return _attach_write_observation(result, kind="xlsx", title=out_title, raw=edited)

    async def generate_image(principal: Principal, args: dict[str, Any]) -> dict[str, Any]:
        prompt = _required_text(args, "prompt", maximum=2000)
        title_raw = args.get("title")
        title_hint = str(title_raw).strip() if isinstance(title_raw, str) else ""
        from pico_orchestrator.image_generate import billed_image_model, selected_image_provider

        image_model = billed_image_model()
        try:
            raw, ext, usage = await _run_bounded(
                generate_image_with_usage(prompt),
                # F5: one Retry-After rest (≤ image timeout window) + one POST.
                seconds=_IMAGE_TIMEOUT_S * 2,
                code="image.timeout",
                message="出图超时（90 秒）。请稍后重试，不能编造图片。",
            )
            title = _ensure_extension(title_hint or "示意图", f".{ext}")
            kind = "png" if ext == "png" else "jpg"
            result = await store.write(
                principal,
                title=title,
                content=raw,
                kind=kind,
            )
            result["format"] = ext
            result["user_message"] = (
                "图已生成。要放进文档时把 artifact id 交给文档工具"
                "（PPT/Word：image_artifact_id；HTML：src=\"pico-artifact:<id>\"）。"
                "已经嵌进文件的不要再单独交一份。"
            )
            extra = {
                "bytes": len(raw),
                "format": ext,
                "provider": selected_image_provider(),
                "artifact_id": result.get("artifact_id"),
            }
            if isinstance(usage, dict):
                extra.update(usage)
            await emit_image_usage(
                principal,
                ok=True,
                model=image_model,
                extra=extra,
            )
            return _attach_write_observation(result, kind=kind, title=title, raw=raw)
        except Exception:
            await emit_image_usage(
                principal,
                ok=False,
                model=image_model,
                extra={"provider": selected_image_provider()},
            )
            raise

    async def generate_diagram(principal: Principal, args: dict[str, Any]) -> dict[str, Any]:
        source = _required_text(args, "source", maximum=32_000)
        kind_raw = args.get("kind")
        kind = str(kind_raw).strip() if isinstance(kind_raw, str) else "mermaid"
        title_raw = args.get("title")
        title_hint = str(title_raw).strip() if isinstance(title_raw, str) else ""
        raw, svg, meta = await _run_bounded(
            render_diagram_bytes(source, kind=kind or "mermaid"),
            seconds=_DIAGRAM_TIMEOUT_S,
            code="diagram.timeout",
            message="结构图超时（30 秒）。请稍后重试，不能假装画出结构图。",
        )
        title = _ensure_extension(title_hint or "结构图", ".png")
        result = await store.write(
            principal,
            title=title,
            content=raw,
            kind="png",
        )
        result["format"] = "png"
        result["diagram_kind"] = meta.get("kind") or "mermaid"
        result["engine"] = meta.get("engine")
        if svg:
            result["svg"] = svg
        if meta.get("svg_omitted"):
            result["svg_omitted"] = True
        result["user_message"] = (
            "结构图已生成。要放进 Word/PPT 时把 artifact id 写入 image_artifact_id，"
            "不要单独当成品交给老师。"
        )
        return _attach_write_observation(result, kind="png", title=title, raw=raw)

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
                    remember_conversation_png(png)
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
            png: bytes | None = None
            try:
                raw = await sidecar_json(
                    "GET",
                    f"/v1/internal/sessions/{session_id}/png",
                    params={
                        "school_id": principal.school_id,
                        "membership_id": principal.membership_id,
                    },
                )
                if isinstance(raw, (bytes, bytearray)) and bytes(raw).startswith(
                    PNG_MAGIC
                ):
                    png = bytes(raw)
            except Exception:
                logger.debug("sandbox screenshot png fetch skipped", exc_info=True)
            if png:
                remember_conversation_png(png)
                try:
                    shot_title = (
                        f"shot-{safe_segment(session_id, fallback='page')}.png"
                    )
                    deny_secret_filename(shot_title)
                    shot = await with_io_timeout(
                        store.write(
                            principal,
                            title=shot_title,
                            content=png,
                            kind="image",
                        ),
                        what="sandbox_browser_screenshot_png",
                    )
                    out = {**out, **raster_meta_from_write(shot, byte_size=len(png))}
                except Exception:
                    logger.debug(
                        "sandbox screenshot artifact write skipped", exc_info=True
                    )
            await _emit(True, {"workspace_id": out.get("workspace_id") or ws})
            return out
        except ToolError as exc:
            await _emit(False, {"error_code": exc.code})
            raise

    async def document_open(principal: Principal, args: dict[str, Any]) -> dict[str, Any]:
        """Open Office as a page/slide content box in the sandbox pane. Not LibreOffice chrome."""
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
                return await _observe_document_open(out, filename=filename or "files", kind="files")

            sandbox_kind, ledger_kind, filename = _office_open_kinds(kind, filename)
            raw: bytes | None = None
            if artifact_id:
                row = await store.read(principal, artifact_id=artifact_id, title=None)
                if not row:
                    raise ToolError("artifact.not_found", "找不到该文档产物")
                filename = str(row.get("title") or row.get("user_label") or filename)
                sandbox_kind, ledger_kind, filename = _office_open_kinds(
                    sandbox_kind, filename
                )
                encoding = str(row.get("content_encoding") or "utf8").lower()
                if encoding == "utf8" and isinstance(row.get("content"), str) and row.get("content"):
                    raise ToolError(
                        "tool.invalid_arguments",
                        "该产物不是二进制 Office 包，拒绝当 Word 打开",
                    )
                raw = _artifact_bytes(row)

            if raw is None and filename:
                raw = _try_read_owner_office(principal, filename)

            if raw is None:
                if not body_text:
                    raise ToolError(
                        "tool.invalid_arguments",
                        "请提供已有文件的 artifact_id、磁盘上的文件名，或要打开的正文。不会编一份文件。",
                    )
                marker = _marker_arg({"marker": args.get("marker")})
                if sandbox_kind == "calc":
                    raw = build_xlsx_document(title=filename, marker=marker, body=body_text)
                elif sandbox_kind == "impress":
                    raw = build_pptx_document(title=filename, marker=marker, body=body_text)
                else:
                    raw = build_docx_document(title=filename, marker=marker, body=body_text)

            if not artifact_id:
                rec = await store.write(
                    principal,
                    title=filename,
                    content=raw,
                    kind=ledger_kind,
                )
                artifact_id = str(rec.get("artifact_id") or rec.get("id") or "").strip()
            if not artifact_id:
                raise ToolError("artifact.store_unavailable", "无法把文档记入账本，打不开内容框。")

            await _emit(
                True,
                {
                    "artifact_id": artifact_id,
                    "workspace_id": ws,
                    "view": "content-box",
                },
            )
            return {
                "ok": True,
                "view": "content-box",
                "artifact_id": artifact_id,
                "filename": filename,
                "title": filename,
                "kind": sandbox_kind,
                "engine": "office-content-box",
                "human_copy": OFFICE_CONTENT_BOX_COPY,
                "observation": {
                    "opened": filename,
                    "kind": sandbox_kind,
                    "view": "content-box",
                    "saw_screen": False,
                },
            }
        except ToolError as exc:
            await _emit(False, {"error_code": exc.code, "workspace_id": ws})
            raise

    async def publish_html_page(principal: Principal, args: dict[str, Any]) -> dict[str, Any]:
        from app.html_pages import publish_html_page as do_publish

        artifact_id = str(args.get("artifact_id") or "").strip()
        return await do_publish(principal, artifact_id=artifact_id)

    async def unpublish_html_page(principal: Principal, args: dict[str, Any]) -> dict[str, Any]:
        from app.html_pages import unpublish_html_page as do_unpublish

        return await do_unpublish(
            principal,
            page_id=str(args.get("page_id") or "").strip(),
            artifact_id=str(args.get("artifact_id") or "").strip(),
        )

    return (
        write_file,
        read_file,
        list_files,
        kb_search,
        generate_html,
        generate_docx,
        generate_pptx,
        generate_xlsx,
        edit_docx,
        edit_pptx,
        edit_xlsx,
        generate_image,
        generate_diagram,
        verify_html,
        inspect_preview,
        workspace_exec,
        browser_open,
        browser_screenshot,
        document_open,
        render_document,
        inspect_document,
        verify_document,
        publish_html_page,
        unpublish_html_page,
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
        generate_xlsx,
        edit_docx,
        edit_pptx,
        edit_xlsx,
        generate_image,
        generate_diagram,
        verify_html,
        inspect_preview,
        workspace_exec,
        browser_open,
        browser_screenshot,
        document_open,
        render_document,
        inspect_document,
        verify_document,
        publish_html_page,
        unpublish_html_page,
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
            description=(
                "Read one Artifact owned by the current membership by id or title. "
                "PDF/docx/xlsx/pptx originals are on this turn's model file channel; "
                "this tool returns ledger extract text when present. "
                "Unread office is not missing — do not ask the teacher to re-upload. "
                "png/jpg stay binary: only id, title, kind, size — no pixels or base64. "
                "HTML drops embedded data: image payloads. "
                "Pass a picture artifact id to a document tool to embed."
            ),
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
                "Create a real .html Artifact that must run offline: inline CSS/JS "
                "and canvas only. A semantic classless visual base is already inlined. "
                "No CDN, no import/script-src of Three.js / Chart.js / "
                "ECharts / KaTeX, no https or //cdn images, no "
                "window.THREE / new Chart / echarts.init. To embed a ledger picture, "
                "set img src to pico-artifact:<artifact_id> (or pico-artifact:0 with "
                "image_artifact_ids). Pico inlines data: URLs when the page is opened "
                "or downloaded. Do not paste base64. "
                "A missing id skips that picture; the page still lands. "
                "The tool fails if the page still needs the network or those engines. "
                "Result includes an observation of what landed. ok is not finished. "
                "Args: title, marker, body?, image_artifact_ids?"
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
                "The PNG is remembered so the teacher's next question can see the page. "
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
                "Capture the current isolated browser screen as a PNG artifact. "
                "The PNG is remembered so the teacher's next question can see the page. "
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
                "Open a Word/Excel/PPT file in the sandbox as a page/slide content box "
                "(not LibreOffice Writer/Impress chrome). Needs an existing artifact_id, "
                "a teacher-disk filename, or body. Does not invent a file. "
                "The file stays OOXML — do not convert to PDF. "
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
                "Create a real OOXML .docx, or patch an existing one. "
                "To change an uploaded file, pass artifact_id|title plus "
                "paragraph_index/text, comment, or values — do not look for a "
                "separate edit tool. Result includes an observation of "
                "what landed (counts, preview — not a score). ok is not finished. "
                "Args: title, marker, body? | spec? | blocks? | artifact_id? "
                "paragraph_index? text? comment? values? output_title?"
            ),
            handler=generate_docx,
            school_scoped=False,
        )
    )
    gw.register(
        ToolSpec(
            name="generate_pptx_document",
            description=(
                "Create a real OOXML .pptx via spec/blocks on stock python-pptx "
                "layouts (title, bullets, table, theme colors). Sibling of "
                "sandbox_pptx_lib (isolated python-pptx) — pick from the "
                "teacher's ask, not a scene word. Free shapes / color blocks / "
                "full-bleed geometry are not this tool; write python-pptx in "
                "sandbox_pptx_lib. Same title replaces the file the teacher "
                "opens. Read observation.outline.images. "
                "A missing image_artifact_id skips that picture; the file still "
                "lands. blocks[].type cover/content/title/page (or omitted) "
                "are slides. To embed a picture, pass generate_image/"
                "generate_diagram artifact id as image_artifact_id on the slide "
                "in spec/blocks. [image:…] in body does not embed. ok is not "
                "finished. To patch an existing deck, pass artifact_id|title plus "
                "slide_index/new_title or values — do not look for a separate edit tool. "
                "Args: title, marker, body? | spec? | blocks? | artifact_id? "
                "slide_index? new_title? values? output_title?"
            ),
            handler=generate_pptx,
            school_scoped=False,
        )
    )
    gw.register(
        ToolSpec(
            name="sandbox_pptx_lib",
            description=(
                "Isolated python-pptx (not host bash, not a second Office OS). "
                "Sibling of generate_pptx_document — not the only PPT path. "
                "Result includes an observation of what landed. ok is not finished. "
                "from pptx import Presentation, Inches, Pt, RGBColor is allowed "
                "(Inches/Pt also on pptx). add_shape and RGBColor color blocks "
                "are this tool. from pathlib import Path is a stub (mkdir ignored; "
                "no host files). prs.save is routed to the ledger (same as save_deck). "
                "Do not import os. "
                "add_title_slide(prs, title, subtitle, image=IMAGE_PATHS[0]); "
                "add_table(prs=prs, rows=grid); IMAGE_PATHS[0] is the first "
                "picture. Must add slides then save_deck(prs) or prs.save. Empty "
                "Presentation();save_deck fails — do not send a placeholder. "
                "A missing image_artifact_ids entry is skipped. Args: source, "
                "title?, image_artifact_ids?"
            ),
            handler=_make_sandbox_pptx_lib(store),
            school_scoped=False,
        )
    )
    gw.register(
        ToolSpec(
            name="generate_xlsx_document",
            description=(
                "Create a real OOXML .xlsx, or patch an existing sheet. "
                "Markdown/TSV tables in body become sheets and rows "
                "(sibling of Word paragraphs / PPT --- slides). "
                "A whole draft in one cell is not a spreadsheet. "
                "To change an uploaded file, pass artifact_id|title plus cell/value "
                "or values — do not look for a separate edit tool. "
                "Result includes an observation of what landed. ok is not finished. "
                "Args: title, marker, body? | spec? | blocks? | artifact_id? "
                "cell? value? sheet? values? output_title?"
            ),
            handler=generate_xlsx,
            school_scoped=False,
        )
    )
    gw.register(
        ToolSpec(
            name="edit_docx_document",
            description=(
                "Edit an already uploaded .docx: replace a paragraph, add a comment, "
                "or fill {{key}} values. Other content stays. Never create a blank template. "
                "Result includes an observation of what landed. ok is not finished. "
                "Args: artifact_id|title, paragraph_index?, text?, comment?, values?, output_title?"
            ),
            handler=edit_docx,
            school_scoped=False,
        )
    )
    gw.register(
        ToolSpec(
            name="edit_pptx_document",
            description=(
                "Edit an already uploaded .pptx: change one slide title or fill {{key}}. "
                "Other slides stay. Never create a blank deck. "
                "Result includes an observation of what landed. ok is not finished. "
                "Args: artifact_id|title, slide_index?, new_title?, values?, output_title?"
            ),
            handler=edit_pptx,
            school_scoped=False,
        )
    )
    gw.register(
        ToolSpec(
            name="edit_xlsx_document",
            description=(
                "Edit an already uploaded .xlsx: set one cell (A1-style; =formula) "
                "or fill {{key}}. Other cells stay. Result includes an observation. "
                "ok is not finished. Args: artifact_id|title, cell?, "
                "value?, sheet?, values?, output_title?"
            ),
            handler=edit_xlsx,
            school_scoped=False,
        )
    )
    gw.register(
        ToolSpec(
            name="render_document",
            description=(
                "Create Word/PPT/Excel from pico.office.spec/v1 (docx/pptx/xlsx). "
                "Tables, images, formulas, comments, {{key}} values go inside the file. "
                "Args: spec, title?"
            ),
            handler=render_document,
            school_scoped=False,
        )
    )
    gw.register(
        ToolSpec(
            name="inspect_document",
            description=(
                "Read structure of an uploaded .docx/.pptx/.xlsx: paragraph/slide/cell "
                "indexes, tables, comments, leftover {{key}}. Embedded pictures are "
                "remembered so the teacher's next question can see the pixels. "
                "Call before generate_* patch (paragraph_index / slide_index / cell). "
                "Old .doc/.ppt/.xls fail in Chinese. "
                "Args: artifact_id|title, kind?"
            ),
            handler=inspect_document,
            school_scoped=False,
        )
    )
    gw.register(
        ToolSpec(
            name="verify_document",
            description=(
                "Fail-closed OOXML check for a ledger Word/PPT/Excel. "
                "Old .doc/.ppt/.xls fail in Chinese. Args: artifact_id|title, kind?"
            ),
            handler=verify_document,
            school_scoped=False,
        )
    )
    gw.register(
        ToolSpec(
            name="publish_html_page",
            description=(
                "Publish an existing HTML artifact to a public URL. "
                "Visitors can open it without login. Forms may POST JSON to the "
                "page collect path; entries land in the publisher's archive. "
                "Args: artifact_id."
            ),
            handler=publish_html_page,
            school_scoped=False,
        )
    )
    gw.register(
        ToolSpec(
            name="unpublish_html_page",
            description=(
                "Revoke a published HTML page. The public URL and collect path "
                "return 404. Args: page_id? | artifact_id?"
            ),
            handler=unpublish_html_page,
            school_scoped=False,
        )
    )
    gw.register(
        ToolSpec(
            name="generate_image",
            description=(
                "Create one downloadable png/jpg via Zhipu glm-image HTTPS API. "
                "On missing key, timeout, or 4xx: honest Chinese failure; never invent pixels. "
                "To place it in Word/PPT, pass the returned artifact id as "
                "image_artifact_id on spec. To place it in HTML, set img src to "
                "pico-artifact:<id>. Do not paste base64. Do not also hand it to the "
                "teacher as a separate download when it is already inside the file. "
                "Args: prompt, title?"
            ),
            handler=generate_image,
            school_scoped=False,
        )
    )
    gw.register(
        ToolSpec(
            name="generate_diagram",
            description=(
                "Draw one structure diagram (flowchart, sequence, org chart) from mermaid "
                "source into a downloadable PNG Artifact. This tool draws structure; "
                "it is not a photo generator. Sibling of generate_image — they do not "
                "veto each other. kind defaults to mermaid; d2 is not wired and fails "
                "honestly. On parse/sandbox failure: honest Chinese failure; never invent "
                "a diagram. To place it in Word/PPT, pass the returned artifact id as "
                "image_artifact_id on spec. Args: source, kind?, title?"
            ),
            handler=generate_diagram,
            school_scoped=False,
        )
    )
    gw.register(
        ToolSpec(
            name="verify_html_document",
            description=(
                "System-side static HTML structure self-check (artifact or inline content). "
                "Fails when the page loads scripts, ES imports, styles, images, or media "
                "from http(s). Returns machine JSON for the control plane (overall/checks). "
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
                "image_artifact_ids": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": (
                        "Ledger png/jpg ids. In body use src=\"pico-artifact:0\" "
                        "or src=\"pico-artifact:<id>\". Missing id skips that picture."
                    ),
                },
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
                    "description": "Existing .docx/.xlsx/.pptx artifact to open as a content box",
                },
                "filename": {
                    "type": "string",
                    "description": "Document filename shown on the content box",
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
                        "Document body. Blank lines separate paragraphs. "
                        "Empty body fails — the tool will not pad filler."
                    ),
                },
                "spec": {
                    "type": "object",
                    "description": "pico.office.spec/v1. Use for tables/images. Overrides body.",
                },
                "blocks": {
                    "type": "array",
                    "description": "spec.blocks shortcut (heading/para/table/image)",
                },
            },
            "required": ["title", "marker"],
        },
        "sandbox_pptx_lib": {
            "type": "object",
            "properties": {
                "source": {
                    "type": "string",
                    "description": (
                        "python-pptx body. from pptx import Presentation, Inches, Pt, "
                        "RGBColor is allowed. from pathlib import Path is a stub. "
                        "prs.save is routed to the ledger. IMAGE_PATHS[0] is the first "
                        "picture. add_title_slide image= and add_table prs=/rows= aliases. "
                        "Do not import os. Add slides then save_deck or prs.save. "
                        "Empty shells fail."
                    ),
                },
                "title": {
                    "type": "string",
                    "description": "Filename, preferably ending with .pptx",
                },
                "image_artifact_ids": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Ledger image ids exposed as IMAGE_PATHS",
                },
            },
            "required": ["source"],
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
                        "Text-only slide draft. Separate slides with a blank line or ---. "
                        "Do not put [image:…] here — it will not embed. "
                        "Empty deck fails — the tool will not invent slides."
                    ),
                },
                "spec": {
                    "type": "object",
                    "description": (
                        "pico.office.spec/v1 slides. Overrides body. "
                        "Each slide may set image_artifact_id to a ledger png/jpg id."
                    ),
                },
                "blocks": {
                    "type": "array",
                    "description": (
                        "spec.blocks shortcut. Slide objects: title, bullets, "
                        "image_artifact_id. type cover/content/title/page (or omitted) "
                        "are slides."
                    ),
                },
            },
            "required": ["title", "marker"],
        },
        "render_document": {
            "type": "object",
            "properties": {
                "spec": {
                    "type": "object",
                    "description": "pico.office.spec/v1 (kind + blocks)",
                },
                "title": {"type": "string", "description": "Download filename"},
            },
            "required": ["spec"],
        },
        "inspect_document": {
            "type": "object",
            "properties": {
                "artifact_id": {"type": "string"},
                "title": {"type": "string"},
                "kind": {"type": "string", "description": "docx, pptx, or xlsx"},
            },
        },
        "verify_document": {
            "type": "object",
            "properties": {
                "artifact_id": {"type": "string"},
                "title": {"type": "string"},
                "kind": {"type": "string", "description": "docx, pptx, or xlsx"},
            },
        },
        "publish_html_page": {
            "type": "object",
            "properties": {
                "artifact_id": {
                    "type": "string",
                    "description": "Existing HTML artifact to publish",
                },
            },
            "required": ["artifact_id"],
        },
        "unpublish_html_page": {
            "type": "object",
            "properties": {
                "page_id": {"type": "string"},
                "artifact_id": {"type": "string"},
            },
        },
        "generate_xlsx_document": {
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "Download filename"},
                "marker": {"type": "string"},
                "body": {"type": "string"},
                "spec": {"type": "object", "description": "pico.office.spec/v1 sheets"},
                "blocks": {"type": "array", "description": "spec.blocks shortcut (sheet objects)"},
            },
            "required": ["title", "marker"],
        },
        "edit_xlsx_document": {
            "type": "object",
            "properties": {
                "artifact_id": {"type": "string"},
                "title": {"type": "string"},
                "cell": {"type": "string", "description": "A1-style address"},
                "value": {"type": "string", "description": "New cell value; = starts a formula"},
                "sheet": {"description": "Sheet name or 1-based index"},
                "values": {
                    "type": "object",
                    "description": "{{key}} replacements",
                },
                "output_title": {"type": "string"},
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
                    "description": "1-based nonempty paragraph to replace or comment",
                },
                "text": {"type": "string", "description": "New paragraph text"},
                "comment": {"type": "string", "description": "Word comment on that paragraph"},
                "values": {
                    "type": "object",
                    "description": "{{key}} replacements",
                },
                "output_title": {
                    "type": "string",
                    "description": "Optional download filename",
                },
            },
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
        "generate_diagram": {
            "type": "object",
            "properties": {
                "source": {
                    "type": "string",
                    "description": "Mermaid source (fences optional). Flow/sequence/org charts.",
                },
                "kind": {
                    "type": "string",
                    "description": "Diagram language. Only mermaid is wired. d2 is rejected.",
                },
                "title": {
                    "type": "string",
                    "description": "Optional download filename ending .png",
                },
            },
            "required": ["source"],
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
