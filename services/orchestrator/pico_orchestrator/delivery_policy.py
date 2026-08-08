"""General engineering-delivery policy (multi-artifact / pipeline / revision / runnable).

Intent detection is **generic** — no exam-case keywords, no fixed filenames.
Used to:
  - force multi-step agent + write tools when user wants real packages
  - inject hard delivery instructions into the skill/system block
  - fail-closed when the run claims success without enough artifacts
"""

from __future__ import annotations

import re
from dataclasses import dataclass


# Titles that are bookkeeping, not user deliverables.
_SKIP_TITLES = frozenset({"回复摘要", "工具产物"})

# Explicit multi-file / multi-deliverable phrasing (language-level, not scenario names).
_MULTI_PHRASE = re.compile(
    r"(?:"
    r"独立\s*(?:可下载\s*)?文件|"
    r"分别\s*(?:交付|生成|写出|落盘|下载)|"
    r"分文件|"
    r"多(?:个|份)\s*(?:独立\s*)?(?:文件|产物|交付|文档)|"
    r"(?:三|四|五|六|七|两|2|3|4|5|6|7)\s*个\s*(?:独立\s*)?(?:文件|产物|交付)|"
    r"禁止\s*(?:合并|合成)\s*(?:成\s*)?(?:一|单)\s*(?:个|份)\s*文件|"
    r"not\s+a\s+single\s+file|"
    r"separate\s+(?:files?|artifacts?)|"
    r"(?:three|four|five|two|\d+)\s+separate\s+files?"
    r")",
    re.IGNORECASE,
)

_PIPELINE_PHRASE = re.compile(
    r"(?:"
    r"流水线|"
    r"每阶段|"
    r"各阶段|"
    r"阶段\s*[1-9一二三四五六]|"
    r"步骤\s*[1-9一二三四五六]|"
    r"stage\s*[1-9]|"
    r"pipeline\s+stage"
    r")",
    re.IGNORECASE,
)

_REVISION_PHRASE = re.compile(
    r"(?:"
    r"改成|改为|改一版|改版|修订|更新\s*(?:一下|版本|文件)|"
    r"把.{1,40}(?:改|更新|调整)|"
    r"联动\s*改|"
    r"同步\s*(?:更新|修改)|"
    r"revi(?:se|sion)|update\s+the\s+(?:file|document|artifact)"
    r")",
    re.IGNORECASE,
)

_RUNNABLE_HTML = re.compile(
    r"(?:"
    r"(?:单页\s*)?html|"
    r"本地\s*可打开|"
    r"可\s*打开\s*的\s*(?:网页|页面)|"
    r"自检|"
    r"交互|"
    r"倒计时|"
    r"local\s+html|"
    r"single[- ]?page\s+html"
    r")",
    re.IGNORECASE,
)

# Numbered deliverable lines: "1) foo" / "1. bar" / "① baz" / "阶段1 …"
_NUMBERED_ITEM = re.compile(
    r"(?m)^\s*(?:"
    r"(?:[1-9]|10)[.)、:：]|"
    r"[①②③④⑤⑥⑦⑧⑨⑩]|"
    r"阶段\s*[1-9一二三四五六七八]|"
    r"步骤\s*[1-9一二三四五六七八]|"
    r"Stage\s*[1-9]"
    r")\s*\S+",
    re.IGNORECASE,
)

# Chinese digit map for "三个文件"
_CN_NUM = {
    "两": 2,
    "二": 2,
    "三": 3,
    "四": 4,
    "五": 5,
    "六": 6,
    "七": 7,
}


@dataclass(frozen=True)
class DeliveryPlan:
    """Resolved delivery expectations for one user turn."""

    multi_deliverable: bool
    pipeline: bool
    revision: bool
    runnable_html: bool
    min_artifacts: int
    force_agent: bool
    instruction: str

    @property
    def engineering(self) -> bool:
        return (
            self.multi_deliverable
            or self.pipeline
            or self.revision
            or self.runnable_html
            or self.min_artifacts > 0
        )


def _count_explicit_n_files(text: str) -> int:
    m = re.search(
        r"([2-9]|10|[两二三四五六七])\s*个\s*(?:独立\s*)?(?:文件|产物|交付|文档)",
        text,
    )
    if not m:
        m = re.search(
            r"(?:three|four|five|two|six|seven|\d+)\s+separate\s+files?",
            text,
            re.IGNORECASE,
        )
        if not m:
            return 0
        raw = m.group(0).lower()
        word = {
            "two": 2,
            "three": 3,
            "four": 4,
            "five": 5,
            "six": 6,
            "seven": 7,
        }
        for k, v in word.items():
            if k in raw:
                return v
        dig = re.search(r"\d+", raw)
        return int(dig.group(0)) if dig else 0
    token = m.group(1)
    if token in _CN_NUM:
        return _CN_NUM[token]
    try:
        return int(token)
    except ValueError:
        return 0


def _count_numbered_items(text: str) -> int:
    return len(_NUMBERED_ITEM.findall(text or ""))


def _count_pipeline_stages(text: str) -> int:
    stages = set()
    for m in re.finditer(r"阶段\s*([1-9一二三四五六七八])", text or ""):
        stages.add(m.group(1))
    for m in re.finditer(r"步骤\s*([1-9一二三四五六七八])", text or ""):
        stages.add(m.group(1))
    for m in re.finditer(r"(?i)stage\s*([1-9])", text or ""):
        stages.add(m.group(1))
    if stages:
        return len(stages)
    if _PIPELINE_PHRASE.search(text or ""):
        # Generic pipeline wording without numbers → expect ≥3 stage files.
        return 3
    return 0


