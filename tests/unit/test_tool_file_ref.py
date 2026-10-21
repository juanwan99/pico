"""pico#1322: a file id put in the wrong argument works the first time.

Ruler R08 740c7f38: workspace_read_file({"path": <artifact id>}) seven times,
same "artifact_id or title is required". nm-3 R08 f1d1948f:
read_office_skill({"id": <artifact id>}) four times, same "id must be docx,
xlsx, or pptx". Both models got out on their own only later.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "orchestrator"))

from pico_orchestrator.gateway import ToolError
from pico_orchestrator.tools_builtin import build_default_gateway

XLSX_ID = "94410b95-3381-41f2-9792-03bb26a30ece"
DOC_ID = "8245e2f7-91db-48df-ada4-2bb56d24a20b"


@dataclass
class P:
    school_id: str = "school-a"
    membership_id: str = "member-a"
    scopes: tuple[str, ...] = ("ai:run",)


class Store:
    def __init__(self) -> None:
        self.rows = [
            {"artifact_id": XLSX_ID, "title": "r08_scores.xlsx", "kind": "edu_office", "content": "姓名,语文"},
            {"artifact_id": DOC_ID, "title": "家长信.md", "kind": "file", "content": "# 家长信"},
        ]

    async def read(self, principal: Any, *, artifact_id: str | None, title: str | None) -> dict[str, Any] | None:
        for row in self.rows:
            if (artifact_id and row["artifact_id"] == artifact_id) or (not artifact_id and row["title"] == title):
                return dict(row)
        return None

    async def list(self, principal: Any, *, limit: int) -> list[dict[str, Any]]:
        return [{k: v for k, v in r.items() if k != "content"} for r in self.rows[:limit]]

    async def write(self, principal: Any, **kwargs: Any) -> dict[str, Any]:
        raise AssertionError("not written here")


@pytest.fixture
def gw():
    return build_default_gateway(Store())


@pytest.mark.asyncio
async def test_read_file_takes_an_artifact_id_given_as_path(gw) -> None:
    got = await gw.invoke(P(), "workspace_read_file", {"path": DOC_ID})
    assert got["artifact"]["title"] == "家长信.md"


@pytest.mark.asyncio
async def test_read_file_takes_a_file_path_by_its_name(gw) -> None:
    got = await gw.invoke(P(), "workspace_read_file", {"path": "/workspace/attachments/家长信.md"})
    assert got["artifact"]["artifact_id"] == DOC_ID


@pytest.mark.asyncio
async def test_read_file_errors_name_the_files_it_could_read(gw) -> None:
    with pytest.raises(ToolError) as empty:
        await gw.invoke(P(), "workspace_read_file", {})
    with pytest.raises(ToolError) as missing:
        await gw.invoke(P(), "workspace_read_file", {"artifact_id": "00000000-0000-0000-0000-000000000000"})
    for err in (empty.value, missing.value):
        assert XLSX_ID in str(err) and "r08_scores.xlsx" in str(err)
    assert missing.value.code == "artifact.not_found"


@pytest.mark.asyncio
async def test_office_skill_takes_the_file_id_and_reads_its_kind(gw) -> None:
    got = await gw.invoke(P(), "read_office_skill", {"id": XLSX_ID})
    assert got["id"] == "xlsx" and got["body"]


@pytest.mark.asyncio
async def test_office_skill_takes_a_file_name(gw) -> None:
    assert (await gw.invoke(P(), "read_office_skill", {"id": "r08_scores.xlsx"}))["id"] == "xlsx"


@pytest.mark.asyncio
async def test_office_skill_says_what_to_pass_when_it_cannot_tell(gw) -> None:
    with pytest.raises(ToolError) as err:
        await gw.invoke(P(), "read_office_skill", {"id": DOC_ID})
    assert err.value.code == "office_skill.unknown"
    assert "docx, xlsx, or pptx" in str(err.value) and "workspace_read_file" in str(err.value)
