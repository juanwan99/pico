"""T-OFFICE-SKILL-VISIBILITY: catalog one line; craft on demand; no bash."""

from __future__ import annotations

import sys
from functools import partial
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock
from zipfile import ZipFile

import httpx
import pytest
from docx import Document
from PIL import Image
from pptx import Presentation
from pptx.util import Inches

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "orchestrator"))

from pi_runner.app import Runner, build_control_app
from pi_runner.policy import RunnerSettings, WorkspaceKey
from pico_orchestrator.capability_loading import (
    CORE_VISIBLE_TOOLS,
    office_skill_visible,
    resolve_visible_tools,
)
from pico_orchestrator.gateway import ToolError
from pico_orchestrator.office.skill_docs import (
    OFFICE_SKILL_IDS,
    load_office_skill_body,
    normalize_office_skill_id,
)
from pico_orchestrator.tools_builtin import build_default_gateway
from pico_orchestrator.true_pi import runner
from pico_orchestrator.true_pi.config import ALLOWED_GATEWAY_TOOLS
from pico_orchestrator.true_pi.runtime import pico_system_text
from pico_orchestrator.usage_hook import bind_usage_context, reset_usage_context
from pico_orchestrator.workbench_progress import (
    workbench_tool_result_line,
    workbench_tool_step_line,
)


def test_read_office_skill_is_core_not_bash() -> None:
    gw = build_default_gateway()
    assert "read_office_skill" in gw.tools
    assert "sandbox_office_lib" not in gw.tools["read_office_skill"].description
    assert "read_office_skill" in ALLOWED_GATEWAY_TOOLS
    assert "read_office_skill" in CORE_VISIBLE_TOOLS
    assert "bash" not in ALLOWED_GATEWAY_TOOLS
    assert workbench_tool_step_line("read_office_skill") == "正在读办公工艺"
    assert workbench_tool_result_line("read_office_skill", ok=True) == "已读办公工艺"
    assert office_skill_visible(resolve_visible_tools(None))


def test_system_catalog_is_one_line_not_craft_body() -> None:
    body = pico_system_text()
    assert "`docx`:" in body
    assert "`xlsx`:" in body
    assert "`pptx`:" in body
    assert "generate_* remains the fast path" not in body
    assert "from docx import Document" not in body
    assert "from openpyxl import Workbook" not in body
    assert "add_heading" not in body
    assert "MSO_SHAPE" not in body
    assert "pi install" not in body
    assert "```bash" not in body
    assert "host bash" not in body.lower()
    assert "sandbox_office_lib" not in runner.WORKSPACE_SYSTEM


def test_office_skill_bodies_have_shared_craft() -> None:
    expected = {
        "docx": ("add_heading", "Table Grid", "section.header", "Document(input_path)", "p.runs"),
        "xlsx": ("=SUM(", "create_sheet", "number_format", "load_workbook(input_path)", 'ws["B2"]'),
        "pptx": (
            "MSO_SHAPE", "RGBColor", "slide_layouts[6]", "Presentation(input_path)", "prs.slides[1]"
        ),
    }
    for sid in OFFICE_SKILL_IDS:
        text = load_office_skill_body(sid)
        assert "sandbox_office_lib" not in text
        assert "pi install" not in text
        assert "```bash" not in text
        # v2 (#959): the box is a full Python; the craft must not pretend otherwise
        assert "Do not import os" not in text
        assert "Do not use a shell" not in text
        assert "Fast path remains" not in text
        assert ".save(output_path)" in text
        for needle in expected[sid]:
            assert needle in text, (sid, needle)


def test_normalize_office_skill_aliases() -> None:
    assert normalize_office_skill_id("Word") == "docx"
    assert normalize_office_skill_id("excel") == "xlsx"
    assert normalize_office_skill_id("slides") == "pptx"
    assert normalize_office_skill_id("office-docx") == "docx"
    assert normalize_office_skill_id("nope") is None


class P:
    def __init__(self) -> None:
        self.school_id = "school-a"
        self.membership_id = "member-a"
        self.scopes = ["ai:run"]


