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
_SANDBOX_TOOLS = frozenset(
    {
        "sandbox_preview_inspect",
        "sandbox_workspace_exec",
        "generate_html_document",
        "sandbox_browser_open",
        "sandbox_browser_screenshot",
        "sandbox_document_open",
    }
)


def bill_to_from_scopes(scopes: Any) -> str:
    """Same rule as app.auth: ai:school-run → school, else member."""
    try:
        seq = list(scopes or [])
    except TypeError:
        seq = []
    return "school" if "ai:school-run" in seq else "member"


@dataclass(frozen=True)
class UsageBind:
    school_id: str
    membership_id: str
    run_id: str | None = None
    task_id: str | None = None
    tool_call_id: str | None = None
    conversation_id: str | None = None
    bill_to: str = "member"


_BIND: ContextVar[UsageBind | None] = ContextVar("pico_usage_bind", default=None)


def bind_usage_context(
    *,
    school_id: str,
    membership_id: str,
    run_id: str | None = None,
    task_id: str | None = None,
    tool_call_id: str | None = None,
    conversation_id: str | None = None,
    bill_to: str | None = None,
    scopes: Any = None,
) -> object:
    """Set request-scoped identity for search/fetch emits. Returns a token to reset."""
    payer = (bill_to or "").strip().lower()
    if payer not in {"school", "member"}:
        payer = bill_to_from_scopes(scopes)
    return _BIND.set(
        UsageBind(
            school_id=school_id,
            membership_id=membership_id,
            run_id=run_id,
            task_id=task_id,
            tool_call_id=tool_call_id,
            conversation_id=(conversation_id or "").strip() or None,
            bill_to=payer,
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


def is_sandbox_tool(name: str) -> bool:
    return (name or "").strip() in _SANDBOX_TOOLS


async def emit_image_usage(
    principal: Any,
    *,
    extra: dict[str, Any] | None = None,
    tool_call_id: str | None = None,
    ok: bool = True,
    source: str = "generate_image",
    model: str | None = None,
) -> None:
    """Record kind=image (Gemini/New API). Swallows all errors."""
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
    payload = dict(extra or {})
    payload["ok"] = bool(ok)
    payload.setdefault("tool", source)
    tokens_unknown = True
    prompt_tokens = payload.get("prompt_tokens")
    completion_tokens = payload.get("completion_tokens")
    total_tokens = payload.get("total_tokens")
    if prompt_tokens is not None or completion_tokens is not None or total_tokens is not None:
        tokens_unknown = False
    try:
        from app.channel_rates import load_rate_card

        rate = load_rate_card().find(kind="image", model=model)
        if rate is not None:
            payload.setdefault("channel_id", rate.id)
    except Exception:
        logger.debug("image channel_id lookup skipped", exc_info=True)
    call_id = (
        (tool_call_id or "").strip()
        or (bind.tool_call_id if bind else "")
        or uuid.uuid4().hex[:12]
    )
    key = f"image:{run_id or 'norun'}:{source}:{call_id}"
    try:
        from app.usage_ledger import record_usage_event
    except Exception:  # noqa: BLE001
        logger.debug("usage_ledger not importable; image emit skipped")
        return
    await record_usage_event(
        school_id=str(school),
        membership_id=str(member),
        kind="image",
        model=(model or "").strip() or None,
        prompt_tokens=prompt_tokens if isinstance(prompt_tokens, int) else None,
        completion_tokens=completion_tokens if isinstance(completion_tokens, int) else None,
        total_tokens=total_tokens if isinstance(total_tokens, int) else None,
        tokens_unknown=tokens_unknown,
        task_id=str(task_id) if task_id else None,
        run_id=str(run_id) if run_id else None,
        source=(source or "generate_image")[:64],
        extra=payload,
        idempotency_key=key[:160],
    )


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
    try:
        from app.channel_rates import load_rate_card

        rate = load_rate_card().find(kind="search", model=name)
        if rate is not None:
            payload.setdefault("channel_id", rate.id)
    except Exception:
        logger.debug("search channel_id lookup skipped", exc_info=True)
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
        model=name[:64],
        tokens_unknown=True,
        task_id=str(task_id) if task_id else None,
        run_id=str(run_id) if run_id else None,
        source=name[:64],
        extra=payload,
        idempotency_key=key[:160],
    )


async def emit_sandbox_usage(
    principal: Any,
    *,
    extra: dict[str, Any] | None = None,
    tool_call_id: str | None = None,
    ok: bool = True,
    source: str = "sandbox",
) -> None:
    """Record kind=sandbox. Swallows all errors (Run path stays up)."""
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
    payload = dict(extra or {})
    if store is not None and "workspace_id" not in payload:
        rid = run_id or getattr(store, "_run_id", None)
        try:
            from pico_orchestrator.sandbox_s1 import workspace_id_for

            payload["workspace_id"] = workspace_id_for(str(school), str(member), rid)
        except Exception:
            logger.debug("sandbox workspace_id hash skipped", exc_info=True)
    payload["ok"] = bool(ok)
    call_id = (
        (tool_call_id or "").strip()
        or (bind.tool_call_id if bind else "")
        or uuid.uuid4().hex[:12]
    )
    phase = str(payload.get("phase") or "inspect")
    art = str(payload.get("artifact_id") or payload.get("workspace_id") or call_id)
    key = f"sandbox:{run_id or 'norun'}:{phase}:{art}:{call_id}"
    try:
        from app.usage_ledger import record_usage_event
    except Exception:  # noqa: BLE001
        logger.debug("usage_ledger not importable; sandbox emit skipped")
        return
    await record_usage_event(
        school_id=str(school),
        membership_id=str(member),
        kind="sandbox",
        tokens_unknown=True,
        task_id=str(task_id) if task_id else None,
        run_id=str(run_id) if run_id else None,
        source=(source or "sandbox")[:64],
        extra=payload,
        idempotency_key=key[:160],
    )
