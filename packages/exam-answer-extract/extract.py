"""exam-answer-extract — answer sheet → answer-card question structure.

Thin adapter over the product brain (``pico_orchestrator.provider``): text goes to
the text model in one shot; page images go to the vision entry page by page; items
are merged by question number. Prompts live in SKILL.md (single semantic source).
No regex / heuristic fallback: an empty extraction is a failure, never a guess.
"""

from __future__ import annotations

import asyncio
import json
import os
import re
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any

ENGINE = "exam-answer-extract/1"
TYPES = ("single_choice", "multi_choice", "fill_in_blank", "short_answer")
SKILL_PATH = Path(__file__).resolve().parent / "SKILL.md"

TEXT_CHUNK_CHARS = 60_000
MAX_TEXT_CHARS = 400_000
DEFAULT_MAX_OUTPUT_TOKENS = 16_000

Completer = Callable[..., Awaitable[str]]


class ExtractError(RuntimeError):
    """Adapter-level failure with a stable code for the HTTP layer."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


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


def load_prompts(skill_text: str | None = None) -> dict[str, str]:
    return {
        "system": _prompt_block("system", skill_text),
        "user_text": _prompt_block("user_text", skill_text),
        "user_page": _prompt_block("user_page", skill_text),
    }


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


def parse_json_array(content: str | None) -> list[Any] | None:
    """Model text → list. Accepts fenced JSON, {questions:[…]}, NDJSON, truncated arrays."""
    raw = strip_fence(content)
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
        return None
    body = raw[start:]
    last = body.rfind("}")
    if last < 0:
        return None
    truncated = re.sub(r",\s*$", "", body[: last + 1])
    truncated += "]" * max(0, truncated.count("[") - truncated.count("]"))
    try:
        repaired = json.loads(truncated)
    except ValueError:
        return None
    return repaired if isinstance(repaired, list) else None


# --------------------------------------------------------------------------- items

_SUB_MARK_RE = re.compile(r"(?:[（(]\s*\d+\s*[）)]|\d+\s*[)）]|[①②③④⑤⑥⑦⑧⑨⑩⑪⑫⑬⑭⑮])")
_VISION_MISS_RE = re.compile(r"未收到|没有收到.*图|看不到.*图|无法查看|无法看到|未提供图")


def count_sub_marks(text: str | None) -> int:
    found = _SUB_MARK_RE.findall(str(text or ""))
    return max(len(found), 1) if found else 1


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


def normalize_item(raw: dict[str, Any], *, page: int | None) -> dict[str, Any] | None:
    try:
        number = int(float(raw.get("number", raw.get("qno", raw.get("question_no")))))
    except (TypeError, ValueError):
        return None
    if number <= 0:
        return None
    qtype = _type_from_hint(raw.get("type"))
    answer = "" if raw.get("answer") is None else str(raw.get("answer")).strip()
    rubric_raw = raw.get("rubric", raw.get("细则", raw.get("scoring_rubric", "")))
    rubric = "" if rubric_raw is None else str(rubric_raw).strip()

    score: int | float | None = raw.get("score")
    if score in ("", None):
        score = None
    else:
        try:
            score = float(score)
            if score < 0:
                score = None
            elif score == int(score):
                score = int(score)
        except (TypeError, ValueError):
            score = None

    if qtype in ("single_choice", "multi_choice"):
        letters = re.sub(r"[^A-Ha-h]", "", answer).upper()
        if letters:
            answer = letters
            if len(letters) > 1 and qtype == "single_choice":
                qtype = "multi_choice"
        try:
            options_count = int(raw.get("options_count") or 4)
        except (TypeError, ValueError):
            options_count = 4
        options_count = options_count if options_count >= 2 else 4
    else:
        options_count = None

    has_figure = raw.get("has_figure") is True or raw.get("hasFigure") is True
    try:
        sub_count = int(raw.get("sub_count") or raw.get("subCount") or 0)
    except (TypeError, ValueError):
        sub_count = 0
    sub_count = max(sub_count, count_sub_marks(answer), 1)
    if has_figure:
        sub_count = max(sub_count, 3)

    quote = str(raw.get("quote") or "").strip()[:60]
    section = raw.get("section")
    return {
        "number": number,
        "type": qtype,
        "section": str(section).strip() if section not in (None, "") else None,
        "answer": answer,
        "rubric": rubric,
        "score": score,
        "options_count": options_count,
        "sub_count": sub_count,
        "has_figure": has_figure,
        "source": {"page": page, "quote": quote},
    }


def items_from_model_text(text: str, *, page: int | None) -> list[dict[str, Any]]:
    parsed = parse_json_array(text) or []
    items: list[dict[str, Any]] = []
    for raw in _flatten(parsed):
        if not isinstance(raw, dict) or is_vision_miss(raw):
            continue
        item = normalize_item(raw, page=page)
        if item is not None and (item["answer"] or item["rubric"]):
            items.append(item)
    return items


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


def merge_items(batches: list[list[dict[str, Any]]]) -> list[dict[str, Any]]:
    """Merge per-page / per-chunk items by number. Earlier batch wins on answer."""
    by_no: dict[int, dict[str, Any]] = {}
    for batch in batches:
        for item in batch:
            prev = by_no.get(item["number"])
            if prev is None:
                by_no[item["number"]] = dict(item)
                continue
            merged = dict(prev)
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
            merged["rubric"] = _merge_rubric(prev["rubric"], item["rubric"])
            merged["sub_count"] = max(prev["sub_count"], item["sub_count"])
            merged["has_figure"] = prev["has_figure"] or item["has_figure"]
            by_no[item["number"]] = merged
    return [by_no[n] for n in sorted(by_no)]


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
    mid = P.product_backend_model(deep=False)
    if _has_images(messages):
        mid = vision_model_for_images(mid)
    if model_out is not None:
        model_out["model"] = mid

    if P.uses_openai_responses_brain(cfg):
        pieces: list[str] = []
        async for piece in P._iter_openai_responses(
            cfg,
            mid,
            _to_responses_messages(messages),
            max_tokens=max_tokens,
            thinking=thinking,
            usage_out=usage_out,
        ):
            pieces.append(piece)
        return "".join(pieces)

    client = P._llm_client(cfg)
    kwargs: dict[str, Any] = {
        "model": mid,
        "messages": _to_chat_messages(messages),
        "stream": False,
        "max_tokens": max_tokens,
        "temperature": 0.1,
    }
    extra = P.thinking_extra_body(mid, thinking=thinking)
    if extra:
        kwargs["extra_body"] = extra
    resp = await client.chat.completions.create(**kwargs)
    usage = getattr(resp, "usage", None)
    if usage is not None and usage_out is not None:
        from pico_orchestrator.usage_parse import add_usage, parse_usage_blob

        merged = add_usage(dict(usage_out) if usage_out else None, parse_usage_blob(usage))
        usage_out.clear()
        if merged:
            usage_out.update(merged)
    choices = getattr(resp, "choices", None) or []
    return str(choices[0].message.content or "") if choices else ""


# --------------------------------------------------------------------------- pipeline


def _env_int(name: str, default: int) -> int:
    try:
        return max(1, int(os.environ.get(name, "") or default))
    except ValueError:
        return default


def _preview(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "")).strip()[:80]


def _failed_page(page: int, exc: BaseException) -> dict[str, Any]:
    code = getattr(exc, "code", None) or type(exc).__name__
    return {"page": page, "ok": False, "count": 0, "error": f"{code}: {_preview(str(exc))}"}


# Relay/proxy hops in front of the brain reset connections in bursts (seen live as
# "upstream error: do request failed" within ~1 s, three in a row inside a 10 s window,
# then the very next request passes). Resets are cheap, so spread attempts across
# a longer window instead of hammering; ExtractError (configuration) is never retried.
_RETRY_BACKOFF_SECONDS = (3.0, 8.0, 20.0, 45.0)
_DEFAULT_ATTEMPTS = 5
_DEFAULT_CONCURRENCY = 4


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
        except Exception as exc:  # noqa: BLE001 — retried, then surfaced by the caller
            last = exc
            if n + 1 < tries:
                await sleep(_RETRY_BACKOFF_SECONDS[min(n, len(_RETRY_BACKOFF_SECONDS) - 1)])
    assert last is not None
    raise last


async def extract_text(
    text: str,
    *,
    subject_code: str | None = None,
    subject_name: str | None = None,
    complete: Completer | None = None,
    prompts: dict[str, str] | None = None,
) -> dict[str, Any]:
    complete = complete or model_complete
    prompts = prompts or load_prompts()
    body = str(text or "").strip()
    if not body:
        raise ExtractError("extract.invalid", "text 是空的")
    body = body[:MAX_TEXT_CHARS]
    tag = subject_tag(subject_code, subject_name)
    chunks = chunk_text(body)
    usage: dict[str, Any] = {}
    model_out: dict[str, Any] = {}
    batches: list[list[dict[str, Any]]] = []
    reports: list[dict[str, Any]] = []
    last_text = ""
    errors: list[BaseException] = []
    for idx, chunk in enumerate(chunks, start=1):
        user = prompts["user_text"].replace("{{subject}}", tag).replace("{{text}}", chunk)
        messages = [
            {"role": "system", "content": prompts["system"]},
            {"role": "user", "content": user},
        ]
        try:
            out = await _complete_with_retry(
                complete, messages, thinking=False, usage=usage, model_out=model_out
            )
        except ExtractError:
            raise
        except Exception as exc:  # noqa: BLE001 — surfaced as model.failed below
            errors.append(exc)
            reports.append(_failed_page(idx, exc))
            continue
        last_text = out
        items = items_from_model_text(out, page=None)
        batches.append(items)
        reports.append({"page": idx, "ok": True, "count": len(items), "error": None})
    return _finish("text", batches, reports, errors, last_text, usage, model_out)


async def extract_pages(
    pages: list[dict[str, Any]],
    *,
    subject_code: str | None = None,
    subject_name: str | None = None,
    complete: Completer | None = None,
    prompts: dict[str, str] | None = None,
    concurrency: int | None = None,
) -> dict[str, Any]:
    """pages: [{page:int, mime:str, data_b64:str}] — one vision call per page, merged."""
    complete = complete or model_complete
    prompts = prompts or load_prompts()
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

    async def one(page: dict[str, Any]) -> tuple[int, list[dict[str, Any]], str, dict[str, Any]]:
        number = int(page["page"])
        messages = [
            {"role": "system", "content": prompts["system"]},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompts["user_page"].replace("{{subject}}", tag)},
                    {"type": "image", "mime": page["mime"], "data_b64": page["data_b64"]},
                ],
            },
        ]
        async with sem:
            try:
                out = await _complete_with_retry(
                    complete, messages, thinking=None, usage=usage, model_out=model_out
                )
            except ExtractError:
                raise
            except Exception as exc:  # noqa: BLE001
                return number, [], "", _failed_page(number, exc)
        items = items_from_model_text(out, page=number)
        return number, items, out, {"page": number, "ok": True, "count": len(items), "error": None}

    results = await asyncio.gather(*(one(p) for p in pages))
    results.sort(key=lambda r: r[0])
    batches = [items for _, items, _, _ in results]
    reports = [rep for _, _, _, rep in results]
    errors = [RuntimeError(rep["error"]) for rep in reports if not rep["ok"]]
    last_text = next((out for _, _, out, rep in reversed(results) if rep["ok"]), "")
    return _finish("pages", batches, reports, errors, last_text, usage, model_out)


def _finish(
    mode: str,
    batches: list[list[dict[str, Any]]],
    reports: list[dict[str, Any]],
    errors: list[BaseException],
    last_text: str,
    usage: dict[str, Any],
    model_out: dict[str, Any],
) -> dict[str, Any]:
    questions = merge_items(batches)
    warnings: list[str] = []
    if errors and questions:
        warnings.append(f"{len(errors)} 页没读成，其余页已合并")
    if not questions:
        if errors and len(errors) == len(reports):
            raise ExtractError("model.failed", f"上游没做成：{_preview(str(errors[-1]))}")
        head = _preview(last_text)
        raise ExtractError(
            "extract.empty",
            "Pico 读完了答案卷，但没有抽出题号"
            + (f"（开头：{head}）" if head else "")
            + "。请换清晰卷或改用带题号的 Word / 文本。",
        )
    null_scores = sum(1 for q in questions if q["score"] is None)
    if null_scores:
        warnings.append(f"{null_scores} 题分值为 null：发布前请老师补分，禁止后端默认 1")
    return {
        "ok": True,
        "engine": ENGINE,
        "mode": mode,
        "model": model_out.get("model"),
        "questions": questions,
        "pages": reports,
        "warnings": warnings,
        "usage": usage or None,
    }
