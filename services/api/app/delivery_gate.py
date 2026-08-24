"""Shared fail-closed delivery gate.

Single source of truth for ``delivery.summary`` observability and the
fail-closed checks so that retry / REST / automation runs (``_execute_run``)
cannot bypass the #375 fail-closed semantics that interactive submissions get
via ``_finalize_run``.

Used by:
- ``services/api/app/openai_compat.py`` -> ``_finalize_run`` (interactive chat)
- ``services/api/app/run_service.py``   -> ``_execute_run``  (retry / /v1/tasks / automation)
"""

from __future__ import annotations

import re
from typing import Any

from pico_orchestrator.delivery_policy import (
    analyze_delivery,
    count_user_artifacts,
    is_bookkeeping_title,
    looks_like_clarification,
)
from pico_orchestrator.document_generators import office_shell_reason


def _office_shell_failure(art_list: list[tuple[Any, ...]]) -> str | None:
    """If every docx or every pptx on this run is an empty shell, fail closed."""
    from app.artifact_store import decode_artifact_payload

    by_ext: dict[str, list[str | None]] = {".docx": [], ".pptx": []}
    for kind, title, _byte_size, inline, encoding in art_list:
        title_s = str(title or "")
        if is_bookkeeping_title(title_s):
            continue
        kind_s = str(kind or "").lower()
        lower = title_s.lower()
        ext = ""
        if kind_s == "docx" or lower.endswith(".docx"):
            ext = ".docx"
        elif kind_s == "pptx" or lower.endswith(".pptx"):
            ext = ".pptx"
        else:
            continue
        try:
            raw = decode_artifact_payload(inline, encoding)
        except Exception:  # noqa: BLE001 — treat corrupt as a shell
            by_ext[ext].append("交件损坏，打不开。")
            continue
        by_ext[ext].append(office_shell_reason(raw, ext))
    for ext, reasons in by_ext.items():
        if reasons and all(reasons):
            return next(r for r in reasons if r)
    return None


