from __future__ import annotations

import sys
from pathlib import Path

import pytest

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
)
from pico_orchestrator.gateway import ToolError
from pico_orchestrator.tools_builtin import build_default_gateway


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


@pytest.mark.asyncio
async def test_workspace_write_rejects_protected_exts():
    gw = build_default_gateway(Mem())
    for title in ("x.html", "a.htm", "b.docx", "c.pptx"):
        with pytest.raises(ToolError) as ei:
            await gw.invoke(P(), "workspace_write_file", {"title": title, "content": "fake"})
        assert "generate_" in ei.value.message or "禁止" in ei.value.message


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


@pytest.mark.asyncio
async def test_generate_docx_rejects_short_body_without_padding():
    gw = build_default_gateway(Mem())
    with pytest.raises(ToolError) as ei:
        await gw.invoke(
            P(),
            "generate_docx_document",
            {"title": "家长会通知.docx", "marker": "M", "body": "一行"},
        )
    assert ei.value.code == "tool.invalid_arguments"
    assert "垫字" in ei.value.message or "正文过短" in ei.value.message


@pytest.mark.asyncio
async def test_generate_pptx_rejects_one_slide_without_padding():
    gw = build_default_gateway(Mem())
    with pytest.raises(ToolError) as ei:
        await gw.invoke(
            P(),
            "generate_pptx_document",
            {"title": "培训.pptx", "marker": "M", "body": "只有一页"},
        )
    assert ei.value.code == "tool.invalid_arguments"
    assert "垫页" in ei.value.message or "不足三页" in ei.value.message


def test_html_generator_not_protected_write():
    html = build_html_document(title="t.html", marker="M")
    assert b"Content-Security-Policy" in html
