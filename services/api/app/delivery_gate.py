"""Shared fail-closed delivery gate.

Single source of truth for ``delivery.summary`` observability and the
fail-closed checks so that retry / REST / automation runs (``_execute_run``)
cannot bypass the #375 fail-closed semantics that interactive submissions get
via ``_finalize_run``.

Used by:
- ``services/api/app/openai_compat.py`` -> ``_finalize_run`` (interactive chat)
- ``services/api/app/run_service.py``   -> ``_execute_run``  (retry / /v1/tasks / automation)

T-HARNESS-SLIM: no prompt-word supervisor. Gates are assistant-claim vs disk
and empty Office zip only.
"""

from __future__ import annotations

from typing import Any

from pico_orchestrator.delivery_policy import (
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
    """Emit ``delivery.summary`` and fail-closed when a file claim is unmet.

    Mutates ``run.status`` / ``run.error`` in place and writes events via
    ``append_event(..., commit=False)``; the caller is responsible for commit.
    """
    from sqlalchemy import select

    from app.db import ArtifactRow, append_event

    del user_prompt
    run_id = run.id

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
    if status in ("succeeded", "failed", "cancelled"):
        await append_event(
            session,
            run_id,
            "delivery.summary",
            {
                "status": status,
                "artifact_count": user_art_count,
                "min_required": 0,
                "titles": titles[:40],
                "multi_deliverable": False,
                "pipeline": False,
                "revision": False,
                "runnable_html": False,
                "implicit_package": False,
                "structure_item_count": 0,
                "prior_artifact_count": 0,
                "ok": status == "succeeded",
                "human_titles": titles[:40],
                "note": (
                    "Prefer run.status + delivery.summary + artifact list over "
                    "client stream timeout alone. "
                    "Scripts: scripts/wait_delivery_summary.py. "
                    "Human lens: open files in app/browser; L0≠人类可用. "
                    "min_required is never guessed from the user prompt."
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
