from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "orchestrator"))

from pico_orchestrator.gateway import Principal, ToolError
from pico_orchestrator.tools_builtin import build_default_gateway, openai_tool_schemas


@dataclass
class P:
    school_id: str
    membership_id: str
    scopes: list[str]


class MemoryArtifactStore:
    def __init__(self) -> None:
        self.rows: dict[tuple[str, str], list[dict[str, Any]]] = {}

    def _rows(self, principal: Principal) -> list[dict[str, Any]]:
        return self.rows.setdefault(
            (principal.school_id, principal.membership_id), []
        )

    async def write(
        self,
        principal: Principal,
        *,
        title: str,
        content: str | bytes,
        kind: str,
    ) -> dict[str, Any]:
        if isinstance(content, bytes):
            size = len(content)
            encoding = "base64"
            import base64
            import hashlib

            stored = base64.b64encode(content).decode("ascii")
            digest = hashlib.sha256(content).hexdigest()
            text_content = None
            content_b64 = stored
        else:
            size = len(content.encode("utf-8"))
            encoding = "utf8"
            digest = __import__("hashlib").sha256(content.encode("utf-8")).hexdigest()
            text_content = content
            content_b64 = None
        row = {
            "artifact_id": f"artifact-{sum(map(len, self.rows.values())) + 1}",
            "title": title,
            "content": text_content,
            "content_base64": content_b64,
            "kind": kind,
            "size": size,
            "byte_size": size,
            "content_encoding": encoding,
            "content_sha256": digest,
        }
        self._rows(principal).append(row)
        return {key: value for key, value in row.items() if key not in {"content", "content_base64"}}

    async def read(
        self,
        principal: Principal,
        *,
        artifact_id: str | None,
        title: str | None,
    ) -> dict[str, Any] | None:
        for row in reversed(self._rows(principal)):
            if artifact_id and row["artifact_id"] == artifact_id:
                return row
            if not artifact_id and row["title"] == title:
                return row
        return None

    async def list(
        self,
        principal: Principal,
        *,
        limit: int,
    ) -> list[dict[str, Any]]:
        return [
            {key: value for key, value in row.items() if key != "content"}
            for row in list(reversed(self._rows(principal)))[:limit]
        ]


@pytest.mark.asyncio
async def test_workspace_tools_use_membership_scoped_artifacts() -> None:
    store = MemoryArtifactStore()
    gateway = build_default_gateway(store)
    owner = P("school-a", "member-a", ["ai:run"])
    outsider = P("school-a", "member-b", ["ai:run"])

    created = await gateway.invoke(
        owner,
        "workspace_write_file",
        {"title": "report.md", "content": "# Result", "kind": "file"},
    )
    artifact_id = created["artifact_id"]
    listed = await gateway.invoke(owner, "workspace_list_files", {})
    assert listed["count"] == 1
    assert listed["artifacts"][0]["artifact_id"] == artifact_id
    read = await gateway.invoke(
        owner, "workspace_read_file", {"artifact_id": artifact_id}
    )
    assert read["artifact"]["content"] == "# Result"

    assert (await gateway.invoke(outsider, "workspace_list_files", {}))["count"] == 0
    with pytest.raises(ToolError, match="Artifact not found") as denied:
        await gateway.invoke(
            outsider, "workspace_read_file", {"artifact_id": artifact_id}
        )
    assert denied.value.code == "artifact.not_found"


@pytest.mark.asyncio
async def test_structured_outline_and_safe_calculator() -> None:
    gateway = build_default_gateway()
    principal = P("school-a", "member-a", ["ai:run"])

    outline = await gateway.invoke(
        principal,
        "structured_outline",
        {"text": "# Plan\n## Prepare\n- Verify\n# Deliver"},
    )
    assert outline["item_count"] == 4
    assert outline["outline"][0]["title"] == "Plan"
    assert outline["outline"][0]["children"][0]["title"] == "Prepare"

    calculated = await gateway.invoke(
        principal, "calculator", {"expression": "(12 + 8) * 3 / 2"}
    )
    assert calculated["result"] == 30

    with pytest.raises(ToolError) as blocked:
        await gateway.invoke(
            principal, "calculator", {"expression": "__import__('os').system('id')"}
        )
    assert blocked.value.code == "calculator.invalid_expression"


def test_new_tools_have_strict_openai_schemas() -> None:
    schemas = {
        schema["function"]["name"]: schema["function"]["parameters"]
        for schema in openai_tool_schemas()
    }
    expected = {
        "workspace_write_file",
        "workspace_read_file",
        "workspace_list_files",
        "structured_outline",
        "calculator",
    }
    assert expected <= schemas.keys()
    assert schemas["workspace_write_file"]["required"] == ["title", "content"]
    assert schemas["calculator"]["required"] == ["expression"]


def test_tool_schemas_are_moonshot_safe() -> None:
    """Kimi/Moonshot rejects parameters with type+anyOf/oneOf/allOf combo."""
    for schema in openai_tool_schemas():
        params = schema["function"]["parameters"]
        assert isinstance(params, dict)
        assert params.get("type") == "object"
        for banned in ("anyOf", "oneOf", "allOf"):
            assert banned not in params, (schema["function"]["name"], banned)
        props = params.get("properties") or {}
        assert isinstance(props, dict)

