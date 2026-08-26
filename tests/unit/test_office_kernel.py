"""T-OFFICE-KERNEL: spec → render table/image, inspect addresses, path B edit, bad OOXML."""

from __future__ import annotations

import base64
import io
import sys
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "orchestrator"))

from pico_orchestrator.artifact_types import is_valid_ooxml_package
from pico_orchestrator.document_generators import build_docx_document, build_pptx_document
from pico_orchestrator.office.edit import edit_by_address
from pico_orchestrator.office.inspect import inspect_bytes
from pico_orchestrator.office.qa import verify_bytes
from pico_orchestrator.office.render import render_spec
from pico_orchestrator.office.spec import SPEC_VERSION, SpecError, parse_spec
from pico_orchestrator.tools_builtin import build_default_gateway
from pico_orchestrator.true_pi.config import ALLOWED_GATEWAY_TOOLS


def _png_bytes() -> bytes:
    from PIL import Image

    buf = io.BytesIO()
    Image.new("RGB", (64, 48), (20, 90, 180)).save(buf, format="PNG")
    return buf.getvalue()


ONE_PNG = _png_bytes()


def _docx_spec() -> dict:
    return {
        "version": SPEC_VERSION,
        "kind": "docx",
        "title": "三年级二班值日表",
        "blocks": [
            {"type": "heading", "text": "三年级二班值日表", "level": 0},
            {"type": "para", "text": "本周值日如下，请对照执行。"},
            {
                "type": "table",
                "headers": ["日期", "值日生", "职责"],
                "rows": [
                    ["周一", "李明", "黑板"],
                    ["周二", "王芳", "扫地"],
                ],
            },
            {
                "type": "image",
                "bytes_b64": base64.b64encode(ONE_PNG).decode("ascii"),
                "alt": "示意图",
            },
        ],
    }


def test_spec_docx_has_real_table_and_image() -> None:
    raw = render_spec(_docx_spec())
    assert is_valid_ooxml_package(raw, ".docx")
    assert verify_bytes(raw, ".docx")["ok"] is True
    with zipfile.ZipFile(io.BytesIO(raw)) as zf:
        names = set(zf.namelist())
        assert "word/document.xml" in names
        xml = zf.read("word/document.xml").decode("utf-8")
        assert "<w:tbl" in xml
        assert "李明" in xml
        assert "值日生" in xml
        media = [n for n in names if n.startswith("word/media/")]
        assert media, "image must be inside the Word package"
    outline = inspect_bytes(raw, ".docx")
    kinds = {a["kind"] for a in outline["addresses"]}
    assert "table" in kinds
    assert outline["table_count"] >= 1
    assert outline["image_count"] >= 1
    addrs = [a["addr"] for a in outline["addresses"]]
    assert any(a.startswith("p:") for a in addrs)
    assert any(a.startswith("t:1") for a in addrs)


def test_spec_pptx_embeds_image_on_slide() -> None:
    spec = {
        "version": SPEC_VERSION,
        "kind": "pptx",
        "title": "分数的初步认识",
        "blocks": [
            {
                "type": "slide",
                "title": "分数的初步认识",
                "bullets": ["一半就是 1/2", "把饼平均分成两份"],
                "image": {"bytes_b64": base64.b64encode(ONE_PNG).decode("ascii")},
            },
            {"type": "slide", "title": "练习", "bullets": ["把纸对折"]},
            {"type": "slide", "title": "小结", "bullets": ["今天认识了分数"]},
        ],
    }
    raw = render_spec(spec)
    assert is_valid_ooxml_package(raw, ".pptx")
    assert verify_bytes(raw, ".pptx")["ok"] is True
    with zipfile.ZipFile(io.BytesIO(raw)) as zf:
        names = set(zf.namelist())
        media = [n for n in names if n.startswith("ppt/media/")]
        assert media, "image must live inside the deck, not a sidecar png"
        slide1 = zf.read("ppt/slides/slide1.xml").decode("utf-8")
        assert "分数" in slide1
        # picture relationship on the slide
        assert "a:blip" in slide1 or "pic:pic" in slide1
    outline = inspect_bytes(raw, ".pptx")
    assert outline["slide_count"] == 3
    assert outline["image_count"] >= 1
    addrs = [a["addr"] for a in outline["addresses"]]
    assert "s:1.title" in addrs
    assert "s:1.image" in addrs


def test_inspect_addresses_then_path_b_keeps_rest() -> None:
    raw = render_spec(_docx_spec())
    outline = inspect_bytes(raw, ".docx")
    paras = [a for a in outline["addresses"] if a["kind"] in {"heading", "para"}]
    assert len(paras) >= 2
    target = next(a for a in paras if "对照执行" in a.get("text", ""))
    edited = edit_by_address(
        raw, ext=".docx", address=target["addr"], text="本周值日已更新，请看表。"
    )
    after = inspect_bytes(edited, ".docx")
    texts = [a.get("text", "") for a in after["addresses"]]
    assert any("已更新" in t for t in texts)
    assert not any("对照执行" in t for t in texts)
    assert any("李明" in t for t in texts)
    assert after["table_count"] == outline["table_count"]
    # table cell edit leaves other cells
    wang = next(a for a in after["addresses"] if a.get("kind") == "cell" and a.get("text") == "王芳")
    li = next(a for a in after["addresses"] if a.get("kind") == "cell" and a.get("text") == "李明")
    cell_edited = edit_by_address(edited, ext=".docx", address=wang["addr"], text="赵强")
    cell_after = inspect_bytes(cell_edited, ".docx")
    cells = {a["addr"]: a.get("text") for a in cell_after["addresses"] if a["kind"] == "cell"}
    assert cells.get(wang["addr"]) == "赵强"
    assert cells.get(li["addr"]) == "李明"


