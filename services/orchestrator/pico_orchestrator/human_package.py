"""Human-facing delivery package — strip machine jargon from final_text.

Ledger / events remain the engineer source of truth (verify, L0, artifact_id).
User-visible chat must default to filenames + how to open, never a self-check report.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from typing import Any

# Titles that are bookkeeping, not user downloads.
_BOOKKEEPING = frozenset({"回复摘要", "summary", "run summary"})

# Machine fields / review jargon that must not appear in the main bubble.
_JARGON_LINE = re.compile(
    r"(?im)^[ \t]*(?:"
    r"artifact[_\s-]?id|verification_level|interaction_status|"
    r"source_wall|content_encoding|L0[_ ]?structure|L1[_ ]?(?:browser|交互)?|"
    r"min_artifacts|min_required|run[_\s-]?id|task[_\s-]?id|"
    r"not_run|not_verified|账本|机读|delivery\.summary|"
    r"overall\s*[:=]\s*(?:pass|fail|partial)|"
    r"checks\s*[:=]|honest_note\s*[:=]"
    r").*$"
)

_JARGON_INLINE = re.compile(
    r"(?i)\b(?:artifact_id|verification_level|interaction_status|source_wall|"
    r"content_encoding|L0_structure|min_artifacts)\b\s*[:=]?\s*`?[\w\-.]+`?"
)

# Full HTML document pasted into chat (source wall).
_HTML_DOC = re.compile(
    r"(?is)(?:```(?:html|htm)?\s*)?<!DOCTYPE\s+html\b.*?</html\s*>\s*(?:```)?|"
    r"(?:```(?:html|htm)?\s*)?<html\b.*?</html\s*>\s*(?:```)?"
)

# Long fenced HTML without doctype still hurts.
_FENCED_HTML = re.compile(r"(?is)```(?:html|htm)\s*\n.*?\n```")

_MARKDOWN_TABLE_L0 = re.compile(
    r"(?im)^\|[^\n]*(?:L0|L1|verification|interaction_status|artifact)[^\n]*\|\s*\n"
    r"(?:\|[^\n]*\|\s*\n)+"
)

# Tool/process chrome that must not linger in the user main bubble (G2).
_PROCESS_LINE = re.compile(
    r"(?m)^[ \t]*[〔\[]?(?:"
    r"调用工具|工具完成|步骤\s*\d+|检查点已保存|仍在处理|正在思考|正在准备"
    r")[^〕\]]*[〕\]]?[ \t]*$"
)
_PROCESS_INLINE = re.compile(
    r"[〔\[](?:调用工具[^〕\]]*|工具完成|步骤\s*\d+|检查点已保存)[〕\]]"
)


def is_bookkeeping_title(title: str | None) -> bool:
    t = (title or "").strip()
    if not t:
        return True
    if t in _BOOKKEEPING:
        return True
    return t.lower() in _BOOKKEEPING


def titles_from_tool_results(
    tool_results: Iterable[tuple[str, dict[str, Any]]] | None,
) -> list[str]:
    """Collect human download titles from write/generate tool results."""
    if not tool_results:
        return []
    out: list[str] = []
    seen: set[str] = set()
    write_tools = {
        "workspace_write_file",
        "generate_html_document",
        "generate_docx_document",
        "generate_pptx_document",
    }
    for name, value in tool_results:
        if name not in write_tools or not isinstance(value, dict):
            continue
        title = value.get("title") or value.get("user_label")
        if not isinstance(title, str):
            continue
        title = title.strip()
        if not title or is_bookkeeping_title(title):
            continue
        key = title.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(title)
    return out


def _strip_html_dumps(text: str) -> str:
    text = _HTML_DOC.sub("", text)
    text = _FENCED_HTML.sub("", text)
    return text


def _strip_jargon(text: str) -> str:
    text = _MARKDOWN_TABLE_L0.sub("", text)
    text = _PROCESS_INLINE.sub("", text)
    lines: list[str] = []
    for line in text.splitlines():
        if _JARGON_LINE.search(line):
            continue
        if _PROCESS_LINE.search(line):
            continue
        cleaned = _JARGON_INLINE.sub("", line)
        # Drop leftover empty bullet rows after inline strip.
        if cleaned.strip() in {"-", "*", "·", "•", "|", "||"}:
            continue
        lines.append(cleaned)
    text = "\n".join(lines)
    # Collapse 3+ blank lines.
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _human_card(titles: list[str]) -> str:
    if not titles:
        return ""
    if len(titles) == 1:
        name = titles[0]
        return (
            f"已准备好文件：**{name}**\n"
            f"请在右侧「结果 / 产物」区点击 **下载** 或 **打开**。"
            f"HTML 请用浏览器本地打开使用。\n"
            f"若要改内容，直接说即可。"
        )
    bullets = "\n".join(f"- **{t}**" for t in titles)
    return (
        f"已准备好 {len(titles)} 个可下载文件：\n{bullets}\n\n"
        f"请在右侧「结果 / 产物」区逐一点 **下载**（文件名优先，勿找 ID）。\n"
        f"需要调整哪一份，直接说文件名即可。"
    )


def _mentions_titles(text: str, titles: list[str]) -> bool:
    if not titles:
        return True
    lower = text.lower()
    hits = 0
    for t in titles:
        base = t.rsplit("/", 1)[-1].strip()
        if base and base.lower() in lower:
            hits += 1
    # At least half of titles (or 1) mentioned.
    need = 1 if len(titles) == 1 else max(1, (len(titles) + 1) // 2)
    return hits >= need


def sanitize_user_facing_text(
    text: str,
    *,
    artifact_titles: list[str] | None = None,
    force_card_if_artifacts: bool = True,
) -> str:
    """Return chat-safe text: human package, no full HTML dump, no machine self-check."""
    raw = (text or "").strip()
    titles = [t.strip() for t in (artifact_titles or []) if t and not is_bookkeeping_title(t)]
    # Preserve unique order.
    seen: set[str] = set()
    uniq: list[str] = []
    for t in titles:
        k = t.lower()
        if k in seen:
            continue
        seen.add(k)
        uniq.append(t)
    titles = uniq

    if not raw and not titles:
        return ""

    stripped = _strip_html_dumps(raw)
    stripped = _strip_jargon(stripped)

    had_html_dump = bool(_HTML_DOC.search(raw) or _FENCED_HTML.search(raw))
    # If model only pasted source / jargon and we have files → replace with card.
    if titles and (not stripped or had_html_dump or len(stripped) < 12):
        return _human_card(titles)

    if titles and force_card_if_artifacts and not _mentions_titles(stripped, titles):
        card = _human_card(titles)
        if stripped:
            return f"{stripped.rstrip()}\n\n---\n{card}"
        return card

    if had_html_dump and titles:
        note = "（完整 HTML 已写入可下载文件，聊天中不再贴源码。）"
        if stripped:
            return f"{stripped.rstrip()}\n\n{note}\n\n{_human_card(titles)}"
        return _human_card(titles)

    return stripped


def engineer_trace_note() -> str:
    """Short pointer for docs — not for user chat."""
    return "Engineer trace: delivery.summary + tool results + /v1/artifacts; not final_text."
