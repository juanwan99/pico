"""Thin adapter: edu JWT → exam-answer-extract package (answer sheet → card structure).

edu keeps file decoding / rasterising / confirm_desk mapping; Pico owns the prompt
(packages/exam-answer-extract/SKILL.md) and the model call. Contract: edu-core#1496.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import logging
import sys
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pico_orchestrator.teacher_text import teacher_safe
from pydantic import BaseModel, Field

from app.auth import Principal, payer_for, require_scope
from app.usage_ledger import record_usage_event

logger = logging.getLogger(__name__)

router = APIRouter(tags=["exam-answer-extract"])

# 试卷录入整份卷一次读（12 页物理卷，edu-core#3157）；讲评课件导出的 PDF 一题占几页，54 页的
# 生物课件（≈ 13MB 页图）题号排到第 48 页，24 页只读到选择题（edu-core#3164）
MAX_PAGES = 60
MAX_PAGE_BYTES = 4 * 1024 * 1024
MAX_TOTAL_BYTES = 40 * 1024 * 1024
MAX_TEXT_CHARS = 400_000
PAGE_MIMES = {"image/jpeg", "image/png", "image/webp"}

PKG = Path("/app/packages/exam-answer-extract")
if not PKG.exists():
    PKG = Path(__file__).resolve().parents[3] / "packages" / "exam-answer-extract"
if str(PKG) not in sys.path:
    sys.path.insert(0, str(PKG))


class PageIn(BaseModel):
    page: int = Field(ge=1, le=MAX_PAGES)
    mime: str = Field(default="image/jpeg", max_length=32)
    content_b64: str


class ExtractIn(BaseModel):
    subject_code: str | None = Field(default=None, max_length=16)
    subject_name: str | None = Field(default=None, max_length=32)
    text: str | None = Field(default=None, max_length=MAX_TEXT_CHARS)
    pages: list[PageIn] | None = Field(default=None, max_length=MAX_PAGES)
    item_id: str | None = Field(default=None, max_length=80)
    task: str | None = Field(default="answers", max_length=16)
    roster: str | None = Field(default=None, max_length=20000)


def _bad(code: str, message: str, status: int = 400) -> HTTPException:
    return HTTPException(status_code=status, detail={"code": code, "message": message})


def _decode_page(page: PageIn) -> tuple[bytes, str]:
    compact = "".join(str(page.content_b64 or "").split())
    if not compact:
        raise _bad("page.invalid", f"第 {page.page} 页没有图片内容")
    try:
        data = base64.b64decode(compact, validate=False)
    except (binascii.Error, ValueError) as exc:
        raise _bad("page.invalid", f"第 {page.page} 页图片不是合法的 base64") from exc
    if len(data) > MAX_PAGE_BYTES:
        raise _bad("page.too_large", f"第 {page.page} 页图片太大（上限 4MB）", 413)
    mime = (page.mime or "").strip().lower()
    if mime == "image/jpg":
        mime = "image/jpeg"
    if mime not in PAGE_MIMES:
        raise _bad("page.invalid", f"第 {page.page} 页图片格式不支持（{mime or 'unknown'}）")
    return data, mime


@router.post("/v1/exam/answer-extract")
async def post_exam_answer_extract(
    body: ExtractIn,
    principal: Principal = Depends(require_scope("ai:run")),
) -> dict[str, Any]:
    has_text = bool((body.text or "").strip())
    has_pages = bool(body.pages)
    if has_text == has_pages:
        raise _bad("extract.invalid", "text 与 pages 二选一")

    digest = hashlib.sha256()
    pages: list[dict[str, Any]] = []
    if has_pages:
        total = 0
        seen: set[int] = set()
        for page in body.pages or []:
            if page.page in seen:
                raise _bad("extract.invalid", f"第 {page.page} 页重复")
            seen.add(page.page)
            data, mime = _decode_page(page)
            total += len(data)
            if total > MAX_TOTAL_BYTES:
                raise _bad("page.too_large", "页图总量太大（上限 40MB）", 413)
            digest.update(data)
            pages.append(
                {"page": page.page, "mime": mime, "data_b64": base64.b64encode(data).decode()}
            )
        pages.sort(key=lambda p: p["page"])
    else:
        digest.update((body.text or "").encode("utf-8"))
    # The same pages go out once per task (paper, then solve / answers): the task and roster are
    # part of what was asked, else the second call shares the first one's usage key and goes unbilled.
    digest.update(f"\0task={body.task or 'answers'}\0roster={body.roster or ''}".encode())
    content_sha = digest.hexdigest()

    result: dict[str, Any] | None = None
    usage: dict[str, Any] | None = None
    try:
        try:
            import extract as extract_mod
        except Exception as exc:
            raise _bad("extract.unavailable", f"答案抽取包不可用：{exc}", 503) from exc
        try:
            if has_pages:
                result = await extract_mod.extract_pages(
                    pages,
                    subject_code=body.subject_code,
                    subject_name=body.subject_name,
                    task=body.task or "answers",
                    roster=body.roster or "",
                )
            else:
                result = await extract_mod.extract_text(
                    body.text or "",
                    subject_code=body.subject_code,
                    subject_name=body.subject_name,
                    task=body.task or "answers",
                    roster=body.roster or "",
                )
        except extract_mod.ExtractError as exc:
            status = {
                "model.unconfigured": 503,
                "model.failed": 502,
                "extract.empty": 422,
                "skill.invalid": 500,
            }.get(exc.code, 400)
            if teacher_safe(str(exc), "") != str(exc):
                logger.warning("exam extract failed: %s", str(exc)[:300])
            raise _bad(exc.code, teacher_safe(str(exc), "这次没读成，请再试一次。"), status) from exc
        except Exception as exc:
            logger.warning("exam extract failed: %s", str(exc)[:300])
            raise _bad("model.failed", "这次没读成，请再试一次。", 502) from exc
        usage = result.pop("usage", None) or None
        return result
    finally:
        if getattr(principal, "school_id", None):
            await record_usage_event(
                school_id=principal.school_id,
                membership_id=principal.membership_id,
                kind="api",
                source="exam_answer_extract",
                model=(result or {}).get("model"),
                prompt_tokens=(usage or {}).get("prompt_tokens"),
                completion_tokens=(usage or {}).get("completion_tokens"),
                total_tokens=(usage or {}).get("total_tokens"),
                tokens_unknown=not usage,
                bill_to=payer_for(principal),
                idempotency_key=(
                    "exam_answer_extract:"
                    f"{principal.school_id}:{body.item_id or content_sha[:16]}:{content_sha}"
                ),
            )
