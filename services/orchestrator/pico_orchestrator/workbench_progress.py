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
        "sandbox_pptx_lib",
        "generate_xlsx_document",
        "edit_docx_document",
        "edit_pptx_document",
        "edit_xlsx_document",
        "render_document",
        "generate_image",
        "generate_diagram",
    }
)

# In-flight line shown while that tool is running.
_DOING: dict[str, str] = {
    "generate_html_document": "正在写网页",
    "generate_docx_document": "正在写 Word",
    "generate_pptx_document": "正在写 PPT",
    "sandbox_pptx_lib": "正在沙箱排 PPT",
    "generate_xlsx_document": "正在写表格",
    "edit_docx_document": "正在改 Word",
    "edit_pptx_document": "正在改 PPT",
    "edit_xlsx_document": "正在改表格",
    "render_document": "正在排文档",
    "inspect_document": "正在读文档结构",
    "verify_document": "正在核对文档",
    "generate_image": "正在出图",
    "generate_diagram": "正在画结构图",
    "workspace_write_file": "正在落盘",
    "workspace_list_files": "正在列文件",
    "workspace_read_file": "正在读文件",
    "verify_html_document": "正在核对网页",
    "web_search": "正在检索",
    "web_fetch": "正在阅读网页",
    "kb_search": "正在查材料",
    "publish_html_page": "正在发布网页",
    "unpublish_html_page": "正在撤回网页",
    "ask_user": "在等你选",
}

_DONE: dict[str, str] = {
    "generate_html_document": "已写网页",
    "generate_docx_document": "已写 Word",
    "generate_pptx_document": "已写 PPT",
    "sandbox_pptx_lib": "已沙箱排 PPT",
    "generate_xlsx_document": "已写表格",
    "edit_docx_document": "已改 Word",
    "edit_pptx_document": "已改 PPT",
    "edit_xlsx_document": "已改表格",
    "render_document": "已排文档",
    "inspect_document": "已读文档结构",
    "verify_document": "已核对文档",
    "generate_image": "已出图",
    "generate_diagram": "已画结构图",
    "workspace_write_file": "已落盘",
    "workspace_list_files": "已列文件",
    "workspace_read_file": "已读文件",
    "verify_html_document": "已核对网页",
    "web_search": "已检索到来源",
    "web_fetch": "已读页",
    "kb_search": "已查到材料",
    "publish_html_page": "已发布网页",
    "unpublish_html_page": "已撤回网页",
    "ask_user": "已选",
}

_FAIL: dict[str, str] = {
    "generate_html_document": "没写成网页",
    "generate_docx_document": "没写成 Word",
    "generate_pptx_document": "没写成 PPT",
    "sandbox_pptx_lib": "没沙箱排出 PPT",
    "generate_xlsx_document": "没写成表格",
    "edit_docx_document": "没改成 Word",
    "edit_pptx_document": "没改成 PPT",
    "edit_xlsx_document": "没改成表格",
    "render_document": "没排成文档",
    "inspect_document": "没读成文档结构",
    "verify_document": "文档核对未完成",
    "generate_image": "没出成图",
    "generate_diagram": "没画出结构图",
    "workspace_write_file": "没落成盘",
    "workspace_list_files": "没列出文件",
    "workspace_read_file": "没读成文件",
    "verify_html_document": "网页核对未完成",
    "web_search": "检索未完成",
    "web_fetch": "读页未完成",
    "kb_search": "没查到材料",
    "publish_html_page": "没发布成网页",
    "unpublish_html_page": "没撤回网页",
    "ask_user": "超时未选",
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


def sidebar_progress_delta(event_type: str, payload: dict[str, Any] | None) -> str:
    """School rail has no TaskRunBar. Tool process must ride `content`."""
    row = payload if isinstance(payload, dict) else {}
    name = str(row.get("tool") or row.get("name") or "").strip()
    if event_type == "tool.call":
        return str(row.get("step_line") or workbench_tool_step_line(name)).strip()
    if event_type != "tool.result":
        return ""
    ok = row.get("ok")
    if ok is None:
        result = row.get("result")
        ok = not tool_result_failed(result) if isinstance(result, dict) else True
    line = workbench_tool_result_line(name, ok=bool(ok))
    extra = str(row.get("user_message") or "").strip()
    if extra and not ok:
        return f"{line}：{extra}"
    return line


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
