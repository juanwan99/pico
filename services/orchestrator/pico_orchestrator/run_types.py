"""Shared multi-step run types.

Used by Pi Agent runtime (default), legacy Kimi path, and API wiring.
The self-built ``run_agent_loop`` was removed in KA-4 HARD (#288); do not revive it.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from pico_orchestrator.provider import ProviderConfig, resolve_provider

EventEmitter = Callable[[str, dict[str, Any]], Awaitable[None]]


@dataclass
class RunCaps:
    # Defaults match delivery tier (pico-agent). Short-chat callers pass short caps.
    # See pico_orchestrator.run_caps and PICO_RUN_* / PICO_RUN_SHORT_* env keys.
    max_seconds: int = 900
    max_tokens: int = 32_000
    # Model context window (history+system+tools). Not the output cap.
    max_context: int = 256_000
    max_retries: int = 2
    max_steps: int = 24
    allowed_tools: list[str] | None = None
    skill_instruction: str = ""
    # Edu sidebar (and similar clients) may replace the default Pico workbench
    # system so the model reads the page short-profile instead of the file cabinet.
    system_prompt: str = ""
    # Delivery landing gate (T-AGENT-LANDING-RELIABLE): when >0, Pi will not
    # report runtime success until at least this many write/generate tool
    # successes land — or it fails closed after one landing retry.
    # 0 = short chat / no file required.
    min_artifacts: int = 0
    # Dual-mode (Pico 快速 / Pico 深度): deep lane runs thinking-on and arms the
    # no-progress circuit breaker; fast lane keeps thinking off and no breaker.
    thinking_on: bool = False
    # Lane labels for receipts. ui_model is pico-fast/pico-deep; backend_model
    # is the DeepSeek id actually spawned (flash vs reasoner).
    ui_model: str = ""
    backend_model: str = ""
    # Deep-lane breaker wall threshold (true_pi): bail out with pi.no_progress
    # when the thinking-on lane has no successful tool execution for this many
    # seconds. Injectable for unit tests; production default 180s.
    no_progress_seconds: int = 180


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
