"""Thin post-run delivery gates. Not a task-guessing supervisor.

Kept:
  - looks_like_delivery_claim / looks_like_clarification (assistant vs disk)
  - count_user_artifacts / is_bookkeeping_title / normalize_artifact_title
  - DeliveryPlan as a no-guess observability stub (min=0, force_agent=False)

Deleted: prompt-word task guessing, auto-force routing, instruction injection,
课件/套件 word tables, compute-then-zero empty spin.
Office empty-shell fail-closed lives in document_generators.office_shell_reason.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# Titles that are bookkeeping, not user deliverables.
_SKIP_TITLES = frozenset({"回复摘要", "工具产物"})

# D4: common typo extensions → canonical (workspace text path).
EXTENSION_TYPO_FIX: dict[str, str] = {
    ".mdd": ".md",
    ".mdown": ".md",
    ".markdown": ".md",
    ".text": ".txt",
    ".htm": ".html",
    ".docxx": ".docx",
    ".pptxx": ".pptx",
}


@dataclass(frozen=True)
class DeliveryPlan:
    """Observability stub. Routing must not guess from the user prompt."""

    multi_deliverable: bool = False
    pipeline: bool = False
    revision: bool = False
    runnable_html: bool = False
    min_artifacts: int = 0
    force_agent: bool = False
    instruction: str = ""
    implicit_package: bool = False
    structure_item_count: int = 0
    prior_artifact_count: int = 0

    @property
    def engineering(self) -> bool:
        return False


def no_guess_plan() -> DeliveryPlan:
    """Constant plan: tools stay mounted; min/force never come from a word list."""
    return DeliveryPlan()


_ASSISTANT_FILE_CLAIM = re.compile(
    r"(?:"
    r"已(?:生成|写入|落盘|交付|创建|导出)|"
    r"文件已|"
    r"请(?:在结果区)?下载|"
    r"(?:artifact|产物).{0,8}(?:已|生成)"
    r")",
    re.IGNORECASE,
)


def looks_like_delivery_claim(text: str) -> bool:
    """True when the *assistant* claimed a file landed.

    This is not a user-prompt classifier and must not read 课件/通知/Word tables
    out of the teacher's message.
    """
    return bool(_ASSISTANT_FILE_CLAIM.search((text or "").strip()))


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
    return bool(q_marks >= 2 and len(s) < 1200)


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
