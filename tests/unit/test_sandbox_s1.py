"""S1 sandbox: isolation, preview inspect, usage emit, no 8080 Chrome."""

from __future__ import annotations

import inspect
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "orchestrator"))
sys.path.insert(0, str(ROOT / "services" / "api"))

os.environ.setdefault("PICO_JWT_SECRET", "test-secret-at-least-32-bytes-long!!")

from pico_orchestrator.gateway import ToolError
from pico_orchestrator.sandbox_s1 import (
    extract_title_h1,
    isolation_dir,
    light_exec_source,
    mint_preview_query,
    try_parse_artifact_preview_url,
    verify_preview_sig,
    workspace_id_for,
)
from pico_orchestrator.tools_builtin import build_default_gateway, openai_tool_schemas


@dataclass
class P:
    school_id: str
    membership_id: str
    scopes: list[str]


class MemoryArtifactStore:
    def __init__(self, *, run_id: str | None = None) -> None:
        self.rows: dict[tuple[str, str], list[dict[str, Any]]] = {}
        self._run_id = run_id
        self._task_id = "task-s1"

    def _rows(self, principal: P) -> list[dict[str, Any]]:
        return self.rows.setdefault((principal.school_id, principal.membership_id), [])

    async def write(
        self,
        principal: P,
        *,
        title: str,
        content: str | bytes,
        kind: str,
    ) -> dict[str, Any]:
        body = content if isinstance(content, str) else content.decode("utf-8")
        row = {
            "artifact_id": f"art-{sum(map(len, self.rows.values())) + 1}",
            "title": title,
            "content": body,
            "kind": kind,
            "run_id": self._run_id,
            "task_id": self._task_id,
            "size": len(body.encode("utf-8")),
        }
        self._rows(principal).append(row)
        return {k: v for k, v in row.items() if k != "content"}

    async def read(
        self,
        principal: P,
        *,
        artifact_id: str | None,
        title: str | None,
    ) -> dict[str, Any] | None:
        for row in reversed(self._rows(principal)):
            if artifact_id and row["artifact_id"] == artifact_id:
                return row
            if not artifact_id and title and row["title"] == title:
                return row
        return None

    async def list(self, principal: P, *, limit: int) -> list[dict[str, Any]]:
        return [
            {k: v for k, v in row.items() if k != "content"}
            for row in list(reversed(self._rows(principal)))[:limit]
        ]


PAGE = """<!DOCTYPE html>
<html><head><title>教案首页</title></head>
<body><h1>第一课</h1><p>hello</p></body></html>
"""


@pytest.mark.asyncio
async def test_inspect_same_run_html_returns_title_h1() -> None:
    store = MemoryArtifactStore(run_id="run-s1")
    gw = build_default_gateway(store)
    owner = P("school-a", "member-a", ["ai:run"])
    created = await gw.invoke(
        owner,
        "generate_html_document",
        {"title": "lesson.html", "marker": "mk-s1", "body": PAGE},
    )
    assert created["preview_path"].startswith("/v1/artifacts/")
    assert "preview=1" in created["preview_url"]
    assert "sig=" in created["preview_url"]
    assert created["workspace_id"].startswith("ws_")
    assert "school-a" not in created["workspace_id"]

    seen = await gw.invoke(
        owner,
        "sandbox_preview_inspect",
        {"artifact_id": created["artifact_id"]},
    )
    assert seen["seen"] is True
    assert seen["title"] == "教案首页"
    assert seen["h1"] == "第一课"

    via_url = await gw.invoke(
        owner,
        "sandbox_preview_inspect",
        {"preview_url": created["preview_url"]},
    )
    assert via_url["title"] == "教案首页"
    assert via_url["h1"] == "第一课"


@pytest.mark.asyncio
async def test_inspect_denies_loopback_health() -> None:
    gw = build_default_gateway(MemoryArtifactStore(run_id="run-s1"))
    owner = P("school-a", "member-a", ["ai:run"])
    with pytest.raises(ToolError) as denied:
        await gw.invoke(
            owner,
            "sandbox_preview_inspect",
            {"preview_url": "http://127.0.0.1:18765/health"},
        )
    assert denied.value.code == "web.denied"


@pytest.mark.asyncio
async def test_inspect_denies_pico_admin_host() -> None:
    gw = build_default_gateway(MemoryArtifactStore())
    owner = P("school-a", "member-a", ["ai:run"])
    with pytest.raises(ToolError) as denied:
        await gw.invoke(
            owner,
            "sandbox_preview_inspect",
            {"preview_url": "https://pico.aivia.asia/login"},
        )
    assert denied.value.code == "web.denied"


@pytest.mark.asyncio
async def test_inspect_denies_other_account_artifact() -> None:
    store = MemoryArtifactStore(run_id="run-s1")
    gw = build_default_gateway(store)
    owner = P("school-a", "member-a", ["ai:run"])
    outsider = P("school-a", "member-b", ["ai:run"])
    created = await gw.invoke(
        owner,
        "generate_html_document",
        {"title": "a.html", "marker": "mk", "body": PAGE},
    )
    with pytest.raises(ToolError) as denied:
        await gw.invoke(
            outsider,
            "sandbox_preview_inspect",
            {"artifact_id": created["artifact_id"]},
        )
    assert denied.value.code == "artifact.not_found"
    with pytest.raises(ToolError) as denied_url:
        await gw.invoke(
            outsider,
            "sandbox_preview_inspect",
            {"preview_url": created["preview_url"]},
        )
    assert denied_url.value.code in {
        "sandbox.preview_denied",
        "sandbox.preview_expired",
        "artifact.not_found",
        "web.denied",
    }


