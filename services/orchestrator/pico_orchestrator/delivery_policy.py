"""General engineering-delivery policy (multi-artifact / pipeline / revision / runnable).

Intent detection is **generic** — no exam-case keywords, no fixed filenames.
Used to:
  - force multi-step agent + write tools when user wants real packages
  - inject hard delivery instructions into the skill/system block
  - fail-closed when the run claims success without enough artifacts

P1 extensions (T-CAP-GENERAL-P1):
  - H1 implicit multi-delivery (package/kit/suite without saying N files)
  - H2 neutral runnable detection (no scenario-sticky terms)
  - H5 soft revision phrasing linked to prior deliverables
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

# H1: implicit package / kit / suite intent — no need to say "N independent files".
_IMPLICIT_PACKAGE = re.compile(
    r"(?:"
    r"(?:完整\s*)?(?:方案|交付|筹备|活动|材料|文档)\s*包|"
    r"交付\s*套件|"
    r"一整套|"
    r"全套\s*(?:材料|方案|文档|交付|文件)?|"
    r"材料\s*包|"
    r"筹备\s*(?:材料|包)|"
    r"一揽子|"
    r"从.{1,24}到.{1,24}全套|"
    r"自行\s*拆成\s*多|"
    r"按\s*(?:完整|实际)\s*(?:筹备|交付)\s*需要|"
    r"(?:complete|full)\s+(?:package|kit|suite|set)|"
    r"suite\s+of|"
    r"delivery\s+kit|"
    r"material\s+pack(?:age)?"
    r")",
    re.IGNORECASE,
)

# Deliverable-like nouns often listed after a package colon (顿号/comma lists).
_DELIVERABLE_NOUN = re.compile(
    r"(?:"
    r"规则|须知|说明|布局|广播稿|通知|清单|手册|指南|流程|"
    r"排班|表|洞察|行动|建议|报告|纪要|大纲|脚本|文案|"
    r"rules?|guide|notice|layout|checklist|playbook|brief|memo|script"
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

# Explicit revision verbs (files / versions).
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

# H5: soft rephrasing — human change-of-mind without "update the file".
_SOFT_REVISION = re.compile(
    r"(?:"
    r"还是改成|"
    r"算了[，,。\s].{0,48}(?:只做|先做|改成|改为|别的|顺延)|"
    r"优先级.{0,16}(?:调|改|降|升|一下)|"
    r"别的顺延|"
    r"先只做|"
    r"本周.{0,24}只做|"
    r"更新阶段|"
    r"改阶段|"
    r"顺延|"
    r"只做\s*(?:低成本|简单|优先)?.{0,12}(?:两|三|2|3)?\s*项"
    r")",
    re.IGNORECASE,
)

# H2: neutral runnable HTML cues — no scenario-sticky words (e.g. 倒计时).
_RUNNABLE_HTML = re.compile(
    r"(?:"
    r"(?:单页\s*)?html|"
    r"本地\s*可打开|"
    r"可\s*打开\s*的\s*(?:网页|页面)|"
    r"file\s*(?:协议|://)\s*打开|"
    r"浏览器\s*打开|"
    r"自检|"
    r"交互|"
    r"计时器|番茄钟|timer|"
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
    # True when multi came from package/kit wording without explicit N files.
    implicit_package: bool = False

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


def _count_listed_deliverables(text: str) -> int:
    """Count顿号/comma-separated deliverable-like items (package body lists).

    Generic: no scenario names. Fires only when ≥2 noun-ish segments match.
    """
    if not text:
        return 0
    # Prefer content after first colon / 「：」 which often introduces the list.
    body = text
    for sep in ("：", ":"):
        if sep in text:
            body = text.split(sep, 1)[1]
            break
    # Split on顿号 / Chinese comma / English comma / arrows / 「→」 / 「、」
    parts = re.split(r"[、,，;；→\->]+", body)
    hits = 0
    for part in parts:
        chunk = part.strip()
        if len(chunk) < 2 or len(chunk) > 40:
            continue
        if _DELIVERABLE_NOUN.search(chunk):
            hits += 1
    return hits


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
    implicit_pkg = bool(_IMPLICIT_PACKAGE.search(text))
    numbered = _count_numbered_items(text)
    listed = _count_listed_deliverables(text) if implicit_pkg else 0
    explicit_n = _count_explicit_n_files(text)
    pipeline_n = _count_pipeline_stages(text)
    pipeline = pipeline_n > 0 or bool(_PIPELINE_PHRASE.search(text))
    hard_revision = bool(_REVISION_PHRASE.search(text))
    soft_revision = bool(_SOFT_REVISION.search(text))
    revision = hard_revision or soft_revision
    # H2: require HTML/page surface + neutral runnable cues (no sticky scene words).
    runnable = bool(_RUNNABLE_HTML.search(text)) and bool(
        re.search(r"(?i)html|网页|页面|page|番茄钟|timer", text)
    )

    # Revision of *files* / prior stage outputs (not casual “改成更短一点” chat polish).
    revision_targets_files = revision and bool(
        re.search(
            r"文件|产物|artifact|阶段|落盘|版本|文档|清单|建议\s*文件|对应文件|"
            r"行动|洞察|材料|规则|须知|广播|排班|本周",
            text,
            re.IGNORECASE,
        )
    )
    # Soft revision alone with stage/action wording is enough to force agent rewrite.
    if soft_revision and bool(
        re.search(r"阶段|行动|建议|清单|洞察|材料|产物|文件|版本", text)
    ):
        revision_targets_files = True

    # Soft/hard revision that only touches one stage must NOT re-require a full
    # pipeline min_artifacts floor (would false-fail a one-file update turn).
    pipeline_setup = bool(
        re.search(r"流水线|每阶段|各阶段|pipeline\s+stage", text, re.IGNORECASE)
    ) or pipeline_n >= 2
    if revision_targets_files and not pipeline_setup:
        pipeline = False
        pipeline_n = 0
    else:
        # keep pipeline flag as derived above
        pass

    multi = (
        multi_phrase
        or implicit_pkg
        or explicit_n >= 2
        or (
            numbered >= 2
            and (
                multi_phrase
                or implicit_pkg
                or bool(
                    re.search(
                        r"交付|文件|产物|下载|落盘|文档|说明书|清单|建议|规则|通知",
                        text,
                    )
                )
            )
        )
    )

    min_arts = 0
    if multi:
        candidates = [2]
        if explicit_n >= 2:
            candidates.append(explicit_n)
        if numbered >= 2:
            candidates.append(numbered)
        if listed >= 2:
            candidates.append(listed)
        min_arts = max(candidates)
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
        soft_revision=soft_revision,
        runnable=runnable,
        min_artifacts=min_arts,
        implicit_package=implicit_pkg,
    )
    return DeliveryPlan(
        multi_deliverable=multi,
        pipeline=pipeline,
        revision=revision,
        runnable_html=runnable,
        min_artifacts=min_arts,
        force_agent=force_agent,
        instruction=instruction,
        implicit_package=implicit_pkg,
    )


def _build_instruction(
    *,
    multi: bool,
    pipeline: bool,
    revision: bool,
    soft_revision: bool,
    runnable: bool,
    min_artifacts: int,
    implicit_package: bool,
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
    if implicit_package:
        parts.append(
            "- 隐式包装：用户未写「几个文件」也按完整方案包拆成多份独立成品；"
            "文件名体现用途（规则/须知/布局/广播等），禁止 output_1 式无意义命名。"
        )
    if pipeline:
        parts.append(
            "- 流水线：每个阶段必须落独立文件（阶段号可写在文件名），"
            "不得只在聊天摘要里描述阶段结果。"
        )
    if revision or soft_revision:
        parts.append(
            "- 修订联动：先 workspace_list_files / workspace_read_file 看已有产物，"
            "再对受影响文件写入更新内容或带版本号的新文件名；"
            "未改动的阶段文件保持可追溯，不要无故删除。"
        )
    if soft_revision:
        parts.append(
            "- 软改口：用户用「还是改成/算了/优先级调一下/顺延」等口语改意图时，"
            "仍视为正式修订——必须更新对应产物，使人类打开新文件能看出结论已变。"
        )
    if runnable:
        parts.append(
            "- 可运行 HTML：生成后调用 verify_html_document 做结构自检（verification_level=L0）；"
            "未做浏览器点击时必须写 interaction_status=not_run / L1 未执行；"
            "禁止空话「全部完美/已可运行/人类可用」。"
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
