#!/usr/bin/env python3
"""Knowledge-base retrieval eval (#1005 / #1006 T1). Not CI.

Three commands, all run on the ECS with /opt/pico/.env loaded:

  gen  — build a golden set from one school's materials already in Meili.
         GPT (via New API) writes teacher-style questions whose answer is a
         verbatim passage of the material; passages that are not verbatim are
         dropped. Output stays on the box (school data), never in the repo.
  held — build a frozen held-out set without a model: one mid-span excerpt per
         file, capped per suffix, gold files excluded. Same file shape as gen,
         `kind` = suffix. Regenerate only with a new --seed and a new --out.
  run  — score a retrieval path against a set, per-item tenant filter, file
         collapse like live: file@k, quote-visible@k (quote inside a returned
         child), quote-in-passages@20 (no collapse), by kind, p50/p95 latency.

  set -a && . /opt/pico/.env && set +a
  python3 scripts/kb-eval.py gen  --school <school_id> --out /opt/pico/data/kb-golden/<school>.json
  python3 scripts/kb-eval.py held --school <school_id> --exclude /opt/pico/data/kb-golden/<school>.json \
                                  --out /opt/pico/data/kb-golden/<school>-held.json
  python3 scripts/kb-eval.py run  --golden /opt/pico/data/kb-golden/<school>-held.json --mode hybrid

Gold is report-only; never tune to it. Prints counts and a markdown table only —
never question text, passages, or titles.
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
NOISE_TITLES = ("回复摘要", "pico-assoc-probe", "报送汇总台账", "summary")
# Legacy binary formats the extractor reports unread; a held-out row there measures nothing.
HELD_SKIP_SUFFIX = {"doc", "ppt", "xls"}
_WS = re.compile(r"\s+")
_EXT = re.compile(r"\.([A-Za-z0-9]{1,8})$")


def _norm(s: str) -> str:
    return _WS.sub("", s or "")


def _suffix(title: str) -> str:
    m = _EXT.search(title or "")
    return m.group(1).lower() if m else "none"


def _aid(row: dict[str, Any]) -> str:
    return str(row.get("artifact_id") or row.get("material_id") or "").strip()


def tenant_filter(school_id: str, membership_id: str) -> str:
    """Same shape as live meili_kb.tenant_filter(include_school=True)."""
    member = (membership_id or "").strip()
    if not member:
        return f"school_id = {_quote(school_id)}"
    return (
        f"school_id = {_quote(school_id)} AND "
        f'(scope = "school" OR (scope = "member" AND membership_id = {_quote(member)}))'
    )


def collapse_by_file(
    hits: list[dict[str, Any]], k: int | None = None, *, passages: int = 1
) -> list[dict[str, Any]]:
    """Mirror of live meili_kb.collapse_hits_by_artifact: one row per content_sha
    (clones merge; legacy rows fall back to artifact id), order = best chunk;
    each row gets `passages` = pooled chunks of that content, itself first, capped,
    and `clone_artifact_ids` = the other ledger ids with identical content."""
    order: list[str] = []
    best: dict[str, dict[str, Any]] = {}
    sibs: dict[str, list[dict[str, Any]]] = {}
    clones: dict[str, list[str]] = {}
    for row in hits:
        aid = _aid(row)
        if not aid:
            continue
        sha = str(row.get("content_sha") or "").strip()
        key = f"sha:{sha}" if sha else f"aid:{aid}"
        if key not in best:
            if k is not None and len(order) >= k:
                continue
            order.append(key)
            best[key] = row
            sibs[key] = []
            clones[key] = [aid]
        else:
            if aid not in clones[key]:
                clones[key].append(aid)
            text = _norm(str(row.get("text") or ""))
            kept = [best[key], *sibs[key]]
            if len(sibs[key]) < passages - 1 and all(
                text != _norm(str(x.get("text") or "")) for x in kept
            ):
                sibs[key].append(row)
    out = []
    for key in order:
        row = dict(best[key])
        row["passages"] = [best[key]] + sibs[key]
        row["clone_artifact_ids"] = clones[key][1:]
        out.append(row)
    return out


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
    filt: str | None = None,
) -> tuple[list[dict[str, Any]], float]:
    url, headers = _meili()
    body: dict[str, Any] = {
        "q": q,
        "filter": filt or f"school_id = {_quote(school_id)}",
        "limit": limit,
        "attributesToRetrieve": attrs
        or [
            "artifact_id",
            "material_id",
            "title",
            "text",
            "parent_text",
            "membership_id",
            "heading",
            "content_sha",
        ],
    }
    if extra:
        body.update(extra)
    t0 = time.perf_counter()
    resp = httpx.post(f"{url}/indexes/{INDEX}/search", json=body, headers=headers, timeout=20.0)
    dt = time.perf_counter() - t0
    resp.raise_for_status()
    return list(resp.json().get("hits") or []), dt


def meili_fetch_all(filt: str, fields: list[str]) -> list[dict[str, Any]]:
    """Documents/fetch with offset paging. /search caps estimated hits at 1000."""
    url, headers = _meili()
    rows: list[dict[str, Any]] = []
    offset = 0
    while True:
        resp = httpx.post(
            f"{url}/indexes/{INDEX}/documents/fetch",
            json={"filter": filt, "limit": 1000, "offset": offset, "fields": fields},
            headers=headers,
            timeout=60.0,
        )
        resp.raise_for_status()
        batch = list(resp.json().get("results") or [])
        rows.extend(batch)
        if len(batch) < 1000:
            return rows
        offset += 1000


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


# --- held ---------------------------------------------------------------------


def cmd_held(args: argparse.Namespace) -> int:
    exclude: set[str] = set()
    if args.exclude:
        gold = json.loads(Path(args.exclude).read_text(encoding="utf-8"))
        exclude = {str(it.get("material_id") or "") for it in gold.get("items") or []}
    rows = meili_fetch_all(
        f"school_id = {_quote(args.school)}",
        ["artifact_id", "title", "text", "membership_id"],
    )
    # One row per file: the longest child. Mid-span excerpt of a long child is
    # the closest cheap stand-in for "teacher quotes a line from the middle".
    by_file: dict[str, dict[str, Any]] = {}
    for row in rows:
        aid = _aid(row)
        title = str(row.get("title") or "")
        if not aid or aid in exclude or any(n in title for n in NOISE_TITLES):
            continue
        if _suffix(title) in HELD_SKIP_SUFFIX:
            continue
        text = str(row.get("text") or "")
        if len(_norm(text)) < args.min_chars or not str(row.get("membership_id") or "").strip():
            continue
        cur = by_file.get(aid)
        if cur is None or len(text) > len(str(cur.get("text") or "")):
            by_file[aid] = row
    per_suffix: dict[str, list[dict[str, Any]]] = {}
    for row in by_file.values():
        per_suffix.setdefault(_suffix(str(row.get("title") or "")), []).append(row)
    rng = random.Random(args.seed)
    items: list[dict[str, Any]] = []
    for suffix in sorted(per_suffix):
        group = per_suffix[suffix]
        rng.shuffle(group)
        for row in group[: args.per_suffix]:
            text = str(row.get("text") or "")
            start = max(0, (len(text) - args.span) // 2)
            excerpt = text[start : start + args.span].strip()
            if len(_norm(excerpt)) < 16:
                continue
            items.append(
                {
                    "id": f"{_aid(row)[:8]}-h",
                    "question": excerpt,
                    "kind": suffix,
                    "material_id": _aid(row),
                    "title": str(row.get("title") or ""),
                    "membership_id": str(row.get("membership_id") or ""),
                    "answer_quote": excerpt,
                }
            )
    out_path = Path(args.out)
    if out_path.exists() and not args.force:
        raise SystemExit(f"{out_path} exists; held-out is frozen. New --seed → new --out, or --force.")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(
            {
                "school_id": args.school,
                "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
                "seed": args.seed,
                "span": args.span,
                "excluded_files": len(exclude),
                "items": items,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    by_kind = {k: len(v) for k, v in per_suffix.items()}
    print(
        json.dumps(
            {
                "written": str(out_path),
                "school_docs": len(rows),
                "eligible_files": len(by_file),
                "items": len(items),
                "by_suffix_pool": by_kind,
            },
            ensure_ascii=False,
        )
    )
    return 0


# --- run ----------------------------------------------------------------------


def rerank_pool(query: str, hits: list[dict[str, Any]], *, model: str) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Reorder the fetched pool via New API /v1/rerank (same call shape as live
    meili_kb.rerank_documents). Returns (ordered hits, score stats). Flat scores
    keep Meili order, like live."""
    base = (os.environ.get("DEEPSEEK_BASE_URL") or "http://127.0.0.1:3000/v1").rstrip("/")
    key = (os.environ.get("DEEPSEEK_API_KEY") or "").strip()
    docs = [
        (" ".join(str(x) for x in (h.get("title"), h.get("heading")) if x) + "\n" + str(h.get("text") or ""))[:2000]
        for h in hits
    ]
    if not docs:
        return hits, {"used": False}
    t0 = time.perf_counter()
    resp = httpx.post(
        f"{base}/rerank",
        # return_documents: New API's Zhipu rerank-pro adapter returns index=0 for
        # every row (2026-09-16); the document text is the only way back.
        json={"model": model, "query": query, "documents": docs, "top_n": len(docs), "return_documents": True},
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        timeout=30.0,
        trust_env=False,
    )
    dt = time.perf_counter() - t0
    resp.raise_for_status()
    results = resp.json().get("results") or []
    by_text = {d: i for i, d in enumerate(docs)}
    raw_idx = []
    for row in results:
        try:
            raw_idx.append(int(row.get("index")))
        except (TypeError, ValueError):
            raw_idx.append(-1)
    degenerate = len(results) > 1 and len(set(raw_idx)) == 1
    order: list[int] = []
    scores: list[float] = []
    for row, idx in zip(results, raw_idx):
        if degenerate:
            doc = row.get("document")
            if isinstance(doc, dict):
                doc = doc.get("text")
            idx = by_text.get(str(doc or ""), -1)
        try:
            score = float(row.get("relevance_score", row.get("score")))
        except (TypeError, ValueError):
            continue
        if 0 <= idx < len(docs) and idx not in order:
            order.append(idx)
            scores.append(score)
    spread = (max(scores) - min(scores)) if len(scores) > 1 else 0.0
    stats = {"used": spread > 1e-6, "spread": round(spread, 4), "top": round(max(scores), 4) if scores else None, "ms": round(dt * 1000, 1)}
    if not stats["used"]:
        return hits, stats
    ordered = [hits[i] for i in order] + [h for i, h in enumerate(hits) if i not in set(order)]
    return ordered, stats


