"""Pico orchestrator package.

TARGET/CURRENT: Pi Agent multi-step runtime (default) + allowlist gateway.
Model: DeepSeek HTTPS (primary). Legacy Kimi Agent path optional rollback only.
Transitional run_agent_loop remains removed (KA-4 HARD).
"""

from pico_orchestrator.pins import AGENT_PINS
from pico_orchestrator.safety import DANGEROUS_TOOL_PATHS, load_pico_agent_tools

__all__ = [
    "AGENT_PINS",
    "DANGEROUS_TOOL_PATHS",
    "load_pico_agent_tools",
]


def _apply_unmaim_doc_body_cap() -> None:
    """#829: raise generate_* body cap to DOC_BODY_MAX (tools_builtin keeps 50k)."""
    from pico_orchestrator import tools_builtin as tb
    from pico_orchestrator.document_generators import DOC_BODY_MAX

    tb._MAX_DOC_BODY = DOC_BODY_MAX


_apply_unmaim_doc_body_cap()
