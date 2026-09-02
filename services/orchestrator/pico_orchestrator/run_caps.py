"""Tiered run budgets: short / delivery / durable.

Package A: delivery (≈900s) for courseware multi-step.
Package B: durable jobs need detach-from-browser + optional longer wall
(default 3600s). Never treat a multi-hour global timeout alone as “durable.”
"""

from __future__ import annotations

from dataclasses import replace
from typing import Literal

from pico_orchestrator.run_types import RunCaps

RunTier = Literal["short", "delivery", "durable"]

# Code defaults (env overrides via Settings; keep in sync with .env.example).
DELIVERY_MAX_SECONDS = 900
DELIVERY_MAX_TOKENS = 32_000
DELIVERY_MAX_CONTEXT = 256_000
DELIVERY_MAX_STEPS = 24
DELIVERY_MAX_RETRIES = 2

SHORT_MAX_SECONDS = 120
SHORT_MAX_TOKENS = 32_000
SHORT_MAX_CONTEXT = 256_000
SHORT_MAX_STEPS = 24
SHORT_MAX_RETRIES = 2

DURABLE_MAX_SECONDS = 3600
DURABLE_MAX_TOKENS = 64_000
DURABLE_MAX_CONTEXT = 256_000
DURABLE_MAX_STEPS = 48
DURABLE_MAX_RETRIES = 2


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
            max_context=SHORT_MAX_CONTEXT,
            max_steps=SHORT_MAX_STEPS,
            max_retries=SHORT_MAX_RETRIES,
        )
    elif tier == "durable":
        base = RunCaps(
            max_seconds=DURABLE_MAX_SECONDS,
            max_tokens=DURABLE_MAX_TOKENS,
            max_context=DURABLE_MAX_CONTEXT,
            max_steps=DURABLE_MAX_STEPS,
            max_retries=DURABLE_MAX_RETRIES,
        )
    else:
        base = RunCaps(
            max_seconds=DELIVERY_MAX_SECONDS,
            max_tokens=DELIVERY_MAX_TOKENS,
            max_context=DELIVERY_MAX_CONTEXT,
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
    durable_seconds: int = DURABLE_MAX_SECONDS,
    detach_on_disconnect: bool = True,
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
            "max_context": SHORT_MAX_CONTEXT,
        },
        "fast": {
            "max_context": SHORT_MAX_CONTEXT,
            "max_tokens": SHORT_MAX_TOKENS,
        },
        "deep": {
            "max_context": DELIVERY_MAX_CONTEXT,
            "max_tokens": DELIVERY_MAX_TOKENS,
        },
        "durable": {
            "max_seconds": durable_seconds,
            "detach_on_disconnect": detach_on_disconnect,
        },
    }
