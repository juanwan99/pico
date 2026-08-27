"""generate_diagram: mermaid → ledger PNG. No self-built layout engine."""

from __future__ import annotations

import base64
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services"))
sys.path.insert(0, str(ROOT / "services" / "orchestrator"))

from pico_orchestrator.capability_loading import CORE_VISIBLE_TOOLS, resolve_visible_tools
from pico_orchestrator.diagram_generate import render_diagram_bytes
from pico_orchestrator.gateway import ToolError
from pico_orchestrator.tools_builtin import build_default_gateway, openai_tool_schemas
from pico_orchestrator.true_pi.config import ALLOWED_GATEWAY_TOOLS
from pico_orchestrator.user_errors import user_message_for_error
from pico_orchestrator.workbench_progress import (
    workbench_tool_result_line,
    workbench_tool_step_line,
)
from sandbox_worker.diagram import (
    normalize_kind,
    normalize_source,
    render_diagram,
    strip_diagram_fences,
)

ONE_PNG = (
    b"\x89PNG\r\n\x1a\n"
    b"\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde"
    b"\x00\x00\x00\x0cIDATx\x9cc``\x00\x00\x00\x04\x00\x01\xa3\x0a\x0d\xe4"
    b"\x00\x00\x00\x00IEND\xaeB`\x82"
)


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

    async def write(self, principal: P, *, title: str, content: str | bytes, kind: str) -> dict[str, Any]:
        row = {
            "artifact_id": f"art-{len(self.rows) + 1}",
            "title": title,
            "kind": kind,
            "byte_size": len(content) if isinstance(content, bytes) else len(content.encode("utf-8")),
        }
        self.rows.append({**row, "content": content})
        return dict(row)

    async def read(self, principal: P, *, artifact_id: str | None, title: str | None) -> dict[str, Any] | None:
        return None

    async def list(self, principal: P, **_kwargs: Any) -> list[dict[str, Any]]:
        return []


def test_strip_mermaid_fences() -> None:
    raw = "```mermaid\nflowchart TD\nA-->B\n```"
    assert strip_diagram_fences(raw) == "flowchart TD\nA-->B"
    assert normalize_source(raw) == "flowchart TD\nA-->B"


def test_empty_and_huge_source_fail_closed() -> None:
    with pytest.raises(ToolError) as empty:
        normalize_source("   \n```\n```\n")
    assert empty.value.code == "tool.invalid_arguments"
    with pytest.raises(ToolError) as huge:
        normalize_source("A" * 40_000)
    assert huge.value.code == "tool.invalid_arguments"


def test_d2_and_unknown_kind_fail_honestly() -> None:
    with pytest.raises(ToolError) as d2:
        normalize_kind("d2")
    assert d2.value.code == "diagram.unsupported"
    assert "mermaid" in d2.value.message
    with pytest.raises(ToolError) as other:
        normalize_kind("kroki")
    assert other.value.code == "diagram.unsupported"


def test_core_and_gateway_include_one_diagram_verb() -> None:
    assert "generate_diagram" in CORE_VISIBLE_TOOLS
    assert "generate_diagram" in ALLOWED_GATEWAY_TOOLS
    assert "generate_diagram" in resolve_visible_tools(None)
    gw = build_default_gateway()
    assert "generate_diagram" in gw.tools
    schemas = {s["function"]["name"] for s in openai_tool_schemas(gw)}
    assert "generate_diagram" in schemas
    ts = (ROOT / "services" / "true_pi_bridge" / "pico-gateway-tools.ts").read_text(
        encoding="utf-8"
    )
    assert '"generate_diagram"' in ts


def test_progress_lines() -> None:
    assert workbench_tool_step_line("generate_diagram") == "正在画结构图"
    assert workbench_tool_result_line("generate_diagram", ok=True) == "已画结构图"
    assert workbench_tool_result_line("generate_diagram", ok=False) == "没画出结构图"


def test_diagram_errors_are_not_image_key_copy() -> None:
    msg = user_message_for_error("这一档只支持 mermaid。D2 还没接，不能假装画出结构图。", code="diagram.unsupported")
    assert "结构图" in msg
    assert "SILICONFLOW" not in msg
    assert "密钥" not in msg
    parse = user_message_for_error("这段结构图语法不对，我没画出来。", code="diagram.parse")
    assert "语法不对" in parse


