"""T-OFFICE-UNREGISTER: generate_*/inspect/edit/render/sandbox_pptx leave the model surface."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "orchestrator"))

from pico_orchestrator.capability_loading import (
    CORE_VISIBLE_TOOLS,
    EXTENDED_TOOLS,
    resolve_visible_tools,
)
from pico_orchestrator.tools_builtin import build_default_gateway, openai_tool_schemas
from pico_orchestrator.true_pi.config import ALLOWED_GATEWAY_TOOLS, UNREGISTERED_OFFICE_TOOLS


def test_unregistered_office_tools_absent_from_model_surface() -> None:
    assert len(ALLOWED_GATEWAY_TOOLS) == 19
    assert len(EXTENDED_TOOLS) == 5
    assert len(CORE_VISIBLE_TOOLS) == 14
    assert set(CORE_VISIBLE_TOOLS) | set(EXTENDED_TOOLS) == set(ALLOWED_GATEWAY_TOOLS)
    for name in UNREGISTERED_OFFICE_TOOLS:
        assert name not in ALLOWED_GATEWAY_TOOLS
        assert name not in CORE_VISIBLE_TOOLS
        assert name not in EXTENDED_TOOLS
        assert name not in resolve_visible_tools(None)

    gw = build_default_gateway()
    schema_names = {s["function"]["name"] for s in openai_tool_schemas(gw)}
    for name in UNREGISTERED_OFFICE_TOOLS:
        assert name not in gw.tools
        assert name not in schema_names

    ts = (ROOT / "services" / "true_pi_bridge" / "pico-gateway-tools.ts").read_text(
        encoding="utf-8"
    )
    for name in UNREGISTERED_OFFICE_TOOLS:
        assert f'"{name}"' not in ts

    assert "sandbox_office_lib" in ALLOWED_GATEWAY_TOOLS
    assert "sandbox_office_lib" in CORE_VISIBLE_TOOLS
    assert "sandbox_office_lib" in gw.tools
    assert "read_office_skill" in CORE_VISIBLE_TOOLS
