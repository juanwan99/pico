"""Pico orchestrator package.

TARGET/CURRENT: open-source Kimi Agent multi-step runtime + allowlist gateway
+ pin checks (KA-4 HARD: transitional run_agent_loop removed).

Package root re-exports below are kept for compatibility (pins/safety symbols).
"""

from pico_orchestrator.pins import AGENT_PINS
from pico_orchestrator.safety import DANGEROUS_TOOL_PATHS, load_pico_agent_tools

__all__ = [
    "AGENT_PINS",
    "DANGEROUS_TOOL_PATHS",
    "load_pico_agent_tools",
]
