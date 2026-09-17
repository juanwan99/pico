"""Thin adapter: edu JWT → field-kb-ingest (Docling). Does not store source."""

from __future__ import annotations

import asyncio
import base64
import binascii
import hashlib
import sys
import uuid
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pico_orchestrator.meili_kb import (
    count_material,
    documents_from_text,
    is_noise_title,
    lab_index_blocked,
    search_materials,
    upsert_documents,
)
from pydantic import BaseModel, Field

from app.auth import (
    Principal,
    enforce_feature,
    feature_enabled,
    payer_for,
    require_any_scope,
)
from app.usage_ledger import record_usage_event

router = APIRouter(tags=["edu-kb-ingest"])

MAX_BYTES = 20 * 1024 * 1024
PKG = Path("/app/packages/field-kb-ingest")
if not PKG.exists():
    PKG = Path(__file__).resolve().parents[3] / "packages" / "field-kb-ingest"
if str(PKG) not in sys.path:
    sys.path.insert(0, str(PKG))


class IngestIn(BaseModel):
    kind: str = Field(default="material", max_length=16)
    title: str = Field(default="", max_length=200)
    filename: str | None = Field(default=None, max_length=180)
    content_b64: str | None = None
    text: str | None = None
    item_id: str | None = Field(default=None, max_length=80)


class SearchIn(BaseModel):
    query: str = Field(min_length=1, max_length=500)
    limit: int = Field(default=8, ge=1, le=50)
    scope: str = Field(default="member", max_length=16)


def _content_item_id(raw: str | None, content_sha: str) -> str:
    value = "".join(ch for ch in str(raw or "") if ch.isalnum() or ch in "-_")[:80]
    return value or content_sha


def _slices_text(slices: list[Any]) -> str:
    parts: list[str] = []
    for row in slices:
        if isinstance(row, dict):
            parts.append(str(row.get("excerpt") or row.get("text") or ""))
        elif isinstance(row, str):
            parts.append(row)
    return "\n\n".join(p.strip() for p in parts if str(p).strip())


def _bad(code: str, message: str, status: int = 400) -> HTTPException:
    return HTTPException(status_code=status, detail={"code": code, "message": message})


def _legacy_ingest_name(filename: str, mapped: str) -> str:
    stem = Path(filename or "file").stem or "file"
    return f"{stem}{mapped}"


async def maybe_convert_legacy(filename: str, data: bytes) -> tuple[str, bytes]:
    """OLE / WPS → OOXML via the existing soffice sidecar. Not a Pico reader."""
    from pico_orchestrator.office.convert import (
        LegacyOfficeConvertError,
        convert_legacy_office_bytes,
    )
    from pico_orchestrator.office.legacy import convert_target_from_name, looks_ooxml

    mapped = convert_target_from_name(filename)
    if not mapped:
        return filename, data
    if looks_ooxml(data):
        return _legacy_ingest_name(filename, mapped), data
    try:
        converted = await convert_legacy_office_bytes(filename, data)
    except LegacyOfficeConvertError as err:
        human = (
            f"《{filename}》是旧格式，这次没能转成知识库能读的文件。"
            f"{err.message}。可以换成 .docx/.xlsx/.pptx 再传。"
        )
        raise _bad("file.legacy_unconvertible", human, 422) from err
    return _legacy_ingest_name(filename, mapped), converted


def _decode(raw: str) -> bytes:
    compact = "".join(str(raw or "").split())
    if not compact:
        raise _bad("file.invalid", "没有文件内容")
    try:
        data = base64.b64decode(compact, validate=False)
    except (binascii.Error, ValueError) as exc:
        raise _bad("file.invalid", "文件内容不是合法的 base64") from exc
    if len(data) > MAX_BYTES:
        raise _bad("file.too_large", "文件太大（上限 20MB）", 413)
    return data


