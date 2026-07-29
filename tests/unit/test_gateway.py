from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "orchestrator"))

from pico_orchestrator.gateway import ToolError
from pico_orchestrator.tools_builtin import build_default_gateway


@dataclass
class P:
    school_id: str
    membership_id: str
    scopes: list[str]


@pytest.mark.asyncio
async def test_allowlist_and_cross_school() -> None:
    gw = build_default_gateway()
    assert any(t["name"] == "fake_edu.list_classes" for t in gw.list_tools())
    assert any(t["name"] == "pico.echo" for t in gw.list_tools())

    a = P(school_id="school-a", membership_id="m1", scopes=["ai:run"])
    out = await gw.invoke(a, "fake_edu.list_classes", {})
    assert out["school_id"] == "school-a"
    assert len(out["classes"]) >= 1

    with pytest.raises(ToolError) as ei:
        await gw.invoke(a, "fake_edu.list_classes", {"school_id": "school-b"})
    assert ei.value.code == "tenant.cross_school"

    with pytest.raises(ToolError) as ei2:
        await gw.invoke(a, "evil.shell", {})
    assert ei2.value.code == "tool.not_allowlisted"
