"""Best-effort usage-ledger emit from gateway tools (no second ledger).

Search/fetch call ``record_usage_event`` when pico-api is on sys.path.
Never raises into the tool path. See docs/USAGE-LEDGER.md §5.
"""

from __future__ import annotations

import logging
import uuid
from contextvars import ContextVar
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)

_SEARCH_TOOLS = frozenset({"web_search", "web_fetch"})


@dataclass(frozen=True)
class UsageBind:
    school_id: str
    membership_id: str
    run_id: str | None = None
    task_id: str | None = None
    tool_call_id: str | None = None


_BIND: ContextVar[UsageBind | None] = ContextVar("pico_usage_bind", default=None)


def bind_usage_context(
    *,
    school_id: str,
    membership_id: str,
    run_id: str | None = None,
    task_id: str | None = None,
    tool_call_id: str | None = None,
) -> object:
    """Set request-scoped identity for search/fetch emits. Returns a token to reset."""
    return _BIND.set(
        UsageBind(
            school_id=school_id,
            membership_id=membership_id,
            run_id=run_id,
            task_id=task_id,
            tool_call_id=tool_call_id,
        )
    )


def reset_usage_context(token: object) -> None:
    try:
        _BIND.reset(token)  # type: ignore[arg-type]
    except Exception:  # noqa: BLE001
        _BIND.set(None)


def current_usage_bind() -> UsageBind | None:
    return _BIND.get()


def is_search_tool(name: str) -> bool:
    return (name or "").strip() in _SEARCH_TOOLS


async def emit_search_usage(
    principal: Any,
    *,
    tool: str,
    extra: dict[str, Any] | None = None,
    tool_call_id: str | None = None,
    ok: bool = True,
) -> None:
    """Record kind=search. Swallows all errors (Run path stays up)."""
    name = (tool or "").strip() or "web_search"
    bind = _BIND.get()
    school = getattr(principal, "school_id", None) or (bind.school_id if bind else "")
    member = getattr(principal, "membership_id", None) or (
        bind.membership_id if bind else ""
    )
    if not school or not member:
        return
    run_id = (bind.run_id if bind else None) or None
    task_id = (bind.task_id if bind else None) or None
    store = getattr(principal, "_pico_artifact_store", None)
    if run_id is None and store is not None:
        run_id = getattr(store, "_run_id", None)
        task_id = task_id or getattr(store, "_task_id", None)
    call_id = (
        (tool_call_id or "").strip()
        or (bind.tool_call_id if bind else "")
        or uuid.uuid4().hex[:12]
    )
    payload = dict(extra or {})
    payload.setdefault("tool", name)
    payload["ok"] = bool(ok)
    key = f"search:{run_id or 'norun'}:{name}:{call_id}"
    try:
        from app.usage_ledger import record_usage_event
    except Exception:  # noqa: BLE001
        logger.debug("usage_ledger not importable; search emit skipped")
        return
    await record_usage_event(
        school_id=str(school),
        membership_id=str(member),
        kind="search",
        tokens_unknown=True,
        task_id=str(task_id) if task_id else None,
        run_id=str(run_id) if run_id else None,
        source=name[:64],
        extra=payload,
        idempotency_key=key[:160],
    )
