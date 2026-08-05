"""Tiered run budgets: short chat vs delivery (pico-agent / multi-step).

Package A (P-COMPLEX-DONE): delivery defaults are long enough for HTML courseware
(≈15 min), while direct-model short chat keeps a tighter wall clock so day-to-day
turns stay snappy. Never use a single global multi-hour cap as a substitute for
durable jobs (package B).
"""

from __future__ import annotations

from dataclasses import replace
from typing import Literal

from pico_orchestrator.run_types import RunCaps

RunTier = Literal["short", "delivery"]

# Code defaults (env overrides via Settings; keep in sync with .env.example).
DELIVERY_MAX_SECONDS = 900
DELIVERY_MAX_TOKENS = 32_000
DELIVERY_MAX_STEPS = 24
DELIVERY_MAX_RETRIES = 2

SHORT_MAX_SECONDS = 120
SHORT_MAX_TOKENS = 8_000
SHORT_MAX_STEPS = 8
SHORT_MAX_RETRIES = 2


def caps_for_tier(
    tier: RunTier,
    *,
    max_seconds: int | None = None,
    max_tokens: int | None = None,
    max_steps: int | None = None,
    max_retries: int | None = None,
    allowed_tools: list[str] | None = None,
    skill_instruction: str = "",
) -> RunCaps:
    """Build RunCaps for the requested tier.

    Explicit kwargs override tier defaults (used when Settings supplies env values).
    """
    if tier == "short":
        base = RunCaps(
            max_seconds=SHORT_MAX_SECONDS,
            max_tokens=SHORT_MAX_TOKENS,
            max_steps=SHORT_MAX_STEPS,
            max_retries=SHORT_MAX_RETRIES,
        )
    else:
        base = RunCaps(
            max_seconds=DELIVERY_MAX_SECONDS,
            max_tokens=DELIVERY_MAX_TOKENS,
            max_steps=DELIVERY_MAX_STEPS,
            max_retries=DELIVERY_MAX_RETRIES,
        )
    return replace(
        base,
        max_seconds=max_seconds if max_seconds is not None else base.max_seconds,
        max_tokens=max_tokens if max_tokens is not None else base.max_tokens,
        max_steps=max_steps if max_steps is not None else base.max_steps,
        max_retries=max_retries if max_retries is not None else base.max_retries,
        allowed_tools=allowed_tools,
        skill_instruction=skill_instruction,
    )


def spend_caps_public(
    *,
    delivery_seconds: int,
    delivery_tokens: int,
    delivery_steps: int,
    delivery_retries: int,
    short_seconds: int,
    short_tokens: int,
) -> dict:
    """Non-sensitive cap snapshot for /health and /v1/meta/freeze."""
    return {
        "max_seconds": delivery_seconds,
        "max_tokens": delivery_tokens,
        "max_steps": delivery_steps,
        "max_retries": delivery_retries,
        "delivery": {
            "max_seconds": delivery_seconds,
            "max_tokens": delivery_tokens,
            "max_steps": delivery_steps,
            "max_retries": delivery_retries,
        },
        "short": {
            "max_seconds": short_seconds,
            "max_tokens": short_tokens,
        },
    }