def _rank_of(material_id: str, hits: list[dict[str, Any]]) -> int | None:
    """Rank of the target file, counting a merged clone (identical content) as a hit."""
    for i, h in enumerate(hits):
        if _aid(h) == material_id or material_id in (h.get("clone_artifact_ids") or []):
            return i + 1
    return None


def _quote_in(quote: str, hits: list[dict[str, Any]], *, with_parent: bool) -> bool:
    """Quote inside what the model sees for these file hits: every carried passage
    (text), optionally plus parent_text."""
    nq = _norm(quote)
    if not nq:
        return False
    for h in hits:
        passages = h.get("passages") if isinstance(h.get("passages"), list) else [h]
        blob = "".join(str((p or {}).get("text") or "") for p in passages)
        if with_parent:
            blob += str(h.get("parent_text") or "")
        if nq in _norm(blob):
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
    quote_child = 0  # quote inside a returned child text after file collapse, top-k
    quote_parent = 0  # same, child+parent_text
    quote_pass20 = 0  # quote inside any of the first 20 raw passages (no collapse)
    in_pool = 0  # target file anywhere in the fetched pool
    lat: list[float] = []
    per_kind: dict[str, list[int | None]] = {}
    per_kind_quote: dict[str, int] = {}
    rerank_used = 0
    rerank_spread: list[float] = []
    errors = 0
    for it in items:
        kind = str(it.get("kind") or "?")
        try:
            if args.mode == "api":
                raw, dt = search_via_api(
                    it["question"],
                    base=args.base,
                    school_id=school,
                    membership_id=it.get("membership_id") or "eval",
                    limit=k * 2,
                )
                # Live already collapsed (content_sha, passages, clone_artifact_ids);
                # re-collapsing here would drop clone credit and hide 0.2 of hits.
                passages = [p for h in raw for p in (h.get("passages") or [h])]
                hits = raw
            else:
                extra = None
                if args.mode == "hybrid":
                    extra = {"hybrid": {"semanticRatio": args.semantic_ratio, "embedder": args.embedder}}
                raw, dt = meili_search(
                    it["question"],
                    school_id=school,
                    limit=args.fetch,
                    extra=extra,
                    filt=tenant_filter(school, str(it.get("membership_id") or "")),
                )
                if args.rerank:
                    # Rerank the head only; the tail keeps Meili order so file@20 is not cut.
                    head, rs = rerank_pool(it["question"], raw[: args.rerank_pool], model=args.rerank)
                    raw = head + raw[args.rerank_pool :]
                    rerank_used += int(bool(rs.get("used")))
                    rerank_spread.append(float(rs.get("spread") or 0.0))
                    dt += float(rs.get("ms") or 0.0) / 1000.0
                passages = raw
                hits = collapse_by_file(raw, passages=args.passages)
        except Exception as exc:  # noqa: BLE001
            errors += 1
            print(f"  error {it['id']}: {type(exc).__name__}", file=sys.stderr)
            ranks.append(None)
            per_kind.setdefault(kind, []).append(None)
            continue
        lat.append(dt)
        r = _rank_of(it["material_id"], hits)
        ranks.append(r)
        per_kind.setdefault(kind, []).append(r)
        in_pool += int(r is not None)
        top = hits[:k]
        qc = _quote_in(it["answer_quote"], top, with_parent=False)
        quote_child += int(qc)
        per_kind_quote[kind] = per_kind_quote.get(kind, 0) + int(qc)
        quote_parent += int(_quote_in(it["answer_quote"], top, with_parent=True))
        quote_pass20 += int(_quote_in(it["answer_quote"], passages[:20], with_parent=True))

    def _stats(rs: list[int | None]) -> dict[str, Any]:
        n = len(rs) or 1
        return {
            "n": len(rs),
            "file@1": round(sum(1 for r in rs if r == 1) / n, 3),
            f"file@{k}": round(sum(1 for r in rs if r is not None and r <= k) / n, 3),
            "file@20": round(sum(1 for r in rs if r is not None and r <= 20) / n, 3),
            "mrr": round(sum(1.0 / r for r in rs if r is not None) / n, 3),
        }

    n_items = len(items) or 1
    overall = _stats(ranks)
    overall[f"quote_child@{k}"] = round(quote_child / n_items, 3)
    overall[f"quote_parent@{k}"] = round(quote_parent / n_items, 3)
    overall["quote_passages@20"] = round(quote_pass20 / n_items, 3)
    overall["in_pool"] = f"{in_pool}/{len(items)}"
    overall["p50_ms"] = round(statistics.median(lat) * 1000, 1) if lat else None
    overall["p95_ms"] = round(sorted(lat)[max(0, round(0.95 * (len(lat) - 1)))] * 1000, 1) if lat else None
    overall["errors"] = errors
    if args.rerank:
        overall["rerank"] = {
            "model": args.rerank,
            "pool": args.rerank_pool,
            "order_changed": f"{rerank_used}/{len(items)}",
            "score_spread_p50": round(statistics.median(rerank_spread), 4) if rerank_spread else None,
        }
    by_kind = {}
    for kk, v in sorted(per_kind.items()):
        st = _stats(v)
        st[f"quote_child@{k}"] = round(per_kind_quote.get(kk, 0) / (len(v) or 1), 3)
        by_kind[kk] = st
    report = {
        "mode": args.mode,
        "set": Path(args.golden).name,
        "fetch": args.fetch,
        "passages": args.passages,
        "school_id": school[:8],
        "overall": overall,
        "by_kind": by_kind,
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    print()
    print(f"| set | mode | n | file@1 | file@{k} | file@20 | quote child@{k} | quote passages@20 | p50 ms | p95 ms |")
    print("|---|---|---|---|---|---|---|---|---|---|")
    o = overall
    mode_label = f"{args.mode}+{args.rerank}" if args.rerank else args.mode
    print(
        f"| {report['set']} | {mode_label} | {o['n']} | {o['file@1']} | {o[f'file@{k}']} | {o['file@20']} "
        f"| {o[f'quote_child@{k}']} | {o['quote_passages@20']} | {o['p50_ms']} | {o['p95_ms']} |"
    )
    for kk, st in by_kind.items():
        print(
            f"| ↳ {kk} | | {st['n']} | {st['file@1']} | {st[f'file@{k}']} | {st['file@20']} "
            f"| {st[f'quote_child@{k}']} | — | — | — |"
        )
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
    h = sub.add_parser("held")
    h.add_argument("--school", required=True)
    h.add_argument("--out", required=True)
    h.add_argument("--exclude", default="", help="golden json whose files are left out")
    h.add_argument("--per-suffix", type=int, default=12, dest="per_suffix")
    h.add_argument("--span", type=int, default=50, help="excerpt chars from the child's middle")
    h.add_argument("--min-chars", type=int, default=120, dest="min_chars")
    h.add_argument("--seed", type=int, default=7)
    h.add_argument("--force", action="store_true")
    h.set_defaults(fn=cmd_held)
    r = sub.add_parser("run")
    r.add_argument("--golden", required=True)
    r.add_argument("--mode", choices=["keyword", "hybrid", "api"], default="hybrid")
    r.add_argument("--k", type=int, default=5)
    r.add_argument("--fetch", type=int, default=80, help="Meili hits before file collapse (live PICO_KB_FETCH)")
    r.add_argument("--passages", type=int, default=3, help="sibling chunks per file hit (live PICO_KB_PASSAGES)")
    r.add_argument("--rerank", default="", help="New API rerank model to test on the pool (e.g. rerank, rerank-pro)")
    r.add_argument("--rerank-pool", type=int, default=80, dest="rerank_pool")
    r.add_argument("--semantic-ratio", type=float, default=0.5, dest="semantic_ratio")
    r.add_argument("--embedder", default="default")
    r.add_argument("--base", default="http://127.0.0.1:18765")
    r.set_defaults(fn=cmd_run)
    args = ap.parse_args()
    return int(args.fn(args))


if __name__ == "__main__":
    sys.exit(main())
