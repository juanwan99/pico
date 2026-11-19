#!/usr/bin/env python3
"""pico#1342 开工前按需加载 · 现网对账（统筹 11-19 定的口径）。只读。

    docker exec -i pico-pico-api-1 python - --days 3 --check < /opt/pico/scripts/pico-step1-input-report.py

两条：
1. 现网跑的桥带按需加载：容器里 pico-gateway-tools.ts 有 lazyPageHands 且装上了（开工表不带网页手，
   打开网页后才加；行为由 tests/unit/test_lazy_page_hands.py 对真桥跑着验）。
2. Pi 运行第 1 步 input token 中位 ≤ --max（默认 8926 = 11-16～11-19 这周的现网中位）。
   取 events 里 agent.step、phase=turn_end、step=1、runtime=pi-true 的 usage.input_tokens。

--check 给了就判：哪条没过 ❌ 退出 1；窗口里没有 Pi 运行也算没过（判不了）。
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from datetime import datetime, timedelta, timezone

BRIDGE = "/app/services/true_pi_bridge/pico-gateway-tools.ts"
MAX_MEDIAN = 8926


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default="/app/data/pico.db")
    ap.add_argument("--bridge", default=BRIDGE)
    ap.add_argument("--days", type=float, default=3)
    ap.add_argument("--since", help="UTC 起点 YYYY-MM-DD HH:MM:SS，给了就不看 --days")
    ap.add_argument("--until", help="UTC 终点，不给 = 现在")
    ap.add_argument("--max", type=int, default=MAX_MEDIAN, help="第 1 步 input 中位上限")
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()
    now = datetime.now(timezone.utc)  # noqa: UP017 — also runs on the host (python 3.10)
    since = args.since or (now - timedelta(days=args.days)).strftime("%Y-%m-%d %H:%M:%S")
    until = args.until or now.strftime("%Y-%m-%d %H:%M:%S")

    with open(args.bridge, encoding="utf-8") as fh:
        src = fh.read()
    lazy = "function lazyPageHands(" in src and "\n  lazyPageHands(pi);" in src
    print(f"桥 {args.bridge}：按需加载网页手 {'在' if lazy else '不在'}")

    con = sqlite3.connect(f"file:{args.db}?mode=ro", uri=True)
    first: list[int] = []
    cached: list[int] = []
    for (payload,) in con.execute(
        "select payload_json from events where type = 'agent.step' and created_at >= ? and created_at < ? "
        "and payload_json like '%turn_end%'",
        (since, until),
    ):
        p = json.loads(payload or "{}")
        if p.get("phase") != "turn_end" or p.get("step") != 1 or p.get("runtime") != "pi-true":
            continue
        usage = p.get("usage") or {}
        n = int(usage.get("input_tokens") or usage.get("prompt_tokens") or 0)
        if n:
            first.append(n)
            cached.append(int(usage.get("cached_tokens") or 0))
    print(f"{since} — {until} UTC  Pi 运行第 1 步 {len(first)} 次")
    median = None
    if first:
        first.sort()
        cached.sort()
        median = first[len(first) // 2]
        print(
            f"  input 中位 {median}（上限 {args.max}），p10 {first[len(first) // 10]}，"
            f"p90 {first[len(first) * 9 // 10]}；其中缓存读中位 {cached[len(cached) // 2]}"
        )
    if not args.check:
        return 0
    bad = []
    if not lazy:
        bad.append("现网桥没带按需加载")
    if median is None:
        bad.append("这段时间没有 Pi 运行，判不了")
    elif median > args.max:
        bad.append(f"第 1 步 input 中位 {median} > {args.max}")
    if bad:
        print("❌ " + "；".join(bad))
        return 1
    print("✅ 开工表不带网页手，第 1 步 input 没涨")
    return 0


if __name__ == "__main__":
    sys.exit(main())