@pytest.mark.parametrize(
    ("sid", "library"), [("docx", "python-docx"), ("xlsx", "openpyxl"), ("pptx", "python-pptx")]
)
@pytest.mark.parametrize("run_id", ["box-run", "gateway-run"])
async def test_read_office_skill_returns_body(sid, library, run_id, monkeypatch) -> None:
    gw = build_default_gateway()
    entry = runner.ProxyEntry("box-run", "llm-token", "", "", "", "tool-token")
    monkeypatch.setitem(runner._REGISTRY, entry.run_id, entry)
    principal = P()
    token = bind_usage_context(
        school_id=principal.school_id, membership_id=principal.membership_id, run_id=run_id
    )
    try:
        out = await gw.invoke(principal, "read_office_skill", {"id": sid})
    finally:
        reset_usage_context(token)
    assert out["ok"] is True
    assert out["id"] == sid
    assert out["body"].endswith(load_office_skill_body(sid))
    assert library in out["body"]
    if run_id == "box-run":
        assert out["execute_with"] == "bash"
        assert "sandbox_office_lib" not in str(out)
        assert f"outputs/<name>.{sid}" in out["body"]
        assert "`bash`" in out["body"]
    else:
        assert out["execute_with"] == "sandbox_office_lib"
        assert f"`sandbox_office_lib` with `kind={sid}`" in out["body"]
        assert out["body"].count("sandbox_office_lib") == 1
        assert "`artifact_id`" in out["body"]
        assert "`output_path = OUTPUT_PATH`" in out["body"]
        assert "`image_artifact_ids`" in out["body"]
        assert "`IMAGE_PATHS`" in out["body"]


@pytest.mark.parametrize(
    ("sid", "tool", "args", "kind"),
    [
        ("docx", "generate_image", {"prompt": "一张插图"}, "jpg"),
        ("pptx", "generate_diagram", {"source": "flowchart TD\nA-->B"}, "png"),
    ],
)
async def test_box_office_skill_embeds_a_generated_picture(sid, tool, args, kind, tmp_path, monkeypatch):
    key = runner.WorkspaceKey.for_run(
        school_id="school-a", membership_id="member-a", conversation_id="c", run_id="box-run"
    )
    entry = runner.ProxyEntry("box-run", "", "", "", "", "", workspace_key=key)
    monkeypatch.setitem(runner._REGISTRY, entry.run_id, entry)
    settings = RunnerSettings(token="runner-test", workspace_root=tmp_path)
    control = Runner(settings)
    control_key = WorkspaceKey(**key.as_dict())
    ws = control.prepare_workspace(control_key, with_memory=False)
    control.sessions[entry.run_id] = SimpleNamespace(key=control_key)
    transport = httpx.ASGITransport(app=build_control_app(control))
    monkeypatch.setattr(runner, "httpx", SimpleNamespace(
        AsyncClient=partial(httpx.AsyncClient, transport=transport), HTTPError=httpx.HTTPError
    ))
    monkeypatch.setenv(runner.RUNNER_URL_ENV, "http://runner.test")
    monkeypatch.setenv(runner.RUNNER_TOKEN_ENV, settings.token)

    picture = BytesIO()
    Image.new("RGB", (2, 2), "white").save(picture, format={"jpg": "JPEG", "png": "PNG"}[kind])
    raw = picture.getvalue()
    monkeypatch.setattr(
        "pico_orchestrator.tools_builtin.generate_image_with_usage",
        AsyncMock(return_value=(raw, kind, None)),
    )
    monkeypatch.setattr(
        "pico_orchestrator.tools_builtin.render_diagram_bytes",
        AsyncMock(return_value=(raw, "", {})),
    )
    store = SimpleNamespace(
        _run_id=entry.run_id,
        write=AsyncMock(return_value={"artifact_id": "picture-id"}),
    )
    gw = build_default_gateway(store)
    principal = P()
    skill = await gw.invoke(principal, "read_office_skill", {"id": sid})
    result = await gw.invoke(principal, tool, args)
    assert f"`{tool}`" in skill["body"]
    assert "`workspace_path`" in skill["body"] and "add_picture" in skill["body"]
    assert "read_office_skill" in result["user_message"]
    path = result["workspace_path"]
    assert path == f"/workspace/work/generated/picture-id.{kind}"
    assert str(Path(path).parent) + "/" in skill["body"]
    local_path = str(ws / Path(path).relative_to("/workspace"))
    assert not list((ws / "outputs").iterdir())
    assert store.write.await_args.kwargs["content"] == raw

    output_path = ws / "outputs" / f"illustrated.{sid}"
    if sid == "docx":
        doc = Document()
        doc.add_picture(local_path)
        doc.save(output_path)
    else:
        deck = Presentation()
        slide = deck.slides.add_slide(deck.slide_layouts[6])
        slide.shapes.add_picture(local_path, Inches(1), Inches(1))
        deck.save(output_path)
    with ZipFile(output_path) as package:
        pictures = [name for name in package.namelist() if "/media/" in name]
        assert len(pictures) == 1
        assert package.read(pictures[0]) == raw


async def test_read_office_skill_rejects_unknown_id() -> None:
    gw = build_default_gateway()
    with pytest.raises(ToolError) as ei:
        await gw.invoke(P(), "read_office_skill", {"id": "bash"})
    assert ei.value.code == "office_skill.unknown"
