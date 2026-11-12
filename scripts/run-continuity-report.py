#!/usr/bin/env python3
"""edu-core#5337 长任务连续性（长稳 E1 续跑 / E3 停止）近 N 天对账。只读。

    docker exec -i pico-pico-api-1 python - --days 7 --check < /opt/pico/scripts/run-continuity-report.py

E1 续跑：被发版重启打断的 run（events run.interrupted / run.resume · reason api.restart）都要接着跑到终态；
判 api_restart_reconciliation 失败的 = 断了没续上；续上后仍 running 且 30 分钟没新事件 = 续丢了。
E3 停止：停下的 run（status cancelled · ended_at 在窗内），停后 60 秒还在记模型账 = Pi 没真停。
--check 给了就判：有断 / 续丢 / 停不下 ❌ 退出 1。
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from collections import Counter
from datetime import datetime, timedelta, timezone

ACTIVE = ("queued", "preparing", "running")
STALE_S = 30 * 60
STOP_GRACE_S = 60


def ts(raw: str) -> datetime:
    return datetime.fromisoformat(str(raw)[:26]).replace(tzinfo=timezone.utc)  # noqa: UP017 — host python 3.10


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default="/app/data/pico.db")
    ap.add_argument("--days", type=float, default=7)
    ap.add_argument("--since", help="UTC 起点 YYYY-MM-DD HH:MM:SS，给了就不看 --days")
    ap.add_argument("--check", action="store_true", help="有断 / 续丢 / 停不下就退出 1")
    args = ap.parse_args()
    now = datetime.now(timezone.utc)  # noqa: UP017
    since = args.since or (now - timedelta(days=args.days)).strftime("%Y-%m-%d %H:%M:%S")
    con = sqlite3.connect(f"file:{args.db}?mode=ro", uri=True)

    def reason_rows(kind: str, reason: str) -> list[str]:
        return [
            r[0]
            for r in con.execute(
                "select distinct run_id from events where type = ? and created_at >= ? "
                "and json_extract(payload_json, '$.reason') = ?",
                (kind, since, reason),
            )
        ]

    # A hard kill skips run.interrupted; the startup run.resume is the sure mark.
    hit = sorted(
        set(reason_rows("run.interrupted", "api.restart"))
        | set(reason_rows("run.resume", "api.restart"))
    )
    lost = reason_rows("run.status", "api_restart_reconciliation")
    outcome: Counter[str] = Counter()
    dropped: list[str] = []
    for run_id in hit:
        status, last = con.execute(
            "select r.status, (select max(created_at) from events where run_id = r.id) "
            "from runs r where r.id = ?",
            (run_id,),
        ).fetchone()
        outcome[status] += 1
        if status in ACTIVE and (now - ts(last)).total_seconds() > STALE_S:
            dropped.append(run_id)

    stopped = con.execute(
        "select id, ended_at from runs where status = 'cancelled' and ended_at >= ?", (since,)
    ).fetchall()
    unstoppable: list[str] = []
    for run_id, ended in stopped:
        late = con.execute(
            "select max(created_at) from usage_events where run_id = ? and created_at > ?",
            (run_id, ended),
        ).fetchone()[0]
        if late and (ts(late) - ts(ended)).total_seconds() > STOP_GRACE_S:
            unstoppable.append(run_id)

    print(f"since {since} UTC")
    print(
        f"E1 续跑：续上 {len(hit)}（终态 {json.dumps(dict(outcome), ensure_ascii=False)}）"
        f" · 续丢 {len(dropped)} · 断了没续 {len(lost)}"
    )
    print(f"E3 停止：停下 {len(stopped)} · 停后 {STOP_GRACE_S}s 还在记账 {len(unstoppable)}")
    bad = {"续丢": dropped, "断了没续": lost, "停不下": unstoppable}
    for name, ids in bad.items():
        for run_id in ids[:10]:
            print(f"  ❌ {name} {run_id}")
    if args.check and any(bad.values()):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
