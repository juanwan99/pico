"""Runtime selector with the Kimi Agent path defaulting strictly off."""

from __future__ import annotations

from typing import Any


async def run_agent_runtime(*, use_kimi_agent: bool = False, **kwargs: Any) -> Any:
    """Dispatch to the selected runtime without changing the default path."""

    if not use_kimi_agent:
        from pico_orchestrator.runner import run_agent_loop

        return await run_agent_loop(**kwargs)

    from pico_orchestrator.kimi_runtime import run_kimi_agent

    return await run_kimi_agent(**kwargs)
