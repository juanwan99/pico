"""T-RESIDENT-SHRINK: CORE shorter; generate_* patches; ceiling stays visible."""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "orchestrator"))

from pico_orchestrator.capability_loading import (
    CORE_VISIBLE_TOOLS,
    EXTENDED_TOOLS,
    ppt_siblings_honest,
    resolve_visible_tools,
)
from pico_orchestrator.office.inspect import inspect_office_bytes
from pico_orchestrator.skill_policy import snapshot_for_skill
from pico_orchestrator.tools_builtin import build_default_gateway
from pico_orchestrator.true_pi.runtime import pico_system_text


@dataclass
class P:
    school_id: str = "school-a"
    membership_id: str = "member-a"
    scopes: list[str] | None = None

    def __post_init__(self) -> None:
        if self.scopes is None:
            self.scopes = ["ai:run"]


class MemoryArtifactStore:
    def __init__(self) -> None:
        self.rows: list[dict[str, Any]] = []

    async def write(
        self,
        principal: P,
        *,
        title: str,
        content: str | bytes,
        kind: str,
    ) -> dict[str, Any]:
        aid = f"art-{len(self.rows) + 1}"
        row = {
            "artifact_id": aid,
            "title": title,
            "content": content,
            "kind": kind,
            "byte_size": len(content) if isinstance(content, (bytes, str)) else 0,
        }
        self.rows.append(row)
        return {k: v for k, v in row.items() if k != "content"}

    async def read(
        self,
        principal: P,
        *,
        artifact_id: str | None,
        title: str | None,
    ) -> dict[str, Any] | None:
        for row in reversed(self.rows):
            if artifact_id and row["artifact_id"] == artifact_id:
                return row
            if not artifact_id and title and row["title"] == title:
                return row
        return None

    async def list(self, principal: P, *, limit: int) -> list[dict[str, Any]]:
        return list(reversed(self.rows))[:limit]


def test_core_is_shorter_and_keeps_office_ceiling() -> None:
    visible = resolve_visible_tools(None)
    assert visible == list(CORE_VISIBLE_TOOLS)
    assert len(visible) == 14
    assert "sandbox_office_lib" in visible
    assert "generate_pptx_document" not in visible
    assert "sandbox_pptx_lib" not in visible
    assert ppt_siblings_honest(visible)
    for name in ("edit_docx_document", "edit_pptx_document", "edit_xlsx_document"):
        assert name not in visible
        assert name not in EXTENDED_TOOLS


def test_no_tool_picker_copy() -> None:
    body = pico_system_text()
    assert "请选工具" not in body
    assert "请选择工具" not in body
    ts = (ROOT / "services" / "true_pi_bridge" / "pico-gateway-tools.ts").read_text(
        encoding="utf-8"
    )
    assert "请选工具" not in ts
    assert "sandbox_office_lib" in body
    assert "generate_pptx_document" not in CORE_VISIBLE_TOOLS


def test_hung_skill_still_honest_on_pptx_siblings() -> None:
    deliver = snapshot_for_skill("skill-deliverable")
    assert deliver is not None
    tools = list(deliver["tools"])
    assert "edit_docx_document" not in tools
    assert ppt_siblings_honest(tools)


@pytest.mark.asyncio
async def test_sandbox_office_lib_patches_existing_paragraph() -> None:
    store = MemoryArtifactStore()
    gw = build_default_gateway(store)
    principal = P()
    created = await gw.invoke(
        principal,
        "sandbox_office_lib",
        {
            "kind": "docx",
            "title": "通知.docx",
            "source": (
                "from docx import Document\n"
                "doc = Document()\n"
                "doc.add_paragraph('第一段足够长的正文内容。')\n"
                "doc.add_paragraph('第二段也要留下。')\n"
                "save_doc(doc)\n"
            ),
        },
    )
    aid = created["artifact_id"]
    patched = await gw.invoke(
        principal,
        "sandbox_office_lib",
        {
            "kind": "docx",
            "title": "通知.docx",
            "artifact_id": aid,
            "source": (
                "from docx import Document\n"
                "old = load_doc()\n"
                "kept = [p.text for p in old.paragraphs if p.text.strip()]\n"
                "doc = Document()\n"
                "doc.add_paragraph('第一段已改，并保留足够长的正文内容。')\n"
                "for line in kept[1:]:\n"
                "    doc.add_paragraph(line)\n"
                "save_doc(doc)\n"
            ),
        },
    )
    assert patched.get("artifact_id")
    row = await store.read(principal, artifact_id=patched["artifact_id"], title=None)
    assert row is not None
    outline = inspect_office_bytes(row["content"], ".docx")
    texts = [str(u.get("text") or "") for u in outline.get("units") or []]
    assert any("第一段已改" in t for t in texts)


@pytest.mark.asyncio
async def test_sandbox_office_lib_patches_existing_cell() -> None:
    store = MemoryArtifactStore()
    gw = build_default_gateway(store)
    principal = P()
    created = await gw.invoke(
        principal,
        "sandbox_office_lib",
        {
            "kind": "xlsx",
            "title": "表.xlsx",
            "source": (
                "from openpyxl import Workbook\n"
                "wb = Workbook()\n"
                "ws = wb.active\n"
                "ws['A1'] = '名'\n"
                "ws['B1'] = '分'\n"
                "ws['A2'] = '张三'\n"
                "ws['B2'] = 90\n"
                "ws['A3'] = '李四'\n"
                "ws['B3'] = 80\n"
                "save_book(wb)\n"
            ),
        },
    )
    aid = created["artifact_id"]
    patched = await gw.invoke(
        principal,
        "sandbox_office_lib",
        {
            "kind": "xlsx",
            "title": "表.xlsx",
            "artifact_id": aid,
            "source": (
                "wb = load_book()\n"
                "ws = wb.active\n"
                "ws['B2'] = 95\n"
                "save_book(wb)\n"
            ),
        },
    )
    assert patched.get("artifact_id")
    row = await store.read(principal, artifact_id=patched["artifact_id"], title=None)
    assert row is not None
    outline = inspect_office_bytes(row["content"], ".xlsx")
    preview = (outline.get("units") or [{}])[0].get("preview") or []
    flat = [str(c) for row in preview for c in row]
    assert any("95" in cell for cell in flat)
