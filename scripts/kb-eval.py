#!/usr/bin/env python3
"""Knowledge-base retrieval eval (#1005 / #1006 T1). Not CI.

Two commands, both run on the ECS with /opt/pico/.env loaded:

  gen  — build a golden set from one school's materials already in Meili.
         GPT (via New API) writes teacher-style questions whose answer is a
         verbatim passage of the material; passages that are not verbatim are
         dropped. Output stays on the box (school data), never in the repo.
  run  — score a retrieval path against the golden set: hit@1, hit@5, MRR,
         chunk hit@5 (answer passage inside a returned text), p50/p95 latency.

  set -a && . /opt/pico/.env && set +a
  python3 scripts/kb-eval.py gen --school <school_id> --out /opt/pico/data/kb-golden/<school>.json
  python3 scripts/kb-eval.py run --golden /opt/pico/data/kb-golden/<school>.json

Prints counts and a markdown table only — never question text or passages.
"""

from __future__ import annotations

import argparse
import json
import os
import random
import re
import statistics
import sys
import time
from pathlib import Path
from typing import Any

import httpx

INDEX = "pico_materials"
NOISE_TITLES = ("回复摘要", "pico-assoc-probe", "报送汇总台账")
_WS = re.compile(r"\s+")


def _norm(s: str) -> str:
    return _WS.sub("", s or "")


def _meili() -> tuple[str, dict[str, str]]:
    url = (os.environ.get("PICO_MEILI_URL") or "http://127.0.0.1:7700").rstrip("/")
    key = (os.environ.get("MEILI_MASTER_KEY") or "").strip()
    headers = {"Content-Type": "application/json"}
    if key:
        headers["Authorization"] = f"Bearer {key}"
    return url, headers


def _quote(v: str) -> str:
    return '"' + v.replace("\\", "\\\\").replace('"', '\\"') + '"'


def meili_search(
    q: str,
    *,
    school_id: str,
    limit: int,
    extra: dict[str, Any] | None = None,
    attrs: list[str] | None = None,
) -> tuple[list[dict[str, Any]], float]:
    url, headers = _meili()
    body: dict[str, Any] = {
        "q": q,
        "filter": f"school_id = {_quote(school_id)}",
        "limit": limit,
        "attributesToRetrieve": attrs
        or ["artifact_id", "material_id", "title", "text", "parent_text", "membership_id", "heading"],
    }
    if extra:
        body.update(extra)
    t0 = time.perf_counter()
    resp = httpx.post(f"{url}/indexes/{INDEX}/search", json=body, headers=headers, timeout=20.0)
    dt = time.perf_counter() - t0
    resp.raise_for_status()
    return list(resp.json().get("hits") or []), dt


# --- gen ----------------------------------------------------------------------

GEN_PROMPT = """你是一名中小学老师，下面是学校知识库里的一份材料。请出 2 个老师日常真的会问、并且答案就在这份材料里的问题：
1. 第一个问题用材料里出现的词。
2. 第二个问题换一种说法（同义词、口语、不要照抄材料词）。
每个问题给出答案所在的原文片段 answer_quote：必须从材料里逐字连续摘出，30–120 个字，不要改字、不要拼接。
只输出 JSON，不要解释：
{{"items":[{{"question":"...","answer_quote":"..."}},{{"question":"...","answer_quote":"..."}}]}}

材料标题：{title}
材料正文：
{text}
"""