@pytest.mark.asyncio
async def test_missing_mermaid_js_fail_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("sandbox_worker.diagram.mermaid_js_path", lambda: None)
    with pytest.raises(ToolError) as caught:
        await render_diagram(source="flowchart TD\nA-->B")
    assert caught.value.code == "diagram.missing_engine"
    assert "画不出来" in caught.value.message


@pytest.mark.asyncio
async def test_worker_render_mocked_playwright(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    js = tmp_path / "mermaid.min.js"
    js.write_text("/* mermaid stub */" + ("x" * 20_000))
    monkeypatch.setenv("PICO_MERMAID_JS_PATH", str(js))

    class FakeLocator:
        async def screenshot(self, **kwargs: Any) -> bytes:
            assert kwargs.get("type") == "png"
            return ONE_PNG

        async def bounding_box(self) -> dict[str, float]:
            return {"x": 0, "y": 0, "width": 240, "height": 80}

    class FakePage:
        def set_default_timeout(self, _ms: int) -> None:
            return None

        async def set_content(self, _html: str, wait_until: str | None = None) -> None:
            return None

        async def add_script_tag(self, path: str) -> None:
            assert Path(path).is_file()

        async def evaluate(self, _script: str, payload: dict[str, str]) -> dict[str, str]:
            assert "A-->B" in payload["source"]
            return {"ok": True, "svg": "<svg xmlns='http://www.w3.org/2000/svg'></svg>"}

        def locator(self, selector: str) -> FakeLocator:
            assert selector == "#diagram"
            return FakeLocator()

    class FakeContext:
        def __init__(self) -> None:
            self.pages: list[Any] = []

        async def new_page(self) -> FakePage:
            return FakePage()

        async def close(self) -> None:
            return None

    class FakeBrowser:
        async def new_context(self, **_kwargs: Any) -> FakeContext:
            return FakeContext()

    async def fake_browser() -> FakeBrowser:
        return FakeBrowser()

    monkeypatch.setattr("sandbox_worker.diagram._ensure_browser", fake_browser)
    out = await render_diagram(source="```mermaid\nflowchart TD\nA-->B\n```")
    assert out["ok"] is True
    assert out["kind"] == "mermaid"
    assert out["engine"].startswith("mermaid@")
    raw = base64.b64decode(out["png_base64"])
    assert raw.startswith(b"\x89PNG")


@pytest.mark.asyncio
async def test_gateway_writes_png_from_sidecar(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_sidecar(method: str, path: str, **_kwargs: Any) -> dict[str, Any]:
        assert method == "POST"
        assert path.endswith("/diagram")
        return {
            "ok": True,
            "kind": "mermaid",
            "engine": "mermaid@11.15.0",
            "png_base64": base64.b64encode(ONE_PNG).decode("ascii"),
            "svg": "<svg xmlns='http://www.w3.org/2000/svg'></svg>",
            "width": 100,
            "height": 40,
        }

    monkeypatch.setattr("pico_orchestrator.diagram_generate.sidecar_json", fake_sidecar)
    store = MemoryArtifactStore()
    gw = build_default_gateway(artifact_store=store)
    owner = P()
    result = await gw.invoke(
        owner,
        "generate_diagram",
        {"source": "flowchart TD\nA-->B", "title": "流程"},
    )
    assert result["title"] == "流程.png"
    assert result["kind"] == "png"
    assert result["diagram_kind"] == "mermaid"
    assert result["svg"]
    assert store.rows[0]["content"].startswith(b"\x89PNG")


@pytest.mark.asyncio
async def test_d2_never_calls_sidecar(monkeypatch: pytest.MonkeyPatch) -> None:
    async def boom(*_args: Any, **_kwargs: Any) -> None:
        raise AssertionError("sidecar must not run for d2")

    monkeypatch.setattr("pico_orchestrator.diagram_generate.sidecar_json", boom)
    with pytest.raises(ToolError) as caught:
        await render_diagram_bytes("x -> y", kind="d2")
    assert caught.value.code == "diagram.unsupported"