@router.post("/v1/kb/ingest")
async def post_kb_ingest(
    body: IngestIn,
    principal: Principal = Depends(require_any_scope("ai:run", "ai:read")),
) -> dict[str, Any]:
    # Invalid base64 still has a stable identity; valid files use decoded bytes.
    raw = body.content_b64 if body.content_b64 else body.text or ""
    content_sha = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    ingest_ok = False  # per-file price only when the file actually went in (#1042)
    try:
        data = None
        if body.content_b64:
            data = _decode(body.content_b64)
            content_sha = hashlib.sha256(data).hexdigest()
        try:
            from ingest import ingest_bytes, ingest_text
        except Exception as exc:
            raise _bad("ingest.unavailable", f"Docling 入库包不可用：{exc}", 503) from exc

        title = (body.title or body.filename or "未命名").strip()
        ingest_name = body.filename or "file"
        try:
            # OCR / Docling are CPU-bound and synchronous: keep them off the
            # event loop so chat keeps flowing while a scan is read.
            if data is not None:
                ingest_name, data = await maybe_convert_legacy(ingest_name, data)
                result = await asyncio.to_thread(
                    ingest_bytes, filename=ingest_name, data=data, title=title, ocr=True
                )
            else:
                result = await asyncio.to_thread(ingest_text, text=body.text or "", title=title)
        except HTTPException:
            raise
        except ModuleNotFoundError as exc:
            raise _bad("docling_missing", "文档转换引擎没就位，请管理员看镜像里的 Docling 后端。", 503) from exc
        except Exception as exc:
            # ingest_bytes already classifies its own errors; this is the last net.
            raise _bad("ingest.failed", "这份没读出来。换个格式再试；持续失败请把文件名发给管理员。", 422) from exc
        slices = result.get("slices") or []
        if not result.get("ok") or not slices:
            code = str(result.get("code") or "empty")
            message = str(result.get("error") or "文件里没读到文字。")
            # Code table: docs/KB-INGEST-FORMATS.md. edu shows `message` verbatim.
            if code in {"ocr_missing", "hf_offline", "docling_missing", "ingest.unavailable"}:
                status = 503
            elif code == "unsupported_format":
                status = 415
            else:
                status = 400
            raise _bad(code, message, status)
        item_id = _content_item_id(body.item_id, content_sha)
        indexed = False
        chunk_count = 0
        skip_reason = None
        if is_noise_title(title):
            skip_reason = "noise"
        elif lab_index_blocked(str(principal.school_id or "")):
            skip_reason = "lab"
        else:
            # Index the full extract. slices[] is a short edu preview (8×800);
            # using only that dropped later sections (live Word 字体/行距 miss).
            full = str(result.get("markdown") or "").strip() or _slices_text(slices)
            docs = documents_from_text(
                artifact_id=item_id,
                title=title,
                text=full,
                school_id=str(principal.school_id or ""),
                membership_id=str(principal.membership_id or ""),
                scope="school",
            )
            indexed = upsert_documents(docs, replace_artifact=True)
            chunk_count = len(docs) if indexed else 0
        ingest_ok = bool(indexed)
        return {
            "ok": True,
            "engine": result.get("engine") or "docling",
            "tags": list(result.get("tags") or []),
            "kind": body.kind,
            "item_id": item_id,
            "indexed": indexed,
            "chunk_count": chunk_count,
            "skip_reason": skip_reason,
            "slices": slices,
        }
    finally:
        # Await the fail-open ledger before either a response or an error escapes.
        if getattr(principal, "school_id", None):
            await record_usage_event(
                school_id=principal.school_id,
                membership_id=principal.membership_id,
                kind="api",
                # #1042: ingest is priced per file (rate card per_call), not per token —
                # Meili makes the embedding calls, Pico never sees those tokens.
                model="kb-ingest-file",
                source="kb_ingest",
                tokens_unknown=True,
                extra={"item_kind": body.kind, "query_count": 1, "ok": ingest_ok},
                bill_to=payer_for(principal),
                idempotency_key=(
                    "kb_ingest:"
                    f"{principal.school_id}:{body.kind}:"
                    f"{_content_item_id(body.item_id, content_sha)}:{content_sha}"
                ),
            )


