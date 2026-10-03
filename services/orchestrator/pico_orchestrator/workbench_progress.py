"""Map true-Pi tool events to short Chinese workbench progress.

Thin adapter only: names already on the ledger, no second progress engine,
no fake percentages.

generate_docx / generate_pptx / sandbox_pptx_lib strings remain so *old*
ledger events still render; they are not live teacher tools.
"""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import urlparse

# Tools that create or edit a user-visible downloadable artifact.
WRITE_TOOLS = frozenset(
    {
        "workspace_write_file",
        "generate_html_document",
        "generate_docx_document",
        "generate_pptx_document",
        "sandbox_pptx_lib",
        "sandbox_office_lib",
        "generate_xlsx_document",
        "edit_docx_document",
        "edit_pptx_document",
        "edit_xlsx_document",
        "render_document",
        "generate_image",
        "generate_diagram",
        "workspace_output",
    }
)

# In-flight line shown while that tool is running.
_DOING: dict[str, str] = {
    "generate_html_document": "正在写网页",
    "generate_docx_document": "正在写 Word",
    "generate_pptx_document": "正在写 PPT",
    "sandbox_pptx_lib": "正在沙箱排 PPT",
    "sandbox_office_lib": "正在沙箱写办公文件",
    "read_office_skill": "正在读办公工艺",
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
    "publish_html_page": "发布不是 Pico 能力",
    "unpublish_html_page": "正在撤回遗留公开页",
    "ask_user": "在等你选",
    "propose_page_mutation": "正在拟左边这页的改动",
    "memory_read": "正在读记忆",
    "memory_write": "正在记进记忆",
    "memory_search": "正在查记忆",
    "sandbox_document_open": "正在打开文档",
    "sandbox_browser_open": "正在阅读网页",
}

_DONE: dict[str, str] = {
    "generate_html_document": "已写网页",
    "generate_docx_document": "已写 Word",
    "generate_pptx_document": "已写 PPT",
    "sandbox_pptx_lib": "已沙箱排 PPT",
    "sandbox_office_lib": "已沙箱写出办公文件",
    "read_office_skill": "已读办公工艺",
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
    "publish_html_page": "未公开发布",
    "unpublish_html_page": "已撤回遗留公开页",
    "ask_user": "已选",
    "propose_page_mutation": "已拟一条改动，等你确认",
}

_FAIL: dict[str, str] = {
    "generate_html_document": "没写成网页",
    "generate_docx_document": "没写成 Word",
    "generate_pptx_document": "没写成 PPT",
    "sandbox_pptx_lib": "没沙箱排出 PPT",
    "sandbox_office_lib": "没沙箱写出办公文件",
    "read_office_skill": "没读到办公工艺",
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
    "publish_html_page": "发布被拒绝（走 Edu 校管批准）",
    "unpublish_html_page": "没撤回遗留公开页",
    "ask_user": "超时未选",
    "propose_page_mutation": "这条改动没拟成",
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


# Pi builtins plus tools whose argument says what this step works on.
_PATH_VERB: dict[str, str] = {"read": "正在读", "write": "正在写", "edit": "正在改"}
_QUERY_VERB: dict[str, str] = {
    "web_search": "正在检索",
    "kb_search": "正在查材料",
    "memory_search": "正在查记忆",
}
_URL_TOOLS = frozenset({"web_fetch", "sandbox_browser_open"})
_DETAIL_MAX = 40


def _short(text: str) -> str:
    one = re.sub(r"\s+", " ", text).strip()
    return one if len(one) <= _DETAIL_MAX else one[: _DETAIL_MAX - 1] + "…"


def _arg(args: dict[str, Any], *keys: str) -> str:
    for key in keys:
        value = args.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def workbench_call_step_line(tool: str, args: dict[str, Any] | None) -> str:
    """In-flight line naming what this call works on (「正在读 教案.docx」).

    Falls back to the tool-only line when the arguments name nothing.
    """
    name = (tool or "").strip()
    base = workbench_tool_step_line(name)
    a = args if isinstance(args, dict) else {}
    detail = ""
    if name in _PATH_VERB:
        path = _arg(a, "path").rstrip("/")
        if path:
            return f"{_PATH_VERB[name]} {_short(path.rsplit('/', 1)[-1])}"
    elif name == "bash":
        first = _arg(a, "command").splitlines()[0] if _arg(a, "command") else ""
        first = re.sub(r"^cd\s+\S+\s*&&\s*", "", first)
        first = re.sub(r"/workspace\b/?", "", first)
        if first.strip():
            return f"正在执行：{_short(first)}"
    elif name in _QUERY_VERB:
        detail = _arg(a, "query")
        if detail:
            return f"{_QUERY_VERB[name]}：{_short(detail)}"
    elif name in _URL_TOOLS:
        host = urlparse(_arg(a, "url")).netloc
        if host:
            return f"正在阅读网页：{host.removeprefix('www.')}"
    else:
        detail = _arg(a, "title", "filename")
    return f"{base}：{_short(detail)}" if detail and base else base


# Pi builtins whose arguments are the work itself (a whole file / script).
_DRAFTING: dict[str, str] = {
    "write": "正在写文件",
    "edit": "正在改文件",
    "bash": "正在写脚本",
}


def workbench_drafting_line(tool: str, chars: int) -> str:
    """Line while a tool call's arguments are still being generated."""
    name = (tool or "").strip()
    base = _DRAFTING.get(name) or workbench_tool_step_line(name) or FALLBACK_DOING
    kb = max(0, int(chars or 0)) // 1024
    return f"{base}（已写 {kb} KB）" if kb else f"{base}…"


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
