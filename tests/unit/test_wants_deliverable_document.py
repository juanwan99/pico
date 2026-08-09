"""S2.2: NL deliverable detection — Office/HTML intent, not material format noise."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "api"))

from app.openai_compat import _wants_deliverable_document as wants_deliverable_document


def test_plain_chinese_word_download_hits() -> None:
    assert wants_deliverable_document("写一份社区周末义工招募一页说明，生成可下载 Word。") is True
    assert (
        wants_deliverable_document(
            "请在同一任务上改一版：把时间改成周日上午；增加条款「雨天改室内」。"
            "重新生成可下载 Word。"
        )
        is True
    )
    assert wants_deliverable_document("生成一份 Word 文档") is True
    assert wants_deliverable_document("请生成docx文件") is True
    assert wants_deliverable_document("做一份 PPT 课件") is True
    assert (
        wants_deliverable_document(
            "请生成一份较完整的社区年度活动方案 Word，分章节写背景、目标。"
        )
        is True
    )


def test_explicit_suffix_still_hits() -> None:
    assert wants_deliverable_document("请实际生成 .docx 文件") is True
    assert wants_deliverable_document("please generate output.pptx") is True


def test_short_answer_and_chat_do_not_hit() -> None:
    assert wants_deliverable_document("17+25，只回答数字，不要生成任何文件。") is False
    assert wants_deliverable_document("你好") is False
    assert wants_deliverable_document("你是什么模型") is False
    assert wants_deliverable_document("") is False


def test_material_mentions_docx_not_office_deliverable() -> None:
    """O1: pasted material listing pdf/docx must not force Word/HTML fail-closed."""
    prompt = (
        "请整理成一份可下载的客户拜访纪要 Markdown 文件（visit-notes.md）。\n"
        "材料：历史文档格式杂（pdf/docx/截图），担心召回质量。"
    )
    assert wants_deliverable_document(prompt) is False
