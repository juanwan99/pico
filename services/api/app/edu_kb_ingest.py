"""Thin adapter: edu JWT → field-kb-ingest (Docling). Does not store source."""

from __future__ import annotations

import base64
import binascii
import sys
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.auth import Principal, require_any_scope

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


def _bad(code: str, message: str, status: int = 400) -> HTTPException:
    return HTTPException(status_code=status, detail={"code": code, "message": message})


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
    _ = principal
    try:
        from ingest import ingest_bytes, ingest_text
    except Exception as exc:  # pragma: no cover - import surface
        raise _bad("ingest.unavailable", f"Docling 入库包不可用：{exc}", 503) from exc

    title = (body.title or body.filename or "未命名").strip()
    try:
        if body.content_b64:
            data = _decode(body.content_b64)
            result = ingest_bytes(filename=body.filename or "file", data=data, title=title)
        else:
            result = ingest_text(text=body.text or "", title=title)
    except ModuleNotFoundError as exc:
        raise _bad("ingest.docling_missing", "现网还没装 Docling，不能入库", 503) from exc
    except Exception as exc:
        raise _bad("ingest.failed", f"Docling 没抽出内容：{exc}", 422) from exc
    slices = result.get("slices") or []
    if not result.get("ok") or not slices:
        code = str(result.get("code") or "empty")
        message = str(result.get("error") or "抽出来是空的")
        status = 503 if code in {"ocr_missing", "hf_offline"} else 400
        raise _bad(code, message, status)
    return {
        "ok": True,
        "engine": result.get("engine") or "docling",
        "kind": body.kind,
        "slices": slices,
    }