def _gpt_json(prompt: str, *, timeout_s: float = 120.0) -> dict[str, Any]:
    base = (os.environ.get("DEEPSEEK_BASE_URL") or "http://127.0.0.1:3000/v1").rstrip("/")
    key = (os.environ.get("DEEPSEEK_API_KEY") or "").strip()
    model = (os.environ.get("KB_EVAL_MODEL") or os.environ.get("DEEPSEEK_MODEL") or "gpt-5.6-sol").strip()
    if not key:
        raise SystemExit("DEEPSEEK_API_KEY (New API token) missing")
    body = {
        "model": model,
        "input": [{"role": "user", "content": prompt}],
        "reasoning": {"effort": "low"},
        "stream": False,
    }
    resp = httpx.post(
        f"{base}/responses",
        json=body,
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        timeout=timeout_s,
        trust_env=False,
    )
    resp.raise_for_status()
    data = resp.json()
    text = ""
    for item in data.get("output") or []:
        for part in item.get("content") or []:
            if part.get("type") in {"output_text", "text"}:
                text += str(part.get("text") or "")
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\n?", "", text).rstrip("`").strip()
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end < 0:
        raise ValueError("no json in model output")
    return json.loads(text[start : end + 1])


def cmd_gen(args: argparse.Namespace) -> int:
    hits, _ = meili_search(
        "",
        school_id=args.school,
        limit=1000,
        attrs=["artifact_id", "title", "text", "membership_id"],
    )
    pool = [
        h
        for h in hits
        if len(h.get("text") or "") >= args.min_chars
        and not any(n in (h.get("title") or "") for n in NOISE_TITLES)
    ]
    rng = random.Random(args.seed)
    rng.shuffle(pool)
    print(f"school docs={len(hits)} eligible={len(pool)} target={args.n}", file=sys.stderr)
    golden: list[dict[str, Any]] = []
    seen_q: set[str] = set()
    used = 0
    for doc in pool:
        if len(golden) >= args.n:
            break
        used += 1
        text = str(doc.get("text") or "")[: args.max_chars]
        try:
            out = _gpt_json(GEN_PROMPT.format(title=doc.get("title") or "", text=text))
        except Exception as exc:  # noqa: BLE001 — skip bad doc, keep going
            print(f"  skip {doc.get('artifact_id','')[:8]}: {type(exc).__name__}", file=sys.stderr)
            continue
        kept = 0
        for i, item in enumerate(out.get("items") or []):
            q = str(item.get("question") or "").strip()
            quote = str(item.get("answer_quote") or "").strip()
            if not q or not quote or q in seen_q:
                continue
            if _norm(quote) not in _norm(text) or len(quote) < 20:
                continue
            seen_q.add(q)
            golden.append(
                {
                    "id": f"{doc['artifact_id'][:8]}-{i}",
                    "question": q,
                    "kind": "literal" if i == 0 else "paraphrase",
                    "material_id": doc["artifact_id"],
                    "title": doc.get("title") or "",
                    "membership_id": doc.get("membership_id") or "",
                    "answer_quote": quote,
                }
            )
            kept += 1
        print(f"  doc {used}: kept {kept} (total {len(golden)})", file=sys.stderr)
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(
            {"school_id": args.school, "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"), "items": golden},
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    kinds = {k: sum(1 for g in golden if g["kind"] == k) for k in ("literal", "paraphrase")}
    print(json.dumps({"written": str(out_path), "items": len(golden), "kinds": kinds, "docs_used": used}))
    return 0


# --- run ----------------------------------------------------------------------


def _rank_of(material_id: str, hits: list[dict[str, Any]]) -> int | None:
    for i, h in enumerate(hits):
        if str(h.get("material_id") or h.get("artifact_id") or "") == material_id:
            return i + 1
    return None


def _chunk_hit(quote: str, hits: list[dict[str, Any]], k: int) -> bool:
    nq = _norm(quote)
    for h in hits[:k]:
        blob = _norm(str(h.get("text") or "") + str(h.get("parent_text") or ""))
        if nq and nq in blob:
            return True
    return False


def search_via_api(q: str, *, base: str, school_id: str, membership_id: str, limit: int) -> tuple[list[dict[str, Any]], float]:
    """Pico /v1/kb/search (once it exists). Proxy key + synthetic membership header."""
    key = (os.environ.get("PICO_OPENAI_PROXY_KEY") or "").strip()
    headers = {
        "Authorization": f"Bearer {key}",
        "X-Pico-Membership-Id": f"{school_id}:{membership_id}",
        "Content-Type": "application/json",
    }
    t0 = time.perf_counter()
    resp = httpx.post(
        f"{base.rstrip('/')}/v1/kb/search",
        json={"query": q, "limit": limit, "scope": "school"},
        headers=headers,
        timeout=30.0,
        trust_env=False,
    )
    dt = time.perf_counter() - t0
    resp.raise_for_status()
    return list(resp.json().get("hits") or []), dt


def cmd_run(args: argparse.Namespace) -> int:
    golden = json.loads(Path(args.golden).read_text(encoding="utf-8"))
    items = golden["items"]
    school = golden["school_id"]
    k = args.k
    ranks: list[int | None] = []
    chunk_hits = 0
    lat: list[float] = []
    per_kind: dict[str, list[int | None]] = {}
    errors = 0
    for it in items:
        try:
            if args.mode == "api":
                hits, dt = search_via_api(
                    it["question"], base=args.base, school_id=school, membership_id=it.get("membership_id") or "eval", limit=k * 2
                )
            else:
                extra = None
                if args.mode == "hybrid":
                    extra = {"hybrid": {"semanticRatio": args.semantic_ratio, "embedder": args.embedder}}
                hits, dt = meili_search(it["question"], school_id=school, limit=k * 2, extra=extra)
        except Exception as exc:  # noqa: BLE001
            errors += 1
            print(f"  error {it['id']}: {type(exc).__name__}", file=sys.stderr)
            ranks.append(None)
            per_kind.setdefault(it["kind"], []).append(None)
            continue
        lat.append(dt)
        r = _rank_of(it["material_id"], hits)
        ranks.append(r)
        per_kind.setdefault(it["kind"], []).append(r)
        if _chunk_hit(it["answer_quote"], hits, k):
            chunk_hits += 1

    def _stats(rs: list[int | None]) -> dict[str, Any]:
        n = len(rs) or 1
        return {
            "n": len(rs),
            "hit@1": round(sum(1 for r in rs if r == 1) / n, 3),
            f"hit@{k}": round(sum(1 for r in rs if r is not None and r <= k) / n, 3),
            "mrr": round(sum(1.0 / r for r in rs if r is not None) / n, 3),
        }

    overall = _stats(ranks)
    overall[f"chunk_hit@{k}"] = round(chunk_hits / (len(items) or 1), 3)
    overall["p50_ms"] = round(statistics.median(lat) * 1000, 1) if lat else None
    overall["p95_ms"] = round(sorted(lat)[max(0, round(0.95 * (len(lat) - 1)))] * 1000, 1) if lat else None
    overall["errors"] = errors
    report = {"mode": args.mode, "school_id": school[:8], "overall": overall, "by_kind": {kk: _stats(v) for kk, v in per_kind.items()}}
    print(json.dumps(report, ensure_ascii=False, indent=2))
    print()
    print(f"| mode | n | hit@1 | hit@{k} | MRR | chunk hit@{k} | p50 ms | p95 ms |")
    print("|---|---|---|---|---|---|---|---|")
    o = overall
    print(f"| {args.mode} | {o['n']} | {o['hit@1']} | {o[f'hit@{k}']} | {o['mrr']} | {o[f'chunk_hit@{k}']} | {o['p50_ms']} | {o['p95_ms']} |")
    for kk, st in report["by_kind"].items():
        print(f"| ↳ {kk} | {st['n']} | {st['hit@1']} | {st[f'hit@{k}']} | {st['mrr']} | — | — | — |")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    g = sub.add_parser("gen")
    g.add_argument("--school", required=True)
    g.add_argument("--out", required=True)
    g.add_argument("--n", type=int, default=50)
    g.add_argument("--min-chars", type=int, default=500, dest="min_chars")
    g.add_argument("--max-chars", type=int, default=6000, dest="max_chars")
    g.add_argument("--seed", type=int, default=1)
    g.set_defaults(fn=cmd_gen)
    r = sub.add_parser("run")
    r.add_argument("--golden", required=True)
    r.add_argument("--mode", choices=["keyword", "hybrid", "api"], default="keyword")
    r.add_argument("--k", type=int, default=5)
    r.add_argument("--semantic-ratio", type=float, default=0.5, dest="semantic_ratio")
    r.add_argument("--embedder", default="default")
    r.add_argument("--base", default="http://127.0.0.1:18765")
    r.set_defaults(fn=cmd_run)
    args = ap.parse_args()
    return int(args.fn(args))


if __name__ == "__main__":
    sys.exit(main())
