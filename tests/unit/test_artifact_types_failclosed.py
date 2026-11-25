from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "orchestrator"))

from pico_orchestrator.artifact_types import (
    is_valid_ooxml_package,
    title_protected_extension,
)
from pico_orchestrator.document_generators import (
    build_docx_document,
    build_html_document,
    build_pptx_document,
    office_shell_reason,
)
from pico_orchestrator.gateway import ToolError
from pico_orchestrator.tools_builtin import build_default_gateway
from pico_orchestrator.true_pi import runner
from pico_orchestrator.usage_hook import bind_usage_context, reset_usage_context


class Mem:
    async def write(self, principal, *, title, content, kind):
        return {
            "title": title,
            "kind": kind,
            "size": len(content) if isinstance(content, (str, bytes)) else 0,
        }

    async def read(self, *a, **k):
        return None

    async def list(self, *a, **k):
        return []


class P:
    school_id = "s"
    membership_id = "m"

    def __init__(self) -> None:
        self.scopes = ["ai:run"]


@pytest.fixture(params=["box-run", "gateway-run"])
def office_run(request, monkeypatch):
    entry = runner.ProxyEntry("box-run", "llm-token", "", "", "", "tool-token")
    monkeypatch.setitem(runner._REGISTRY, entry.run_id, entry)
    return request.param


def _assert_office_hint(message, run_id, kind, library):
    if run_id == "box-run":
        assert "sandbox_office_lib" not in message
        assert library in message
        assert f"outputs/<文件名>.{kind}" in message
    else:
        assert f"sandbox_office_lib（kind={kind}）" in message


async def test_workspace_write_rejects_protected_exts(office_run):
    store = Mem()
    store._run_id = office_run
    gw = build_default_gateway(store, register_unregistered_office=True)
    for ext in ("html", "htm"):
        with pytest.raises(ToolError, match="generate_html_document"):
            await gw.invoke(P(), "workspace_write_file", {"title": f"x.{ext}", "content": "fake"})
    for kind, library in (("docx", "python-docx"), ("xlsx", "openpyxl"), ("pptx", "python-pptx")):
        with pytest.raises(ToolError) as ei:
            await gw.invoke(P(), "workspace_write_file", {"title": f"x.{kind}", "content": "fake"})
        _assert_office_hint(ei.value.message, office_run, kind, library)


def test_ooxml_validation():
    marker = "M1"
    docx = build_docx_document(title="t.docx", marker=marker)
    pptx = build_pptx_document(title="t.pptx", marker=marker)
    assert is_valid_ooxml_package(docx, ".docx")
    assert is_valid_ooxml_package(pptx, ".pptx")
    assert not is_valid_ooxml_package(b"not a zip", ".docx")
    assert not is_valid_ooxml_package(b"PK\x03\x04fake", ".docx")
    assert not is_valid_ooxml_package(b"this is text renamed to docx", ".docx")
    assert title_protected_extension("lesson.docx") == ".docx"
    assert title_protected_extension("note.txt") is None


async def test_generate_docx_rejects_short_body_without_padding(office_run):
    store = Mem()
    store._run_id = office_run
    gw = build_default_gateway(store, register_unregistered_office=True)
    with pytest.raises(ToolError) as ei:
        await gw.invoke(
            P(),
            "generate_docx_document",
            {"title": "家长会通知.docx", "marker": "M", "body": "一行"},
        )
    assert ei.value.code == "tool.invalid_arguments"
    assert "垫字" in ei.value.message or "空" in ei.value.message
    _assert_office_hint(ei.value.message, office_run, "docx", "python-docx")


async def test_generate_pptx_accepts_one_slide_and_rejects_empty(office_run):
    store = Mem()
    store._run_id = office_run
    gw = build_default_gateway(store, register_unregistered_office=True)
    one = await gw.invoke(
        P(),
        "generate_pptx_document",
        {"title": "培训.pptx", "marker": "M", "body": "只有一页"},
    )
    assert one.get("format") == "pptx"
    with pytest.raises(ToolError) as ei:
        await gw.invoke(
            P(),
            "generate_pptx_document",
            {"title": "空.pptx", "marker": "M", "body": "   "},
        )
    assert ei.value.code == "tool.invalid_arguments"
    assert "垫页" in ei.value.message or "没有可渲染" in ei.value.message
    _assert_office_hint(ei.value.message, office_run, "pptx", "python-pptx")


@pytest.mark.parametrize(("kind", "library"), [("docx", "python-docx"), ("pptx", "python-pptx")])
def test_office_shell_tool_error_uses_run_mode(office_run, kind, library):
    token = bind_usage_context(school_id="s", membership_id="m", run_id=office_run)
    try:
        message = office_shell_reason(b"", f".{kind}")
    finally:
        reset_usage_context(token)
    assert message
    _assert_office_hint(message, office_run, kind, library)


@pytest.mark.parametrize(("kind", "library"), [("docx", "python-docx"), ("pptx", "python-pptx")])
async def test_artifact_content_rejects_invalid_office_bytes(office_run, kind, library, monkeypatch):
    from app import main

    artifact = SimpleNamespace(id="a", title=f"x.{kind}", inline="fake", run_id=office_run)
    monkeypatch.setattr(
        main.run_service, "get_artifact_for_principal", AsyncMock(return_value=artifact)
    )
    with pytest.raises(HTTPException) as ei:
        await main.get_artifact_content("a", principal=P(), session=None)
    assert ei.value.status_code == 415
    _assert_office_hint(ei.value.detail, office_run, kind, library)


def test_html_generator_not_protected_write():
    html = build_html_document(title="t.html", marker="M")
    assert b"Content-Security-Policy" in html
