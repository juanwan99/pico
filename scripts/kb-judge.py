#!/usr/bin/env python3
"""Human-judge table for #1052 T1. Not CI. School gold stays on the box.

Prints 问 / 命中段 / 模型答 / 参考原句. Owner marks 对/错.
Channel overload stops honestly — never invents answers.

  set -a && . /opt/pico/.env && set +a
  python3 scripts/kb-judge.py --golden /opt/pico/data/kb-golden/<school>-held.json
  python3 scripts/kb-judge.py --golden … --chat --base http://127.0.0.1:18765
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import random
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

import httpx

ROOT = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location("kb_eval", ROOT / "kb-eval.py")
assert _spec is not None and _spec.loader is not None
kb_eval = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(kb_eval)

CHANNEL_RED = (
    "overloaded",
    "503",
    "524",
    "do_request_failed",
    "temporarily unavailable",
    "繁忙",
    "过载",
)


def pick_items(items: list[dict[str, Any]], n: int, seed: int) -> list[dict[str, Any]]:
    rng = random.Random(seed)
    by: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in items:
        by[str(item.get("kind") or "?")].append(item)
    for bucket in by.values():
        rng.shuffle(bucket)
    picked: list[dict[str, Any]] = []
    while len(picked) < n and any(by.values()):
        for kind in list(by):
            if by[kind]:
                picked.append(by[kind].pop())
            if len(picked) >= n:
                break
    return picked


def _clip(text: str, n: int = 160) -> str:
    s = " ".join((text or "").split())
    return s if len(s) <= n else s[: n - 1] + "…"


def _hit_passage(hits: list[dict[str, Any]]) -> str:
    if not hits:
        return ""
    top = hits[0]
    passages = top.get("passages") if isinstance(top.get("passages"), list) else [top]
    blob = ""
    for row in passages:
        if not isinstance(row, dict):
            continue
        blob = str(row.get("text") or row.get("excerpt") or "")
        if blob:
            break
    if not blob:
        blob = str(top.get("text") or top.get("excerpt") or "")
    return _clip(blob)


def search_one(item: dict[str, Any], *, school: str, args: argparse.Namespace) -> dict[str, Any]:
    k = int(args.k)
    if args.mode == "api":
        raw, dt = kb_eval.search_via_api(
            item["question"],
            base=args.base,
            school_id=school,
            membership_id=item.get("membership_id") or "eval",
            limit=k * 2,
        )
        hits = raw
    else:
        extra = None
        if args.mode == "hybrid":
            extra = {
                "hybrid": {"semanticRatio": args.semantic_ratio, "embedder": args.embedder}
            }
        raw, dt = kb_eval.meili_search(
            item["question"],
            school_id=school,
            limit=args.fetch,
            extra=extra,
            filt=kb_eval.tenant_filter(school, str(item.get("membership_id") or "")),
        )
        if args.rerank:
            head, _rs = kb_eval.rerank_pool(
                item["question"], raw[: args.rerank_pool], model=args.rerank
            )
            raw = head + raw[args.rerank_pool :]
        hits = kb_eval.collapse_by_file(raw, passages=args.passages)
    rank = kb_eval._rank_of(item["material_id"], hits)
    return {
        "hits": hits,
        "ms": round(dt * 1000, 1),
        "file_at_k": bool(rank is not None and rank <= k),
        "passage": _hit_passage(hits[:k]),
    }


def chat_answer(
    question: str, *, base: str, school: str, member: str
) -> tuple[str, str | None]:
    key = (os.environ.get("PICO_OPENAI_PROXY_KEY") or "").strip()
    if not key:
        return "", "no_proxy_key"
    headers = {
        "Authorization": f"Bearer {key}",
        "X-Pico-Membership-Id": f"{school}:{member}",
        "Content-Type": "application/json",
    }
    try:
        with httpx.stream(
            "POST",
            f"{base.rstrip('/')}/v1/chat/completions",
            json={
                "model": os.environ.get("PICO_REGRESS_MODEL") or "gpt-5.6-sol",
                "stream": True,
                "messages": [{"role": "user", "content": question}],
            },
            headers=headers,
            timeout=180.0,
            trust_env=False,
        ) as resp:
            if resp.status_code >= 400:
                return "", f"http_{resp.status_code}"
            parts: list[str] = []
            for line in resp.iter_lines():
                if not line or not line.startswith("data:"):
                    continue
                data = line[5:].strip()
                if data == "[DONE]":
                    break
                try:
                    obj = json.loads(data)
                except json.JSONDecodeError:
                    continue
                delta = ((obj.get("choices") or [{}])[0].get("delta") or {})
                parts.append(str(delta.get("content") or ""))
            text = "".join(parts).strip()
            return _clip(text, 240), None
    except Exception as exc:  # noqa: BLE001
        return "", type(exc).__name__


def is_channel_red(err: str | None) -> bool:
    low = (err or "").lower()
    return any(n.lower() in low for n in CHANNEL_RED)


def render_table(rows: list[dict[str, Any]]) -> str:
    lines = [
        "| # | 问 | 命中段 | 模型答 | 参考原句 | 人判 |",
        "|---:|---|---|---|---|---|",
    ]
    for i, row in enumerate(rows, 1):
        lines.append(
            "| {i} | {q} | {hit} | {ans} | {ref} | {judge} |".format(
                i=i,
                q=_clip(str(row.get("question") or ""), 80),
                hit=_clip(str(row.get("hit_passage") or ""), 80),
                ans=_clip(str(row.get("model_answer") or row.get("channel") or ""), 80),
                ref=_clip(str(row.get("answer_quote") or ""), 80),
                judge=row.get("human_judge") or "",
            )
        )
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--golden", required=True)
    ap.add_argument("--limit", type=int, default=20)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--mode", choices=["keyword", "hybrid", "api"], default="hybrid")
    ap.add_argument("--k", type=int, default=5)
    ap.add_argument("--fetch", type=int, default=80)
    ap.add_argument("--passages", type=int, default=3)
    ap.add_argument("--rerank", default="rerank-pro")
    ap.add_argument("--rerank-pool", type=int, default=40, dest="rerank_pool")
    ap.add_argument("--semantic-ratio", type=float, default=0.5, dest="semantic_ratio")
    ap.add_argument("--embedder", default="default")
    ap.add_argument("--base", default="http://127.0.0.1:18765")
    ap.add_argument("--chat", action="store_true")
    ap.add_argument("--out", default="")
    args = ap.parse_args()
    golden = json.loads(Path(args.golden).read_text(encoding="utf-8"))
    school = str(golden.get("school_id") or "")
    items = pick_items(list(golden.get("items") or []), max(1, int(args.limit)), int(args.seed))
    rows: list[dict[str, Any]] = []
    channel_stop = False
    channel_err = ""
    for item in items:
        rec: dict[str, Any] = {
            "id": item.get("id"),
            "kind": item.get("kind"),
            "question": item.get("question"),
            "answer_quote": item.get("answer_quote"),
            "hit_passage": "",
            "model_answer": "",
            "file_at_k": False,
            "human_judge": "",
            "channel": "",
        }
        try:
            found = search_one(item, school=school, args=args)
            rec["hit_passage"] = found["passage"]
            rec["file_at_k"] = found["file_at_k"]
        except Exception as exc:  # noqa: BLE001
            rec["channel"] = f"search_{type(exc).__name__}"
            if is_channel_red(rec["channel"]):
                channel_stop = True
                channel_err = rec["channel"]
        if args.chat and not channel_stop:
            ans, err = chat_answer(
                str(item.get("question") or ""),
                base=args.base,
                school=school,
                member=str(item.get("membership_id") or "eval"),
            )
            rec["model_answer"] = ans
            if err:
                rec["channel"] = err
                if is_channel_red(err) or err.startswith("http_5"):
                    channel_stop = True
                    channel_err = err
        elif not args.chat:
            rec["channel"] = rec["channel"] or "search_only"
        rows.append(rec)
        if channel_stop:
            break
    report = {
        "n": len(rows),
        "asked": len(items),
        "school_id": school[:8],
        "chat": bool(args.chat),
        "channel_red": channel_stop,
        "channel_err": channel_err,
        "file_at_k": sum(1 for r in rows if r.get("file_at_k")),
        "rows": rows,
    }
    text = json.dumps(report, ensure_ascii=False, indent=2)
    print(text)
    print()
    print(render_table(rows))
    if channel_stop:
        print(f"\n渠道红，已停：{channel_err}", file=sys.stderr)
    if args.out:
        Path(args.out).write_text(text + "\n\n" + render_table(rows) + "\n", encoding="utf-8")
    return 2 if channel_stop else 0


if __name__ == "__main__":
    raise SystemExit(main())
