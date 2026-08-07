"""S2.2: NL deliverable detection must not require tool names or .docx suffix."""

from __future__ import annotations

import re


def wants_deliverable_document(prompt: str) -> bool:
    """Mirror of services/api/app/openai_compat._wants_deliverable_document."""
    text = prompt or ""
    if not text.strip():
        return False
    return bool(
        re.search(
            r"\.(?:html?|docx|pptx)\b|"
            r"\b(?:html|docx|pptx|powerpoint)\b|"
            r"幻灯片|课件|网页文件|word\s*文档|PPT|Power\s*Point|"
            r"生成.{0,40}(?:html|网页|word|docx|ppt|pptx|幻灯片|文档)|"
            r"(?:可下载|下载|导出|重新生成|改一版|改版|一页).{0,24}"
            r"(?:Word|word|WORD|文档|docx|PPT|pptx|html|幻灯片|课件)|"
            r"(?:Word|word|WORD|docx|PPT|pptx).{0,16}(?:文件|文档|下载)|"
            r"(?:方案|说明|通知|报告|小结).{0,8}(?:Word|word|docx|PPT|pptx)",
            text,
            re.IGNORECASE,
        )
    )


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
    assert wants_deliverable_document("output.pptx please") is True


def test_short_answer_and_chat_do_not_hit() -> None:
    assert wants_deliverable_document("17+25，只回答数字，不要生成任何文件。") is False
    assert wants_deliverable_document("你好") is False
    assert wants_deliverable_document("你是什么模型") is False
    assert wants_deliverable_document("") is False
