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

# Strong pipeline language only. Bare「阶段一/步骤1」alone is NOT enough —
# those appear in meta labels (「阶段一验收」) and section titles without
# meaning multi-stage deliverable pipelines.
_PIPELINE_PHRASE = re.compile(
    r"(?:"
    r"流水线|"
    r"每阶段|"
    r"各阶段|"
    r"pipeline\s+stage|"
    r"multi[- ]?stage\s+pipeline"
    r")",
    re.IGNORECASE,
)

# Hard revision verbs (files / versions) — generic.
# Includes multi-round same-session revision ("第二轮修改") and versioned
# re-delivery ("输出 v3 / 更新版"), not bare chat「修改一下语气」.
_REVISION_PHRASE = re.compile(
    r"(?:"
    r"改成|改为|改一版|改版|修订|更新\s*(?:一下|版本|文件)|"
    r"把.{1,40}(?:改|更新|调整)|"
    r"联动\s*改|"
    r"同步\s*(?:更新|修改)|"
    r"第[一二三四五六七八九\d]+\s*轮\s*(?:修改|改版|改)|"
    r"再改(?:一版|一次|一遍)?|"
    r"继续\s*(?:修改|改版|改一版|改)|"
    r"同一会话.{0,16}(?:修改|改版|改一版|继续改|再改)|"
    r"输出\s*(?:更新版|新版|v\d+)|"
    r"更新版\s*(?:Markdown|markdown|文件|文档|md)?"
    r"|[-_]v\d+\.(?:md|txt|html|docx|pptx|pdf)\b"
    r"|revi(?:se|sion)|update\s+the\s+(?:file|document|artifact)"
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

# Single delivery unit (one file/page/doc) — language-level, not domain titles.
# Prevents content sections inside one HTML/课件 from inflating multi-file min.
_SINGLE_UNIT = re.compile(
    r"(?:"
    r"一\s*[份个张本]|单\s*[页个份文件]|"
    r"(?:做|生成|写|交付|准备|制作)\s*一\s*[份个张]|"
    r"一份.{0,20}(?:html|HTML|网页|页面|课件|教案|文档|互动页)|"
    r"(?:html|HTML|网页|页面|课件).{0,12}(?:一份|一个|单页)|"
    r"single[- ]?page|"
    r"one\s+(?:html|page|file|document)"
    r")",
    re.IGNORECASE,
)

# Explicit multi-file language (overrides single-unit).
_EXPLICIT_MULTI_FILE = re.compile(
    r"(?:"
    r"分别\s*(?:交付|生成|写出|落盘|下载|写成)|"
    r"独立\s*(?:可下载\s*)?文件|"
    r"多(?:个|份)\s*(?:独立\s*)?(?:文件|产物|交付|文档)|"
    r"分文件|"
    r"禁止\s*(?:合并|合成)\s*(?:成\s*)?(?:一|单)\s*(?:个|份)\s*文件|"
    r"separate\s+(?:files?|artifacts?)|"
    r"not\s+a\s+single\s+file"
    r")",
    re.IGNORECASE,
)

# Feature pairs inside one document (含分页和测验) — not multi-file lists.
_FEATURE_JOIN = re.compile(
    r"(?:含|有|带|包括|具备|附带|含有)\s*.{0,20}(?:与|和|及).{0,20}",
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
        r"([2-9]|10|[两二三四五六七])\s*个\s*(?:独立\s*)?(?:可下载\s*)?(?:文件|产物|交付|文档)",
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


def _looks_like_single_unit(text: str) -> bool:
    """True when the user asks for one document/page (not N independent files)."""
    if not text:
        return False
    # Negated multi ("不要拆成多个独立文件") must not block single-unit.
    scan = _strip_negated_multi_clauses(text)
    if _EXPLICIT_MULTI_FILE.search(scan) or _IMPLICIT_PACKAGE.search(text):
        return False
    if _count_explicit_n_files(text) >= 2:
        return False
    return bool(_SINGLE_UNIT.search(text))


def _count_parallel_list_items(text: str) -> int:
    """Count顿号/comma/与|和|及 parallel enumerations (structure-first).

    Prefers content after first colon. Does **not** require domain nouns.
    Avoids treating prose commas (「改成更短一点，语气友好」) as multi-deliverable.
    Also avoids feature pairs inside one document via _FEATURE_JOIN.
    """
    if not text:
        return 0
    has_dunhao = "、" in text
    has_colon = ("：" in text) or (":" in text)
    has_arrow = ("→" in text) or ("->" in text)
    # Dual short labels joined by 与|和|及 (e.g. 说明与清单).
    has_cn_join = bool(re.search(r"\S{1,16}\s*(?:与|和|及)\s*\S{1,16}", text))
    # Content features of one unit are not multi-file lists.
    feature_only = bool(_FEATURE_JOIN.search(text)) and not has_dunhao and not has_arrow
    if feature_only and not has_colon and not _EXPLICIT_MULTI_FILE.search(text):
        return 0

    body = text
    if has_colon:
        for sep in ("：", ":"):
            if sep in text:
                tail = text.split(sep, 1)[1]
                body = re.split(r"[。！？\n]", tail, maxsplit=1)[0]
                break
        # Title + content description after colon is often one document, not N files.
        # e.g. single-unit doc title with section packing after colon.
        # Only count if body itself is a clear parallel deliverable list (顿号 etc.).
        if (
            _looks_like_single_unit(text)
            and not has_dunhao
            and not has_arrow
            and not _EXPLICIT_MULTI_FILE.search(text)
            and "、" not in body
            and not re.search(r"\s+与\s+|\s+和\s+|\s+及\s+", body)
        ):
            # comma-separated description of sections → not multi-file
            return 0
    elif has_dunhao or has_arrow or (has_cn_join and not feature_only):
        body = text
    else:
        # English/Chinese comma alone in free prose is too noisy — skip.
        return 0

    # Note: bare "/" is NOT a list separator — UI action chains like
    # 「添加/勾选/删除」must not inflate multi-file min_artifacts.
    parts = re.split(r"[、,，;；|]|→|->|\s+与\s+|\s+和\s+|\s+及\s+", body)
    hits = [p.strip() for p in parts if _is_structure_segment(p)]
    # Drop segments that look like imperative prose / media meta / content packing,
    # not independent deliverable labels. Structural/grammar only (E3: no sample-face
    # domain noun table as dedicated filters — see REMOVED_OVERFIT_PHRASES).
    clean: list[str] = []
    for h in hits:
        if re.search(r"^(?:把|请|将|让|把刚才|含|有|带|并|且|输出|文件须|再)", h):
            continue
        if re.search(r"改成|改为|语气|友好|新增一条|跟进|更新版|可再下载", h) and len(h) > 8:
            continue
        # Media / openability meta (language-level).
        if re.search(
            r"本地\s*打开|可打开|浏览器|自检|file\s*打开|可用$|请做",
            h,
            re.IGNORECASE,
        ):
            continue
        # Packing density / section-role grammar: "3 页…", pure "…页" content-role labels
        # (not file deliverables). Avoid domain word tables.
        if re.search(r"^\d+\s*页", h):
            continue
        if re.fullmatch(r"[\w\u4e00-\u9fff]{1,10}页", h) and not re.search(
            r"(?:文件|文档|清单|说明|手册|纪要|方案|模板|稿)", h
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
    """Observability count: structural enumeration across patterns (raw).

    Do **not** feed this raw count straight into min_artifacts when an explicit
    file count or named multi-file set is present — creative briefs pack
    ①②③ / 镜头 / 段落 outlines that are content parts, not independent files.
    """
    return max(
        _count_numbered_items(text),
        _count_parallel_list_items(text),
        _count_lettered_items(text),
        0,
    )


def _count_named_files(text: str) -> set[str]:
    """Filenames with common deliverable extensions mentioned in the prompt."""
    return {
        m.group(0).lower()
        for m in re.finditer(
            r"[\w\u4e00-\u9fff.-]+\.(?:md|txt|html|docx|pptx|pdf|json|csv|lrc|srt)\b",
            text or "",
            re.IGNORECASE,
        )
    }


def _stage_as_file_language(text: str) -> bool:
    """True when stages are framed as independent deliverables, not content parts."""
    return bool(
        re.search(
            r"(?:"
            r"每阶段|各阶段|"
            r"阶段.{0,12}独立\s*(?:文件|产物|交付)|"
            r"独立\s*(?:文件|产物).{0,16}阶段|"
            r"每阶段.{0,8}(?:文件|产物|落盘)|"
            r"pipeline\s+stage"
            r")",
            text or "",
            re.IGNORECASE,
        )
    )


def _count_pipeline_stages(text: str) -> int:
    """Count multi-stage pipeline intent. Single「阶段一」label alone → 0.

    Requires ≥2 distinct numbered stages **with stage-as-file language**, a
    ≥3-hop arrow chain with deliverable framing, or a strong pipeline phrase
    (流水线/每阶段/各阶段). Bare content packing like「阶段1 前奏 / 阶段2 主歌」
    inside a creative brief must **not** inflate min_artifacts.
    """
    stages: set[str] = set()
    for m in re.finditer(r"阶段\s*([1-9一二三四五六七八])", text or ""):
        stages.add(m.group(1))
    for m in re.finditer(r"步骤\s*([1-9一二三四五六七八])", text or ""):
        stages.add(m.group(1))
    for m in re.finditer(r"(?i)stage\s*([1-9])", text or ""):
        stages.add(m.group(1))
    # Arrow chains: 现状摘要 → 选项对比 → 推荐决策
    arrow_parts = re.split(r"\s*→\s*|\s*->\s*", text or "")
    arrow_n = 0
    if len(arrow_parts) >= 3:
        ok = sum(1 for p in arrow_parts if _is_structure_segment(p.strip()[:36]))
        if ok >= 3:
            arrow_n = ok
    stage_files = _stage_as_file_language(text or "")
    strong_phrase = bool(_PIPELINE_PHRASE.search(text or ""))
    # Numbered 阶段/步骤 only count when framed as independent stage files
    # or paired with strong pipeline language — not creative section labels.
    if len(stages) >= 2 and (stage_files or strong_phrase):
        return max(len(stages), arrow_n)
    if arrow_n >= 3 and (stage_files or strong_phrase or _EXPLICIT_MULTI_FILE.search(text or "")):
        return arrow_n
    # Strong phrase without numbers → default 3-stage kit
    if strong_phrase:
        return 3
    return 0


def looks_like_clarification(text: str) -> bool:
    """True when the assistant is asking the user to clarify — not claiming delivery.

    Generic: no topic-word tables. Used so clarification turns are not fail-closed
    as deliverable_missing_artifact (chat-only claims still fail).
    """
    s = (text or "").strip()
    if len(s) < 8:
        return False
    # Claimed / completed delivery → not clarification.
    # Future tense ("再落盘可下载…") is still clarification; past/done claims are not.
    if re.search(
        r"(?:"
        r"已(?:生成|写入|落盘|交付|创建|完成|导出)|"
        r"文件已|"
        r"请(?:在结果区)?下载|"
        r"(?:artifact|产物).{0,8}(?:已|生成)|"
        r"```(?:file:|html|python|javascript)"
        r")",
        s,
        re.IGNORECASE,
    ):
        return False
    q_marks = s.count("？") + s.count("?")
    clarify_cue = bool(
        re.search(
            r"(?:"
            r"请问|请确认|需要确认|方便说明|先确认|先问|"
            r"几个问题|两点确认|想先了解|还想确认|先确认两点|"
            r"你希望|您希望|更倾向|哪一种|是否需要|要不要|"
            r"可以先|在开始.{0,8}之前|开始之前|"
            r"澄清|确认一下|补充一下|回复后我再|"
            r"which\s+(?:do\s+you|would\s+you)|"
            r"could\s+you\s+(?:confirm|clarify|tell)|"
            r"before\s+i\s+(?:start|begin|write|generate)"
            r")",
            s,
            re.IGNORECASE,
        )
    )
    if clarify_cue and (q_marks >= 1 or "：" in s or ":" in s or "）" in s or ")" in s):
        return True
    # Multiple questions without delivery claim.
    if q_marks >= 2 and len(s) < 1200:
        return True
    return False


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


def _strip_negated_multi_clauses(text: str) -> str:
    """Drop clauses that *forbid* multi-file packing so they do not fire multi.

    e.g. 「不要拆成多个独立文件」「别分成多份文件」are single-unit intent.
    Keep positive multi (「分别交付」「禁止合并成一个文件」).
    """
    if not text:
        return text
    cleaned = re.sub(
        r"(?:不要|别|请勿|无需|不用|切勿)\s*"
        r"(?:"
        r"(?:拆成|分成)\s*多\s*(?:个|份)?\s*(?:独立\s*)?(?:可下载\s*)?(?:文件|产物|交付|文档)?"
        r"|多个?\s*(?:独立\s*)?(?:可下载\s*)?(?:文件|产物|交付|文档)"
        r"|独立\s*(?:可下载\s*)?文件"
        r"|分文件"
        r"|多(?:个|份)\s*(?:独立\s*)?(?:文件|产物|交付|文档)"
        r")",
        " ",
        text,
        flags=re.IGNORECASE,
    )
    return cleaned


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

    multi_scan = _strip_negated_multi_clauses(text)
    multi_phrase = bool(_MULTI_PHRASE.search(multi_scan))
    implicit_pkg = bool(_IMPLICIT_PACKAGE.search(text))
    structure_n = _count_structure_items(text)
    explicit_n = _count_explicit_n_files(text)
    pipeline_n = _count_pipeline_stages(text)
    # pipeline_n already gates on stage-as-file / strong phrase (not bare 阶段 labels).
    pipeline = pipeline_n >= 2 or bool(_PIPELINE_PHRASE.search(text))

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

    # G1: structure enumeration alone must not force multi-file when the user
    # asked for a single unit (one HTML/课件/文档). Explicit multi/package/pipeline
    # still force multi. No title/keyword exam tables.
    single_unit = _looks_like_single_unit(text)
    structure_multi = structure_n >= 2 and not single_unit
    # O2: same-session revision enumerates *changes* (改成…，并新增…), not N files.
    # Do not promote structure_multi for revision unless multi-file language is explicit.
    explicit_multi = bool(_EXPLICIT_MULTI_FILE.search(multi_scan))
    if (
        revision_targets_files
        and not multi_phrase
        and not implicit_pkg
        and explicit_n < 2
        and not explicit_multi
    ):
        structure_multi = False
    # One named file target (e.g. brief-v3.md) + change bullets ≠ N independent files.
    named_files = _count_named_files(text)
    single_named_file = len(named_files) == 1
    if (
        single_named_file
        and not multi_phrase
        and not implicit_pkg
        and explicit_n < 2
        and not explicit_multi
    ):
        structure_multi = False
        if not single_unit and (
            revision_targets_files
            or re.search(
                r"可下载|Markdown|markdown|更新版|落盘",
                text,
                re.IGNORECASE,
            )
        ):
            single_unit = True
    multi = multi_phrase or implicit_pkg or explicit_n >= 2 or structure_multi

    # Single-unit intent wins over weak pipeline misreads (meta「阶段一」etc.).
    if single_unit and not multi and not multi_phrase and not implicit_pkg:
        pipeline = False
        pipeline_n = 0

    # --- min_artifacts ---
    # Prefer **file-count signals** (explicit N files / ≥2 named files) over raw
    # structure packing (①②③ creative parts, 镜头 lists, content 阶段 labels).
    # True multi "分别写 N 文件" still min≥N; creative multi-parts ≠ N files.
    named_n = len(named_files)
    file_count_signals: list[int] = []
    if explicit_n >= 2:
        file_count_signals.append(explicit_n)
    if named_n >= 2 and (multi_phrase or explicit_multi or explicit_n >= 2 or multi):
        file_count_signals.append(named_n)

    min_arts = 0
    if multi:
        if file_count_signals:
            # Explicit/named file count wins — do not max with structure_n.
            min_arts = max(file_count_signals)
            min_arts = max(min_arts, 2)
        else:
            candidates = [2]
            # Structure-only multi: parallel/lettered deliverable lists still count.
            # Prefer parallel+lettered over raw numbered content packing when both exist.
            parallel_n = _count_parallel_list_items(text)
            lettered_n = _count_lettered_items(text)
            deliverable_struct = max(parallel_n, lettered_n, 0)
            if deliverable_struct >= 2 and not single_unit:
                candidates.append(deliverable_struct)
            elif structure_n >= 2 and not single_unit:
                # Numbered-only structure without explicit file N: use structure but
                # cap hard so content outlines cannot demand dozens of files.
                candidates.append(min(structure_n, 6))
            min_arts = max(candidates)
    if pipeline:
        # Pipeline floor only when no explicit multi-file count already set the bar.
        if not file_count_signals:
            min_arts = max(min_arts, pipeline_n if pipeline_n >= 2 else 3)
    if runnable and min_arts == 0:
        min_arts = 1
    if revision_targets_files and min_arts == 0:
        min_arts = 1
    # Single-unit file/page delivery: success needs one file, not N content sections.
    # Require clear file/surface language so bare「做一个…说明」chat stays force_agent=False.
    single_file_delivery = bool(
        single_unit
        and not multi
        and not pipeline
        and re.search(
            r"(?:"
            r"单文件|独立文件|可下载|"
            r"\.(?:md|txt|html|docx|pptx|pdf)\b|"
            r"markdown|Markdown|"
            r"html|HTML|网页|课件|"
            r"交付\s*(?:一份|一个|文件)|"
            r"文件名"
            r")",
            text,
            re.IGNORECASE,
        )
    )
    if single_file_delivery and min_arts == 0:
        min_arts = 1

    force_agent = multi or pipeline or runnable or revision_targets_files or single_file_delivery

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
        "【工程交付纪律 · 对工具/系统 · 非用户体检单】",
        "- 短答可不建文件；一旦用户要交付物，必须用工具写入账本，禁止只在聊天里交卷。",
        "- 真 Office/HTML 用 generate_*_document；其它文本/清单/说明用 workspace_write_file。",
        "- 禁止用代码块改后缀冒充 .html/.docx/.pptx。",
        "- 禁止把多个交付物合并成「一个文件里的多个标题」冒充多产物。",
        "- 扩展名必须与类型一致（.md/.txt/.html/.docx…）；禁止 .mdd 等错误后缀。",
        (
            "- **用户主回复=人包**：文件名、用途、打开/下载方式、可改什么；"
            "禁止向用户输出 artifact_id / L0 / L1 / verification_level / interaction_status / "
            "source_wall / encoding / 账本术语 / 完整 HTML 源码墙。机审字段只给系统。"
        ),
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
            "生成后必须调用 verify_html_document（结果供系统，勿向用户复读字段名）；"
            "未做真机点击时不要对用户空口「全部完美/已可交互」。"
            "交付动作=指引用户在结果区下载文件名并本地打开。"
        )
    if min_artifacts > 0:
        parts.append(
            f"- 本轮成功条件（系统）：账本中本 run 至少 {min_artifacts} 个用户可见产物"
            "（排除「回复摘要」类记账标题）。"
            "对用户：列出这些文件名并指向下载，勿念成功条件字段。"
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
    "日记页",  # sample-face content section (E3: structural filter instead)
    "知识页",  # sample-face content section
    "小测验",  # sample-face content section
    "分页",  # sample-face UI feature word as multi-file filter
    "测验",  # sample-face alone as multi-file filter
)
