"""General engineering-delivery policy (multi-artifact / pipeline / revision / runnable).

Intent detection is **structural and session-aware** — not exam-phrase overfit.

Used to:
  - force multi-step agent + write tools when user wants real packages
  - inject hard delivery instructions into the skill/system block
  - fail-closed when the run claims success without enough artifacts

T-CAP-HEURISTIC-DEEP:
  - D1 min_artifacts from enumeration structure (not domain noun tables)
  - D2 revision from change-of-mind + prior artifacts (not exam soft phrases)
  - D3 runnable from media words only (no app names like 番茄钟)
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

# Implicit package / kit / suite — structural multi, not domain product names.
_IMPLICIT_PACKAGE = re.compile(
    r"(?:"
    r"(?:完整\s*)?(?:方案|交付|材料|文档)\s*包|"
    r"交付\s*套件|"
    r"一整套|"
    r"全套\s*(?:材料|方案|文档|交付|文件)?|"
    r"材料\s*包|"
    r"一揽子|"
    r"从.{1,24}到.{1,24}全套|"
    r"自行\s*拆成\s*多|"
    r"按\s*(?:完整|实际)\s*(?:筹备|交付|会议)\s*需要|"
    r"(?:complete|full)\s+(?:package|kit|suite|set)|"
    r"suite\s+of|"
    r"delivery\s+kit|"
    r"material\s+pack(?:age)?"
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

# Hard revision verbs (files / versions) — generic.
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

# D2: generic change-of-mind / scope shrink — NOT exam soft phrases.
# See REMOVED_OVERFIT_PHRASES for the deleted exam soft-revision set.
_CHANGE_OF_MIND = re.compile(
    r"(?:"
    r"还是改成|还是改为|"
    r"推翻|改口|收回|"
    r"太(?:激进|保守|复杂|简单|乐观)|"
    r"只保留|收窄|缩成|缩到|"
    r"重新考虑|换一[个种]|换方案|"
    r"上次|上一[版轮次]|之前的(?:推荐|结论|方案|决策|文件)|"
    r"改得更|改成更|"
    r"change\s+(?:of\s+)?mind|"
    r"(?:too\s+)?(?:aggressive|conservative)|"
    r"keep\s+only|narrow\s+(?:to|down)"
    r")",
    re.IGNORECASE,
)

# Casual chat polish — must NOT force file revision.
_CASUAL_POLISH = re.compile(
    r"(?:"
    r"更短一点|语气|友好一些|润色|精简一下回答|改成口语"
    r")",
    re.IGNORECASE,
)

# D3: media + interaction surface only — no concrete app names (番茄钟 etc.).
_RUNNABLE_MEDIA = re.compile(
    r"(?:"
    r"(?:单页\s*)?html|"
    r"本地\s*可打开|"
    r"可\s*打开\s*的\s*(?:网页|页面)|"
    r"file\s*(?:协议|://)\s*打开|"
    r"浏览器\s*打开|"
    r"local\s+html|"
    r"single[- ]?page\s+html|"
    r"\btimer\b|"
    r"计时器|"
    r"交互\s*(?:页|页面|控件)?"
    r")",
    re.IGNORECASE,
)

_HTML_SURFACE = re.compile(
    r"(?i)html|网页|页面|\bpage\b|单页",
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

# A/B style short labels: "A 规格说明、B 验收清单" or "A) foo B) bar"
_LETTERED_ITEM = re.compile(
    r"(?:(?<=^)|(?<=\s)|(?<=[：:、,，;；]))"
    r"[A-Za-z][)）．.、:：]\s*\S+"
    r"|(?:(?<=^)|(?<=\s)|(?<=[：:]))"
    r"[A-Za-z]\s+[^\s、,，;；]{1,24}"
)

_CN_NUM = {
    "两": 2,
    "二": 2,
    "三": 3,
    "四": 4,
    "五": 5,
    "六": 6,
    "七": 7,
}

# D4: common typo extensions → canonical (workspace text path).
EXTENSION_TYPO_FIX: dict[str, str] = {
    ".mdd": ".md",
    ".mdown": ".md",
    ".markdown": ".md",
    ".text": ".txt",
    ".htm": ".html",  # normalize; generate_html already forces .html
    ".docxx": ".docx",
    ".pptxx": ".pptx",
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
    # Structural enumeration count used for min (0 if none).
    structure_item_count: int = 0
    # Prior artifacts informed revision (session graph).
    prior_artifact_count: int = 0

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


def _is_structure_segment(chunk: str) -> bool:
    """Accept short list labels; reject empty/long prose sentences.

    Domain-agnostic: no business noun allowlist (R1).
    """
    s = (chunk or "").strip()
    if len(s) < 2 or len(s) > 36:
        return False
    # Drop pure conjunction leftovers.
    if s in {"与", "和", "及", "以及", "or", "and", "the", "a", "an"}:
        return False
    # Full sentence → not a list item.
    if re.search(r"[。！？?!]$", s) and len(s) > 12:
        return False
    if s.count("，") + s.count(",") >= 2:
        return False
    # Must contain a letter/digit/CJK char.
    return bool(re.search(r"[\w\u4e00-\u9fff]", s, re.UNICODE))


def _count_parallel_list_items(text: str) -> int:
    """Count顿号/comma/与|和|及 parallel enumerations (structure-first).

    Prefers content after first colon. Does **not** require domain nouns.
    Avoids treating prose commas (「改成更短一点，语气友好」) as multi-deliverable.
    """
    if not text:
        return 0
    has_dunhao = "、" in text
    has_colon = ("：" in text) or (":" in text)
    has_arrow = ("→" in text) or ("->" in text)
    # Dual short labels joined by 与|和|及 (e.g. 说明与清单).
    has_cn_join = bool(re.search(r"\S{1,16}\s*(?:与|和|及)\s*\S{1,16}", text))

    body = text
    if has_colon:
        for sep in ("：", ":"):
            if sep in text:
                tail = text.split(sep, 1)[1]
                body = re.split(r"[。！？\n]", tail, maxsplit=1)[0]
                break
    elif has_dunhao or has_arrow or has_cn_join:
        body = text
    else:
        # English/Chinese comma alone in free prose is too noisy — skip.
        return 0

    # Note: bare "/" is NOT a list separator — UI action chains like
    # 「添加/勾选/删除」must not inflate multi-file min_artifacts.
    parts = re.split(r"[、,，;；|]|→|->|\s+与\s+|\s+和\s+|\s+及\s+", body)
    hits = [p.strip() for p in parts if _is_structure_segment(p)]
    # Drop segments that look like imperative prose / media meta, not list labels.
    clean: list[str] = []
    for h in hits:
        if re.search(r"^(?:把|请|将|让|把刚才)", h):
            continue
        if re.search(r"改成|改为|语气|友好", h) and len(h) > 10:
            continue
        if re.search(
            r"本地\s*打开|可打开|浏览器|自检|file\s*打开|可用$|请做",
            h,
            re.IGNORECASE,
        ):
            continue
        clean.append(h)
    return len(clean) if len(clean) >= 2 else 0
def _count_lettered_items(text: str) -> int:
    found = _LETTERED_ITEM.findall(text or "")
    # Filter short noise
    n = 0
    for item in found:
        s = item.strip()
        if len(s) >= 3:
            n += 1
    return n if n >= 2 else 0


def _count_structure_items(text: str) -> int:
    """Primary min signal: structural enumeration across patterns."""
    return max(
        _count_numbered_items(text),
        _count_parallel_list_items(text),
        _count_lettered_items(text),
        0,
    )


def _count_pipeline_stages(text: str) -> int:
    stages = set()
    for m in re.finditer(r"阶段\s*([1-9一二三四五六七八])", text or ""):
        stages.add(m.group(1))
    for m in re.finditer(r"步骤\s*([1-9一二三四五六七八])", text or ""):
        stages.add(m.group(1))
    for m in re.finditer(r"(?i)stage\s*([1-9])", text or ""):
        stages.add(m.group(1))
    # Arrow chains: 现状摘要 → 选项对比 → 推荐决策
    arrow_parts = re.split(r"\s*→\s*|\s*->\s*", text or "")
    if len(arrow_parts) >= 3:
        ok = sum(1 for p in arrow_parts if _is_structure_segment(p.strip()[:36]))
        if ok >= 3:
            stages.update(str(i) for i in range(ok))
    if stages:
        return len(stages)
    if _PIPELINE_PHRASE.search(text or ""):
        return 3
    return 0


def normalize_artifact_title(title: str) -> tuple[str, str | None]:
    """D4: fix known typo extensions; return (title, fix_note|None)."""
    t = (title or "").strip()
    if not t or "." not in t.split("/")[-1]:
        return t, None
    base, ext = t.rsplit(".", 1)
    ext_dot = "." + ext.lower()
    if ext_dot in EXTENSION_TYPO_FIX:
        fixed = EXTENSION_TYPO_FIX[ext_dot]
        return f"{base}{fixed}", f"extension {ext_dot} → {fixed}"
    return t, None


def analyze_delivery(
    prompt: str,
    *,
    prior_artifact_titles: list[str] | None = None,
    prior_artifact_count: int | None = None,
) -> DeliveryPlan:
    """Derive a DeliveryPlan from NL intent + optional session artifact graph."""
    text = prompt or ""
    prior_titles = [t for t in (prior_artifact_titles or []) if t and t not in _SKIP_TITLES]
    prior_n = (
        int(prior_artifact_count)
        if prior_artifact_count is not None
        else len(prior_titles)
    )

    multi_phrase = bool(_MULTI_PHRASE.search(text))
    implicit_pkg = bool(_IMPLICIT_PACKAGE.search(text))
    structure_n = _count_structure_items(text)
    explicit_n = _count_explicit_n_files(text)
    pipeline_n = _count_pipeline_stages(text)
    pipeline = pipeline_n > 0 or bool(_PIPELINE_PHRASE.search(text))

    hard_revision = bool(_REVISION_PHRASE.search(text))
    change_mind = bool(_CHANGE_OF_MIND.search(text))
    casual = bool(_CASUAL_POLISH.search(text))
    # Casual chat polish wins over bare「改成」when no deliverable/file graph.
    if casual and not change_mind:
        hard_revision = False
    wants_revision = hard_revision or change_mind

    # D3: media surface required; no concrete app-name dependency.
    runnable = bool(_RUNNABLE_MEDIA.search(text)) and bool(_HTML_SURFACE.search(text))

    # D2: revision of prior deliverables (session graph + generic change-of-mind).
    mentions_deliverable = bool(
        re.search(
            r"文件|产物|artifact|阶段|落盘|版本|文档|清单|决策|方案|推荐|"
            r"对应文件|更新\s*(?:一下|文件|版本)",
            text,
            re.IGNORECASE,
        )
    )
    revision_targets_files = bool(
        wants_revision
        and (
            (prior_n >= 1 and (change_mind or hard_revision))
            or (hard_revision and mentions_deliverable)
            or (change_mind and mentions_deliverable)
        )
    )

    # Single-stage revision must not re-floor pipeline min.
    pipeline_setup = bool(
        re.search(r"流水线|每阶段|各阶段|pipeline\s+stage", text, re.IGNORECASE)
    ) or pipeline_n >= 2
    if revision_targets_files and not pipeline_setup:
        pipeline = False
        pipeline_n = 0

    multi = multi_phrase or implicit_pkg or explicit_n >= 2 or structure_n >= 2

    min_arts = 0
    if multi:
        candidates = [2]
        if explicit_n >= 2:
            candidates.append(explicit_n)
        if structure_n >= 2:
            candidates.append(structure_n)
        min_arts = max(candidates)
    if pipeline:
        min_arts = max(min_arts, pipeline_n if pipeline_n >= 2 else 3)
    if runnable and min_arts == 0:
        min_arts = 1
    if revision_targets_files and min_arts == 0:
        min_arts = 1

    force_agent = multi or pipeline or runnable or revision_targets_files

    instruction = _build_instruction(
        multi=multi,
        pipeline=pipeline,
        revision=revision_targets_files,
        soft_revision=change_mind and revision_targets_files,
        runnable=runnable,
        min_artifacts=min_arts,
        implicit_package=implicit_pkg,
        prior_n=prior_n,
        prior_titles=prior_titles[:12],
    )
    return DeliveryPlan(
        multi_deliverable=multi,
        pipeline=pipeline,
        revision=revision_targets_files,
        runnable_html=runnable,
        min_artifacts=min_arts,
        force_agent=force_agent,
        instruction=instruction,
        implicit_package=implicit_pkg,
        structure_item_count=structure_n,
        prior_artifact_count=prior_n,
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
    prior_n: int,
    prior_titles: list[str],
) -> str:
    parts: list[str] = [
        "【工程交付纪律 · 通用】",
        "- 短答可不建文件；一旦用户要交付物，必须用工具写入 Artifact 账本，禁止只在聊天里交卷。",
        "- 真 Office/HTML 用 generate_*_document；其它文本/清单/说明用 workspace_write_file。",
        "- 禁止用代码块改后缀冒充 .html/.docx/.pptx。",
        "- 禁止把多个交付物合并成「一个文件里的多个标题」冒充多产物。",
        "- 扩展名必须与类型一致（.md/.txt/.html/.docx…）；禁止 .mdd 等错误后缀。",
    ]
    if multi or min_artifacts >= 2:
        parts.append(
            f"- 多交付：至少写入 **{max(min_artifacts, 2)}** 个独立 Artifact"
            "（不同 title），每个交付物一次 write/generate 调用。"
            "并列枚举/编号列表有几项就尽量对应几份文件。"
        )
    if implicit_package:
        parts.append(
            "- 隐式包装：用户未写「几个文件」也按完整套件拆成多份独立成品；"
            "文件名体现用途，禁止 output_1 式无意义命名。"
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
            "未改动文件保持可追溯，不要无故删除。"
        )
    if soft_revision or (revision and prior_n > 0):
        hint = "、".join(prior_titles[:6]) if prior_titles else "（会话已有交付物）"
        parts.append(
            f"- 会话改口：用户推翻/收窄/调整上次结论时，必须在已交付产物图上更新"
            f"（已知产物线索：{hint}）；使人类打开新文件能看出结论已变。"
        )
    if runnable:
        parts.append(
            "- 可运行 HTML：body 传完整可交互文档（真 button/script，禁止源码墙）；"
            "生成后 verify_html_document（L0）；L1 未点击则写 not_run；"
            "禁止空话「全部完美/人类可用」。"
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

# D0 self-audit: phrases/words removed vs T-CAP-GENERAL-P1 overfit set.
REMOVED_OVERFIT_PHRASES: tuple[str, ...] = (
    "广播稿",  # domain noun table entry
    "须知",  # domain noun table entry (exam-isomorphic)
    "布局",  # domain noun table entry
    "排班",  # domain noun table entry
    "洞察",  # domain noun table entry
    "只做低成本",  # soft-revision exam phrase
    "别的顺延",  # soft-revision exam phrase
    "先只做",  # soft-revision exam phrase
    "本周…只做",  # soft-revision exam phrase
    "顺延",  # as primary soft trigger
    "番茄钟",  # runnable app name
)
