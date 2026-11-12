#!/usr/bin/env python3
"""edu-core#5288 Pico 用量按入口（工作台 / 侧栏 / 智慧大脑 / 考试）出数：近 N 小时。只读。

    docker exec -i pico-pico-api-1 python - --hours 24 < /opt/pico/scripts/pico-usage-by-entry.py

entry = edu 票上的 <定位>.<来源>（workbench.web 是工作台走代理来的）；#5288 之前的行记 unknown。
--expect sidebar.propose,workbench.web 给了就判：这些入口近 N 小时没有一行 ❌ 退出 1（#5288 验收用）。
"""

from __future__ import annotations

import argparse
import sqlite3
import sys
from datetime import UTC, datetime, timedelta


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default="/app/data/pico.db")
    ap.add_argument("--hours", type=float, default=24)
    ap.add_argument("--expect", default="", help="逗号分隔的入口，近 N 小时必须有行")
    args = ap.parse_args()
    since = (datetime.now(UTC) - timedelta(hours=args.hours)).replace(tzinfo=None)
    con = sqlite3.connect(f"file:{args.db}?mode=ro", uri=True)
    rows = con.execute(
        """
        SELECT COALESCE(json_extract(extra_json, '$.entry'), 'unknown') AS entry,
               COALESCE(json_extract(extra_json, '$.bill_to'), 'member') AS bill_to,
               COUNT(*), COALESCE(SUM(total_tokens), 0), COUNT(DISTINCT membership_id)
          FROM usage_events
         WHERE created_at >= ?
         GROUP BY 1, 2
         ORDER BY 1, 2
        """,
        (since.isoformat(sep=" "),),
    ).fetchall()
    print(f"近 {args.hours:g} 小时（UTC {since:%m-%d %H:%M} 起）Pico 用量按入口")
    print(f"{'入口':<32}{'记账':<8}{'行数':>6}{'tokens':>12}{'人数':>6}")
    seen: set[str] = set()
    place: dict[str, int] = {}
    for entry, bill, n, tokens, people in rows:
        seen.add(entry)
        head = entry.split(".", 1)[0]
        place[head] = place.get(head, 0) + n
        print(f"{entry:<32}{bill:<8}{n:>6}{tokens:>12}{people:>6}")
    print("按定位：" + "，".join(f"{k} {v}" for k, v in sorted(place.items())) if place else "按定位：（无）")
    want = [e.strip() for e in args.expect.split(",") if e.strip()]
    miss = [e for e in want if e not in seen]
    if miss:
        print(f"❌ 没有行：{', '.join(miss)}")
        return 1
    if want:
        print(f"✅ 都有：{', '.join(want)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