async def apply_delivery_gate(
    session: Any,
    run: Any,
    *,
    final_text: str | None,
    user_prompt: str | None,
) -> None:
    """Emit ``delivery.summary`` and fail-closed when delivery intent is unmet.

    Mutates ``run.status`` / ``run.error`` in place and writes events via
    ``append_event(..., commit=False)``; the caller is responsible for commit.
    """
    from sqlalchemy import select

    from app.db import ArtifactRow, TaskRow, append_event

    # Lazy imports keep this module out of the openai_compat <-> run_service cycle.
    from app.openai_compat import (
        _prior_artifact_titles_for_principal,
        _wants_deliverable_document,
    )

    run_id = run.id

    # Principal-scoped prior titles when available on the run's school/membership.
    prior_titles: list[str] = []
    try:
        task = await session.get(TaskRow, run.task_id) if run.task_id else None
        if task is not None:

            class _P:
                school_id = task.school_id
                membership_id = task.membership_id

            prior_titles = await _prior_artifact_titles_for_principal(_P())
    except Exception:  # noqa: BLE001 — policy must not fail the run
        prior_titles = []

    prompt_for_plan = user_prompt or run.prompt or ""
    plan = analyze_delivery(prompt_for_plan, prior_artifact_titles=prior_titles)
    named = _wants_deliverable_document(prompt_for_plan)
    if not named:
        from dataclasses import replace as _dc_replace_plan

        plan = _dc_replace_plan(plan, min_artifacts=0, force_agent=False)
    elif int(plan.min_artifacts or 0) < 1:
        from dataclasses import replace as _dc_replace_plan

        plan = _dc_replace_plan(plan, min_artifacts=1)

    art_rows = await session.execute(
        select(
            ArtifactRow.kind,
            ArtifactRow.title,
            ArtifactRow.byte_size,
            ArtifactRow.inline,
            ArtifactRow.content_encoding,
        ).where(ArtifactRow.run_id == run_id)
    )
    art_list = list(art_rows.all())
    titles = [
        str(title or "")
        for _kind, title, _bs, _inline, _enc in art_list
        if title and not is_bookkeeping_title(str(title))
    ]
    user_art_count = count_user_artifacts(
        [(kind, title, byte_size) for kind, title, byte_size, _inline, _enc in art_list]
    )

    status = run.status
    # G5 observability: machine-readable delivery summary (always, when we have a plan).
    # G1 ok: multi/pipeline require min count; single-unit with ≥1 file is user-visible OK.
    multi_or_pipeline = bool(plan.multi_deliverable or plan.pipeline)
    if plan.min_artifacts <= 0:
        delivery_ok = True
    elif multi_or_pipeline:
        delivery_ok = user_art_count >= plan.min_artifacts
    else:
        delivery_ok = user_art_count >= 1
    if status in ("succeeded", "failed", "cancelled"):
        await append_event(
            session,
            run_id,
            "delivery.summary",
            {
                "status": status,
                "artifact_count": user_art_count,
                "min_required": plan.min_artifacts,
                "titles": titles[:40],
                "multi_deliverable": plan.multi_deliverable,
                "pipeline": plan.pipeline,
                "revision": plan.revision,
                "runnable_html": plan.runnable_html,
                "implicit_package": bool(
                    getattr(plan, "implicit_package", False)
                ),
                "structure_item_count": int(
                    getattr(plan, "structure_item_count", 0) or 0
                ),
                "prior_artifact_count": int(
                    getattr(plan, "prior_artifact_count", 0) or 0
                ),
                "ok": delivery_ok if status == "succeeded" else False,
                "human_titles": titles[:40],
                "note": (
                    "Prefer run.status + delivery.summary + artifact list over "
                    "client stream timeout alone. "
                    "Scripts: scripts/wait_delivery_summary.py. "
                    "Human lens: open files in app/browser; L0≠人类可用. "
                    "G1: single-unit + ≥1 file is ok even if heuristic min was higher."
                ),
            },
            commit=False,
        )

    # S2.2 / landing: this-round named Word/PPT/HTML without a real user-visible file.
    # Markdown / .txt / generic workspace files are valid when the turn did not
    # name Office/HTML. When min_artifacts>=1 (incl. multi), zero real files must
    # never stay succeeded.
    if (
        named
        and status == "succeeded"
        and (
            plan.min_artifacts <= 1
            or user_art_count == 0
        )
        and not (
            plan.multi_deliverable
            and user_art_count > 0
            and user_art_count < plan.min_artifacts
        )
    ):
        # multi short-delivery (1 of N) is handled by delivery_min_artifacts below;
        # this block catches chat-only / zero-byte "success".
        wants_office_binary = bool(
            re.search(
                r"(?:生成|重新生成|下载|可下载|导出|交付|做成|输出).{0,40}"
                r"(?:Word|word|docx|PPT|pptx|html|幻灯片|课件|网页)",
                prompt_for_plan,
                re.IGNORECASE,
            )
        ) or bool(plan.runnable_html)
        has_real_file = False
        for kind, title, byte_size, _inline, _enc in art_list:
            title_s = str(title or "")
            kind_s = str(kind or "").lower()
            if is_bookkeeping_title(title_s):
                continue
            lower = title_s.lower()
            size_ok = (byte_size or 0) > 0
            if wants_office_binary:
                if kind_s in {"docx", "html", "htm", "pptx"} and size_ok:
                    has_real_file = True
                    break
                if lower.endswith((".docx", ".html", ".htm", ".pptx")) and size_ok:
                    has_real_file = True
                    break
            else:
                # Any non-bookkeeping titled artifact with bytes (md/txt/file/doc…).
                if size_ok and title_s.strip():
                    has_real_file = True
                    break
        if not has_real_file:
            # Clarification / awaiting-user: honest non-failure (not chat-only claim).
            if looks_like_clarification(final_text or ""):
                await append_event(
                    session,
                    run_id,
                    "delivery.summary",
                    {
                        "status": "succeeded",
                        "artifact_count": user_art_count,
                        "min_required": plan.min_artifacts,
                        "ok": False,
                        "awaiting_user": True,
                        "reason": "clarification",
                        "note": "Model asked clarifying questions; not a delivery failure.",
                    },
                    commit=False,
                )
            else:
                run.status = "failed"
                if wants_office_binary:
                    # P2 truthfulness: if other-format files exist, say so —
                    # never claim "no downloadable file" while files are present.
                    has_any_file = any(
                        not is_bookkeeping_title(str(title or ""))
                        and (byte_size or 0) > 0
                        for _kind, title, byte_size, _inline, _enc in art_list
                    )
                    if has_any_file:
                        run.error = (
                            "未生成要求的 Word/HTML 文件（本轮产物为其他格式，可下载）。"
                            "请用「生成可下载 Word/HTML」的专用工具重新生成；"
                            "其他格式不能当作 Word/HTML 交付。"
                        )
                    else:
                        run.error = (
                            "交件未生成可下载的真文件（HTML/Word/PPT）。"
                            "请点「再跑一次」或重新描述「生成可下载 Word/HTML」；"
                            "纯文字摘要不能当作文件交付。"
                        )
                else:
                    run.error = (
                        "交件未写入可下载文件。请用工具落盘后再交；"
                        "纯聊天复述不能当作文件交付。"
                    )
                await append_event(
                    session,
                    run_id,
                    "run.status",
                    {
                        "status": "failed",
                        "reason": "deliverable_missing_artifact",
                        "user_message": run.error,
                        "runtime": "fail-closed",
                    },
                    commit=False,
                )

    # G1: fail-closed min count only for true multi/pipeline intent.
    # Single-unit delivery with ≥1 user-visible file must not fail solely
    # because a heuristic expected more content-sections-as-files.
    # Clarification turns (awaiting user) must not fail on min either.
    fail_closed_min = (
        run.status == "succeeded"
        and plan.min_artifacts > 0
        and user_art_count < plan.min_artifacts
        and (multi_or_pipeline or user_art_count == 0)
        and not looks_like_clarification(final_text or "")
    )
    if fail_closed_min:
        run.status = "failed"
        run.error = (
            f"工程交付未满足多产物要求：需要至少 {plan.min_artifacts} 个独立文件，"
            f"本轮仅 {user_art_count} 个。"
            "请分文件写入（禁止单长文多标题冒充），再跑一次。"
        )
        await append_event(
            session,
            run_id,
            "run.status",
            {
                "status": "failed",
                "reason": "delivery_min_artifacts",
                "min_required": plan.min_artifacts,
                "artifact_count": user_art_count,
                "user_message": run.error,
                "runtime": "fail-closed",
            },
            commit=False,
        )
        # else path: keep succeeded; delivery.summary.ok already True for single-unit ≥1

    # Word/PPT must open with real body (not a three-line XML zip).
    if run.status == "succeeded" and not looks_like_clarification(final_text or ""):
        shell_reason = _office_shell_failure(art_list)
        if shell_reason:
            run.status = "failed"
            run.error = shell_reason
            await append_event(
                session,
                run_id,
                "run.status",
                {
                    "status": "failed",
                    "reason": "office_body_too_thin",
                    "user_message": run.error,
                    "runtime": "fail-closed",
                },
                commit=False,
            )
