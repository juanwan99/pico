"""Write-tool observation: facts only. No score. No scene gate."""

from __future__ import annotations

import base64
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "orchestrator"))

from pico_orchestrator.document_generators import build_pptx_document
from pico_orchestrator.gateway import ToolError
from pico_orchestrator.office.inspect import inspect_office_bytes
from pico_orchestrator.skill_policy import instruction_for_snapshot, snapshot_for_skill
from pico_orchestrator.tool_observation import observe_write
from pico_orchestrator.tools_builtin import build_default_gateway, openai_tool_schemas


@dataclass
class P:
    school_id: str
    membership_id: str
    scopes: list[str]


class MemoryArtifactStore:
    def __init__(self) -> None:
        self.rows: list[dict[str, Any]] = []
        self.blobs: dict[str, bytes] = {}

    async def write(
        self,
        principal: P,
        *,
        title: str,
        content: str | bytes,
        kind: str,
    ) -> dict[str, Any]:
        del principal
        raw = content if isinstance(content, bytes) else content.encode("utf-8")
        row = {
            "artifact_id": f"art-{len(self.rows) + 1}",
            "title": title,
            "kind": kind,
            "byte_size": len(raw),
        }
        self.rows.append(row)
        self.blobs[row["artifact_id"]] = raw
        return dict(row)

    async def read(
        self,
        principal: P,
        *,
        artifact_id: str | None = None,
        title: str | None = None,
    ) -> dict[str, Any] | None:
        del principal
        for row in self.rows:
            if artifact_id and row["artifact_id"] == artifact_id:
                out = dict(row)
                out["content_base64"] = base64.b64encode(self.blobs[row["artifact_id"]]).decode(
                    "ascii"
                )
                return out
            if title and row["title"] == title:
                out = dict(row)
                out["content_base64"] = base64.b64encode(self.blobs[row["artifact_id"]]).decode(
                    "ascii"
                )
                return out
        return None


def test_observe_pptx_is_counts_not_a_score() -> None:
    raw = build_pptx_document(
        title="deck.pptx",
        marker="mk",
        body="页一\n要点甲\n\n---\n页二\n要点乙\n要点丙",
    )
    seen = observe_write(kind="pptx", title="deck.pptx", raw=raw)
    assert seen["kind"] == "pptx"
    assert seen["outline"]["slides"] >= 2
    pages = seen["outline"]["pages"]
    assert pages[0]["title"]
    assert pages[0]["preview"]
    assert "pass" not in seen
    assert "score" not in seen
    assert "crowded" not in seen


@pytest.mark.asyncio
async def test_generate_pptx_returns_observation() -> None:
    store = MemoryArtifactStore()
    gw = build_default_gateway(store)
    owner = P(school_id="s", membership_id="m", scopes=["*"])
    out = await gw.invoke(
        owner,
        "generate_pptx_document",
        {
            "title": "汇报.pptx",
            "marker": "mk-obs",
            "body": "封面\n副题\n\n---\n内容\n一条",
        },
    )
    assert out["artifact_id"]
    obs = out["observation"]
    assert obs["kind"] == "pptx"
    assert obs["outline"]["slides"] >= 2
    assert "pages" in obs["outline"]
    assert obs["outline"]["pages"][0].get("preview")


@pytest.mark.asyncio
async def test_edit_pptx_returns_observation() -> None:
    store = MemoryArtifactStore()
    gw = build_default_gateway(store)
    owner = P(school_id="s", membership_id="m", scopes=["*"])
    made = await gw.invoke(
        owner,
        "generate_pptx_document",
        {
            "title": "汇报.pptx",
            "marker": "mk-edit",
            "body": "封面\n副题\n\n---\n内容\n一条",
        },
    )
    out = await gw.invoke(
        owner,
        "edit_pptx_document",
        {
            "artifact_id": made["artifact_id"],
            "slide_index": 1,
            "new_title": "改过的封面",
        },
    )
    assert out["edited"] is True
    obs = out["observation"]
    assert obs["kind"] == "pptx"
    assert obs["outline"]["pages"][0]["title"] == "改过的封面"
    assert "score" not in obs