def test_pptx_path_b_keeps_other_slides() -> None:
    spec = {
        "version": SPEC_VERSION,
        "kind": "pptx",
        "title": "培训",
        "blocks": [
            {"type": "slide", "title": "开场", "bullets": ["目标一", "目标二"]},
            {"type": "slide", "title": "中段", "bullets": ["常规"]},
            {"type": "slide", "title": "收尾", "bullets": ["跟进"]},
        ],
    }
    raw = render_spec(spec)
    edited = edit_by_address(raw, ext=".pptx", address="s:1.title", text="课堂导入")
    outline = inspect_bytes(edited, ".pptx")
    titles = {a["addr"]: a.get("text") or a.get("title") for a in outline["addresses"]}
    assert titles.get("s:1.title") == "课堂导入"
    assert any(a.get("title") == "中段" or a.get("text") == "中段" for a in outline["addresses"])
    bullet_edited = edit_by_address(edited, ext=".pptx", address="s:1.b:1", text="新目标")
    after = inspect_bytes(bullet_edited, ".pptx")
    slide1_bullets = [
        a["text"]
        for a in after["addresses"]
        if a.get("kind") == "bullet" and a["addr"].startswith("s:1.")
    ]
    assert "新目标" in slide1_bullets
    assert "目标二" in slide1_bullets
    titles = [a.get("text") or a.get("title") for a in after["addresses"] if a.get("kind") in {"slide", "slide_title"}]
    assert any(t == "中段" for t in titles)
    assert any(t == "收尾" for t in titles)


def test_verify_bad_ooxml_fails_closed() -> None:
    junk = b"not-a-zip"
    report = verify_bytes(junk, ".docx")
    assert report["ok"] is False
    assert report["ooxml"] is False
    with pytest.raises(ValueError, match="不是真 Word"):
        inspect_bytes(junk, ".docx")
    thin = b"PK\x03\x04" + b"\x00" * 40
    report2 = verify_bytes(thin, ".pptx")
    assert report2["ok"] is False


def test_xlsx_spec_rejected_on_card1() -> None:
    with pytest.raises(SpecError, match="卡 2"):
        parse_spec({"version": SPEC_VERSION, "kind": "xlsx", "title": "t", "blocks": []})


def test_generate_docx_via_spec_and_markdown_table() -> None:
    body = (
        "本周安排如下。\n\n"
        "| 项目 | 时间 |\n"
        "| --- | --- |\n"
        "| 签到 | 13:50 |\n"
        "| 开会 | 14:00 |"
    )
    raw = build_docx_document(title="安排.docx", marker="TAB1", body=body)
    with zipfile.ZipFile(io.BytesIO(raw)) as zf:
        xml = zf.read("word/document.xml").decode("utf-8")
        assert "<w:tbl" in xml
        assert "13:50" in xml
        assert "TAB1" in xml
    spec_raw = build_docx_document(title="t.docx", marker="SPEC1", spec=_docx_spec())
    assert is_valid_ooxml_package(spec_raw, ".docx")


def test_generate_pptx_plain_body_still_three_slides() -> None:
    body = "开场：培训目标\n\n---\n\n中段：三项课堂常规\n\n---\n\n收尾：下周跟进"
    raw = build_pptx_document(title="教师培训.pptx", marker="TRAIN3", body=body)
    outline = inspect_bytes(raw, ".pptx")
    assert outline["slide_count"] >= 3


def test_pi_allowlist_includes_office_verbs_not_bash() -> None:
    assert {
        "inspect_document",
        "render_document",
        "edit_document",
        "verify_document",
    } <= ALLOWED_GATEWAY_TOOLS
    assert "bash" not in ALLOWED_GATEWAY_TOOLS
    gw = build_default_gateway()
    for name in (
        "inspect_document",
        "render_document",
        "edit_document",
        "verify_document",
        "generate_docx_document",
        "generate_pptx_document",
    ):
        assert name in gw.tools
    ts = (ROOT / "services" / "true_pi_bridge" / "pico-gateway-tools.ts").read_text(
        encoding="utf-8"
    )
    for name in ("inspect_document", "render_document", "edit_document", "verify_document"):
        assert f'"{name}"' in ts
    system = (
        ROOT
        / "services"
        / "orchestrator"
        / "pico_orchestrator"
        / "agent_assets"
        / "system.md"
    ).read_text(encoding="utf-8")
    assert "inspect_document" in system
    assert "不要写 python-docx" in system or "Do not write python-docx" in system
    assert "Short questions" in system
