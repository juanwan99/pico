"""exam-answer-extract — answer sheet → answer-card question structure.

Thin adapter over the product brain (``pico_orchestrator.provider``): text goes to
the text model in one shot; page images go to the vision entry page by page; items
are merged by question number. Prompts live in SKILL.md (single semantic source).
No regex / heuristic fallback: an empty extraction is a failure, never a guess.
"""

from __future__ import annotations

import asyncio
import base64
import io
import json
import logging
import os
import re
from collections.abc import Awaitable, Callable
from dataclasses import replace
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

ENGINE = "exam-answer-extract/1"
TYPES = ("single_choice", "multi_choice", "fill_in_blank", "short_answer")
SKILL_PATH = Path(__file__).resolve().parent / "SKILL.md"

TEXT_CHUNK_CHARS = 60_000
MAX_TEXT_CHARS = 400_000
DEFAULT_MAX_OUTPUT_TOKENS = 16_000
CONTINUE_ROUNDS = 4

Completer = Callable[..., Awaitable[str]]


class ExtractError(RuntimeError):
    """Adapter-level failure with a stable code for the HTTP layer."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


class ThinkingRanOut(RuntimeError):
    """The call stopped at its output cap with most of it spent thinking: the answer is cut.

    Not an ExtractError: callers treat it as a failed read (a page re-reads without
    thinking, a structure read just does not vote) instead of building a card from it.
    """


# --------------------------------------------------------------------------- prompts


def _prompt_block(name: str, skill_text: str | None = None) -> str:
    text = skill_text if skill_text is not None else SKILL_PATH.read_text(encoding="utf-8")
    start = f"<!-- prompt:{name} -->"
    end = f"<!-- /prompt:{name} -->"
    i = text.find(start)
    j = text.find(end, i + len(start)) if i >= 0 else -1
    if i < 0 or j < 0:
        raise ExtractError("skill.invalid", f"SKILL.md 缺少提示块 {name}")
    block = text[i + len(start) : j].strip()
    if block.startswith("```"):
        lines = block.split("\n")[1:]
        while lines and lines[-1].strip() != "```":
            lines.pop()
        block = "\n".join(lines[:-1] if lines else [])
    return block.strip()


TASKS = ("answers", "structure", "solve", "paper")


def load_prompts(skill_text: str | None = None, task: str = "answers") -> dict[str, str]:
    t = task if task in TASKS else "answers"
    suffix = "" if t == "answers" else f"_{t}"
    prompts = {
        "system": _prompt_block(f"system{suffix}", skill_text),
        "user_text": _prompt_block(f"user_text{suffix}", skill_text),
        "user_page": _prompt_block(f"user_page{suffix}", skill_text),
    }
    if t == "structure":
        prompts["user_pages"] = _prompt_block("user_pages_structure", skill_text)
    return prompts


def subject_tag(subject_code: str | None, subject_name: str | None) -> str:
    name = (subject_name or "").strip() or (subject_code or "").strip()
    return f"（科目 {name}）" if name else ""


# --------------------------------------------------------------------------- JSON


def strip_fence(content: str | None) -> str:
    c = str(content or "").strip()
    if c.startswith("```"):
        c = "\n".join(c.split("\n")[1:])
        end = c.rfind("```")
        if end >= 0:
            c = c[:end]
    return c.strip()


# LaTeX commands whose first letter is also a JSON escape (\n \r \t). Only read as LaTeX
# inside $…$: outside math "well\ni think" / "x\tan apple" / "see below\ne.g." are a real newline
# or tab followed by text, and the model writes formulas in $…$ (SKILL.md). \b \f are never
# meant as JSON escapes in a paper, so they are LaTeX anywhere.
_LATEX_JSON_LOOKALIKE = frozenset(
    {
        "times", "theta", "tan", "tanh", "text", "textbf", "textrm", "tfrac", "tilde", "to", "top",
        "triangle", "triangleq", "tau", "therefore", "neq", "ne", "nu", "not", "notin", "nabla", "neg",
        "ni", "nleq", "ngeq", "nmid", "nexists", "nolimits", "right", "rightarrow", "rho", "rangle",
        "rceil", "rfloor", "rm", "frac", "dfrac", "forall", "flat", "frown", "fbox", "beta", "bar",
        "binom", "bf", "boldsymbol", "bot", "because", "big", "bigg", "bigcup", "bigcap", "bullet",
        "backslash", "boxed", "bmod", "bigl", "bigr", "biggl", "biggr", "bmatrix", "begin",
    }
)
_ESCAPE_RE = re.compile(r'\\(\\|u[0-9a-fA-F]{4}|["/]|[A-Za-z]+|.)', re.DOTALL)


def _fix_escape(tok: str, in_math: bool) -> str:
    if tok in ("\\", '"', "/") or re.fullmatch(r"u[0-9a-fA-F]{4}", tok):
        return "\\" + tok
    if tok[0] in "nrt":
        # Ambiguous: LaTeX only inside $…$ and only for a known command; else the JSON escape
        # (just its one letter — the letters after it are ordinary text). Paper text never holds
        # a real backspace / form feed, so \b \f are always LaTeX ("面积 \frac{1}{2}ab").
        if in_math and tok in _LATEX_JSON_LOOKALIKE:
            return "\\\\" + tok
        return "\\" + tok
    return "\\\\" + tok


def escape_latex(raw: str) -> str:
    r"""Double the backslashes of LaTeX the model left bare inside JSON strings.

    Stems are written with $…$ LaTeX. A bare "\perp" makes the whole array unparseable and a
    bare "\frac" parses as form feed + "rac", silently. Valid JSON escapes are kept; \b \f are
    always LaTeX; the ambiguous \n \r \t + letters are LaTeX only inside $…$ in a JSON string.
    """
    out: list[str] = []
    i, n = 0, len(raw)
    in_string = in_math = False
    while i < n:
        ch = raw[i]
        if not in_string:
            if ch == '"':
                in_string, in_math = True, False
            out.append(ch)
            i += 1
        elif ch == "\\":
            m = _ESCAPE_RE.match(raw, i)
            if not m:  # trailing lone backslash
                out.append("\\\\")
                i += 1
                continue
            out.append(_fix_escape(m.group(1), in_math))
            i = m.end()
        elif ch == '"':
            in_string = False
            out.append(ch)
            i += 1
        elif ch == "$":
            step = 2 if raw.startswith("$$", i) else 1
            in_math = not in_math
            out.append(raw[i : i + step])
            i += step
        else:
            out.append(ch)
            i += 1
    return "".join(out)


def parse_json_array(content: str | None) -> list[Any] | None:
    """Model text → list. Accepts fenced JSON, {questions:[…]}, NDJSON, truncated arrays."""
    raw = escape_latex(strip_fence(content))
    if not raw:
        return None
    try:
        value = json.loads(raw)
    except ValueError:
        value = None
    if isinstance(value, list):
        return value
    if isinstance(value, dict):
        for key in ("questions", "items"):
            if isinstance(value.get(key), list):
                return value[key]
        if any(k in value for k in ("number", "qno", "question_no")):
            return [value]
        return None

    ndjson: list[Any] = []
    for line in raw.split("\n"):
        t = line.strip().rstrip(",")
        if not (t.startswith("{") and t.endswith("}")):
            continue
        try:
            obj = json.loads(t)
        except ValueError:
            continue
        if isinstance(obj, dict):
            ndjson.append(obj)
    if ndjson:
        return ndjson

    start = raw.find("[")
    if start < 0:
        salvaged = salvage_numbered_dicts(raw)
        return salvaged or None
    body = raw[start:]
    last = body.rfind("}")
    if last >= 0:
        truncated = re.sub(r",\s*$", "", body[: last + 1])
        truncated += "]" * max(0, truncated.count("[") - truncated.count("]"))
        try:
            repaired = json.loads(truncated)
        except ValueError:
            repaired = None
        if isinstance(repaired, list) and repaired:
            return repaired
    salvaged = salvage_numbered_dicts(raw)
    return salvaged or None


def salvage_numbered_dicts(raw: str) -> list[dict[str, Any]]:
    """Keep numbered objects even when the model truncated the last key (``"rubr``)."""
    out: list[dict[str, Any]] = []
    seen: set[int] = set()
    for m in re.finditer(r"\{[^{}]*\}", raw or ""):
        try:
            obj = json.loads(m.group(0))
        except ValueError:
            obj = None
        if isinstance(obj, dict) and any(k in obj for k in ("number", "qno", "question_no")):
            try:
                n = int(float(obj.get("number", obj.get("qno", obj.get("question_no")))))
            except (TypeError, ValueError):
                continue
            if n > 0 and n not in seen:
                seen.add(n)
                out.append(obj)
    for m in re.finditer(r'"number"\s*:\s*(\d+)', raw or ""):
        n = int(m.group(1))
        if n <= 0 or n in seen:
            continue
        window = (raw or "")[max(0, m.start() - 40) : m.end() + 180]
        typ = re.search(r'"type"\s*:\s*"([^"]+)"', window)
        obj: dict[str, Any] = {"number": n}
        if typ:
            obj["type"] = typ.group(1)
        seen.add(n)
        out.append(obj)
    return out


# --------------------------------------------------------------------------- items

# Sub-question level only: (1)（1）1). ①② are blanks inside one 小问, never sub-questions.
_SUB_MARK_RE = re.compile(r"[（(]\s*(\d{1,2})\s*[）)]|(?<![\w.+\-*/^])(\d{1,2})\s*[)）]")
# 改错题「“X”改为“Y”」: the model read the printed wrong word as the right one when X == Y.
_FIX_PAIR_RE = re.compile(r"[“\"「]([^”\"」]{1,12})[”\"」]\s*改为\s*[“\"「]([^”\"」]{1,12})[”\"」]")
_VISION_MISS_RE = re.compile(r"未收到|没有收到.*图|看不到.*图|无法查看|无法看到|未提供图")


def count_sub_marks(text: str | None) -> int:
    """Longest run (1)(2)…(k) in the text; a stray f(5) or repeated (1) does not add 小问."""
    nums = {int(a or b) for a, b in _SUB_MARK_RE.findall(str(text or ""))}
    k = 0
    while k + 1 in nums:
        k += 1
    return max(k, 1)


def split_by_sub_marks(text: str | None) -> dict[int, str]:
    """「（1）…（2）…」→ {1: …, 2: …}: marks taken in order 1, 2, … (a stray f(5) or repeated (1) is text)."""
    s = str(text or "")
    marks: list[tuple[int, int, int]] = []
    for m in _SUB_MARK_RE.finditer(s):
        if int(m.group(1) or m.group(2)) == len(marks) + 1:
            marks.append((len(marks) + 1, m.start(), m.end()))
    if len(marks) < 2:
        return {}
    ends = [start for _, start, _ in marks[1:]] + [len(s)]
    return {n: s[end:stop].strip(" \n；;。") for (n, _, end), stop in zip(marks, ends)}


def self_corrected_fix(answer: str | None) -> bool:
    """True when a 改错 pair reads 「X 改为 X」— the wrong word was silently corrected."""
    return any(a.strip() == b.strip() for a, b in _FIX_PAIR_RE.findall(str(answer or "")))


def _score_value(raw: Any) -> int | float | None:
    if raw in ("", None) or isinstance(raw, bool):
        return None
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return None
    if value < 0:
        return None
    return int(value) if value == int(value) else value


def _normalize_subs(raw: Any) -> list[dict[str, Any]]:
    """Model-given 小问 list. Scores the rubric does not state stay null — never spread."""
    if not isinstance(raw, list):
        return []
    by_sub: dict[int, dict[str, Any]] = {}
    for s in raw:
        if not isinstance(s, dict):
            continue
        try:
            sub = int(s.get("sub"))
        except (TypeError, ValueError):
            continue
        if sub < 1:
            continue
        answer = "" if s.get("answer") is None else str(s.get("answer")).strip()
        score = _score_value(s.get("score"))
        # half points exist on real rubrics; 2.67 only comes from spreading a total
        if isinstance(score, float) and score * 2 != int(score * 2):
            score = None
        by_sub[sub] = _merge_sub(by_sub.get(sub), {"sub": sub, "answer": answer, "score": score})
    return [by_sub[n] for n in sorted(by_sub)]


def _merge_sub(prev: dict[str, Any] | None, nxt: dict[str, Any]) -> dict[str, Any]:
    if prev is None:
        return dict(nxt)
    return {
        "sub": prev["sub"],
        "answer": prev["answer"] or nxt["answer"],
        "score": prev["score"] if prev["score"] is not None else nxt["score"],
    }


def merge_subs(a: list[dict[str, Any]], b: list[dict[str, Any]], *, append: int = 0) -> list[dict[str, Any]]:
    """append: the 小问 a continuation page carries on (its answer goes after the earlier part)."""
    by_sub = {s["sub"]: dict(s) for s in a}
    for s in b:
        prev = by_sub.get(s["sub"])
        merged = _merge_sub(prev, s)
        if append and s["sub"] == append and prev is not None and prev["answer"] and s["answer"]:
            merged["answer"] = _merge_text(prev["answer"], s["answer"])
        by_sub[s["sub"]] = merged
    return [by_sub[n] for n in sorted(by_sub)]


def answer_from_subs(answer: str, subs: list[dict[str, Any]]) -> str:
    """Keep the model's answer when it already carries every （n）; else rebuild it from subs."""
    if len(subs) < 2 or count_sub_marks(answer) >= len(subs):
        return answer
    if not any(s["answer"] for s in subs):
        return answer
    return "\n".join(f"（{s['sub']}）{s['answer']}" for s in subs)


def subs_total(subs: list[dict[str, Any]]) -> int | float | None:
    if not subs or any(s["score"] is None for s in subs):
        return None
    total = sum(s["score"] for s in subs)
    return int(total) if total == int(total) else total


def _type_from_hint(raw: Any) -> str:
    s = str(raw or "")
    low = s.lower()
    if low in TYPES:
        return low
    if re.search(r"不定项|多选|多项", s) or "multi" in low:
        return "multi_choice"
    if re.search(r"单选|单项|选择", s) or "choice" in low or "objective" in low:
        return "single_choice"
    if "填空" in s or "blank" in low or low == "fill":
        return "fill_in_blank"
    return "short_answer"


def _flatten(raw_list: list[Any]) -> list[dict[str, Any]]:
    """Section envelopes ({questionNumbers, answers}) → one dict per question."""
    out: list[dict[str, Any]] = []
    for raw in raw_list:
        if not isinstance(raw, dict):
            continue
        nums = raw.get("questionNumbers") or raw.get("question_numbers")
        if isinstance(nums, list) and nums:
            answers = raw.get("answers") if isinstance(raw.get("answers"), list) else []
            for idx, num in enumerate(nums):
                out.append(
                    {
                        "number": num,
                        "type": raw.get("type"),
                        "section": raw.get("section"),
                        "answer": answers[idx] if idx < len(answers) else "",
                        "score": raw.get("scorePerQuestion") or raw.get("score"),
                        "options_count": raw.get("options_count"),
                    }
                )
            continue
        nested = raw.get("questions")
        if isinstance(nested, list) and nested and all(isinstance(q, dict) for q in nested):
            for q in nested:
                item = dict(q)
                item.setdefault("section", raw.get("section"))
                item.setdefault("type", raw.get("type"))
                out.append(item)
            continue
        out.append(raw)
    return out


def is_vision_miss(item: dict[str, Any]) -> bool:
    text = " ".join(str(item.get(k) or "") for k in ("answer", "rubric", "text"))
    return bool(_VISION_MISS_RE.search(text))


def normalize_item(
    raw: dict[str, Any], *, page: int | None, task: str = "answers"
) -> dict[str, Any] | None:
    if raw.get("kind") == "material":
        return _normalize_material(raw, page=page)
    # 0 is never a 题号: the page prompt asks for number 0 on page-top continuations,
    # and the model sometimes forgets the companion "continued": true.
    try:
        number = int(float(raw.get("number", raw.get("qno", raw.get("question_no")))))
    except (TypeError, ValueError):
        if raw.get("continued") is not True:
            return None
        number = 0
    if number < 0:
        return None
    qtype = _type_from_hint(raw.get("type"))
    answer = "" if raw.get("answer") is None else str(raw.get("answer")).strip()
    rubric_raw = raw.get("rubric", raw.get("细则", raw.get("scoring_rubric", "")))
    rubric = "" if rubric_raw is None else str(rubric_raw).strip()

    score = _score_value(raw.get("score"))

    if qtype in ("single_choice", "multi_choice"):
        letters = re.sub(r"[^A-Ha-h]", "", answer).upper()
        if letters:
            answer = letters
            if task not in ("structure", "paper") and len(letters) > 1 and qtype == "single_choice":
                qtype = "multi_choice"
        try:
            raw_opts = raw.get("options_count")
            options_count = int(raw_opts) if raw_opts not in (None, "") else None
        except (TypeError, ValueError):
            options_count = None
        if task in ("structure", "paper"):
            if options_count is not None and options_count < 2:
                options_count = None
        else:
            if options_count is None or options_count < 2:
                options_count = 4
    else:
        options_count = None

    has_figure = raw.get("has_figure") is True or raw.get("hasFigure") is True
    try:
        sub_count = int(raw.get("sub_count") or raw.get("subCount") or 0)
    except (TypeError, ValueError):
        sub_count = 0
    subs = [] if qtype in ("single_choice", "multi_choice") else _normalize_subs(raw.get("subs"))
    if subs:
        if any(not s["answer"] for s in subs):
            # the model wrote the whole 「（1）…（2）…」 in answer and left subs blank (一模 18, edu-core#3164)
            parts = split_by_sub_marks(answer)
            subs = [{**s, "answer": s["answer"] or parts.get(s["sub"], "")} for s in subs]
        answer = answer_from_subs(answer, subs)
        sub_count = subs[-1]["sub"]
        if score is None:
            score = subs_total(subs)
    else:
        sub_count = max(sub_count, count_sub_marks(answer), 1)
        if has_figure and task != "paper":
            sub_count = max(sub_count, 3)

    quote = str(raw.get("quote") or "").strip()[:60]
    section = raw.get("section")
    blanks = (
        []
        if qtype in ("single_choice", "multi_choice")
        else _normalize_blanks(raw.get("blanks"))
    )
    return {
        "number": number,
        "type": qtype,
        "section": str(section).strip() if section not in (None, "") else None,
        "answer": answer,
        "rubric": rubric,
        "analysis": _text(raw.get("analysis", raw.get("解析"))),
        "stem": _text(raw.get("stem")),
        "material_id": None,
        "figures": _normalize_figures(raw.get("figures"), page=page),
        "score": score,
        "options_count": options_count,
        "sub_count": sub_count,
        "subs": subs,
        "has_figure": has_figure,
        "blanks": blanks,
        "uncertain": raw.get("uncertain") is True,
        "source": {"page": page, "quote": quote},
    }


def _text(raw: Any) -> str:
    return "" if raw is None else str(raw).strip()


def _numbers(raw: Any) -> list[int]:
    if not isinstance(raw, list):
        return []
    out: set[int] = set()
    for v in raw:
        try:
            n = int(float(v))
        except (TypeError, ValueError):
            continue
        if n > 0:
            out.add(n)
    return sorted(out)


def _normalize_figures(raw: Any, *, page: int | None) -> list[dict[str, Any]]:
    """Figure boxes on a page image, 0–1000 of page width / height. Text reads have no page → []."""
    if page is None or not isinstance(raw, list):
        return []
    out: list[dict[str, Any]] = []
    for f in raw:
        if not isinstance(f, dict):
            continue
        native = f.get("box_2d")
        box = native if native is not None else f.get("box")
        if not isinstance(box, list) or len(box) != 4:
            continue
        try:
            a0, b0, a1, b1 = (min(max(round(float(v)), 0), 1000) for v in box)
        except (TypeError, ValueError):
            continue
        # box_2d is the vision models' native [ymin, xmin, ymax, xmax]; box is [x0, y0, x1, y1].
        x0, y0, x1, y1 = (b0, a0, b1, a1) if native is not None else (a0, b0, a1, b1)
        x0, x1 = min(x0, x1), max(x0, x1)
        y0, y1 = min(y0, y1), max(y0, y1)
        if x1 - x0 < 10 or y1 - y0 < 10:
            continue
        out.append({"page": page, "box": [x0, y0, x1, y1]})
    return out


def _normalize_material(raw: dict[str, Any], *, page: int | None) -> dict[str, Any] | None:
    """Shared 材料 (passage / poem / data) is its own item; it never rides on one question."""
    text = _text(raw.get("material", raw.get("text")))
    figures = _normalize_figures(raw.get("figures"), page=page)
    if not text and not figures:
        return None
    return {
        "kind": "material",
        "material": text,
        "material_for": _numbers(raw.get("material_for")),
        "figures": figures,
        "continued": raw.get("continued") is True,
    }


def is_material(item: dict[str, Any]) -> bool:
    return item.get("kind") == "material"


def collect_materials(
    batches: list[list[dict[str, Any]]], questions: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Reading order → materials with ids; tag each question with the material it rests on.

    A material without material_for owns the questions after it until the next material.
    The same material_for seen twice (one passage re-read on two pages) is one material.
    """
    out: list[dict[str, Any]] = []
    by_key: dict[tuple[int, ...], dict[str, Any]] = {}
    open_mat: dict[str, Any] | None = None
    for batch in batches:
        for item in batch:
            if is_material(item):
                key = tuple(item["material_for"])
                same = by_key.get(key) if key else None
                if same is not None:
                    same["material"] = _merge_text(same["material"], item["material"])
                    same["figures"] = same["figures"] + item["figures"]
                    open_mat = None
                    continue
                mat = {
                    "id": f"M{len(out) + 1}",
                    "material_for": list(item["material_for"]),
                    "material": item["material"],
                    "figures": list(item["figures"]),
                }
                out.append(mat)
                if key:
                    by_key[key] = mat
                open_mat = None if key else mat
            elif open_mat is not None and item["number"] not in open_mat["material_for"]:
                open_mat["material_for"].append(item["number"])
    by_no = {q["number"]: q for q in questions}
    for mat in out:
        mat["material_for"] = sorted(set(mat["material_for"]))
        for n in mat["material_for"]:
            q = by_no.get(n)
            if q is not None and q.get("material_id") is None:
                q["material_id"] = mat["id"]
    return out


def _normalize_blanks(raw: Any) -> list[dict[str, Any]]:
    """Pass through model-tagged 空. Missing / unknown flex is dropped — never guessed."""
    if not isinstance(raw, list):
        return []
    out: list[dict[str, Any]] = []
    for b in raw:
        if not isinstance(b, dict):
            continue
        flex = str(b.get("flex") or "").strip().lower()
        if flex not in ("fixed", "open"):
            continue
        text = "" if b.get("text") is None else str(b.get("text")).strip()
        try:
            sub = int(b.get("sub") or 1)
        except (TypeError, ValueError):
            sub = 1
        out.append({"sub": max(sub, 1), "text": text, "flex": flex})
    return out


def items_from_model_text(
    text: str, *, page: int | None, task: str = "answers"
) -> list[dict[str, Any]]:
    parsed = parse_json_array(text) or []
    items: list[dict[str, Any]] = []
    for raw in _flatten(parsed):
        if not isinstance(raw, dict) or is_vision_miss(raw):
            continue
        item = normalize_item(raw, page=page, task=task)
        if item is None:
            continue
        items.append(item)
    return items


def _gap_owner(
    batches: list[list[dict[str, Any]]], idx: int, pos: int, last: int, order: list[int] | None
) -> int:
    """Whose page-top continuation this is when the page before it was not read.

    The question it continues started before this page, and the next 题号 read after it starts
    later; so it is the question just before that next one (roster order when edu sent the first
    round's 题号, else next − 1). Never older than the last question read; 0 = unknown, dropped.
    """
    nxt = 0
    for j in range(idx, len(batches)):
        for item in batches[j][pos + 1 :] if j == idx else batches[j]:
            if not is_material(item) and item["number"] > 0:
                nxt = item["number"]
                break
        if nxt:
            break
    if order:
        if nxt in order:
            i = order.index(nxt)
            owner = order[i - 1] if i > 0 else 0
        else:
            owner = 0 if nxt else order[-1]
    else:
        owner = nxt - 1 if nxt else 0
    return owner if owner >= last and owner > 0 else 0


def _split_new_marks(text: str, after: int) -> list[tuple[int, str]]:
    """A continuation page's text cut at the （n）marks that open new 小问 (after+1, after+2, …);
    the part before the first one carries on 小问 `after`."""
    s = text or ""
    marks: list[tuple[int, int, int]] = []
    for m in _SUB_MARK_RE.finditer(s):
        if int(m.group(1) or m.group(2)) == after + len(marks) + 1:
            marks.append((after + len(marks) + 1, m.start(), m.end()))
    trim = " \n；;。"
    parts = [(after, s[: marks[0][1]] if marks else s)]
    for k, (n, _, end) in enumerate(marks):
        parts.append((n, s[end : marks[k + 1][1] if k + 1 < len(marks) else len(s)]))
    # a new (n) is kept even with nothing after it (its place in the order still counts)
    return [(n, t.strip(trim)) for n, t in parts if n != after or t.strip(trim)]


def _renumber_continued(item: dict[str, Any], seen: int) -> dict[str, Any]:
    """Put a continuation page's 小问 under the 卷面 (n) they belong to.

    One page = one call, so the page after 17 (1) numbers its own 小问 from 1 again: 「（2）…」
    came back as sub 1 and lost to the real (1) in the merge, and 17–21 of a 54-page 讲评 PDF
    lost every printed answer after (1) that way (edu-core#3164). seen = the owner's last 小问 so
    far; text before the page's first new (n) still belongs to it and is appended to it.
    """
    if not seen or item["type"] in ("single_choice", "multi_choice"):
        return item
    subs = item.get("subs") or []
    # the page's own (n) marks say which 小问 it holds; the stem has them, an answer-only read has
    # them in the answer
    targets = [n for n, _ in _split_new_marks(item.get("stem") or item.get("answer") or "", seen)] or [seen]
    if not subs:
        parts = [(n, t) for n, t in _split_new_marks(item.get("answer") or "", seen) if t]
        if parts and len(parts) == 1 and parts[0][0] == seen:
            parts = [(targets[0], parts[0][1])]  # unmarked answer: the 小问 the stem opens
            circled = re.match(r"\s*([①-⑳])", item.get("stem") or "")
            if circled and targets[0] == seen and not re.match(r"\s*[①-⑳]", parts[0][1]):
                # 「②图中的序列…」 page: its answer is the ② of that 小问
                parts = [(seen, circled.group(1) + parts[0][1])]
        if not parts:
            return item
        return {
            **item,
            "subs": [{"sub": n, "answer": t, "score": None} for n, t in parts],
            "_tail_sub": seen if parts[0][0] == seen else 0,
        }
    nums = [s["sub"] for s in subs]
    if all(n in targets or n > seen for n in nums):
        return {**item, "_tail_sub": seen if seen in nums else 0}
    # numbered from 1 again: map them onto the page's (n) in order
    pick = {n: targets[min(i, len(targets) - 1)] for i, n in enumerate(nums)}
    renum: dict[int, dict[str, Any]] = {}
    for s in subs:
        t = pick[s["sub"]]
        prev = renum.get(t)
        renum[t] = {**s, "sub": t} if prev is None else {**prev, "answer": _merge_text(prev["answer"], s["answer"])}
    return {
        **item,
        "subs": [renum[t] for t in sorted(renum)],
        "blanks": [{**b, "sub": pick.get(b["sub"], b["sub"])} for b in item.get("blanks") or []],
        "_tail_sub": seen if seen in renum else 0,
    }


def attach_continued(
    batches: list[list[dict[str, Any]]], ok: list[bool] | None = None, order: list[int] | None = None
) -> list[list[dict[str, Any]]]:
    """Page-top content with no new 题号 (number 0) belongs to the last question read so far.

    One page = one model call, so the model on page 3 cannot know that its leading
    (3)(4) continue 17 from page 2; it marks them continued and the merge order says whose.
    Its 小问 are renumbered under the owner's (see _renumber_continued). A page that was not
    read only hides itself: a continuation after it goes to the question just before the next
    题号 (_gap_owner), and is dropped only when that is unknown or nothing was read before it.
    """
    last = 0
    gap = False
    seen: dict[int, int] = {}
    last_mat: dict[str, Any] | None = None
    out: list[list[dict[str, Any]]] = []
    for idx, batch in enumerate(batches):
        kept: list[dict[str, Any]] = []
        for pos, item in enumerate(batch):
            if is_material(item):
                if not item["continued"]:
                    last_mat = {**item, "figures": list(item["figures"])}
                    kept.append(last_mat)
                elif last_mat is not None:
                    last_mat["material"] = _merge_text(last_mat["material"], item["material"])
                    last_mat["figures"] += item["figures"]
                continue
            if item["number"] == 0:
                owner = _gap_owner(batches, idx, pos, last, order) if gap else last
                if owner:
                    item = _renumber_continued({**item, "number": owner}, seen.get(owner, 0))
                    last = max(last, owner)
                    kept.append(item)
                else:
                    continue
            else:
                kept.append(item)
            n = item["number"]
            subs_max = max((s["sub"] for s in item.get("subs") or []), default=0)
            stem_marks = count_sub_marks(item.get("stem")) if item.get("stem") else 0
            seen[n] = max(seen.get(n, 0), subs_max, stem_marks)
        numbers = [i["number"] for i in kept if not is_material(i)]
        if numbers:
            last = max(last, max(numbers))
            gap = False
        if ok is not None and idx < len(ok) and not ok[idx]:
            gap = True
            last_mat = None
        out.append(kept)
    return out


def _merge_blanks(prev: list[dict[str, Any]], nxt: list[dict[str, Any]]) -> list[dict[str, Any]]:
    have = {b["sub"] for b in prev}
    return prev + [b for b in nxt if b["sub"] not in have]


def _merge_rubric(prev: str, nxt: str) -> str:
    if not nxt:
        return prev
    if not prev:
        return nxt
    if nxt in prev:
        return prev
    if prev in nxt:
        return nxt
    return f"{prev}\n{nxt}"


def _merge_text(prev: str, nxt: str) -> str:
    """Same rule as the rubric: a page-top continuation appends, a repeat is dropped."""
    return _merge_rubric(prev or "", nxt or "")


def merge_items(batches: list[list[dict[str, Any]]], *, solve: bool = False) -> list[dict[str, Any]]:
    """Merge per-page / per-chunk items by number. Earlier batch wins on answer.

    solve: every page that shows a question answers all of it, so a second page's analysis /
    rubric is the same solution written again (一模 10 / 17 / 21 twice over, edu-core#3164); it is
    only added when that page answered 小问 the earlier one left blank (17 (3)(4) on the next page).
    """
    by_no: dict[int, dict[str, Any]] = {}
    for batch in batches:
        for item in batch:
            if is_material(item):
                continue
            page = (item.get("source") or {}).get("page")
            prev = by_no.get(item["number"])
            if prev is None:
                by_no[item["number"]] = {**item, "on_pages": [page] if page else []}
                continue
            merged = dict(prev)
            if page and page not in merged["on_pages"]:
                merged["on_pages"] = sorted([*merged["on_pages"], page])
            if not prev["answer"] and item["answer"]:
                merged.update(
                    {
                        "answer": item["answer"],
                        "type": item["type"],
                        "options_count": item["options_count"],
                        "source": item["source"],
                    }
                )
            if prev["score"] is None and item["score"] is not None:
                merged["score"] = item["score"]
            if not prev["section"] and item["section"]:
                merged["section"] = item["section"]
            answered = {x["sub"] for x in prev.get("subs") or [] if x["answer"]}
            adds = not solve or any(x["answer"] and x["sub"] not in answered for x in item.get("subs") or [])
            if adds or not prev["rubric"]:
                merged["rubric"] = _merge_rubric(prev["rubric"], item["rubric"])
            for key in ("analysis", "stem"):
                if adds or not prev.get(key):
                    merged[key] = _merge_text(prev.get(key, ""), item.get(key, ""))
            merged["figures"] = (prev.get("figures") or []) + (item.get("figures") or [])
            subs = merge_subs(prev.get("subs") or [], item.get("subs") or [], append=item.get("_tail_sub") or 0)
            merged["subs"] = subs
            if subs:
                merged["answer"] = answer_from_subs(merged["answer"], subs)
                merged["sub_count"] = subs[-1]["sub"]
                if merged["score"] is None:
                    merged["score"] = subs_total(subs)
            else:
                merged["sub_count"] = max(prev["sub_count"], item["sub_count"])
            merged["has_figure"] = prev["has_figure"] or item["has_figure"]
            merged["uncertain"] = bool(prev.get("uncertain") or item.get("uncertain"))
            merged["blanks"] = _merge_blanks(prev.get("blanks") or [], item.get("blanks") or [])
            by_no[item["number"]] = merged
    for q in by_no.values():
        q.pop("_tail_sub", None)
    return [by_no[n] for n in sorted(by_no)]


def json_looks_truncated(raw: str) -> bool:
    s = strip_fence(raw).rstrip()
    if not s:
        return False
    if s.endswith("]"):
        return False
    return "[" in s or '"number"' in s


_ROSTER_PAGES_RE = re.compile(r"\s+pages=([\d,]+)")


def roster_pages(roster: str) -> dict[int, set[int]]:
    """题号 → pages it sits on, from roster lines tagged ` pages=2,3` (edu sends the pages the
    paper read found each question on). Untagged lines are absent: every page may answer them."""
    out: dict[int, set[int]] = {}
    for line in (roster or "").splitlines():
        m = re.match(r"\s*(\d+)\s", line + " ")
        tag = _ROSTER_PAGES_RE.search(line)
        if not m or not tag:
            continue
        pages = {int(p) for p in tag.group(1).split(",") if p.isdigit() and int(p) > 0}
        if pages:
            out[int(m.group(1))] = pages
    return out


def roster_for_page(roster: str, page: int) -> str:
    """The roster lines this page may answer, page tags stripped. A tagged question is asked
    only on its own pages, so a page cannot guess at a question it cannot see."""
    keep: list[str] = []
    for line in (roster or "").splitlines():
        tag = _ROSTER_PAGES_RE.search(line)
        if tag and page not in {int(p) for p in tag.group(1).split(",") if p.isdigit()}:
            continue
        keep.append(_ROSTER_PAGES_RE.sub("", line))
    return "\n".join(keep).strip()


def roster_numbers(roster: str) -> list[int]:
    out: list[int] = []
    for m in re.finditer(r"(?m)^(\d+)\s", roster or ""):
        n = int(m.group(1))
        if n > 0:
            out.append(n)
    return out


def chunk_text(text: str, limit: int = TEXT_CHUNK_CHARS) -> list[str]:
    text = text.replace("\r\n", "\n").strip()
    if len(text) <= limit:
        return [text] if text else []
    chunks: list[str] = []
    buf: list[str] = []
    size = 0
    for line in text.split("\n"):
        if size + len(line) + 1 > limit and buf:
            chunks.append("\n".join(buf))
            buf, size = [], 0
        buf.append(line)
        size += len(line) + 1
    if buf:
        chunks.append("\n".join(buf))
    return chunks


# --------------------------------------------------------------------------- model


def _has_images(messages: list[dict[str, Any]]) -> bool:
    for msg in messages:
        content = msg.get("content")
        if isinstance(content, list) and any(
            isinstance(p, dict) and p.get("type") == "image" for p in content
        ):
            return True
    return False


def _to_chat_messages(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for msg in messages:
        content = msg.get("content")
        if isinstance(content, list):
            parts: list[dict[str, Any]] = []
            for p in content:
                if p.get("type") == "image":
                    url = f"data:{p['mime']};base64,{p['data_b64']}"
                    parts.append({"type": "image_url", "image_url": {"url": url}})
                else:
                    parts.append({"type": "text", "text": str(p.get("text") or "")})
            out.append({"role": msg["role"], "content": parts})
        else:
            out.append({"role": msg["role"], "content": str(content or "")})
    return out


def _to_responses_messages(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for msg in messages:
        content = msg.get("content")
        if isinstance(content, list) and msg.get("role") != "system":
            parts: list[dict[str, Any]] = []
            for p in content:
                if p.get("type") == "image":
                    url = f"data:{p['mime']};base64,{p['data_b64']}"
                    parts.append({"type": "input_image", "image_url": url, "detail": "high"})
                else:
                    parts.append({"type": "input_text", "text": str(p.get("text") or "")})
            out.append({"role": msg["role"], "content": parts})
        else:
            out.append({"role": msg["role"], "content": str(content or "")})
    return out


async def model_complete(
    messages: list[dict[str, Any]],
    *,
    max_tokens: int = DEFAULT_MAX_OUTPUT_TOKENS,
    thinking: bool | None = False,
    usage_out: dict[str, Any] | None = None,
    model_out: dict[str, Any] | None = None,
) -> str:
    """One completion against the product brain. Images switch to the vision entry."""
    from pico_orchestrator import provider as P
    from pico_orchestrator.vision import vision_model_for_images

    cfg = P.resolve_provider()
    if cfg is None:
        raise ExtractError(
            "model.unconfigured", "Pico 没配模型脑（DEEPSEEK_API_KEY / KIMI_API_KEY）"
        )
    if thinking:
        # 推理的 token 也算在输出上限里：不另给，一页三道遗传大题推满 16k 就把答案截掉了（edu-core#3164）
        max_tokens += think_tokens()
    mid = P.product_backend_model(deep=False)
    if _has_images(messages):
        mid = vision_model_for_images(mid)
    # Same New API, next model when the brain's channel or key is dead — the
    # same rule as chat (pico#1271): 401/402/403, no channel, quota gone — or
    # busy: a 429 / 5xx that outlasted the retry. Vertex quota 429s one model,
    # not the backup on its own key (3 papers at once: 50 × 429 in 3 min, pages
    # fell back to no thinking, edu-core#3509). A refusal or a timeout stays on
    # this model. Image pages skip a backup that cannot read images.
    models = [mid]
    if cfg.name == "deepseek" and P.uses_new_api_openai_overlay(cfg):
        from pico_orchestrator.brain_ha import brain_candidates
        from pico_orchestrator.vision import model_accepts_image

        images = _has_images(messages)
        models = [
            m for m in brain_candidates(mid) if not images or model_accepts_image(m)
        ][:2] or [mid]
    from pico_orchestrator import upstream
    from pico_orchestrator.brain_ha import mark_down

    sent = [0]
    for i, model in enumerate(models):
        budget = upstream.CALL_BUDGET - sent[0]  # three requests across both models
        if i + 1 < len(models) and budget > 1:
            budget -= 1  # the head leaves the backup one request
        try:
            text = await _complete_once(
                P, cfg, model, messages, sent, budget=budget,
                max_tokens=max_tokens, thinking=thinking, usage_out=usage_out,
            )
        except Exception as exc:
            dead = _brain_dead(exc)
            if i + 1 >= len(models) or upstream.CALL_BUDGET - sent[0] < 1 or not (dead or _brain_busy(exc)):
                raise
            if dead:
                mark_down(model)
            logger.warning(
                "exam brain %s %s, next %s: %s",
                model, "dead" if dead else "busy", models[i + 1], str(exc)[:200],
            )
            continue
        if model_out is not None:
            model_out["model"] = model  # bill the model that answered
        return text
    raise AssertionError("unreachable")


def _brain_dead(exc: BaseException) -> bool:
    """This model cannot answer now (key / channel / quota), not a busy or slow one."""
    from pico_orchestrator import upstream
    from pico_orchestrator.brain_ha import is_model_dead

    status = upstream.status_of(exc)
    if status in upstream.RETRY_STATUS or isinstance(exc, TimeoutError):
        return False
    return status in upstream.DEAD_STATUS or is_model_dead(f"{exc} {exc.__cause__ or ''}")


def _brain_busy(exc: BaseException) -> bool:
    """The relay kept answering 429 / 5xx through the retry: this model's quota, not the request."""
    from pico_orchestrator import upstream

    return upstream.status_of(exc) in upstream.RETRY_STATUS


async def _complete_once(
    P: Any,
    cfg: Any,
    mid: str,
    messages: list[dict[str, Any]],
    sent: list[int],
    *,
    budget: int,
    max_tokens: int,
    thinking: bool | None,
    usage_out: dict[str, Any] | None,
) -> str:
    """One model through Pico's one door (key slot, budget, pause before a retry)."""
    cfg = replace(cfg, model=mid)
    # Wire follows the model we send, not the brain's: gpt-*/grok-* on
    # chat/completions get 400 invalid_request from New API (pico#1288).
    if P.uses_openai_responses_brain(cfg):

        async def read_stream() -> str:
            sent[0] += 1
            pieces: list[str] = []
            async for piece in P._iter_openai_responses(
                cfg,
                mid,
                _to_responses_messages(messages),
                max_tokens=max_tokens,
                thinking=thinking,
                usage_out=usage_out,
                purpose="exam",
            ):
                pieces.append(piece)
            return "".join(pieces)

        return await P.call_once(cfg, "exam", read_stream, budget=budget)

    client = P._llm_client(cfg)
    kwargs: dict[str, Any] = {
        "model": mid,
        "messages": _to_chat_messages(messages),
        "stream": False,
        "max_tokens": max_tokens,
        "temperature": 0.1,
        "user": "pico-exam",
    }
    extra = P.thinking_extra_body(mid, thinking=thinking)
    if extra:
        kwargs["extra_body"] = extra

    async def create() -> Any:
        sent[0] += 1
        return await client.chat.completions.create(**kwargs)

    resp = await P.call_once(cfg, "exam", create, budget=budget)
    usage = getattr(resp, "usage", None)
    spent: dict[str, Any] = {}
    if usage is not None:
        from pico_orchestrator.usage_parse import add_usage, parse_usage_blob

        spent = parse_usage_blob(usage) or {}
        if usage_out is not None:
            merged = add_usage(dict(usage_out) if usage_out else None, spent)
            usage_out.clear()
            if merged:
                usage_out.update(merged)
    choices = getattr(resp, "choices", None) or []
    if choices and thought_out(getattr(choices[0], "finish_reason", None), spent, max_tokens):
        # Gemini 3 behind New API thought 15.4k of 16k on a structure read and cut the paper
        # after question 4; the "continue" reads then guessed 17 / 21 as one sub each (edu-core#3508).
        logger.warning(
            "exam extract %s thinking ate the output: reasoning=%s completion=%s cap=%s thinking=%s",
            mid, spent.get("reasoning_tokens"), spent.get("completion_tokens"), max_tokens, thinking,
        )
        raise ThinkingRanOut(f"模型思考用完了输出上限（{spent.get('reasoning_tokens')} / {max_tokens}），这次没读全")
    return str(choices[0].message.content or "") if choices else ""


def thought_out(finish_reason: Any, spent: dict[str, Any], max_tokens: int) -> bool:
    """Stopped at the cap and thinking took at least half of the output."""
    if str(finish_reason or "") != "length":
        return False
    reasoning = int(spent.get("reasoning_tokens") or 0)
    output = int(spent.get("completion_tokens") or 0) or max_tokens
    return reasoning > 0 and reasoning * 2 >= output


# --------------------------------------------------------------------------- pipeline


def _env_int(name: str, default: int) -> int:
    try:
        return max(1, int(os.environ.get(name, "") or default))
    except ValueError:
        return default


def _env_seconds(name: str, default: float) -> float:
    try:
        value = float(os.environ.get(name, "") or default)
    except ValueError:
        return default
    return value if value > 0 else default


async def hedged(
    make: Callable[[], Awaitable[str]], *, after: float, slot: asyncio.Semaphore | None = None
) -> str:
    """Send once; no answer after `after` seconds → send the same once more, first answer wins.

    The copy waits for a free `slot` (it never takes a page's place); the loser is cancelled.
    Both failed → the first one's error.
    """
    first = asyncio.ensure_future(make())
    done, _ = await asyncio.wait({first}, timeout=after)
    if done:
        return first.result()

    logger.warning("exam extract call no answer after %ss, sending a copy", after)
    started = asyncio.Event()

    async def copy() -> str:
        if slot is None:
            started.set()
            return await make()
        async with slot:
            started.set()
            return await make()

    second = asyncio.ensure_future(copy())
    pending = {first, second}
    try:
        while pending:
            done, pending = await asyncio.wait(pending, return_when=asyncio.FIRST_COMPLETED)
            for task in done:
                if task.exception() is None:
                    return task.result()
            if first in done and not started.is_set():
                break  # the first failed and the copy never got a slot: nothing left to wait for
        raise first.exception() if first.done() and first.exception() else second.exception()
    finally:
        for task in (first, second):
            if not task.done():
                task.cancel()


def _preview(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "")).strip()[:80]


def _failed_page(page: int, exc: BaseException) -> dict[str, Any]:
    code = getattr(exc, "code", None) or type(exc).__name__
    return {"page": page, "ok": False, "count": 0, "error": f"{code}: {_preview(str(exc))}"}


# Gemini blocks some whole pages at the prompt (``prompt_blocked … SAFETY``) whatever
# safetySettings say: OFF / BLOCK_NONE were blocked alike on a chemistry key whose
# halves each read fine (pico#1193). The block is not deterministic either: one biology
# page (fragile-X pedigree + gel, edu-core#3164) was blocked in 1 of 6 identical reads, and
# whole + both halves in two live runs. So the whole page is asked again a couple of times
# before it is cut in halves (backup brains were tried: sol 400s on this path, grok
# timed out on a full page and misread a small one).
_SAFETY_REASKS = 2
_SAFETY_BLOCK_RE = re.compile(r"prompt_blocked|blocked by Gemini|\bSAFETY\b|PROHIBITED_CONTENT")


class SafetyBlocked(RuntimeError):
    """The brain refused the page image itself; retrying the same bytes cannot help."""


def is_safety_block(exc: BaseException) -> bool:
    return isinstance(exc, SafetyBlocked) or bool(_SAFETY_BLOCK_RE.search(str(exc)))


def split_page_image(mime: str, data_b64: str) -> list[dict[str, str]] | None:
    """Cut a page image in two at the emptiest row of its middle third (never mid-line).

    Each half carries y0 / y1, its span on the page (0–1000), to map its figure boxes back.
    None when the bytes are not an image Pillow can open — the page then stays failed.
    """
    from PIL import Image

    try:
        img = Image.open(io.BytesIO(base64.b64decode(data_b64)))
        img.load()
    except Exception:  # noqa: BLE001 — undecodable page: no split, caller reports the block
        return None
    width, height = img.size
    if height < 6:
        return None
    ink = img.convert("L").point(lambda v: 255 if v < 160 else 0)
    mid = height // 2

    def score(y: int) -> tuple[int, int]:
        return ink.crop((0, y, width, y + 1)).histogram()[255], abs(y - mid)

    cut = min(range(height // 3, 2 * height // 3), key=score)
    halves = []
    for box in ((0, 0, width, cut), (0, cut, width, height)):
        buf = io.BytesIO()
        img.crop(box).save(buf, format="PNG")
        halves.append(
            {
                "mime": "image/png",
                "data_b64": base64.b64encode(buf.getvalue()).decode(),
                "y0": round(box[1] * 1000 / height),
                "y1": round(box[3] * 1000 / height),
            }
        )
    return halves


def remap_half_figures(items: list[dict[str, Any]], y0: int, y1: int) -> list[dict[str, Any]]:
    """A half read gives boxes on the half (0–1000 of its height); the crop runs on the whole page.

    Unmapped, 一模 page 5's bottom-half table box framed 17's text above it (edu-core#3164).
    """

    def page_y(v: int) -> int:
        return round(y0 + v * (y1 - y0) / 1000)

    out = []
    for item in items:
        figures = [
            {**f, "box": [f["box"][0], page_y(f["box"][1]), f["box"][2], page_y(f["box"][3])]}
            for f in item.get("figures") or []
        ]
        out.append({**item, "figures": figures})
    return out


def fill_from(base: list[dict[str, Any]], extra: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Items read from a blocked page's text layer fill what the half reads left out.

    A question the halves never saw is added; one they saw keeps its fields (and its figure
    boxes, the text read has none) and takes only the ones still empty.
    """
    out = [dict(i) for i in base]
    by_no = {i["number"]: i for i in out if not is_material(i) and i["number"] > 0}
    texts = {m["material"] for m in out if is_material(m)}
    for item in extra:
        if is_material(item):
            if item["material"] and item["material"] not in texts:
                out.append(item)
            continue
        have = by_no.get(item["number"])
        if have is None:
            out.append(item)
            if item["number"] > 0:
                by_no[item["number"]] = item
            continue
        for key in ("stem", "answer", "analysis", "rubric", "section"):
            if not have.get(key) and item.get(key):
                have[key] = item[key]
        if have["score"] is None:
            have["score"] = item["score"]
        have["subs"] = merge_subs(have.get("subs") or [], item.get("subs") or [])
        have["blanks"] = _merge_blanks(have.get("blanks") or [], item.get("blanks") or [])
    return out


# Resending a page belongs to Pico's door to the relay (pico#1271: three requests
# at most, a pause before each retry). The old 5 tries here × the door's 3 × 4 pages
# × continuation rounds hammered a busy relay. PICO_EXAM_EXTRACT_ATTEMPTS stays as
# an ops knob (a whole-page re-ask, e.g. after a 240 s page timeout); default once.
_DEFAULT_ATTEMPTS = 1
# pause before the one re-read of pages an upstream burst took out (extract_pages)
_PAGE_REASK_PAUSE_S = 20
# Pages of one paper in flight; the relay key's slot cap bounds all papers together.
_DEFAULT_CONCURRENCY = 4
# Reasoning effort for one page image. "low" (thinking=False) matched or beat "medium"
# on every page of the 1092×1648 gold scan (21 runs, edu-core#1506) and returns rubric
# pages in half the time; the miss-reads came from 524 px pages, not from effort.
# "medium" stays one env flip away. It must ask for thinking explicitly: the provider
# default for Gemini flash is now thinking off (#1183), so None no longer meant medium.
_DEFAULT_PAGE_EFFORT = "low"
_DEFAULT_SOLVE_EFFORT = "medium"
_DEFAULT_THINK_TOKENS = 16_000
# A page read that has not answered after this long gets the same request once more, and the
# first answer wins. Live (edu-core#3164 probe, 66 page reads): 300–700-token reads normally take
# 6–11 s, yet 7 of them sat 64–233 s (one 489-token page 236 s, the same page 7 s when re-sent):
# the relay stalls, the page is not heavy. Raising the 240 s limit or cutting pages fixes neither.
# Long legit reads (10k-token outputs, 70–100 s) may get a copy too; the first one still wins.
_DEFAULT_HEDGE_S = 60
# copies in flight per paper on top of its pages (the relay key's slot cap still bounds all)
_DEFAULT_HEDGE_SLOTS = 2


def think_tokens() -> int:
    """开推理时另加在输出上限上的 token（推理也算输出，不另给就挤掉答案）。

    Gemini 3.8 flash 经 New API 推理不封顶：thinking_budget 8192、reasoning_effort low 都照推
    13–23k，thinking_level low 等于不推（实测 edu-core#3164）。所以只加余量，推爆了由
    extract_pages 的 read 退回不推理再读一次。
    """
    return _env_int("PICO_EXAM_EXTRACT_THINK_TOKENS", _DEFAULT_THINK_TOKENS)


def page_thinking() -> bool:
    effort = (os.environ.get("PICO_EXAM_EXTRACT_PAGE_EFFORT") or _DEFAULT_PAGE_EFFORT).strip().lower()
    return effort == "medium"


def task_thinking(task: str, default: bool) -> bool:
    """Solving thinks; reading (structure / paper / printed answers) keeps its effort.

    Without thinking the solve wrote its working into analysis (「等等，重新分析」, two answers
    to one question) and got 12 / 21 of 一模定稿 wrong against its own analysis (edu-core#3164).
    """
    if task != "solve":
        return default
    effort = (os.environ.get("PICO_EXAM_EXTRACT_SOLVE_EFFORT") or _DEFAULT_SOLVE_EFFORT).strip().lower()
    return effort == "medium"


async def _complete_with_retry(
    complete: Completer,
    messages: list[dict[str, Any]],
    *,
    thinking: bool | None,
    usage: dict[str, Any],
    model_out: dict[str, Any],
    attempts: int | None = None,
    timeout: int | None = None,
    sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
) -> str:
    tries = attempts or _env_int("PICO_EXAM_EXTRACT_ATTEMPTS", _DEFAULT_ATTEMPTS)
    limit = timeout or _env_int("PICO_EXAM_EXTRACT_PAGE_SECONDS", 240)
    last: BaseException | None = None
    for n in range(tries):
        try:
            return await asyncio.wait_for(
                complete(messages, thinking=thinking, usage_out=usage, model_out=model_out),
                timeout=limit,
            )
        except ExtractError:
            raise
        except Exception as exc:
            if is_safety_block(exc):
                raise SafetyBlocked(str(exc)) from exc
            last = exc
            if n + 1 < tries:
                from pico_orchestrator.upstream import backoff

                await sleep(backoff(exc, n))
    assert last is not None
    raise last


def _fill_user_template(template: str, *, subject: str, text: str = "", roster: str = "") -> str:
    # page tags steer which page is asked; the model never sees them (text reads have no pages)
    table = _ROSTER_PAGES_RE.sub("", roster or "").strip() or "（无题号表，按试卷全部作答）"
    return (
        (template or "")
        .replace("{{subject}}", subject)
        .replace("{{roster}}", table)
        .replace("{{text}}", text)
    )


# Structure read from text is asked twice at once and compared (edu-core#3164: 一模定稿 18 题
# 「（1）…（2）①②③」read as 2 小问 three runs, then 3 小问 once — same text, same prompt).
# Agreeing reads go out as they are; a disagreement gets a third read and each question takes
# the majority. Text reads are small (a 21-question Word is ~5k tokens), so the vote is cheap
# and adds no wait (the two go out together).
_STRUCTURE_VOTES = 2


def structure_signature(q: dict[str, Any]) -> tuple[Any, ...]:
    """What the card is built from: 题型 / 分值 / 选项数 / 小问 (a choice question has no 小问:
    a read that gives one a stray sub_count still builds the same card)."""
    if q.get("type") in ("single_choice", "multi_choice"):
        return (q.get("type"), q.get("score"), q.get("options_count"), None, ())
    subs = tuple(s.get("sub") for s in q.get("subs") or [])
    return (q.get("type"), q.get("score"), q.get("options_count"), q.get("sub_count"), subs)


def _describe_signature(sig: tuple[Any, ...]) -> str:
    qtype, score, options, subs_n, _ = sig
    parts = [str(qtype)]
    if score is not None:
        parts.append(f"{score} 分")
    if options:
        parts.append(f"{options} 选项")
    if qtype not in ("single_choice", "multi_choice"):
        parts.append(f"{subs_n} 问")
    return " ".join(parts)


def vote_structure(reads: list[list[dict[str, Any]]]) -> tuple[list[dict[str, Any]], list[str]]:
    """Per question number, the structure most reads agree on (ties: the first read's)."""
    need = (len(reads) + 1) // 2
    numbers = sorted({q["number"] for read in reads for q in read})
    out: list[dict[str, Any]] = []
    warnings: list[str] = []
    for number in numbers:
        found = [q for read in reads for q in read if q["number"] == number]
        if len(found) < need:
            # a card one question short with nobody told is worse than one too many
            warnings.append(f"第 {number} 题只有一次读到，没排进卡，请老师核对卷上有没有这题")
            continue
        sigs = [structure_signature(q) for q in found]
        best = max(sigs, key=lambda s: (sigs.count(s), -sigs.index(s)))
        if sigs.count(best) * 2 <= len(reads):
            seen = "；".join(dict.fromkeys(_describe_signature(s) for s in sigs))
            warnings.append(f"第 {number} 题结构几次读得不一样（{seen}），先按第一种排，请老师核对卡上这题")
        out.append(found[sigs.index(best)])
    return out, warnings


async def extract_text(
    text: str,
    *,
    subject_code: str | None = None,
    subject_name: str | None = None,
    complete: Completer | None = None,
    prompts: dict[str, str] | None = None,
    task: str = "answers",
    roster: str = "",
) -> dict[str, Any]:
    args = dict(
        subject_code=subject_code, subject_name=subject_name, complete=complete,
        prompts=prompts, task=task, roster=roster,
    )
    votes = _env_int("PICO_EXAM_STRUCTURE_VOTES", _STRUCTURE_VOTES)
    if task != "structure" or votes < 2:
        return await _extract_text_once(text, **args)
    usage: dict[str, Any] = {}
    model_out: dict[str, Any] = {}

    async def once() -> dict[str, Any] | BaseException:
        try:
            return await _extract_text_once(text, usage=usage, model_out=model_out, **args)
        except Exception as exc:  # noqa: BLE001 — a failed read just does not vote
            return exc

    results = list(await asyncio.gather(once(), once()))
    reads = [r for r in results if isinstance(r, dict)]
    if not reads:
        raise results[0]
    agree = len(reads) == 2 and [structure_signature(q) for q in reads[0]["questions"]] == [
        structure_signature(q) for q in reads[1]["questions"]
    ] and [q["number"] for q in reads[0]["questions"]] == [q["number"] for q in reads[1]["questions"]]
    if len(reads) == 2 and not agree:
        third = await once()
        if isinstance(third, dict):
            reads.append(third)
        logger.warning(
            "exam structure reads disagree, %s reads: %s",
            len(reads),
            [[(q["number"], structure_signature(q)[3]) for q in r["questions"]] for r in reads[:2]],
        )
    if len(reads) == 1 or agree:
        return {**reads[0], "usage": usage or None, "votes": len(results)}
    questions, warnings = vote_structure([r["questions"] for r in reads])
    # Per-question 小问分合计 warnings belong to whichever read each question came from.
    kept = [w for w in reads[0]["warnings"] if "小问分合计" not in w]
    for q in questions:
        total = subs_total(q.get("subs") or [])
        if total is not None and q["score"] is not None and total != q["score"]:
            kept.append(f"第 {q['number']} 题小问分合计 {total} ≠ 题分 {q['score']}，请老师核对")
    return {
        **reads[0],
        "questions": questions,
        "warnings": [*kept, *warnings],
        "usage": usage or None,
        "votes": len(reads),
    }


async def _extract_text_once(
    text: str,
    *,
    subject_code: str | None = None,
    subject_name: str | None = None,
    complete: Completer | None = None,
    prompts: dict[str, str] | None = None,
    task: str = "answers",
    roster: str = "",
    usage: dict[str, Any] | None = None,
    model_out: dict[str, Any] | None = None,
) -> dict[str, Any]:
    complete = complete or model_complete
    prompts = prompts or load_prompts(task=task)
    body = str(text or "").strip()
    if not body:
        raise ExtractError("extract.invalid", "text 是空的")
    body = body[:MAX_TEXT_CHARS]
    tag = subject_tag(subject_code, subject_name)
    chunks = chunk_text(body)
    usage = {} if usage is None else usage
    model_out = {} if model_out is None else model_out
    batches: list[list[dict[str, Any]]] = []
    reports: list[dict[str, Any]] = []
    last_text = ""
    errors: list[BaseException] = []
    think = task_thinking(task, False)

    async def ask(messages: list[dict[str, Any]]) -> str:
        try:
            return await _complete_with_retry(complete, messages, thinking=think, usage=usage, model_out=model_out)
        except ThinkingRanOut:
            if not think:
                raise
            # same rule as a page: thinking ran out, read again without (edu-core#3508)
            logger.warning("exam extract text thinking ran out, reading without")
            return await _complete_with_retry(complete, messages, thinking=False, usage=usage, model_out=model_out)

    for idx, chunk in enumerate(chunks, start=1):
        user = _fill_user_template(prompts["user_text"], subject=tag, text=chunk, roster=roster)
        messages = [
            {"role": "system", "content": prompts["system"]},
            {"role": "user", "content": user},
        ]
        try:
            out = await ask(messages)
        except ExtractError:
            raise
        except Exception as exc:  # noqa: BLE001 — surfaced as model.failed below
            errors.append(exc)
            batches.append([])
            reports.append(_failed_page(idx, exc))
            continue
        last_text = out
        items = items_from_model_text(out, page=None, task=task)
        batches.append(items)
        reports.append({"page": idx, "ok": True, "count": len(items), "error": None})
    wanted = roster_numbers(roster)
    merged = merge_items(attach_continued(batches))
    have = {q["number"] for q in merged}
    truncated = json_looks_truncated(last_text)
    for extra in range(CONTINUE_ROUNDS):
        missing = [n for n in wanted if n not in have] if wanted else []
        if wanted:
            if not missing:
                break
        elif not truncated:
            break
        start_from = missing[0] if missing else ((max(have) + 1) if have else 1)
        cont = (
            f"上次 JSON 不完整。已抽出题号 {sorted(have)[:40]}{'…' if len(have) > 40 else ''}。"
            f"只返回从 {start_from} 起还没抽出的题，仍是 JSON 数组。\n"
            + (f"题号表未完成：{missing[:40]}\n" if missing else "")
            + body
        )
        messages = [
            {"role": "system", "content": prompts["system"]},
            {"role": "user", "content": cont},
        ]
        try:
            out = await ask(messages)
        except ExtractError:
            raise
        except Exception as exc:  # noqa: BLE001
            errors.append(exc)
            break
        last_text = out
        items = items_from_model_text(out, page=None, task=task)
        if not items:
            break
        batches.append(items)
        reports.append({"page": 100 + extra, "ok": True, "count": len(items), "error": None})
        merged = merge_items(attach_continued(batches))
        have = {q["number"] for q in merged}
        truncated = json_looks_truncated(out)
    return _finish("text", batches, reports, errors, last_text, usage, model_out, task)


async def extract_pages(
    pages: list[dict[str, Any]],
    *,
    subject_code: str | None = None,
    subject_name: str | None = None,
    complete: Completer | None = None,
    prompts: dict[str, str] | None = None,
    concurrency: int | None = None,
    task: str = "answers",
    roster: str = "",
    sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
) -> dict[str, Any]:
    """pages: [{page:int, mime:str, data_b64:str}] — one vision call per page, merged."""
    complete = complete or model_complete
    prompts = prompts or load_prompts(task=task)
    if not pages:
        raise ExtractError("extract.invalid", "pages 是空的")
    tag = subject_tag(subject_code, subject_name)
    # Pages go out in parallel, bounded. 1 was a workaround while the ECS egress hop
    # reset concurrent uploads (pico #979); that hop now chains through DMIT
    # (edu-core#1506) and 3×300 KB / 2×1.5 MB concurrent uploads pass, so a 4-page scan
    # is one wave. Per-page retry/backoff below still absorbs a stray reset.
    limit = concurrency or _env_int("PICO_EXAM_EXTRACT_CONCURRENCY", _DEFAULT_CONCURRENCY)
    sem = asyncio.Semaphore(limit)
    usage: dict[str, Any] = {}
    model_out: dict[str, Any] = {}

    on_page = roster_pages(roster)

    def page_roster(number: int) -> str:
        return roster_for_page(roster, number) if on_page else roster

    def own(number: int, items: list[dict[str, Any]]) -> list[dict[str, Any]]:
        # A question the paper read placed on other pages is not this page's to answer:
        # the old "earlier page wins" merge let page 1's guess beat the real page (#3157).
        return [i for i in items if is_material(i) or i["number"] not in on_page or number in on_page[i["number"]]]

    by_page = {int(p["page"]): p for p in pages}

    thinking = task_thinking(task, page_thinking())
    unthought: set[int] = set()  # 推爆了、不推理读成的页
    hedge_after = _env_seconds("PICO_EXAM_EXTRACT_HEDGE_SECONDS", _DEFAULT_HEDGE_S)
    hedge_slot = asyncio.Semaphore(_env_int("PICO_EXAM_EXTRACT_HEDGE_SLOTS", _DEFAULT_HEDGE_SLOTS))

    async def plain(messages: list[dict[str, Any]]) -> str:
        # a read without thinking is short; one that sits past hedge_after is a stalled relay call
        return await hedged(
            lambda: _complete_with_retry(complete, messages, thinking=False, usage=usage, model_out=model_out),
            after=hedge_after,
            slot=hedge_slot,
        )

    async def read(image: dict[str, Any] | None, number: int, text: str = "") -> str:
        content: list[dict[str, Any]] = [
            {"type": "text", "text": _fill_user_template(prompts["user_page"], subject=tag, roster=page_roster(number))},
        ]
        if image is not None:
            content.append({"type": "image", "mime": image["mime"], "data_b64": image["data_b64"]})
        if text:
            content.append({"type": "text", "text": (PAGE_TEXT_HEAD if image is not None else PAGE_TEXT_ONLY_HEAD) + text})
        nxt = by_page.get(number + 1)
        if task == "solve" and nxt is not None and image is not None:
            # A choice question at the foot of a page has its options on the next one (一模定稿 5:
            # stem + A/B on page 1, C/D on page 2; 13: stem + figure on 3, options on 4). Alone,
            # page 1 left 5 blank or guessed from A/B (edu-core#3164); the next page rides along.
            content += [
                {"type": "text", "text": "下一页（只用来看本页最后一题接下去的部分）："},
                {"type": "image", "mime": nxt["mime"], "data_b64": nxt["data_b64"]},
            ]
        messages = [{"role": "system", "content": prompts["system"]}, {"role": "user", "content": content}]
        if not thinking:
            return await plain(messages)
        # 推理不封顶：难页推满时限 / 输出上限，答案截断或整页超时（一模 21 题两条带那页推 23k、
        # 第 20、21 题整题没做出，edu-core#3164）。推一次，推爆了这页不推理再读，不丢页。
        try:
            out = await _complete_with_retry(
                complete, messages, thinking=True, usage=usage, model_out=model_out, attempts=1
            )
        except (ExtractError, SafetyBlocked):
            raise
        except Exception as exc:  # noqa: BLE001 — read again below without thinking
            logger.warning("exam extract page %s thinking failed, reading without: %s", number, str(exc)[:200])
        else:
            if not json_looks_truncated(out) and parse_json_array(out) is not None:
                return out
            logger.warning("exam extract page %s thinking ran out, reading without", number)
        out = await plain(messages)
        unthought.add(number)
        return out

    async def read_halves(
        number: int, page: dict[str, Any], blocked: SafetyBlocked
    ) -> tuple[int, list[dict[str, Any]], str, dict[str, Any]]:
        halves = split_page_image(page["mime"], page["data_b64"])
        if not halves:
            return number, [], "", {**_failed_page(number, blocked), "safety": True}
        parts: list[list[dict[str, Any]] | None] = []
        outs: list[str] = []
        for half in halves:
            try:
                out = await read(half, number)
            except ExtractError:
                raise
            except Exception:  # noqa: BLE001 — that half stays unread, reported below
                parts.append(None)
                continue
            outs.append(out)
            parts.append(remap_half_figures(items_from_model_text(out, page=number, task=task), half["y0"], half["y1"]))
        top, bottom = parts
        # The bottom half's leading number 0 continues the top half's last question;
        # with the top unread its owner is unknown, so it is dropped (as across pages).
        items = list(top or [])
        last = max((i["number"] for i in items if not is_material(i)), default=0)
        for item in bottom or []:
            if is_material(item):
                # a continued material stays continued: attach_continued joins it to the
                # top half's material, or drops it when the top half is unread
                if not (item["continued"] and top is None):
                    items.append(item)
                continue
            if item["number"] == 0 and top is None:
                continue
            items.append({**item, "number": last} if item["number"] == 0 and last else item)
        missing = "".join(name for name, part in (("上", top), ("下", bottom)) if part is None)
        if missing and page.get("text"):
            # A half the brain still refuses: read the page from its PDF text layer instead (一模 5,
            # 16–18 stems lost, edu-core#3164). No image, so no figure boxes from this read.
            try:
                out = await read(None, number, page["text"])
            except ExtractError:
                raise
            except Exception as exc:  # noqa: BLE001 — stays reported as blocked
                logger.warning("exam extract page %s text-only read failed: %s", number, str(exc)[:200])
            else:
                outs.append(out)
                extra = [{**i, "figures": []} for i in items_from_model_text(out, page=number, task=task)]
                items = fill_from(items, extra)
                report = {"page": number, "ok": True, "count": len(items), "error": None, "safety": True, "text_only": True}
                return number, own(number, items), "\n".join(outs), report
        report = {
            "page": number,
            "ok": not missing,
            "count": len(items),
            "error": f"SafetyBlocked: 整页被安全审查拦下，切半重读后{missing}半页仍没读成" if missing else None,
            "safety": True,
        }
        return number, own(number, items), "\n".join(outs), report

    async def read_whole() -> dict[str, Any] | None:
        # Structure is short (number / type / score per question) but its rules sit in section
        # headers on one page and govern the next: 「一、选择题 每小题 2 分」 on page 1 covers 6–12
        # on page 2, 「有一项或多项符合」 on page 3 covers 14–16 on page 4. Read page by page those
        # lost the header (scores estimated, 多选 read as 单选, edu-core#3164), so the structure of
        # the whole paper is one call. Any failure falls back to the per-page read below.
        content: list[dict[str, Any]] = [
            {"type": "text", "text": _fill_user_template(prompts["user_pages"], subject=tag, roster=roster)}
        ]
        for page in pages:
            content.append({"type": "text", "text": f"第 {int(page['page'])} 页"})
            content.append({"type": "image", "mime": page["mime"], "data_b64": page["data_b64"]})
        messages = [{"role": "system", "content": prompts["system"]}, {"role": "user", "content": content}]
        try:
            out = await _complete_with_retry(
                complete, messages, thinking=page_thinking(), usage=usage, model_out=model_out
            )
        except ExtractError:
            raise
        except Exception as exc:  # noqa: BLE001 — per-page read takes over
            logger.warning("exam structure whole-paper read failed, per page instead: %s", _preview(str(exc)))
            return None
        items = [i for i in items_from_model_text(out, page=None, task=task) if is_material(i) or i["number"] > 0]
        if not items:
            logger.warning("exam structure whole-paper read empty, per page instead: %s", _preview(out))
            return None
        # A partial read is worse than per page (16:3x live: only the choice section came back,
        # every 大题 lost): 题号 must run 1..max with no gap and some question must reach the last page.
        numbers = {i["number"] for i in items if not is_material(i)}
        top = max(numbers, default=0)
        gaps = [n for n in range(1, top + 1) if n not in numbers]
        on_pages = {
            int(p)
            for r in _flatten(parse_json_array(out) or [])
            if isinstance(r, dict)
            for p in (r.get("pages") if isinstance(r.get("pages"), list) else [r.get("pages", r.get("page"))])
            if isinstance(p, (int, float)) and not isinstance(p, bool)
        }
        last = int(pages[-1]["page"])
        if not top or gaps or last not in on_pages:
            logger.warning(
                "exam structure whole-paper read partial (max %s, gaps %s, pages %s of %s), per page instead",
                top, gaps[:20], sorted(on_pages), last,
            )
            return None
        reports = [{"page": int(p["page"]), "ok": True, "count": 0, "error": None} for p in pages]
        reports[0]["count"] = len(items)
        return _finish("pages", [items] + [[] for _ in pages[1:]], reports, [], out, usage, model_out, task)

    async def one(page: dict[str, Any]) -> tuple[int, list[dict[str, Any]], str, dict[str, Any]]:
        number = int(page["page"])
        if on_page and not page_roster(number):
            # every question on the roster sits on other pages: nothing to answer here
            return number, [], "", {"page": number, "ok": True, "count": 0, "error": None, "skipped": True}
        async with sem:
            try:
                out = await read(page, number, page.get("text") or "")
            except ExtractError:
                raise
            except SafetyBlocked as exc:
                # 原文原因留在日志里（老师只看到「被安全审查拦下」），查是哪类拦截
                logger.warning("exam extract page %s safety blocked: %s", number, str(exc)[:400])
                out = None
                for _ in range(_env_int("PICO_EXAM_EXTRACT_SAFETY_REASKS", _SAFETY_REASKS)):
                    try:
                        out = await read(page, number, page.get("text") or "")
                        break
                    except SafetyBlocked as again:
                        logger.warning("exam extract page %s blocked again: %s", number, str(again)[:200])
                    except ExtractError:
                        raise
                    except Exception:  # noqa: BLE001 — halves below
                        break
                if out is None:
                    return await read_halves(number, page, exc)
                items = own(number, items_from_model_text(out, page=number, task=task))
                return number, items, out, {"page": number, "ok": True, "count": len(items), "error": None, "safety": True}
            except Exception as exc:  # noqa: BLE001
                return number, [], "", _failed_page(number, exc)
        items = own(number, items_from_model_text(out, page=number, task=task))
        return number, items, out, {"page": number, "ok": True, "count": len(items), "error": None}

    if prompts.get("user_pages") and len(pages) > 1:
        whole = await read_whole()
        if whole is not None:
            return whole

    results = await asyncio.gather(*(one(p) for p in pages))
    # A page lost to an upstream burst (Vertex 429 "Resource exhausted" outlasting the door's three
    # sends) gets one more go once the burst has passed: edu-core#3164 lost page 3 of a solve that
    # way and three answers with it. Background jobs, so the pause costs nothing the teacher waits
    # on; safety blocks already had their re-asks and halves, skipped pages never called.
    lost = {r[0] for r in results if not r[3]["ok"] and not r[3].get("safety")}
    if lost:
        await sleep(_env_int("PICO_EXAM_EXTRACT_PAGE_REASK_PAUSE_S", _PAGE_REASK_PAUSE_S))
        again = await asyncio.gather(*(one(p) for p in pages if int(p["page"]) in lost))
        redo = {r[0]: r for r in again}
        results = [redo.get(r[0], r) for r in results]
    # A page whose text layer prints 【答案】/【解析】 but read back with nothing printed lost them
    # (讲评 PDF 17–21, edu-core#3164): read it once more; still nothing → the teacher is told below.
    unprinted: set[int] = set()
    if task == "paper":
        unprinted = {
            r[0] for r in results
            if r[3]["ok"] and _PRINTED_RE.search(by_page[r[0]].get("text") or "") and not any(map(_has_printed, r[1]))
        }
        if unprinted:
            again = await asyncio.gather(*(one(by_page[n]) for n in sorted(unprinted)))
            redo = {r[0]: r for r in again if r[3]["ok"] and any(map(_has_printed, r[1]))}
            results = [redo.get(r[0], r) for r in results]
            unprinted -= set(redo)
    results.sort(key=lambda r: r[0])
    batches = [items for _, items, _, _ in results]
    reports = [rep for _, _, _, rep in results]
    errors = [RuntimeError(rep["error"]) for rep in reports if not rep["ok"]]
    last_text = next((out for _, _, out, rep in reversed(results) if rep["ok"]), "")
    try:
        result = _finish(
            "pages", batches, reports, errors, last_text, usage, model_out, task, order=roster_numbers(roster) or None
        )
    except ExtractError as exc:
        # every tagged question filtered off its wrong pages: an empty answer, not a failed read
        if not (on_page and exc.code == "extract.empty" and not errors):
            raise
        result = {
            "ok": True,
            "engine": ENGINE,
            "mode": "pages",
            "model": model_out.get("model"),
            "questions": [],
            "materials": [],
            "pages": reports,
            "warnings": [],
            "usage": usage or None,
        }
    if on_page:
        # A question whose page the paper read got wrong is filtered off every page and comes
        # back empty: say so instead of leaving a silent blank (no whole-paper re-ask, that
        # doubles the calls). edu shows this line to the teacher.
        answered = {q["number"] for q in result["questions"] if has_answer(q)}
        missing = sorted(n for n in on_page if n not in answered)
        if missing:
            nums = "、".join(str(n) for n in missing)
            result["warnings"].append(f"第 {nums} 题按所在页没做出答案，请老师核对或手动填")
    if unprinted:
        for n in sorted(unprinted):
            nums = "、".join(str(q["number"]) for q in result["questions"] if n in (q.get("on_pages") or []))
            result["warnings"].append(
                f"第 {n} 页文字层里印着答案或解析，读回来没有" + (f"（第 {nums} 题）" if nums else "") + "，请老师按卷面核对"
            )
    if unthought and task == "solve":
        # 不推理做的答案准头低（一模 5 题不推理答 B、推理答 D），老师得知道哪几页要重点核
        nums = "、".join(str(n) for n in sorted(unthought))
        result["warnings"].append(f"第 {nums} 页没用推理做题，AI 答案请重点核对")
    return result


# Page text layer (edu pdftotext per page, edu-core#3164): 讲评课件 hide answers under grey boxes in the
# slide image while the text layer has them; images mis-read 芟 as 茇. The brain takes words from the
# text and structure / figures from the image.
PAGE_TEXT_HEAD = (
    "本页文字层（从文件里直接取出的原字：图上看不清、被色块盖住的字也在里面；顺序可能乱，图里的字可能没有）。"
    "题干、选项、答案、解析、分数的字以它为准，题号结构和图仍看页图：\n"
)
PAGE_TEXT_ONLY_HEAD = (
    "本页的页图没法给你（被审查拦下），下面是本页文字层（从文件里直接取出的原字，顺序可能乱、图没有）。"
    "照它把本页的题读出来，figures 写 []：\n"
)

_ANALYSIS_PICK_RE = re.compile(r"(?:故选|故答案为|答案为|答案是|应选|所以选|因此选)\s*[：:]?\s*([A-H](?:\s*[、,，和与及]?\s*[A-H])*)")


_PRINTED_RE = re.compile(r"【\s*(?:答案|解析|详解|分析|点睛)\s*】|(?:^|\n)\s*(?:答案|解析)\s*[:：]")


def _has_printed(item: dict[str, Any]) -> bool:
    """A question read back with something printed on it: answer, analysis, rubric or a 小问 answer."""
    if is_material(item):
        return False
    return bool(item.get("answer") or item.get("analysis") or item.get("rubric")) or any(
        s.get("answer") for s in item.get("subs") or []
    )


def analysis_pick(q: dict[str, Any]) -> str | None:
    """A choice question's letters by its own analysis (「故选 BC」, last one wins); None when it names none."""
    if q["type"] not in ("single_choice", "multi_choice"):
        return None
    found = _ANALYSIS_PICK_RE.findall(q.get("analysis") or "")
    if not found:
        return None
    return "".join(sorted(set(re.sub(r"[^A-H]", "", found[-1]))))


def has_answer(q: dict[str, Any]) -> bool:
    if str(q.get("answer") or "").strip():
        return True
    return any(str(s.get("answer") or "").strip() for s in q.get("subs") or [] if isinstance(s, dict))


def _finish(
    mode: str,
    batches: list[list[dict[str, Any]]],
    reports: list[dict[str, Any]],
    errors: list[BaseException],
    last_text: str,
    usage: dict[str, Any],
    model_out: dict[str, Any],
    task: str = "answers",
    order: list[int] | None = None,
) -> dict[str, Any]:
    ok = [rep["ok"] for rep in reports] if len(reports) == len(batches) else None
    attached = attach_continued(batches, ok, order)
    questions = merge_items(attached, solve=task == "solve")
    materials = collect_materials(attached, questions)
    warnings: list[str] = []
    blocked = [rep["page"] for rep in reports if rep.get("safety") and not rep["ok"]]
    if len(errors) > len(blocked) and questions:
        warnings.append(f"{len(errors) - len(blocked)} 页没读成，其余页已合并")
    for page in blocked:
        warnings.append(f"第 {page} 页被安全审查拦下，切成两半重读仍没读全：这页的题请老师按卷面手动录入答案")
    if not questions:
        if errors and len(errors) == len(reports):
            raise ExtractError("model.failed", f"这次没读成：{_preview(str(errors[-1]))}")
        head = _preview(last_text)
        raise ExtractError(
            "extract.empty",
            "Pico 读完了答案卷，但没有抽出题号"
            + (f"（开头：{head}）" if head else "")
            + "。请换清晰卷或改用带题号的 Word / 文本。",
        )
    for q in questions:
        picked = analysis_pick(q) if task == "solve" else None
        if picked and picked != "".join(sorted(set(q["answer"]))):
            q["uncertain"] = True
            warnings.append(f"第 {q['number']} 题解析结论是 {picked}、答案写的是 {q['answer'] or '空'}，请老师核对")
        if self_corrected_fix(q["answer"]):
            q["uncertain"] = True
            warnings.append(f"第 {q['number']} 题改错答案左右读成同一个词，卷面错字可能被读成了正字，请老师按卷面核对")
        total = subs_total(q.get("subs") or [])
        if total is not None and q["score"] is not None and total != q["score"]:
            warnings.append(f"第 {q['number']} 题小问分合计 {total} ≠ 题分 {q['score']}，请老师核对")
    null_scores = sum(1 for q in questions if q["score"] is None)
    if null_scores:
        warnings.append(f"{null_scores} 题分值为 null：发布前请老师补分，禁止后端默认 1")
    return {
        "ok": True,
        "engine": ENGINE,
        "mode": mode,
        "model": model_out.get("model"),
        "questions": questions,
        "materials": materials,
        "pages": reports,
        "warnings": warnings,
        "usage": usage or None,
    }