@pytest.mark.asyncio
async def test_edit_fill_zero_hit_must_not_claim_filled() -> None:
    store = MemoryArtifactStore()
    gw = build_default_gateway(store)
    owner = P(school_id="s", membership_id="m", scopes=["*"])
    made = await gw.invoke(
        owner,
        "generate_docx_document",
        {
            "title": "通知.docx",
            "spec": {
                "kind": "docx",
                "blocks": [
                    {"type": "para", "text": "{{姓名}} 同学，{{学期}} 成绩。"},
                ],
            },
        },
    )
    miss = await gw.invoke(
        owner,
        "edit_docx_document",
        {"artifact_id": made["artifact_id"], "values": {"班级": "三年二班"}},
    )
    assert miss["edited"] is False
    assert miss["filled"] is False
    assert miss["filled_keys"] == []
    assert miss["artifact_id"] == made["artifact_id"]
    assert "未修改" in str(miss.get("message") or "")
    assert "姓名" in miss["leftover"]
    assert "学期" in miss["leftover"]

    hit = await gw.invoke(
        owner,
        "edit_docx_document",
        {
            "artifact_id": made["artifact_id"],
            "values": {"姓名": "张三", "学期": "2026春"},
        },
    )
    assert hit["filled"] is True
    assert hit["filled_keys"] == ["姓名", "学期"]
    assert hit["leftover"] == []


@pytest.mark.asyncio
async def test_edit_xlsx_fill_zero_hit_must_not_claim_filled() -> None:
    store = MemoryArtifactStore()
    gw = build_default_gateway(store)
    owner = P(school_id="s", membership_id="m", scopes=["*"])
    made = await gw.invoke(
        owner,
        "generate_xlsx_document",
        {
            "title": "人数.xlsx",
            "spec": {
                "kind": "xlsx",
                "sheets": [
                    {
                        "name": "汇总",
                        "headers": ["组", "人数"],
                        "rows": [["红", "{{红组}}"]],
                    }
                ],
            },
        },
    )
    miss = await gw.invoke(
        owner,
        "edit_xlsx_document",
        {"artifact_id": made["artifact_id"], "values": {"蓝组": "3"}},
    )
    assert miss["edited"] is False
    assert miss["filled"] is False
    assert miss["filled_keys"] == []
    assert miss["artifact_id"] == made["artifact_id"]
    assert "未修改" in str(miss.get("message") or "")
    assert "红组" in miss["leftover"]
    hit = await gw.invoke(
        owner,
        "edit_xlsx_document",
        {"artifact_id": made["artifact_id"], "values": {"红组": "4"}},
    )
    assert hit["edited"] is True
    assert hit["filled"] is True
    assert hit["filled_keys"] == ["红组"]
    assert hit["leftover"] == []


@pytest.mark.asyncio
async def test_xlsx_values_cell_map_is_rejected_not_edited() -> None:
    store = MemoryArtifactStore()
    gw = build_default_gateway(store)
    owner = P(school_id="s", membership_id="m", scopes=["*"])
    made = await gw.invoke(
        owner,
        "generate_xlsx_document",
        {
            "title": "销量.xlsx",
            "spec": {
                "kind": "xlsx",
                "sheets": [
                    {
                        "name": "Sales",
                        "headers": ["Product", "Quantity", "UnitPrice"],
                        "rows": [["Alpha", 7, 13], ["Beta", 4, 19], ["Gamma", 9, 11]],
                    }
                ],
            },
        },
    )
    with pytest.raises(ToolError) as denied:
        await gw.invoke(
            owner,
            "generate_xlsx_document",
            {
                "artifact_id": made["artifact_id"],
                "sheet": "Sales",
                "values": {
                    "D1": "Revenue",
                    "D2": "=B2*C2",
                    "D3": "=B3*C3",
                    "D4": "=B4*C4",
                    "A6": "Total",
                    "D6": "=SUM(D2:D4)",
                },
            },
        )
    assert denied.value.code == "tool.invalid_arguments"
    assert "不是单元格映射" in denied.value.message
    assert len(store.rows) == 1


