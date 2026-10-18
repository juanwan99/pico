#!/usr/bin/env python3
"""How hard Pico leans on one upstream channel (pico#1344). Read-only, host side.

AIProxy banned the key on 10-18: every request looked like a new conversation
and too many ran at once. This reads New API's own log (sqlite, read-only) and
prints, for one channel over a window:

* requests, and the same-key peak of requests in flight at once;
* prompt-cache hit rate and the share of requests with no cache at all;
* session share: requests whose ``prompt_cache_key`` is a conversation session
  (Pi's session id or Pico's ``pcs-…``). Pico sends ``session_id`` with the
  same value, so this is the share that carried the session header; the old
  per-prompt hash (``pico-…``) and no key carried none. New API logs only the
  key's first and last 4 characters, hence the prefixes;
* from a conversation's second request on, the share that hit the cache.

Pass lines (card acceptance): peak <= 4, session share >= 99 %, second-step-on
hit share >= 90 %. Exit 1 on a miss.

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
SESSION_MIN = 0.99
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
    sessioned = kinds["pi_session"] + kinds["conversation"]
    return {
        "requests": n,
        "peak": peak(spans),
        "cache_hit": cached / prompt if prompt else 0.0,
        "zero_cache": zero / n if n else 0.0,
        "kinds": dict(kinds),
        "session_share": sessioned / n if n else 0.0,
        "sessions": len(seen),
        "later_steps": later,
        "later_hit": later_hit / later if later else 0.0,
    }


def verdict(m: dict) -> list[str]:
    miss = []
    if m["peak"] > PEAK_MAX:
        miss.append(f"同时请求峰值 {m['peak']} > {PEAK_MAX}")
    if m["session_share"] < SESSION_MIN:
        miss.append(f"带会话的请求 {m['session_share']:.1%} < {SESSION_MIN:.0%}")
    if m["later_steps"] and m["later_hit"] < LATER_HIT_MIN:
        miss.append(f"同一对话第 2 步起命中缓存 {m['later_hit']:.1%} < {LATER_HIT_MIN:.0%}")
    return miss


def _ts(text: str) -> int:
    return int(datetime.fromisoformat(text).replace(tzinfo=SH).timestamp())


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--db", default=DB)
    ap.add_argument("--channel", default="aiproxy-openai", help="New API channel name")
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
    rows = db.execute(
        "select created_at, use_time, prompt_tokens, other from logs"
        " where type = 2 and channel_id = ? and created_at >= ? and created_at < ? order by created_at",
        (ids[0], since, until),
    ).fetchall()
    m = measure(rows)
    span = f"{datetime.fromtimestamp(since, SH):%m-%d %H:%M} – {datetime.fromtimestamp(until, SH):%m-%d %H:%M}"
    print(f"通道 {args.channel} · {span}（上海时间）")
    print(
        f"请求 {m['requests']} · 同一把 key 同时请求峰值 {m['peak']} · 缓存命中 {m['cache_hit']:.0%}"
        f" · 零缓存 {m['zero_cache']:.0%}"
    )
    print(
        f"带会话 {m['session_share']:.1%}（{m['kinds']}）· 会话 {m['sessions']} 个"
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
