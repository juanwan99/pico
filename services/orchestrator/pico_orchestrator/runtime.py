"""Runtime selector with the Kimi Agent gate and canary scope defaulting off."""

from __future__ import annotations

from collections.abc import Collection
from typing import Any


async def run_agent_runtime(
    *,
    use_kimi_agent: bool = False,
    kimi_agent_canary_membership_ids: Collection[str] = (),
    **kwargs: Any,
) -> Any:
    """Dispatch allowlisted principals to Kimi without changing the default path."""

    principal = kwargs.get("principal")
    membership_id = str(getattr(principal, "membership_id", ""))
    use_kimi_canary = (
        use_kimi_agent
        and bool(membership_id)
        and membership_id in kimi_agent_canary_membership_ids
    )
    if not use_kimi_canary:
        from pico_orchestrator.runner import run_agent_loop

        return await run_agent_loop(**kwargs)

    from pico_orchestrator.kimi_runtime import run_kimi_agent

    return await run_kimi_agent(**kwargs)
