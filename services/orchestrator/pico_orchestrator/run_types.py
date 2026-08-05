"""Shared multi-step run types (no transitional loop implementation).

Used by Kimi Agent runtime and API wiring. The self-built ``run_agent_loop``
was removed in KA-4 HARD (#288); rollback is redeploy of a prior tip.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from pico_orchestrator.provider import ProviderConfig, resolve_provider

EventEmitter = Callable[[str, dict[str, Any]], Awaitable[None]]


@dataclass
class RunCaps:
    max_seconds: int = 120
    max_tokens: int = 8000
    max_retries: int = 2
    max_steps: int = 8
    allowed_tools: list[str] | None = None
    skill_instruction: str = ""


@dataclass
class RunResult:
    status: str  # succeeded|failed|cancelled
    final_text: str
    error: str | None = None
    token_usage: dict[str, int] | None = None
    artifact_markdown: str | None = None
    change_proposal: dict[str, Any] | None = None


class CancelledError(Exception):
    pass


def provider_label(cfg: ProviderConfig | None = None) -> str:
    c = cfg or resolve_provider()
    if not c:
        return ""
    return f"{c.name}:{c.model}"
