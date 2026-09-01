"""Park a true-Pi turn until the teacher picks an option.

One verb, no second HITL OS. LibreChat answers via POST /v1/runs/{id}/ask-answer.
"""

from __future__ import annotations

import asyncio
from typing import Any

ASK_TIMEOUT_SEC = 180.0
_MAX_Q = 400
_MAX_OPT = 80
_MAX_OPTS = 6


class AskTimedOut(Exception):
    """HITL park expired with no answer. This is not a teacher choice."""

    def __init__(self, question: str = "") -> None:
        super().__init__("ask timeout")
        self.question = question or ""

_PENDING: dict[str, asyncio.Future[str]] = {}
_QUESTIONS: dict[str, dict[str, Any]] = {}


def pending(run_id: str) -> dict[str, Any] | None:
    return _QUESTIONS.get(run_id)


def answer(run_id: str, text: str) -> bool:
    chosen = (text or "").strip()[:_MAX_Q]
    if not chosen:
        return False
    fut = _PENDING.get(run_id)
    if fut is None or fut.done():
        return False
    fut.set_result(chosen)
    return True


def cancel(run_id: str) -> None:
    fut = _PENDING.pop(run_id, None)
    _QUESTIONS.pop(run_id, None)
    if fut is not None and not fut.done():
        fut.cancel()


def _clean_options(raw: Any) -> list[str]:
    if not isinstance(raw, list):
        return []
    out: list[str] = []
    seen: set[str] = set()
    for item in raw:
        label = str(item).strip()[:_MAX_OPT]
        if not label or label in seen:
            continue
        seen.add(label)
        out.append(label)
        if len(out) >= _MAX_OPTS:
            break
    return out


async def park(
    run_id: str,
    question: str,
    options: Any,
    emit: Any,
    *,
    timeout: float = ASK_TIMEOUT_SEC,
) -> dict[str, Any]:
    q = (question or "").strip()[:_MAX_Q]
    opts = _clean_options(options)
    if not q:
        return {"ok": False, "error": "question required"}
    if len(opts) < 2:
        return {"ok": False, "error": "need at least two options"}
    loop = asyncio.get_running_loop()
    fut: asyncio.Future[str] = loop.create_future()
    _PENDING[run_id] = fut
    _QUESTIONS[run_id] = {"question": q, "options": opts}
    try:
        if emit is not None:
            await emit(
                "ui.prompt.begin",
                {
                    "source": "true-pi",
                    "waiting": True,
                    "text": q,
                    "options": opts,
                },
            )
        chosen = await asyncio.wait_for(asyncio.shield(fut), timeout=timeout)
        if emit is not None:
            await emit(
                "ui.prompt.end",
                {
                    "source": "true-pi",
                    "waiting": False,
                    "text": "已选",
                    "answer": chosen,
                },
            )
        return {"ok": True, "answer": chosen, "question": q}
    except TimeoutError:
        if emit is not None:
            await emit(
                "ui.prompt.end",
                {"source": "true-pi", "waiting": False, "text": "超时未选"},
            )
        return {"ok": False, "error": "timeout", "question": q}
    except asyncio.CancelledError:
        if emit is not None:
            await emit(
                "ui.prompt.end",
                {"source": "true-pi", "waiting": False, "text": "已取消"},
            )
        raise
    finally:
        _PENDING.pop(run_id, None)
        _QUESTIONS.pop(run_id, None)