@router.post("/v1/kb/search")
async def post_kb_search(
    body: SearchIn,
    principal: Principal = Depends(require_any_scope("ai:run", "ai:read")),
) -> dict[str, Any]:
    """Same Meili path as Pi kb_search. Tenant comes from the JWT, not the body."""
    include_school = str(body.scope or "").strip().lower() == "school"
    enforce_feature(principal, "kb")
    try:
        result = search_materials(
            body.query,
            school_id=principal.school_id,
            membership_id=principal.membership_id,
            limit=body.limit,
            include_school=include_school,
            rerank_ok=feature_enabled(principal, "rerank"),
        )
    except RuntimeError as exc:
        raise _bad("kb.unavailable", "材料库暂时不可用，没有查到。不能编造材料内容。", 503) from exc
    if result.get("reranked"):
        # #1042: the rerank call costs tokens; plain search does not.
        await record_usage_event(
            school_id=principal.school_id,
            membership_id=principal.membership_id,
            kind="search",
            model=str((result.get("rerank_usage") or {}).get("model") or "") or None,
            prompt_tokens=(result.get("rerank_usage") or {}).get("prompt_tokens"),
            completion_tokens=(result.get("rerank_usage") or {}).get("completion_tokens"),
            total_tokens=(result.get("rerank_usage") or {}).get("total_tokens"),
            tokens_unknown=not isinstance(
                (result.get("rerank_usage") or {}).get("total_tokens"), int
            ),
            source="kb_rerank",
            extra={"tool": "kb_rerank", "query_count": 1, "ok": True},
            bill_to=payer_for(principal),
            idempotency_key=f"search:norun:kb_rerank:{uuid.uuid4().hex[:12]}",
        )
    hits = []
    for row in result.get("hits") or []:
        if not isinstance(row, dict):
            continue
        if str(row.get("school_id") or "") and str(row["school_id"]) != principal.school_id:
            continue
        row_scope = str(row.get("scope") or "member")
        row_member = str(row.get("membership_id") or "")
        if include_school:
            if row_scope != "school" and row_member != principal.membership_id:
                continue
        elif row_member and row_member != principal.membership_id:
            continue
        hits.append(
            {
                "chunk_id": row.get("chunk_id"),
                "artifact_id": row.get("artifact_id") or row.get("material_id"),
                "material_id": row.get("material_id") or row.get("artifact_id"),
                "title": row.get("title") or "",
                "heading": row.get("heading") or "",
                "page": row.get("page"),
                "text": row.get("text") or "",
                "parent_text": row.get("parent_text") or "",
                # Same file's other pooled chunks, top chunk first (#1006 knife 3).
                "passages": [p for p in (row.get("passages") or []) if isinstance(p, dict)],
                # Other ledger files with identical extracted content (#1006 knife 4).
                "clone_artifact_ids": [str(a) for a in (row.get("clone_artifact_ids") or [])],
            }
        )
    return {
        "ok": True,
        "mode": "keyword",
        "hybrid": bool(result.get("hybrid")),
        "reranked": bool(result.get("reranked")),
        "rerank_skip": str(result.get("rerank_skip") or ""),
        "include_school": include_school,
        "count": len(hits),
        "hits": hits,
    }


@router.get("/v1/kb/items/{item_id}")
async def get_kb_item(
    item_id: str,
    principal: Principal = Depends(require_any_scope("ai:run", "ai:read")),
) -> dict[str, Any]:
    aid = _content_item_id(item_id, "")
    if not aid:
        raise _bad("kb.invalid", "没有材料 id")
    try:
        n = count_material(aid, school_id=str(principal.school_id or ""), scope="school")
    except RuntimeError as exc:
        raise _bad("kb.unavailable", "材料库暂时不可用，没有查到。不能编造材料内容。", 503) from exc
    return {
        "ok": True,
        "item_id": aid,
        "scope": "school",
        "chunk_count": n,
        "ready": n > 0,
    }
