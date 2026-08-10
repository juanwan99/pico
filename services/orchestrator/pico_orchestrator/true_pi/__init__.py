"""True Pi harness bypass (phase-1 shadow / optional bypass).

Default multi-step path remains hosted ``pi_runtime.run_pi_agent``.
This package must stay thin: RPC client, tool callback, event map, landing gate.
"""

from __future__ import annotations

from pico_orchestrator.true_pi.config import (
    TRUE_PI_BYPASS_ENV,
    TRUE_PI_SHADOW_ENV,
    shadow_enabled,
    true_pi_available,
)
from pico_orchestrator.true_pi.runtime import run_true_pi_agent
from pico_orchestrator.true_pi.shadow import maybe_shadow_after_hosted, shadow_diff

__all__ = [
    "TRUE_PI_BYPASS_ENV",
    "TRUE_PI_SHADOW_ENV",
    "maybe_shadow_after_hosted",
    "run_true_pi_agent",
    "shadow_diff",
    "shadow_enabled",
    "true_pi_available",
]
