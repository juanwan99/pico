"""Runtime selector: Kimi Agent default when gate is on; no silent dual-run."""

from __future__ import annotations

from collections.abc import Collection
from typing import Any


def _as_principal_key(school_id: str, membership_id: str) -> tuple[str, str] | None:
    school = (school_id or "").strip()
    membership = (membership_id or "").strip()
    if not school or not membership:
        return None
    return (school, membership)


def _is_allow_all_entry(entry: Any) -> bool:
    """True for explicit all-principals canary tokens."""
    if not isinstance(entry, str):
        return False
    token = entry.strip()
    return token in {"*", "*:*"}


def canary_allows_all(canary_principals: Collection[Any]) -> bool:
    """Empty canary or explicit ``*`` / ``*:*`` means every principal is eligible."""
    if not canary_principals:
        return True
    return any(_is_allow_all_entry(entry) for entry in canary_principals)


def principal_in_canary(
    *,
    school_id: str,
    membership_id: str,
    canary_principals: Collection[Any],
) -> bool:
    """True only when the joint (school_id, membership_id) is allowlisted.

    Accepts canary entries as (school, membership) tuples or "school:membership"
    strings. Bare membership strings never match (fail-closed).
    Explicit ``*`` / ``*:*`` are handled by :func:`canary_allows_all`, not here.
    """
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


def should_use_kimi_agent(
    *,
    use_kimi_agent: bool,
    school_id: str,
    membership_id: str,
    canary_principals: Collection[Any],
    legacy_agent_loop_emergency: bool = False,
) -> bool:
    """Decide whether the multi-step agent path uses Kimi Agent.

    Production default (KA-3): ``use_kimi_agent=True`` and empty canary → all
    principals. Non-empty canary restricts to joint keys. Emergency forces the
    transitional ``run_agent_loop`` path. There is no silent dual-run/fallback.
    """
    if legacy_agent_loop_emergency:
        return False
    if not use_kimi_agent:
        return False
    if canary_allows_all(canary_principals):
        return True
    return principal_in_canary(
        school_id=school_id,
        membership_id=membership_id,
        canary_principals=canary_principals,
    )


async def run_agent_runtime(
    *,
    use_kimi_agent: bool = False,
    kimi_agent_canary_principals: Collection[Any] = (),
    kimi_agent_canary_membership_ids: Collection[Any] | None = None,
    legacy_agent_loop_emergency: bool = False,
    **kwargs: Any,
) -> Any:
    """Dispatch to Kimi Agent when the gate allows; otherwise transitional loop.

    When ``use_kimi_agent`` is true and the canary collection is empty (or
    contains ``*`` / ``*:*``), every principal uses Kimi Agent — production
    default after KA-3. A non-empty joint-key list keeps restricted canary
    mode. ``legacy_agent_loop_emergency`` forces ``run_agent_loop`` (default
    off). Failures do not silently fall back between runtimes.
    """

    canary = (
        kimi_agent_canary_principals
        if kimi_agent_canary_principals
        else (kimi_agent_canary_membership_ids or ())
    )
    principal = kwargs.get("principal")
    school_id = str(getattr(principal, "school_id", "") or "")
    membership_id = str(getattr(principal, "membership_id", "") or "")
    use_kimi = should_use_kimi_agent(
        use_kimi_agent=use_kimi_agent,
        school_id=school_id,
        membership_id=membership_id,
        canary_principals=canary,
        legacy_agent_loop_emergency=legacy_agent_loop_emergency,
    )
    if not use_kimi:
        from pico_orchestrator.runner import run_agent_loop

        return await run_agent_loop(**kwargs)

    from pico_orchestrator.kimi_runtime import run_kimi_agent

    return await run_kimi_agent(**kwargs)
