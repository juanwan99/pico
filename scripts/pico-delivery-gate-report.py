#!/usr/bin/env python3
"""pico#1334 对账：近 N 天交付门判了多少次「说交了没文件」，其中有没有误拦没工具的一轮。只读。

    docker exec pico-pico-api-1 python scripts/pico-delivery-gate-report.py --days 1

每轮的 delivery.summary 记 writers_visible：
  false = 这一轮没给模型工具（edu 服务端要细则 / 判分 / JSON 的调用），不该被判「说交了没文件」
  true  = 有工具，照判
  null  = 没标（#1334 上线前的轮次，或没经过入口的老路径）
有一次 writers_visible=false 却被判 deliverable_missing_artifact → ❌，退出 1。
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from collections import Counter
from datetime import UTC, datetime, timedelta

GATE_REASONS = ("deliverable_missing_artifact",)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default="/app/data/pico.db")
    ap.add_argument("--days", type=float, default=1.0)
    args = ap.parse_args()

    since = (datetime.now(UTC) - timedelta(days=args.days)).strftime("%Y-%m-%d %H:%M:%S")
    con = sqlite3.connect(f"file:{args.db}?mode=ro", uri=True)
    summaries: dict[str, object] = {}
    for run_id, payload in con.execute(
        "select run_id, payload_json from events where type='delivery.summary' and created_at >= ?",
        (since,),
    ):
        summaries[run_id] = json.loads(payload or "{}").get("writers_visible")
    gated = [
        run_id
        for run_id, payload in con.execute(
            "select run_id, payload_json from events where type='run.status' and created_at >= ?",
            (since,),
        )
        if json.loads(payload or "{}").get("reason") in GATE_REASONS
    ]

    turns = Counter(str(v).lower() if v is not None else "null" for v in summaries.values())
    by_writers = Counter(
        str(summaries.get(r)).lower() if summaries.get(r) is not None else "null" for r in gated
    )
    print(f"近 {args.days:g} 天（{since} UTC 起）")
    print(f"  轮次：有工具 {turns['true']} · 没工具 {turns['false']} · 没标 {turns['null']}")
    print(f"  判「说交了没文件」{len(gated)} 次：有工具 {by_writers['true']} · "
          f"没工具 {by_writers['false']} · 没标 {by_writers['null']}")
    bad = by_writers["false"]
    if bad:
        print(f"❌ 没工具的一轮被判了 {bad} 次（应为 0）")
        return 1
    print("✅ 没工具的轮次 0 次被判「说交了没文件」")
    return 0


if __name__ == "__main__":
    sys.exit(main())
