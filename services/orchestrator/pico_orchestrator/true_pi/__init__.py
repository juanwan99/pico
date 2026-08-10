"""True Pi harness bypass (phase-1 shadow / optional bypass).

Default multi-step path remains hosted ``pi_runtime.run_pi_agent``.
This package must stay thin: RPC client, tool callback, event map, landing gate.
"""

from __future__ import annotations

from pico_orchestrator.true_pi.config import (
    HOSTED_LOOP_ENV,
    TRUE_PI_BYPASS_ENV,
    TRUE_PI_DEFAULT_ENV,
    TRUE_PI_SHADOW_ENV,
    shadow_enabled,
    should_use_true_pi,
    true_pi_available,
    true_pi_default_enabled,
)
from pico_orchestrator.true_pi.runtime import run_true_pi_agent
from pico_orchestrator.true_pi.shadow import maybe_shadow_after_hosted, shadow_diff

__all__ = [
    "HOSTED_LOOP_ENV",
    "TRUE_PI_BYPASS_ENV",
    "TRUE_PI_DEFAULT_ENV",
    "TRUE_PI_SHADOW_ENV",
    "maybe_shadow_after_hosted",
    "run_true_pi_agent",
    "shadow_diff",
    "shadow_enabled",
    "should_use_true_pi",
    "true_pi_available",
    "true_pi_default_enabled",
]