def analyze_delivery(prompt: str) -> DeliveryPlan:
    """Derive a DeliveryPlan from natural-language intent (no scenario hardcodes)."""
    text = prompt or ""
    multi_phrase = bool(_MULTI_PHRASE.search(text))
    numbered = _count_numbered_items(text)
    explicit_n = _count_explicit_n_files(text)
    pipeline_n = _count_pipeline_stages(text)
    pipeline = pipeline_n > 0 or bool(_PIPELINE_PHRASE.search(text))
    revision = bool(_REVISION_PHRASE.search(text))
    runnable = bool(_RUNNABLE_HTML.search(text)) and bool(
        re.search(r"(?i)html|网页|页面|page", text)
    )

    multi = multi_phrase or explicit_n >= 2 or (numbered >= 2 and (
        multi_phrase
        or bool(
            re.search(
                r"交付|文件|产物|下载|落盘|文档|说明书|清单|建议|规则|通知",
                text,
            )
        )
    ))

    # Revision of *files* (not casual “改成更短一点” chat polish).
    revision_targets_files = revision and bool(
        re.search(
            r"文件|产物|artifact|阶段|落盘|版本|文档|清单|建议\s*文件|对应文件",
            text,
            re.IGNORECASE,
        )
    )

    min_arts = 0
    if multi:
        min_arts = max(explicit_n, numbered if numbered >= 2 else 0, 2)
    if pipeline:
        min_arts = max(min_arts, pipeline_n if pipeline_n >= 2 else 3)
    if runnable and min_arts == 0:
        min_arts = 1
    if revision_targets_files and min_arts == 0:
        # At least one updated/new artifact when revising prior file deliverables.
        min_arts = 1

    force_agent = multi or pipeline or runnable or revision_targets_files

    instruction = _build_instruction(
        multi=multi,
        pipeline=pipeline,
        revision=revision,
        runnable=runnable,
        min_artifacts=min_arts,
    )
    return DeliveryPlan(
        multi_deliverable=multi,
        pipeline=pipeline,
        revision=revision,
        runnable_html=runnable,
        min_artifacts=min_arts,
        force_agent=force_agent,
        instruction=instruction,
    )


def _build_instruction(
    *,
    multi: bool,
    pipeline: bool,
    revision: bool,
    runnable: bool,
    min_artifacts: int,
) -> str:
    parts: list[str] = [
        "【工程交付纪律 · 通用】",
        "- 短答可不建文件；一旦用户要交付物，必须用工具写入 Artifact 账本，禁止只在聊天里交卷。",
        "- 真 Office/HTML 用 generate_*_document；其它文本/清单/说明用 workspace_write_file。",
        "- 禁止用代码块改后缀冒充 .html/.docx/.pptx。",
        "- 禁止把多个交付物合并成「一个文件里的多个标题」冒充多产物。",
    ]
    if multi or min_artifacts >= 2:
        parts.append(
            f"- 多交付：至少写入 **{max(min_artifacts, 2)}** 个独立 Artifact"
            "（不同 title），每个交付物一次 write/generate 调用。"
        )
    if pipeline:
        parts.append(
            "- 流水线：每个阶段必须落独立文件（阶段号可写在文件名），"
            "不得只在聊天摘要里描述阶段结果。"
        )
    if revision:
        parts.append(
            "- 修订联动：先 workspace_list_files / workspace_read_file 看已有产物，"
            "再对受影响文件写入更新内容或带版本号的新文件名；"
            "未改动的阶段文件保持可追溯，不要无故删除。"
        )
    if runnable:
        parts.append(
            "- 可运行 HTML：生成后调用 verify_html_document 做结构自检；"
            "未实际验证的项必须写「未验证/失败点」，禁止空话「全部完美/已可运行」。"
        )
    if min_artifacts > 0:
        parts.append(
            f"- 本轮成功条件：账本中本 run 至少 {min_artifacts} 个用户可见产物"
            "（排除「回复摘要」类记账标题）。"
        )
    return "\n".join(parts)


def count_user_artifacts(
    rows: list[tuple[str | None, str | None, int | None]] | list[dict],
) -> int:
    """Count deliverable artifacts, skipping bookkeeping titles.

    Accepts either (kind, title, byte_size) tuples or dict rows with those keys.
    """
    n = 0
    seen_titles: set[str] = set()
    for row in rows:
        if isinstance(row, dict):
            title = str(row.get("title") or "")
            byte_size = int(row.get("byte_size") or 0)
        else:
            _kind, title_raw, byte_size_raw = row
            title = str(title_raw or "")
            byte_size = int(byte_size_raw or 0)
        if not title or title in _SKIP_TITLES:
            continue
        # Zero-byte placeholders do not count.
        if byte_size <= 0 and not title:
            continue
        key = title.strip().lower()
        if key in seen_titles:
            continue
        seen_titles.add(key)
        n += 1
    return n


def is_bookkeeping_title(title: str | None) -> bool:
    return str(title or "") in _SKIP_TITLES


ENGINEERING_SKILL_ID = "skill-engineering-delivery"
"""Auto-selected when multi/pipeline/runnable intent is detected without an explicit skill."""
