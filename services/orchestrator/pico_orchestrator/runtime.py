"""Runtime selector for the Kimi Agent production-default and canary scopes."""

from __future__ import annotations

from collections.abc import Collection
from typing import Any


def _as_principal_key(school_id: str, membership_id: str) -> tuple[str, str] | None:
    school = (school_id or "").strip()
    membership = (membership_id or "").strip()
    if not school or not membership:
        return None
    return (school, membership)


def principal_in_canary(
    *,
    school_id: str,
    membership_id: str,
    canary_principals: Collection[Any],
) -> bool:
    """True only when the joint (school_id, membership_id) is allowlisted.

    Accepts canary entries as (school, membership) tuples or "school:membership"
    strings. Bare membership strings never match (fail-closed).
    """
    key = _as_principal_key(school_id, membership_id)
    if key is None:
        return False
    for entry in canary_principals:
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


async def run_agent_runtime(
    *,
    use_kimi_agent: bool = False,
    legacy_agent_loop_emergency: bool = False,
    kimi_agent_all_principals: bool | None = None,
    kimi_agent_canary_principals: Collection[Any] = (),
    kimi_agent_canary_membership_ids: Collection[Any] | None = None,
    **kwargs: Any,
) -> Any:
    """Dispatch principals to Kimi according to the runtime scope.

    With the runtime enabled, an empty canary collection means all principals;
    a non-empty collection retains joint-key canary matching. The emergency
    legacy override is explicit and never acts as a failure fallback. The legacy
    ``kimi_agent_canary_membership_ids`` kwarg is accepted only as an alias for
    joint principal collections (same shape); bare membership ids never match.
    """

    canary = (
        kimi_agent_canary_principals
        if kimi_agent_canary_principals
        else (kimi_agent_canary_membership_ids or ())
    )
    principal = kwargs.get("principal")
    school_id = str(getattr(principal, "school_id", "") or "")
    membership_id = str(getattr(principal, "membership_id", "") or "")
    wildcard = any(
        entry in {"*", "*:*"}
        or (isinstance(entry, (tuple, list)) and tuple(entry) == ("*", "*"))
        for entry in canary
    )
    all_principals = not canary if kimi_agent_all_principals is None else kimi_agent_all_principals
    use_kimi_runtime = (
        use_kimi_agent
        and not legacy_agent_loop_emergency
        and (
            all_principals
            or wildcard
            or principal_in_canary(
                school_id=school_id,
                membership_id=membership_id,
                canary_principals=canary,
            )
        )
    )
    if not use_kimi_runtime:
        from pico_orchestrator.runner import run_agent_loop

        return await run_agent_loop(**kwargs)

    from pico_orchestrator.kimi_runtime import run_kimi_agent

    return await run_kimi_agent(**kwargs)
