from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "orchestrator"))

from pico_orchestrator.tools_builtin import build_default_gateway, openai_tool_schemas


@dataclass
class P:
    school_id: str
    membership_id: str
    scopes: list[str]


@pytest.mark.asyncio
async def test_schemas_and_propose():
    gw = build_default_gateway()
    schemas = openai_tool_schemas(gw)
    names = {s["function"]["name"] for s in schemas}
    assert "fake_edu_list_classes" in names
    assert "pico_propose_change" in names
    p = P("school-a", "m", ["ai:run"])
    out = await gw.invoke(
        p,
        "pico_propose_change",
        {"title": "t", "summary": "s", "payload": {"a": 1}},
    )
    assert out["proposal"]["status"] == "proposed"
