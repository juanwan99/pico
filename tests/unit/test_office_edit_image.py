"""T-AGENT-EXT-V1: python-docx/pptx edit originals + SiliconFlow image mock."""

from __future__ import annotations

import io
import sys
import zipfile
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "orchestrator"))

from pico_orchestrator.artifact_types import is_valid_ooxml_package
from pico_orchestrator.document_generators import build_docx_document
from pico_orchestrator.gateway import ToolError
from pico_orchestrator.image_generate import (
    NO_KEY_MESSAGE,
    REJECT_MESSAGE,
    generate_image_bytes,
)
from pico_orchestrator.office_editors import edit_docx_bytes, edit_pptx_title_bytes
from pico_orchestrator.skill_policy import snapshot_for_skill
from pico_orchestrator.tools_builtin import build_default_gateway, openai_tool_schemas
from pico_orchestrator.true_pi.config import ALLOWED_GATEWAY_TOOLS

ONE_PNG = (
    b"\x89PNG\r\n\x1a\n"
    b"\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde"
    b"\x00\x00\x00\x0cIDATx\x9cc``\x00\x00\x00\x04\x00\x01\xa3\x0a\x0d\xe4"
    b"\x00\x00\x00\x00IEND\xaeB`\x82"
)


def _three_para_docx() -> bytes:
    from docx import Document

    doc = Document()
    doc.add_paragraph("第一段保持")
    doc.add_paragraph("第二段也在")
    doc.add_paragraph("第三段很长很长很长很长很长很长很长很长")
    out = io.BytesIO()
    doc.save(out)
    return out.getvalue()


def _two_slide_pptx() -> bytes:
    from pptx import Presentation

    deck = Presentation()
    first = deck.slides.add_slide(deck.slide_layouts[0])
    first.shapes.title.text = "原标题"
    second = deck.slides.add_slide(deck.slide_layouts[1])
    second.shapes.title.text = "第二页还在"
    out = io.BytesIO()
    deck.save(out)
    return out.getvalue()


def test_edit_docx_keeps_other_paragraphs() -> None:
    raw = _three_para_docx()
    assert is_valid_ooxml_package(raw, ".docx")
    edited = edit_docx_bytes(raw, paragraph_index=3, text="第三段短")
    assert is_valid_ooxml_package(edited, ".docx")
    from docx import Document

    doc = Document(io.BytesIO(edited))
    texts = [p.text.strip() for p in doc.paragraphs if p.text.strip()]
    assert texts[0] == "第一段保持"
    assert texts[1] == "第二段也在"
    assert texts[2] == "第三段短"
    assert "很长很长" not in texts[2]
    with zipfile.ZipFile(io.BytesIO(edited)) as zf:
        assert "word/document.xml" in zf.namelist()
        assert "word/styles.xml" in zf.namelist()
    generated = build_docx_document(title="x.docx", marker="MARK", body="另造")
    with zipfile.ZipFile(io.BytesIO(generated)) as zf:
        generated_names = set(zf.namelist())
    with zipfile.ZipFile(io.BytesIO(edited)) as zf:
        edited_names = set(zf.namelist())
    assert "word/styles.xml" in edited_names
    assert "word/styles.xml" in generated_names
    assert "MARK" in zf_document_xml(generated)


def zf_document_xml(raw: bytes) -> str:
    with zipfile.ZipFile(io.BytesIO(raw)) as zf:
        return zf.read("word/document.xml").decode("utf-8")


def test_edit_pptx_keeps_other_slides() -> None:
    raw = _two_slide_pptx()
    edited = edit_pptx_title_bytes(raw, slide_index=1, new_title="课堂导入")
    assert is_valid_ooxml_package(edited, ".pptx")
    from pptx import Presentation

    deck = Presentation(io.BytesIO(edited))
    assert deck.slides[0].shapes.title.text.strip() == "课堂导入"
    assert deck.slides[1].shapes.title.text.strip() == "第二页还在"
    assert len(deck.slides) == 2


@pytest.mark.asyncio
async def test_generate_image_no_key_chinese(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("SILICONFLOW_API_KEY", raising=False)
    with pytest.raises(ToolError) as caught:
        await generate_image_bytes("分数的初步认识")
    assert caught.value.code == "image.unconfigured"
    assert "不能编造" in caught.value.message
    assert caught.value.message == NO_KEY_MESSAGE


@pytest.mark.asyncio
async def test_generate_image_mock_https_png(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SILICONFLOW_API_KEY", "test-key-not-a-secret")
    import base64

    async def fake_post(payload, *, api_key, timeout):
        assert api_key == "test-key-not-a-secret"
        assert payload["prompt"]
        return SimpleNamespace(
            status_code=200,
            json=lambda: {
                "images": [{"b64_json": base64.b64encode(ONE_PNG).decode("ascii")}]
            },
        )

    monkeypatch.setattr("pico_orchestrator.image_generate._post_images", fake_post)
    raw, ext = await generate_image_bytes("分数的初步认识课堂示意图")
    assert ext == "png"
    assert raw.startswith(b"\x89PNG")


@pytest.mark.asyncio
async def test_generate_image_4xx_no_fake(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SILICONFLOW_API_KEY", "test-key-not-a-secret")

    async def fake_post(payload, *, api_key, timeout):
        return SimpleNamespace(status_code=400, json=lambda: {"error": "bad"})

    monkeypatch.setattr("pico_orchestrator.image_generate._post_images", fake_post)
    with pytest.raises(ToolError) as caught:
        await generate_image_bytes("画一只猫")
    assert caught.value.code == "image.provider"
    assert caught.value.message == REJECT_MESSAGE
    assert "不能编造" in caught.value.message


def test_sidebar_chat_has_no_edit_or_image_tools() -> None:
    chat = snapshot_for_skill("skill.chat")
    assert chat is not None
    assert chat["tools"] == []
    assert openai_tool_schemas(build_default_gateway(), allowed_tools=[]) == []
    forbidden = {
        "edit_docx_document",
        "edit_pptx_document",
        "generate_image",
        "generate_diagram",
    }
    assert forbidden.isdisjoint(chat["tools"])
    deliver = snapshot_for_skill("skill-deliverable")
    assert deliver is not None
    assert forbidden <= set(deliver["tools"])
    assert forbidden <= ALLOWED_GATEWAY_TOOLS
    gw_names = set(build_default_gateway().tools)
    assert forbidden <= gw_names
    ts = (ROOT / "services" / "true_pi_bridge" / "pico-gateway-tools.ts").read_text(
        encoding="utf-8"
    )
    for name in forbidden:
        assert f'"{name}"' in ts
