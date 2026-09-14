#!/usr/bin/env python3
"""Teacher run failure rate from the Pico ledger (read-only helper, not a truth source).

Stage-1 metric for #994: what teachers actually hit, bucketed by cause. Counts
only — never prints prompts, errors verbatim, or ids.

On the ECS (runs inside the API container, which owns the SQLite file):
    docker cp scripts/teacher-failure-rate.py pico-pico-api-1:/tmp/tfr.py \
      && docker exec pico-pico-api-1 python3 /tmp/tfr.py --db /app/data/pico.db

Anywhere else: python3 scripts/teacher-failure-rate.py --db path/to/pico.db
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import statistics
from collections import Counter

BUCKETS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("upstream_relay", ("do_request_failed", "do request failed", "new_api_error", "connection reset", "7890")),
    ("upstream_524", ("524", "等首包")),
    ("upstream_503", ("temporarily unavailable", "(503)")),
    ("upstream_overloaded", ("overloaded",)),
    ("rate_or_busy", ("429", "过于频繁", "concurrency", "并发已满")),
    ("deploy_killed", ("terminated", "owner was lost", "restart")),
    ("ask_timeout", ("ask.timeout", "超时未选")),
    ("timeout", ("timeout", "超时")),
    ("model_slot", ("invalid request", "模型不可用")),
    ("office_sandbox", ("sandbox.", "office.", "no_output")),
    ("empty_response", ("empty model response", "没有生成")),
    ("delivery_gate", ("没有可下载的真文件",)),
)


def bucket(error: str | None) -> str:
    low = (error or "").lower()
    if not low:
        return "no_error_text"
    for name, needles in BUCKETS:
        if any(n.lower() in low for n in needles):
            return name
    return "other"


def window(con: sqlite3.Connection, hours: int) -> dict:
    rows = con.execute(
        """
        select status, error,
               (julianday(ended_at) - julianday(started_at)) * 86400 as wall_s
        from runs
        where created_at >= datetime('now', ?)
        """,
        (f"-{int(hours)} hour",),
    ).fetchall()
    total = len(rows)
    status = Counter(r[0] for r in rows)
    failed = [r for r in rows if r[0] == "failed"]
    buckets = Counter(bucket(r[1]) for r in failed)
    ok_walls = [r[2] for r in rows if r[0] == "succeeded" and r[2] is not None and r[2] >= 0]
    fail_rate = (len(failed) / total) if total else 0.0
    return {
        "hours": hours,
        "runs": total,
        "status": dict(status),
        "fail_rate": round(fail_rate, 4),
        "fail_buckets": dict(buckets.most_common()),
        "ok_p50_s": round(statistics.median(ok_walls), 1) if ok_walls else None,
        "ok_p90_s": round(sorted(ok_walls)[int(len(ok_walls) * 0.9) - 1], 1) if len(ok_walls) >= 10 else None,
    }


def by_day(con: sqlite3.Connection, days: int) -> list[dict]:
    rows = con.execute(
        """
        select substr(created_at, 1, 10) as day, status, count(*)
        from runs
        where created_at >= datetime('now', ?)
        group by 1, 2 order by 1
        """,
        (f"-{int(days)} day",),
    ).fetchall()
    per: dict[str, Counter] = {}
    for day, status, n in rows:
        per.setdefault(day, Counter())[status] = n
    out = []
    for day in sorted(per):
        c = per[day]
        total = sum(c.values())
        out.append(
            {
                "day": day,
                "runs": total,
                "failed": c.get("failed", 0),
                "fail_rate": round(c.get("failed", 0) / total, 3) if total else 0.0,
            }
        )
    return out


def render_markdown(report: dict) -> str:
    lines = ["| 窗口 | 轮数 | 失败率 | 成功 p50 | 失败归并 |", "|---|---:|---:|---:|---|"]
    for w in report["windows"]:
        buckets = ", ".join(f"{k} {v}" for k, v in w["fail_buckets"].items()) or "—"
        p50 = f"{w['ok_p50_s']}s" if w["ok_p50_s"] is not None else "—"
        lines.append(f"| 近 {w['hours']}h | {w['runs']} | {w['fail_rate'] * 100:.1f}% | {p50} | {buckets} |")
    lines.append("")
    lines.append("| 日 | 轮数 | 失败 | 失败率 |")
    lines.append("|---|---:|---:|---:|")
    for d in report["by_day"]:
        lines.append(f"| {d['day']} | {d['runs']} | {d['failed']} | {d['fail_rate'] * 100:.1f}% |")
    return "\n".join(lines)


def build_report(db_path: str, *, days: int = 7) -> dict:
    con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        return {
            "windows": [window(con, 24), window(con, 24 * days)],
            "by_day": by_day(con, days),
        }
    finally:
        con.close()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db", default="/app/data/pico.db")
    ap.add_argument("--days", type=int, default=7)
    ap.add_argument("--json", action="store_true", help="print JSON instead of markdown")
    args = ap.parse_args()
    report = build_report(args.db, days=args.days)
    print(json.dumps(report, ensure_ascii=False, indent=2) if args.json else render_markdown(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
