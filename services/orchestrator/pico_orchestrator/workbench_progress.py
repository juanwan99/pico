"""Map true-Pi tool events to short Chinese workbench progress.

Thin adapter only: names already on the ledger, no second progress engine,
no fake percentages.
"""

from __future__ import annotations

from typing import Any

# Tools that create or edit a user-visible downloadable artifact.
WRITE_TOOLS = frozenset(
    {
        "workspace_write_file",
        "generate_html_document",
        "generate_docx_document",
        "generate_pptx_document",
        "render_document",
        "edit_document",
        "edit_docx_document",
        "edit_pptx_document",
        "generate_image",
    }
)

# In-flight line shown while that tool is running.
_DOING: dict[str, str] = {
    "generate_html_document": "正在写网页",
    "generate_docx_document": "正在写 Word",
    "generate_pptx_document": "正在写课件",
    "inspect_document": "正在读文档结构",
    "render_document": "正在生成文档",
    "edit_document": "正在改文档",
    "verify_document": "正在核对文档",
    "edit_docx_document": "正在改 Word",
    "edit_pptx_document": "正在改课件",
    "generate_image": "正在出图",
    "workspace_write_file": "正在落盘",
    "workspace_list_files": "正在列文件",
    "workspace_read_file": "正在读文件",
    "verify_html_document": "正在核对网页",
    "web_search": "正在检索",
    "web_fetch": "正在阅读网页",
    "kb_search": "正在查材料",
}

_DONE: dict[str, str] = {
    "generate_html_document": "已写网页",
    "generate_docx_document": "已写 Word",
    "generate_pptx_document": "已写课件",
    "inspect_document": "已读文档结构",
    "render_document": "已生成文档",
    "edit_document": "已改文档",
    "verify_document": "已核对文档",
    "edit_docx_document": "已改 Word",
    "edit_pptx_document": "已改课件",
    "generate_image": "已出图",
    "workspace_write_file": "已落盘",
    "workspace_list_files": "已列文件",
    "workspace_read_file": "已读文件",
    "verify_html_document": "已核对网页",
    "web_search": "已检索到来源",
    "web_fetch": "已读页",
    "kb_search": "已查到材料",
}

_FAIL: dict[str, str] = {
    "generate_html_document": "没写成网页",
    "generate_docx_document": "没写成 Word",
    "generate_pptx_document": "没写成课件",
    "inspect_document": "没读成文档结构",
    "render_document": "没生成文档",
    "edit_document": "没改成文档",
    "verify_document": "文档核对未完成",
    "edit_docx_document": "没改成 Word",
    "edit_pptx_document": "没改成课件",
    "generate_image": "没出成图",
    "workspace_write_file": "没落成盘",
    "workspace_list_files": "没列出文件",
    "workspace_read_file": "没读成文件",
    "verify_html_document": "网页核对未完成",
    "web_search": "检索未完成",
    "web_fetch": "读页未完成",
    "kb_search": "没查到材料",
}

FALLBACK_DOING = "正在调工具"
FALLBACK_DONE = "工具已完成"
FALLBACK_FAIL = "工具没完成"


def workbench_tool_step_line(tool: str) -> str:
    """One Chinese in-flight line. Empty only when the tool name is empty."""
    name = (tool or "").strip()
    if not name:
        return ""
    return _DOING.get(name, FALLBACK_DOING)


def workbench_tool_result_line(tool: str, *, ok: bool) -> str:
    name = (tool or "").strip()
    if not name:
        return FALLBACK_DONE if ok else FALLBACK_FAIL
    table = _DONE if ok else _FAIL
    fallback = FALLBACK_DONE if ok else FALLBACK_FAIL
    return table.get(name, fallback)


def tool_result_failed(result: Any) -> bool:
    if not isinstance(result, dict):
        return False
    if result.get("ok") is False:
        return True
    err = result.get("error")
    return bool(err)


def failed_write_user_message(tool_results: list[tuple[str, dict[str, Any]]] | None) -> str | None:
    """If write/edit tools ran and none succeeded, Chinese why. Else None."""
    attempted = 0
    succeeded = 0
    last_err: str | None = None
    last_code: str | None = None
    for name, value in tool_results or []:
        if name not in WRITE_TOOLS:
            continue
        attempted += 1
        if not isinstance(value, dict) or not tool_result_failed(value):
            succeeded += 1
            continue
        err = value.get("error") or value.get("message") or value.get("user_message")
        last_err = str(err) if err else last_err
        code = value.get("code")
        if isinstance(code, str) and code.strip():
            last_code = code.strip()
    if attempted == 0 or succeeded > 0:
        return None
    from pico_orchestrator.user_errors import user_message_for_error

    return user_message_for_error(last_err, code=last_code)