@pytest.mark.asyncio
async def test_xlsx_cell_edits_keep_source_and_formulas() -> None:
    store = MemoryArtifactStore()
    gw = build_default_gateway(store)
    owner = P(school_id="s", membership_id="m", scopes=["*"])
    made = await gw.invoke(
        owner,
        "generate_xlsx_document",
        {
            "title": "销量.xlsx",
            "spec": {
                "kind": "xlsx",
                "sheets": [
                    {
                        "name": "Sales",
                        "headers": ["Product", "Quantity", "UnitPrice"],
                        "rows": [["Alpha", 7, 13], ["Beta", 4, 19], ["Gamma", 9, 11]],
                    }
                ],
            },
        },
    )
    current = made["artifact_id"]
    patches = [
        ("D1", "Revenue"),
        ("D2", "=B2*C2"),
        ("D3", "=B3*C3"),
        ("D4", "=B4*C4"),
        ("A6", "Total"),
        ("D6", "=SUM(D2:D4)"),
    ]
    for cell, value in patches:
        out = await gw.invoke(
            owner,
            "generate_xlsx_document",
            {
                "artifact_id": current,
                "sheet": "Sales",
                "cell": cell,
                "value": value,
            },
        )
        assert out["edited"] is True
        current = out["artifact_id"]
    row = await store.read(owner, artifact_id=current, title=None)
    assert row is not None
    raw = store.blobs[current]
    outline = inspect_office_bytes(raw, ".xlsx")
    assert outline["formulas"] >= 4
    preview = (outline.get("units") or [{}])[0].get("preview") or []
    flat = [str(c) for line in preview for c in line]
    assert any("Alpha" in cell for cell in flat)
    assert any("7" in cell for cell in flat)
    assert any("Revenue" in cell or "Total" in cell for cell in flat)
    schemas = {s["function"]["name"]: s["function"]["parameters"] for s in openai_tool_schemas()}
    xlsx_props = schemas["generate_xlsx_document"]["properties"]
    assert "values" in xlsx_props
    assert "A1" in xlsx_props["values"]["description"] or "cell" in xlsx_props["values"]["description"]


@pytest.mark.asyncio
async def test_document_open_does_not_invent_a_file(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_sidecar(method, path, **kwargs):
        del method, path, kwargs
        raise AssertionError("must not open a made-up file")

    monkeypatch.setattr(
        "pico_orchestrator.tools_builtin.sidecar_json", fake_sidecar
    )
    from pico_orchestrator.gateway import ToolError

    gw = build_default_gateway()
    owner = P(school_id="s", membership_id="m", scopes=["*"])
    with pytest.raises(ToolError, match="不会编一份文件"):
        await gw.invoke(owner, "sandbox_document_open", {"kind": "impress"})


def test_deliverable_skill_is_not_a_playbook() -> None:
    text = instruction_for_snapshot(snapshot_for_skill("skill-deliverable"))
    assert "日常 PPT" not in text
    assert "必须分别调用" not in text
    assert "按教学目标" not in text
    assert "observation" in text
    assert "问学校材料" in text
    assert "才 kb_search" in text
    lesson = instruction_for_snapshot(snapshot_for_skill("skill-lesson-outline"))
    assert "教学目标" not in lesson
    assert "必须调用 generate_" not in lesson
    for sid in ("skill-summarize", "skill-translate", "skill-meeting-notes"):
        body = instruction_for_snapshot(snapshot_for_skill(sid))
        assert "必须调用 generate_" not in body
        assert "必须调用专用" not in body
        assert "不要发明一套" in body
