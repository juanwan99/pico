"""S2.2: NL deliverable detection must not require tool names or .docx suffix."""

from __future__ import annotations

from pathlib import Path


def _load_wants():
    """Load helper without importing full openai_compat deps."""
    path = (
        Path(__file__).resolve().parents[2]
        / "services"
        / "api"
        / "app"
        / "openai_compat.py"
    )
    text = path.read_text(encoding="utf-8")
    # Extract function body by compiling a minimal module with just the function.
    start = text.index("def _wants_deliverable_document")
    # next top-level def after this one
    rest = text[start:]
    # find next \ndef at beginning of line that is not nested
    end = None
    for i, line in enumerate(rest.splitlines()[1:], start=1):
        if line.startswith(("def ", "async def ", "class ")):
            # reconstruct end offset
            end = sum(len(l) + 1 for l in rest.splitlines()[:i])
            break
    src = rest if end is None else rest[:end]
    ns: dict = {}
    exec(src, ns)  # noqa: S102 — unit test isolates pure helper
    return ns["_wants_deliverable_document"]


wants = _load_wants()


def test_plain_chinese_word_download_hits() -> None:
    assert wants("写一份社区周末义工招募一页说明，生成可下载 Word。") is True
    assert wants(
        "请在同一任务上改一版：把时间改成周日上午；增加条款「雨天改室内」。"
        "重新生成可下载 Word。"
    ) is True
    assert wants("生成一份 Word 文档") is True
    assert wants("请生成docx文件") is True
    assert wants("做一份 PPT 课件") is True
    assert wants(
        "请生成一份较完整的社区年度活动方案 Word，分章节写背景、目标。"
    ) is True


def test_explicit_suffix_still_hits() -> None:
    assert wants("请实际生成 .docx 文件") is True
    assert wants("output.pptx please") is True


def test_short_answer_and_chat_do_not_hit() -> None:
    assert wants("17+25，只回答数字，不要生成任何文件。") is False
    assert wants("你好") is False
    assert wants("你是什么模型") is False
    assert wants("") is False
