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

from typing import Any

from pico_orchestrator.delivery_policy import (
    analyze_delivery,
    count_user_artifacts,
    is_bookkeeping_title,
    looks_like_clarification,
    looks_like_delivery_claim,
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
    from app.openai_compat import _prior_artifact_titles_for_principal

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
    from dataclasses import replace as _dc_replace_plan

    # Never fail-closed from a user-prompt word list. Observability only.
    plan = _dc_replace_plan(plan, min_artifacts=0, force_agent=False)

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

    # Fail-closed only when the assistant claimed a file landed and none did.
    # Do not read 课件/通知/Word tables out of the user prompt.
    if (
        status == "succeeded"
        and user_art_count == 0
        and looks_like_delivery_claim(final_text or "")
        and not looks_like_clarification(final_text or "")
    ):
        run.status = "failed"
        run.error = (
            "本轮声称已交文件，但没有可下载的真文件。"
            "请用工具落盘后再交；纯聊天复述不能当作文件交付。"
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
