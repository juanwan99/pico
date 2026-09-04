"""edu-core sidebar propose — explicit marker only. Not NL heuristics."""

from __future__ import annotations

import json
from typing import Any

from pico_orchestrator.capability_loading import CORE_VISIBLE_TOOLS

JSON_ONLY_OUTPUT = "json_only_no_files"
_JSON_KEY_COMPACT = '"output":"json_only_no_files"'
_JSON_KEY_SPACED = '"output": "json_only_no_files"'

HONEST_MISS_SUMMARY = "网上没查到。没有可用网页来源，不能报日期或校外结论。"
SIDEBAR_WEB_SYSTEM = (
    "网搜已执行。校外事实和日期只能写 webHits 里有的。"
    "webHits.honest_miss 或 retrieved=false：summary 必须明说没查到，"
    "禁止写「我在网上查的」，禁止自报训练截止日期或瞎日期。"
    "有来源：标明来自网。"
)
SIDEBAR_WORKBENCH_HINT = (
    "侧栏优先操控和填写左边当前页；确认后走学校原命令。"
    "出文档、出图、改文件、落盘用和 Pico 工作台同一套手，不要因为在侧栏就少工具或推去另一个窗。"
    "分级读：人没点名要格子或全文时，只认当前页名/文件名，不要把切片当成全表，不要声称已读完全文。"
    "人要处理、拆格、填表、对数据时必须读齐：上传文件用 inspect_document，"
    "看 leftover_rows / leftover_cols，用 start_row / start_col 接着读，直到两者都是 0。"
    "左边打开的表：page.table 只是当前屏切片（学校最多塞 16 列×12 行），不是全量。"
    "切片不够就说明还没读完，不要按切片列数去插列；学校分页口未到之前，先按已见格子+空列填。"
    "工具结果回来后再决定下一手。看不清、对不上、失败了就换手或问一句，不要一轮空口说完。"
    "学校数据表最多 40 个字段（含隐藏列和右侧空字母列）。"
    "拆「学科 / 姓名」用 fill_cells：原格留学科，右侧已有空列写姓名；c 可以大于 page.table 列数。"
    "不要靠 insert_col 扩列。insert_col 失败「最多 40 个字段」立刻停插，改填已有空列。"
    "fill_cells 每条最多约 80 格，多了分多条。没有空列才说明人先删空列，不要再插。"
)

# Same CORE hands as workbench. Not a second, smaller tool set.
EDU_SIDEBAR_DEFAULT_TOOLS: tuple[str, ...] = CORE_VISIBLE_TOOLS
EDU_SIDEBAR_ALLOWED_TOOLS = frozenset(EDU_SIDEBAR_DEFAULT_TOOLS)


def sidebar_chat_only(*, edu_sidebar: bool, json_only: bool) -> bool:
    """json_only stays one-shot. Edu sidebar is not chat_only: it enters Pi.

    Never force_agent from a prompt guess. Hands are CORE, same as workbench.
    """
    del edu_sidebar
    return bool(json_only)


def edu_sidebar_tool_ceiling(request_tools: list[str] | None) -> list[str] | None:
    """None = CORE (workbench default). Edu empty/web-only lists are not a castration."""
    del request_tools
    return None


def with_sidebar_workbench_hint(system: str | None) -> str:
    if system and SIDEBAR_WORKBENCH_HINT in system:
        return system
    if system:
        return f"{system}\n{SIDEBAR_WORKBENCH_HINT}"
    return SIDEBAR_WORKBENCH_HINT


def is_json_only_propose(
    prompt: str | None,
    *,
    output_header: str | None = None,
) -> bool:
    """True only for the edu sidebar contract. Workbench chat stays false."""
    header = output_header if isinstance(output_header, str) else ""
    header = header.strip()
    if header == JSON_ONLY_OUTPUT:
        return True
    text = prompt or ""
    return _JSON_KEY_COMPACT in text or _JSON_KEY_SPACED in text


def asked_from_sidebar_prompt(prompt: str | None) -> str:
    text = str(prompt or "").strip()
    if not text:
        return ""
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return text[:500]
    if isinstance(parsed, dict) and parsed.get("asked") is not None:
        return str(parsed.get("asked") or "").strip()[:500]
    return text[:500]


def shape_web_hits(raw: dict[str, Any] | None) -> dict[str, Any]:
    row = raw if isinstance(raw, dict) else {}
    sources: list[dict[str, str]] = []
    for item in row.get("sources") or []:
        if not isinstance(item, dict):
            continue
        url = str(item.get("url") or "").strip()
        if not url:
            continue
        sources.append(
            {
                "title": str(item.get("title") or item.get("name") or "").strip()[:200],
                "url": url[:400],
                "snippet": str(item.get("snippet") or item.get("excerpt") or "").strip()[:280],
            }
        )
        if len(sources) >= 6:
            break
    retrieved = bool(row.get("retrieved")) and bool(sources)
    message = str(row.get("message") or "").strip()
    if not retrieved and not message:
        message = "未检索到可用来源"
    return {
        "retrieved": retrieved,
        "honest_miss": (not retrieved) or bool(row.get("honest_miss")),
        "message": message[:240],
        "sources": sources,
        "teacher_sources_md": str(row.get("teacher_sources_md") or "")[:800],
    }


def inject_web_hits(prompt: str | None, hits: dict[str, Any] | None) -> str:
    text = str(prompt or "")
    payload = shape_web_hits(hits)
    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict):
            parsed["webHits"] = payload
            return json.dumps(parsed, ensure_ascii=False)
    except json.JSONDecodeError:
        pass
    return text + "\n" + json.dumps({"webHits": payload}, ensure_ascii=False)


def honest_miss_json(hits: dict[str, Any] | None = None) -> str:
    shaped = shape_web_hits(hits)
    return json.dumps(
        {
            "summary": shaped.get("message") or HONEST_MISS_SUMMARY,
            "mutations": [],
            "draft": None,
            "bindSuggestions": [],
        },
        ensure_ascii=False,
    )
