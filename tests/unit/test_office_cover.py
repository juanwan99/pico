"""T-OFFICE-COVER: Excel / comments / template fill / legacy fail-closed."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "orchestrator"))

from pico_orchestrator.artifact_types import is_valid_ooxml_package
from pico_orchestrator.office.edit import comment_docx_bytes, edit_xlsx_cell_bytes
from pico_orchestrator.office.fill import fill_office_bytes
from pico_orchestrator.office.inspect import inspect_office_bytes
from pico_orchestrator.office.legacy import LEGACY_OFFICE_ERROR
from pico_orchestrator.office.qa import verify_office_bytes
from pico_orchestrator.office.render import render_spec
from pico_orchestrator.office.spec import parse_spec
from pico_orchestrator.true_pi.config import ALLOWED_GATEWAY_TOOLS


def test_xlsx_grades_formula_and_edit_cell():
    spec = parse_spec(
        {
            "kind": "xlsx",
            "title": "成绩表",
            "theme": {"accent": "1F4E79", "heading_font": "Calibri"},
            "sheets": [
                {
                    "name": "成绩",
                    "headers": ["姓名", "语文", "数学", "总分"],
                    "rows": [
                        ["张三", 90, 85, "=B2+C2"],
                        ["李四", 80, 88, "=B3+C3"],
                    ],
                }
            ],
        }
    )
    raw = render_spec(spec)
    assert is_valid_ooxml_package(raw, ".xlsx")
    outline = inspect_office_bytes(raw, ".xlsx")
    assert outline["sheets"] == 1
    assert outline["formulas"] >= 2
    sheet = outline["units"][0]
    assert sheet["name"] == "成绩"
    assert "姓名" in sheet["headers"]
    edited = edit_xlsx_cell_bytes(raw, cell="C2", value="95")
    after = inspect_office_bytes(edited, ".xlsx")
    preview = after["units"][0]["preview"]
    assert any(95 in row or "95" in [str(c) for c in row] for row in preview)
    assert after["formulas"] >= 1


def test_docx_comment_roundtrip():
    spec = parse_spec(
        {
            "kind": "docx",
            "title": "通知",
            "blocks": [
                {"type": "heading", "text": "本周安排", "level": 0},
                {"type": "para", "text": "请核对学生名单。"},
            ],
            "comments": [{"paragraph": 2, "text": "这里数据要核"}],
        }
    )
    raw = render_spec(spec)
    outline = inspect_office_bytes(raw, ".docx")
    assert outline["comments"] >= 1
    texts = [u["text"] for u in outline["units"] if u["kind"] == "comment"]
    assert any("要核" in t for t in texts)
    extra = comment_docx_bytes(raw, paragraph_index=1, text="标题也看一眼")
    after = inspect_office_bytes(extra, ".docx")
    assert after["comments"] >= 2


def test_template_placeholder_fill():
    spec = parse_spec(
        {
            "kind": "docx",
            "title": "成绩通知",
            "blocks": [
                {"type": "heading", "text": "成绩通知", "level": 0},
                {"type": "para", "text": "{{姓名}} 同学，{{学期}} 语文 {{语文}} 分。"},
            ],
        }
    )
    raw = render_spec(spec)
    before = inspect_office_bytes(raw, ".docx")
    assert "姓名" in before["placeholders"]
    filled = fill_office_bytes(
        raw, ".docx", {"姓名": "张三", "学期": "2026春", "语文": "90"}
    )
    after = inspect_office_bytes(filled, ".docx")
    paras = [u["text"] for u in after["units"] if u["kind"] in {"para", "heading"}]
    assert any("张三" in t and "2026春" in t and "90" in t for t in paras)
    assert after["placeholders"] == []


def test_legacy_formats_fail_closed():
    check = verify_office_bytes(b"PK\x03\x04junk", ".xls")
    assert check["ok"] is False
    assert "另存为" in str(check["error"])
    with pytest.raises(ValueError, match="另存为"):
        inspect_office_bytes(b"not-ole", ".doc")
    with pytest.raises(ValueError, match="另存为"):
        inspect_office_bytes(b"not-ole", ".ppt")
    assert LEGACY_OFFICE_ERROR


def test_cover_tools_on_pi_allowlist():
    for name in (
        "generate_xlsx_document",
        "edit_xlsx_document",
        "render_document",
        "inspect_document",
        "verify_document",
    ):
        assert name in ALLOWED_GATEWAY_TOOLS
    assert "bash" not in ALLOWED_GATEWAY_TOOLS
    assert len(ALLOWED_GATEWAY_TOOLS) == 25
