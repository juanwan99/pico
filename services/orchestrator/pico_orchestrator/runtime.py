"""Runtime selector: Pi Agent is the default multi-step kernel (HANDOFF-WB-PI).

Kimi Agent path is legacy opt-in only (``PICO_LEGACY_KIMI_AGENT_RUNTIME``).
Transitional ``run_agent_loop`` remains removed (KA-4 HARD); do not revive it.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Collection
from typing import Any

from pico_orchestrator.run_types import RunResult
from pico_orchestrator.user_errors import enrich_fail_payload

logger = logging.getLogger(__name__)


def _maybe_schedule_true_pi_shadow(*, hosted_result: RunResult, **kwargs: Any) -> None:
    """Fire-and-forget shadow when PICO_TRUE_PI_SHADOW=1. Hosted path unchanged."""
    try:
        from pico_orchestrator.true_pi.config import shadow_enabled
        from pico_orchestrator.true_pi.shadow import maybe_shadow_after_hosted
    except Exception:  # noqa: BLE001
        return
    if not shadow_enabled():
        return
    prompt = str(kwargs.get("prompt") or "")
    principal = kwargs.get("principal")
    if principal is None or not prompt:
        return

    async def _run() -> None:
        try:
            await maybe_shadow_after_hosted(
                prompt=prompt,
                principal=principal,
                hosted_result=hosted_result,
                caps=kwargs.get("caps"),
                artifact_store=kwargs.get("artifact_store"),
                is_cancelled=kwargs.get("is_cancelled"),
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "true_pi shadow schedule failed (hosted unaffected): %s",
                type(exc).__name__,
            )

    try:
        loop = asyncio.get_running_loop()
        loop.create_task(_run())
    except RuntimeError:
        # No running loop (sync tests) — skip shadow.
        return

_NO_RUNTIME = (
    "no multi-step runtime selected; enable PICO_PI_AGENT_RUNTIME=1 (default) "
    "or PICO_LEGACY_KIMI_AGENT_RUNTIME=1 for rollback. "
    "transitional run_agent_loop remains removed (KA-4 HARD)."
)

# Test hooks: when set, dispatch uses these callables instead of real modules.
_PI_IMPL: Any = None
_KIMI_IMPL: Any = None


def _as_principal_key(school_id: str, membership_id: str) -> tuple[str, str] | None:
    school = (school_id or "").strip()
    membership = (membership_id or "").strip()
    if not school or not membership:
        return None
    return (school, membership)


def _is_allow_all_entry(entry: Any) -> bool:
    if not isinstance(entry, str):
        return False
    token = entry.strip()
    return token in {"*", "*:*"}


def canary_allows_all(canary_principals: Collection[Any]) -> bool:
    """True only when canary entries include explicit ``*`` / ``*:*``."""
    return any(_is_allow_all_entry(entry) for entry in canary_principals)


def principal_in_canary(
    *,
    school_id: str,
    membership_id: str,
    canary_principals: Collection[Any],
) -> bool:
    """True only when the joint (school_id, membership_id) is allowlisted."""
    key = _as_principal_key(school_id, membership_id)
    if key is None:
        return False
    for entry in canary_principals:
        if _is_allow_all_entry(entry):
            continue
        if isinstance(entry, (tuple, list)) and len(entry) == 2:
            candidate = _as_principal_key(str(entry[0]), str(entry[1]))
            if candidate == key:
                return True
            continue
        if isinstance(entry, str) and ":" in entry:
            school, membership = entry.split(":", 1)
            candidate = _as_principal_key(school, membership)
            if candidate == key:
                return True
    return False


def should_use_pi_agent(
    *,
    use_pi_agent: bool,
    school_id: str = "",
    membership_id: str = "",
    canary_principals: Collection[Any] = (),
    pi_agent_allow_all: bool = True,
) -> bool:
    """Decide whether multi-step uses Pi (product default kernel)."""
    if not use_pi_agent:
        return False
    if pi_agent_allow_all or canary_allows_all(canary_principals):
        return True
    if not canary_principals:
        return False
    return principal_in_canary(
        school_id=school_id,
        membership_id=membership_id,
        canary_principals=canary_principals,
    )


def should_use_kimi_agent(
    *,
    use_kimi_agent: bool,
    school_id: str,
    membership_id: str,
    canary_principals: Collection[Any],
    kimi_agent_allow_all: bool = False,
    legacy_agent_loop_emergency: bool = False,
) -> bool:
    """Legacy Kimi Agent gate (rollback only). Emergency flag is a permanent no-op."""
    del legacy_agent_loop_emergency
    if not use_kimi_agent:
        return False
    if kimi_agent_allow_all or canary_allows_all(canary_principals):
        return True
    return principal_in_canary(
        school_id=school_id,
        membership_id=membership_id,
        canary_principals=canary_principals,
    )


async def _fail_closed_no_loop(
    *, emit: Any, reason: str, code: str = "runtime.loop_removed"
) -> RunResult:
    payload = enrich_fail_payload(
        {
            "status": "failed",
            "reason": reason,
            "code": code,
            "runtime": None,
        }
    )
    if emit is not None:
        await emit("run.status", payload)
    return RunResult(status="failed", final_text="", error=reason)


async def run_agent_runtime(
    *,
    use_pi_agent: bool = True,
    pi_agent_canary_principals: Collection[Any] = (),
    pi_agent_allow_all: bool = True,
    use_kimi_agent: bool = False,
    use_legacy_kimi_agent: bool | None = None,
    kimi_agent_canary_principals: Collection[Any] = (),
    kimi_agent_canary_membership_ids: Collection[Any] | None = None,
    kimi_agent_allow_all: bool = False,
    legacy_agent_loop_emergency: bool = False,
    **kwargs: Any,
) -> Any:
    """Dispatch multi-step to Pi (default) or legacy Kimi; never the removed loop.

    Preference order when both enabled: **Pi wins** (product default).
    ``use_legacy_kimi_agent`` is an alias of ``use_kimi_agent``.
    """
    del legacy_agent_loop_emergency

    if use_legacy_kimi_agent is not None:
        use_kimi_agent = bool(use_legacy_kimi_agent)

    principal = kwargs.get("principal")
    school_id = str(getattr(principal, "school_id", "") or "")
    membership_id = str(getattr(principal, "membership_id", "") or "")
    emit = kwargs.get("emit")
    # Hosted pi_runtime / kimi do not take these; true-pi session tree does.
    persist_pi_session = bool(kwargs.pop("persist_pi_session", False))
    conversation_id = kwargs.pop("conversation_id", None)
    # Hosted pi_runtime rejects this kwarg. true_pi needs the ledger run_id
    # so llm-pass remember/has_turn_files use the same key (not a fresh tp-*).
    run_id = kwargs.pop("run_id", None)

    use_pi = should_use_pi_agent(
        use_pi_agent=use_pi_agent,
        school_id=school_id,
        membership_id=membership_id,
        canary_principals=pi_agent_canary_principals,
        pi_agent_allow_all=pi_agent_allow_all,
    )
    if use_pi:
        # Phase-2: optional true-Pi default / canary (rollback: PICO_HOSTED_LOOP=1).
        use_true = False
        try:
            from pico_orchestrator.true_pi.config import (
                should_use_true_pi,
                true_pi_available,
            )

            use_true = should_use_true_pi(
                school_id=school_id,
                membership_id=membership_id,
            )
        except Exception:  # noqa: BLE001
            use_true = False

        if use_true and _PI_IMPL is None:
            from pico_orchestrator.capability_loading import workenv_mode

            # Overlay owns ``pi`` when PICO_WORKENV=pi; host PATH need not have it.
            if not true_pi_available() and workenv_mode() != "pi":
                return await _fail_closed_no_loop(
                    emit=emit,
                    reason=(
                        "true Pi selected (default/canary/bypass) but pi binary "
                        "not available; install pin or set PICO_HOSTED_LOOP=1"
                    ),
                    code="true_pi.binary_missing",
                )
            from pico_orchestrator.true_pi.runtime import run_true_pi_agent

            return await run_true_pi_agent(
                **kwargs,
                persist_pi_session=persist_pi_session,
                conversation_id=conversation_id,
                run_id=run_id,
            )

        if _PI_IMPL is not None:
            result = await _PI_IMPL(**kwargs)
        else:
            from pico_orchestrator.pi_runtime import run_pi_agent

            result = await run_pi_agent(**kwargs)
        # Phase-1 shadow: never blocks / never replaces hosted result.
        _maybe_schedule_true_pi_shadow(hosted_result=result, **kwargs)
        return result

    canary = (
        kimi_agent_canary_principals
        if kimi_agent_canary_principals
        else (kimi_agent_canary_membership_ids or ())
    )
    use_kimi = should_use_kimi_agent(
        use_kimi_agent=use_kimi_agent,
        school_id=school_id,
        membership_id=membership_id,
        canary_principals=canary,
        kimi_agent_allow_all=kimi_agent_allow_all,
    )
    if use_kimi:
        if _KIMI_IMPL is not None:
            return await _KIMI_IMPL(**kwargs)
        from pico_orchestrator.kimi_runtime import run_kimi_agent

        return await run_kimi_agent(**kwargs)

    if use_kimi_agent and not use_kimi:
        reason = "principal not on legacy Kimi Agent canary/allow-all; " + _NO_RUNTIME
        code = "runtime.not_allowlisted"
    elif not use_pi_agent and not use_kimi_agent:
        reason = _NO_RUNTIME
        code = "runtime.pi_required"
    else:
        reason = "Pi gate off / not allowlisted and no legacy Kimi; " + _NO_RUNTIME
        code = "runtime.pi_required"
    return await _fail_closed_no_loop(emit=emit, reason=reason, code=code)
