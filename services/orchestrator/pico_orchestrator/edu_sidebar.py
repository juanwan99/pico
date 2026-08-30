"""edu-core sidebar propose — explicit marker only. Not NL heuristics."""

from __future__ import annotations

import json
from typing import Any

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
    "侧栏只填当前页。改已有 Word/PPT 或出图，请去 Pico 工作台。"
    "本侧栏不得调用 generate_* / edit_* / 出图，不得落 Artifact。"
)

# Sidebar may enter Pi. Never inherit office CORE. Later page verbs join this set.
EDU_SIDEBAR_ALLOWED_TOOLS = frozenset({"web_search", "web_fetch"})


def sidebar_chat_only(*, edu_sidebar: bool, json_only: bool) -> bool:
    """json_only stays one-shot. Edu sidebar is not chat_only: it enters Pi.

    Still never force_agent / land artifacts: no skill guess, request tool ceiling.
    """
    del edu_sidebar
    return bool(json_only)


def edu_sidebar_tool_ceiling(request_tools: list[str] | None) -> list[str]:
    """Empty list = Pi with no tools. None must not fall through to CORE office tools."""
    if not request_tools:
        return []
    return [t for t in request_tools if t in EDU_SIDEBAR_ALLOWED_TOOLS]


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
