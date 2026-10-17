"""Human-facing delivery package — strip machine jargon from final_text.

Ledger / events remain the engineer source of truth (verify, L0, artifact_id).
User-visible chat must default to filenames + how to open, never a self-check report.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from typing import Any

# Official plan-mode TUI chrome that must not enter the teacher bubble.
_ANSI_RE = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")
_EXECUTE_PLAN_LINE = re.compile(r"(?im)^[ \t]*execute the plan\b.*$")
_PLAN_STATUS_CHROME = re.compile(r"(?i)(?:⏸\s*plan|📋\s*\d+/\d+|plan mode)")

# Titles that are bookkeeping, not user downloads.
_BOOKKEEPING = frozenset({"回复摘要", "summary", "run summary"})

# Teacher-facing identity is Pico. Strip first-person backend-model claims.
_MODEL_BRAND = (
    r"(?:GPT-?[\w.]*|ChatGPT|Claude[\w.-]*|DeepSeek[\w.-]*|Gemini[\w.-]*|"
    r"Kimi|通义千问|通义|豆包|Qwen[\w.-]*|GLM-?[\w.]*)"
)
_MODEL_SELF_INLINE = re.compile(
    rf"(?i)(?:我是|我叫|本模型是|底层模型是|I'm|I am|I['’]m)\s+"
    rf"(?:一个?)?{_MODEL_BRAND}\b"
)
_PICO_ID_FLUFF_ZH = re.compile(r"我是 Pico\s*(?:开发的)?(?:助手|大模型|语言模型)")
_PICO_ID_FLUFF_EN = re.compile(r"(?i)I am Pico(?:\s+language model|\s+AI assistant|\s+assistant)")

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


# Full HTML document pasted into chat (source wall).
_HTML_DOC = re.compile(
    r"(?is)(?:```(?:html|htm)?\s*)?<!DOCTYPE\s+html\b.*?</html\s*>\s*(?:```)?|"
    r"(?:```(?:html|htm)?\s*)?<html\b.*?</html\s*>\s*(?:```)?"
)

# Long fenced HTML without doctype still hurts.
_FENCED_HTML = re.compile(r"(?is)```(?:html|htm)\s*\n.*?\n```")


# Tool/process chrome that must not linger in the user main bubble (G2).
# Long process diaries are stripped; short mid-run UI chrome is not final_text.
_PROCESS_LINE = re.compile(
    r"(?m)^[ \t]*[〔\[]?(?:"
    r"调用工具|工具完成|步骤\s*\d+|检查点已保存|仍在处理|正在思考|正在准备|"
    r"正在写|正在改|正在调工具|正在落盘|正在出图|正在画|正在列文件|正在读文件|"
    r"正在检索|正在阅读|正在核对"
    r")[^〕\]]*[〕\]]?[ \t]*$"
)
# Model status headlines that landed as assistant text (**Generating …**).
_EN_PROCESS_HEADLINE = re.compile(
    r"(?im)^[ \t]*\*\*(?:Generating|Finalizing|Creating|Writing|Drawing|Building)[^*]{0,80}\*\*[ \t]*$"
)

# L0 / structure self-check engineer wall (#394 Y1) — main bubble never a lab report.
# Structural phrases from verify_html honest_note or model paraphrases.
_L0_SELFCHECK_LINE = re.compile(
    r"(?im)^[ \t]*(?:"
    r".*(?:结构自检|静态自检|系统侧|二进制编码|content_encoding|"
    r"verification_level|interaction_status|"
    r"未做浏览器|未经真机|真机点击|无头浏览器|"
    r"未宣称\s*L1|不夸大其可用性|写入账本|"
    r"机读字段|自检说明|L0[_ ]?structure|L1[_ ]?(?:browser|交互)?).*"
    r"|[ \t]*verify\b.*(?:base64|不可读|二进制|系统侧|复读).*"
    r"|[ \t]*正在准备[.。…]*[ \t]*"
    r")$"
)
# Mid-paragraph L0 walls when the model packs self-check into one long line with product copy.
_ENGINEER_VERIFY_LINE = _L0_SELFCHECK_LINE
# Pure engineer EN self-check lines (no Chinese product copy mixed in).
_ENGINEER_EN_LINE = re.compile(
    r"(?im)^[ \t]*(?:Now\s+)?(?:let me|I'll|I will|I need to)\b.*"
    r"(?:verification|system-side|structure\s*check|self-?check).*$"
)
# Do not use _ENGINEER_EN_LINE alone to drop mixed EN+中文 lines — strip inline first.


# Tool-parameter monologue / planning diary (#384 / T-FIX-MAIN-BUBBLE-CLEAN).
# Structural patterns — not a per-prompt denylist.
_TOOL_MONOLOGUE_LINE = re.compile(
    r"(?im)^[ \t]*(?:"
    r".*\b(?:generate_(?:html|docx|pptx)_document|workspace_write(?:_file)?)\b.*|"
    r".*(?:JSON\s*escape|escape\s*JSON|body\s*参数|tool\s*参数|"
    r"function\.arguments|tool_calls?)\b.*|"
    r"(?:Let me|I'll|I will|I need to|First|Next|Then)\b.*"
    r"(?:tool|function|generate_|workspace_write|argument|parameter|JSON|escape|"
    r"verification|system-side|HTML|quiz|document|interactive).*"
    r"|The\s+(?:verify|generate|workspace)\w*(?:\s+(?:tool|function|schema))?\b.*"
    r"|All\s+(?:(?:\d+|[A-Za-z]+)\s+)?deliverables?\s+(?:are|were|have\s+been|is|has\s+been)\s+(?:created|generated|delivered|prepared|completed)\b.*"
    r"|\bpassed\s+(?:the\s+)?verification\b.*"
    r"|(?:我先|让我|我将|接下来|首先)\b.*(?:工具|参数|转义|落盘|写文件|构造|校验).*"
    r")$"
)
_TOOL_MONOLOGUE_BLOCK = re.compile(
    # Bound engineer planning clauses; stop before Chinese product copy when possible.
    r"(?is)(?:(?:Now\s+)?Let me (?:build|construct|call|prepare|write|run|create|make|confirm|finalize)\b[^\n\u4e00-\u9fff]{0,200}"
    r"|I'll (?:use|call|invoke|write|run|create|build|make|confirm|finalize)\b[^\n\u4e00-\u9fff]{0,200}"
    r"|I will (?:use|call|create|build|make|write|confirm|finalize)\b[^\n\u4e00-\u9fff]{0,200}"
    r"|I need to (?:call|use|invoke|run|create|build)\b[^\n\u4e00-\u9fff]{0,160}"
    r"|I['’]ve (?:delivered|generated|created|prepared|completed)\b[^\n\u4e00-\u9fff]{0,200}"
    r"|All\s+(?:(?:\d+|[A-Za-z]+)\s+)?files?\s+(?:are|were|have\s+been)?\s*delivered\b[^\n\u4e00-\u9fff]{0,200}"
    r"|All\s+(?:(?:\d+|[A-Za-z]+)\s+)?deliverables?\s+(?:are|were|have\s+been|is|has\s+been)\s+(?:created|generated|delivered|prepared|completed)\b[^\n\u4e00-\u9fff]{0,200}"
    r"|\bdeliverables?\s+(?:are|were|is|have\s+been)\s+(?:created|generated|delivered)\b[^\n\u4e00-\u9fff]{0,200}"
    r"|\bpassed\s+(?:the\s+)?verification\b[^\n\u4e00-\u9fff]{0,160}"
    r"|The\s+(?:[A-Za-z]+\s+){0,5}passed\s+(?:the\s+)?verification\b[^\n\u4e00-\u9fff]{0,160}"
    r"|Here(?:['’]s| is)\s+the\s+(?:final\s+)?delivery\s+summary\b[^\n\u4e00-\u9fff]{0,160}"
    r"|Let\s+me\s+(?:confirm|finalize|verify|summarize)\b[^\n\u4e00-\u9fff]{0,160}"
    r"|The\s+(?:verify|generate|workspace)\w*(?:\s+(?:tool|function|schema))?\b[^\n\u4e00-\u9fff]{0,240}"
    r"|我先(?:构造|准备|调用)[^\n]{0,80}"
    r"|让我(?:构造|调用|写)[^\n]{0,80})"
)
# 「正在准备…」mid-run chrome that must not linger once the bubble is settled.
_TOOL_NAME_BARE = re.compile(
    r"(?i)\b(?:generate_(?:html|docx|pptx)_document|workspace_write_file|"
    r"verify_html_document)\b"
)


def _is_office_title(title: str) -> bool:
    return title.lower().endswith((".pptx", ".docx", ".xlsx"))


def _is_image_title(title: str) -> bool:
    return title.lower().endswith((".png", ".jpg", ".jpeg", ".gif", ".webp"))


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
        "sandbox_pptx_lib",
        "sandbox_office_lib",
        "generate_xlsx_document",
        "edit_docx_document",
        "edit_pptx_document",
        "edit_xlsx_document",
        "render_document",
        "generate_image",
        "generate_diagram",
    }
    image_tools = {"generate_image", "generate_diagram"}
    collected: list[tuple[str, str]] = []
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
        collected.append((name, title))
    has_office = any(_is_office_title(title) for _name, title in collected)
    for name, title in collected:
        if has_office and (name in image_tools or _is_image_title(title)):
            continue
        out.append(title)
    return out


def _strip_html_dumps(text: str) -> str:
    text = _HTML_DOC.sub("", text)
    text = _FENCED_HTML.sub("", text)
    return text


def _pico_self_repl(match: re.Match[str]) -> str:
    lead = match.group(0)
    if re.search(r"(?i)\bi(?:\s+am|['’]m)\b", lead):
        return "I am Pico"
    return "我是 Pico"


def _strip_model_identity(text: str) -> str:
    """Swap first-person backend-model claims to Pico. Leave third-party mentions."""
    raw = text or ""
    if not raw.strip():
        return raw
    out = _MODEL_SELF_INLINE.sub(_pico_self_repl, raw)
    out = _PICO_ID_FLUFF_ZH.sub("我是 Pico", out)
    return _PICO_ID_FLUFF_EN.sub("I am Pico", out)


def looks_like_tool_monologue(text: str) -> bool:
    """True when the blob is mostly tool-planning diary (for stream gates)."""
    raw = (text or "").strip()
    if not raw:
        return False
    if _TOOL_MONOLOGUE_BLOCK.search(raw):
        return True
    if _TOOL_NAME_BARE.search(raw) and len(raw) < 800:
        # Bare tool name in a short bubble is almost never user-facing product copy.
        return True
    lines = [ln for ln in raw.splitlines() if ln.strip()]
    if not lines:
        return False
    hits = sum(
        1
        for ln in lines
        if _TOOL_MONOLOGUE_LINE.search(ln)
        or _PROCESS_LINE.search(ln)
        or _EN_PROCESS_HEADLINE.search(ln)
        or _JARGON_LINE.search(ln)
        or _ENGINEER_EN_LINE.search(ln)
        or _L0_SELFCHECK_LINE.search(ln)
    )
    return hits >= max(1, (len(lines) + 1) // 2)


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


def strip_ansi(text: str | None) -> str:
    """Drop VT/ANSI color codes leaked by official plan-mode TUI paint()."""
    if not text:
        return ""
    return _ANSI_RE.sub("", str(text))


def is_plan_passphrase(text: str | None) -> bool:
    """True for official 'Execute the plan*' / plan-mode status chrome."""
    raw = strip_ansi(text).strip()
    if not raw:
        return False
    if _EXECUTE_PLAN_LINE.search(raw):
        return True
    if raw.lower().startswith("execute the plan"):
        return True
    return bool(_PLAN_STATUS_CHROME.search(raw) and len(raw) < 80)


def public_progress_delta(payload: dict[str, Any] | None) -> str:
    """User-bubble line for plan.progress. Empty = do not stream chrome/passphrase."""
    data = payload or {}
    raw = strip_ansi(str(data.get("text") or "")).strip()
    custom = str(data.get("customType") or "")
    method = str(data.get("method") or "")
    if not raw:
        return ""
    if is_plan_passphrase(raw) or custom == "plan-mode-execute":
        return ""
    if method == "setStatus":
        return ""
    if custom == "plan-todo-list":
        return "正在整理步骤"
    if method == "setWidget":
        return "正在按步骤办理"
    return ""


def sanitize_user_facing_text(
    text: str,
    *,
    artifact_titles: list[str] | None = None,
    force_card_if_artifacts: bool = True,
) -> str:
    """Chat-safe text: no pasted page source, no model / provider name. Nothing else."""
    del force_card_if_artifacts
    raw = strip_ansi(text or "").strip()
    raw = _EXECUTE_PLAN_LINE.sub("", raw).strip()
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
    stripped = _strip_model_identity(stripped)

    # The model's own words stand (pico#1320). Only an empty reply — e.g. it pasted
    # nothing but page source — gets a plain download line so the bubble is not blank.
    if titles and not stripped.strip():
        return _human_card(titles)
    return stripped






def engineer_trace_note() -> str:
    """Short pointer for docs — not for user chat."""
    return "Engineer trace: delivery.summary + tool results + /v1/artifacts; not final_text."