@pytest.mark.asyncio
async def test_inspect_denies_unsigned_loopback_artifact_path() -> None:
    gw = build_default_gateway(MemoryArtifactStore())
    owner = P("school-a", "member-a", ["ai:run"])
    with pytest.raises(ToolError) as denied:
        await gw.invoke(
            owner,
            "sandbox_preview_inspect",
            {
                "preview_url": "http://127.0.0.1:18765/v1/artifacts/art-1/content",
            },
        )
    assert denied.value.code == "web.denied"


@pytest.mark.asyncio
async def test_sandbox_usage_emit_kind_and_no_money() -> None:
    captured: list[dict[str, Any]] = []

    async def fake_record(**kwargs: Any) -> None:
        captured.append(kwargs)

    store = MemoryArtifactStore(run_id="run-s1")
    gw = build_default_gateway(store)
    owner = P("school-a", "member-a", ["ai:run"])
    with patch("app.usage_ledger.record_usage_event", fake_record):
        created = await gw.invoke(
            owner,
            "generate_html_document",
            {"title": "u.html", "marker": "mk", "body": PAGE},
        )
        await gw.invoke(
            owner,
            "sandbox_preview_inspect",
            {"artifact_id": created["artifact_id"]},
        )
    sandbox_rows = [row for row in captured if row.get("kind") == "sandbox"]
    assert sandbox_rows
    for row in sandbox_rows:
        assert row["kind"] == "sandbox"
        assert row.get("source") == "sandbox"
        assert row.get("tokens_unknown") is True
        extra = row.get("extra") or {}
        assert extra.get("billing") is not True
        joined = " ".join(extra.keys()).lower()
        for banned in ("price", "currency", "cost", "charge", "billing", "amount"):
            assert banned not in joined
        assert "duration_ms" in extra
        assert extra.get("artifact_id") or extra.get("workspace_id")


@pytest.mark.asyncio
async def test_workspace_read_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    import pico_orchestrator.sandbox_s1 as s1

    monkeypatch.setattr(s1, "IO_TIMEOUT_S", 0.05)

    class SlowStore(MemoryArtifactStore):
        async def read(self, principal, *, artifact_id, title):
            import asyncio

            await asyncio.sleep(1)

    gw = build_default_gateway(SlowStore())
    owner = P("school-a", "member-a", ["ai:run"])
    with pytest.raises(ToolError) as timed:
        await gw.invoke(owner, "workspace_read_file", {"artifact_id": "missing"})
    assert timed.value.code == "workspace.timeout"


def test_sandbox_module_does_not_use_8080_or_chrome() -> None:
    import pico_orchestrator.sandbox_s1 as s1

    src = inspect.getsource(s1)
    assert "8080" not in src
    assert "18088" not in src
    assert "playwright" not in src.lower()
    assert "puppeteer" not in src.lower()
    assert "chromium" not in src.lower()
    assert "webdriver" not in src.lower()


def test_isolation_dirs_do_not_overlap_accounts(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PICO_SANDBOX_ROOT", str(tmp_path))
    a = isolation_dir("school-a", "member-a", "run-1")
    b = isolation_dir("school-a", "member-b", "run-1")
    c = isolation_dir("school-b", "member-a", "run-1")
    d = isolation_dir("school-a", "member-a", "run-2")
    assert a != b != c
    assert a != d
    assert workspace_id_for("school-a", "member-a", "run-1") != workspace_id_for(
        "school-a", "member-b", "run-1"
    )


def test_extract_title_h1_and_preview_token_roundtrip() -> None:
    title, h1 = extract_title_h1(PAGE)
    assert title == "教案首页"
    assert h1 == "第一课"
    path, exp = mint_preview_query(
        artifact_id="art-9",
        school_id="school-a",
        membership_id="member-a",
        run_id="run-s1",
    )
    parsed = try_parse_artifact_preview_url(path)
    assert parsed is not None
    assert parsed["artifact_id"] == "art-9"
    assert verify_preview_sig(
        artifact_id="art-9",
        school_id="school-a",
        membership_id="member-a",
        run_id="run-s1",
        exp=exp,
        sig=parsed["sig"],
    ) is None
    assert (
        verify_preview_sig(
            artifact_id="art-9",
            school_id="school-a",
            membership_id="member-b",
            run_id="run-s1",
            exp=exp,
            sig=parsed["sig"],
        )
        == "sandbox.preview_denied"
    )


def test_light_exec_parses_but_denies_host_modules() -> None:
    out = light_exec_source("x = 1 + 2\n")
    assert out["parsed"] is True
    assert out["executed"] is False
    with pytest.raises(ToolError) as denied:
        light_exec_source("import os\nos.system('id')\n")
    assert denied.value.code == "sandbox.exec_denied"


@pytest.mark.asyncio
async def test_sandbox_exec_html_and_forbidden_python() -> None:
    gw = build_default_gateway(MemoryArtifactStore(run_id="run-s1"))
    owner = P("school-a", "member-a", ["ai:run"])
    parsed = await gw.invoke(
        owner, "sandbox_workspace_exec", {"html": PAGE, "title": "v2.html"}
    )
    assert parsed["title"] == "教案首页"
    assert parsed["h1"] == "第一课"
    assert parsed["executed"] is False
    with pytest.raises(ToolError) as denied:
        await gw.invoke(
            owner,
            "sandbox_workspace_exec",
            {"source": "import subprocess\n"},
        )
    assert denied.value.code == "sandbox.exec_denied"


def test_tool_schemas_include_inspect() -> None:
    names = {s["function"]["name"] for s in openai_tool_schemas()}
    assert "sandbox_preview_inspect" in names
    assert "sandbox_workspace_exec" in names
    assert "web_search" in names
