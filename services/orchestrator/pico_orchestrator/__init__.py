"""Pico orchestrator package.

CURRENT: transitional OpenAI-compatible tool loop + allowlist gateway + pin checks.
TARGET:  open-source Kimi Agent runtime (docs/TRUTH-FREEZE.md). Do not describe
this package as "Kimi Agent integrated" until the runtime path is real.

Package root re-exports below are kept for compatibility (pins/safety symbols).
"""

from pico_orchestrator.pins import AGENT_PINS
from pico_orchestrator.safety import DANGEROUS_TOOL_PATHS, load_pico_agent_tools

__all__ = [
    "AGENT_PINS",
    "DANGEROUS_TOOL_PATHS",
    "load_pico_agent_tools",
]
