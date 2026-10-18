#!/usr/bin/env python3
"""Is Pico using one upstream channel the way it is meant to (pico#1344). Read-only, host side.

AIProxy banned the key on 10-18. Owner 10-18 07:3x PDT: not a rate problem but
a usage problem — AIProxy (a coding subscription) is for long multi-round
sessions only; one-shot calls never go there; caps are only a backstop. This
reads New API's own log (sqlite, read-only) and prints, for one channel over a
window:

* requests, and the same-key peak of requests in flight at once;
* prompt-cache hit rate and the share of requests with no cache at all;
* session share: requests whose ``prompt_cache_key`` is a conversation session
  (Pi's session id or Pico's ``pcs-…``). Pico sends ``session_id`` with the
  same value, so this is the share that carried the session header; the old
  per-prompt hash (``pico-…``) and no key carried none. New API logs only the
  key's first and last 4 characters, hence the prefixes;
* from a conversation's second request on, the share that hit the cache;
* one-shot requests: anything that is not a Pi run (``pcs-…``, ``pico-…``, no
  key) — Pico's direct road answers in one call — and Pi sessions that sent
  only one request in the window (listed, not judged: a short run may end in
  one step).

Only Pico's own token is judged (``--token``, default ``pico-gateway``); other
tokens on the channel (smoke checks, probes) are counted on one line apart.

Pass lines (card acceptance): one-shot requests 0, second-step-on hit share
>= 90 %, peak <= 4 (backstop). Exit 1 on a miss.

    python3 scripts/pico-upstream-pressure-report.py --days 1
    python3 scripts/pico-upstream-pressure-report.py --since "2026-10-19 08:00" --until "2026-10-19 20:00"
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
import time
from collections import Counter
from datetime import datetime, timedelta, timezone

SH = timezone(timedelta(hours=8))
DB = "/home/ops/new-api/data/one-api.db"
PEAK_MAX = 4
LATER_HIT_MIN = 0.90


def key_kind(hint: str) -> str:
    """Kind of ``prompt_cache_key`` from New API's hint (``abcd...wxyz``)."""
    if not hint:
        return "none"
    if hint.startswith("pcs-"):
        return "conversation"
    if hint.startswith("pico"):
        return "prompt_hash"
    return "pi_session"


def _key(other: dict) -> str:
    aff = (other.get("admin_info") or {}).get("channel_affinity") or {}
    if aff.get("key_path") != "prompt_cache_key":
        return ""
    return str(aff.get("key_hint") or "")


def _fp(other: dict) -> str:
    aff = (other.get("admin_info") or {}).get("channel_affinity") or {}
    return str(aff.get("key_fp") or aff.get("key_hint") or "")


def peak(spans: list[tuple[float, float]]) -> int:
    edges = sorted([(a, 1) for a, _ in spans] + [(b, -1) for _, b in spans])
    cur = top = 0
    for _, d in edges:
        cur += d
        top = max(top, cur)
    return top


def measure(rows: list[tuple[int, int, int, str]]) -> dict:
    """rows: (created_at, use_time_s, prompt_tokens, other_json), oldest first."""
    spans, kinds, seen = [], Counter(), Counter()
    cached = prompt = zero = later = later_hit = 0
    for created, use_s, pt, raw in rows:
        other = json.loads(raw or "{}")
        ca = int(other.get("cache_tokens") or 0)
        spans.append((created - (use_s or 0), created))
        cached += ca
        prompt += pt or 0
        zero += 0 if ca else 1
        kinds[key_kind(_key(other))] += 1
        fp = _fp(other)
        if fp:
            if seen[fp]:
                later += 1
                later_hit += 1 if ca else 0
            seen[fp] += 1
    n = len(rows)
    return {
        "requests": n,
        "peak": peak(spans),
        "cache_hit": cached / prompt if prompt else 0.0,
        "zero_cache": zero / n if n else 0.0,
        "kinds": dict(kinds),
        "one_shot": n - kinds["pi_session"],
        "sessions": len(seen),
        "single_request_sessions": sum(
            1 for fp, c in seen.items() if c == 1 and key_kind(fp) == "pi_session"
        ),
        "later_steps": later,
        "later_hit": later_hit / later if later else 0.0,
    }


def verdict(m: dict) -> list[str]:
    miss = []
    if m["one_shot"]:
        miss.append(f"一问请求 {m['one_shot']} 次（应为 0）")
    if m["later_steps"] and m["later_hit"] < LATER_HIT_MIN:
        miss.append(f"同一对话第 2 步起命中缓存 {m['later_hit']:.1%} < {LATER_HIT_MIN:.0%}")
    if m["peak"] > PEAK_MAX:
        miss.append(f"同时请求峰值 {m['peak']} > {PEAK_MAX}")
    return miss


def _ts(text: str) -> int:
    return int(datetime.fromisoformat(text).replace(tzinfo=SH).timestamp())


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--db", default=DB)
    ap.add_argument("--channel", default="aiproxy-openai", help="New API channel name")
    ap.add_argument("--token", default="pico-gateway", help="New API token whose requests are judged")
    ap.add_argument("--days", type=float, default=1.0)
    ap.add_argument(
        "--since", default="", help="Shanghai time, e.g. 2026-10-19 08:00 (overrides --days)"
    )
    ap.add_argument("--until", default="", help="Shanghai time")
    args = ap.parse_args()

    until = _ts(args.until) if args.until else int(time.time())
    since = _ts(args.since) if args.since else int(until - args.days * 86400)
    db = sqlite3.connect(f"file:{args.db}?mode=ro", uri=True)
    # The log's channel_name column stays empty; resolve the name through channels.
    ids = [r[0] for r in db.execute("select id from channels where name = ?", (args.channel,))]
    if not ids:
        print(f"没有叫 {args.channel} 的通道", file=sys.stderr)
        return 2
    window = "type = 2 and channel_id = ? and created_at >= ? and created_at < ?"
    rows = db.execute(
        f"select created_at, use_time, prompt_tokens, other from logs where {window}"
        " and token_name = ? order by created_at",
        (ids[0], since, until, args.token),
    ).fetchall()
    others = db.execute(
        f"select token_name, count(*) from logs where {window} and token_name != ?"
        " group by token_name order by 2 desc",
        (ids[0], since, until, args.token),
    ).fetchall()
    m = measure(rows)
    span = f"{datetime.fromtimestamp(since, SH):%m-%d %H:%M} – {datetime.fromtimestamp(until, SH):%m-%d %H:%M}"
    print(f"通道 {args.channel} · 令牌 {args.token} · {span}（上海时间）")
    if others:
        print("不判：" + " · ".join(f"{name or '（无令牌）'} {n} 次" for name, n in others))
    print(
        f"请求 {m['requests']} · 同一把 key 同时请求峰值 {m['peak']} · 缓存命中 {m['cache_hit']:.0%}"
        f" · 零缓存 {m['zero_cache']:.0%}"
    )
    print(
        f"一问请求 {m['one_shot']}（{m['kinds']}）· 会话 {m['sessions']} 个"
        f"（只发一次的 Pi 会话 {m['single_request_sessions']} 个，不判）"
        f" · 第 2 步起 {m['later_steps']} 次、命中缓存 {m['later_hit']:.0%}"
    )
    if not rows:
        print("这段时间没有请求，没得判")
        return 0
    miss = verdict(m)
    print("✅ 三条都过" if not miss else "❌ " + "；".join(miss))
    return 1 if miss else 0


if __name__ == "__main__":
    sys.exit(main())
