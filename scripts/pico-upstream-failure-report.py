#!/usr/bin/env python3
"""pico#1336 对账：近 N 天因上游（模型渠道）失败的运行，按类分。只读。

    docker exec -i pico-pico-api-1 python - --days 3 < /opt/pico/scripts/pico-upstream-failure-report.py

每条失败运行分四个维度：错误类（密钥暂停 / 502 / 429·繁忙 / 断流 / 403 无正文）、
Pi 还是直答、失败前有没有输出、老师对话还是服务端调用（有没有对话 id）。
老师对话里出现上游失败 → ❌（列出 run id 前 8 位），退出 1；只有服务端调用或没有 → ✅。
smoke / regress 测试校不算老师。
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from collections import Counter
from datetime import UTC, datetime, timedelta

TEST_SCHOOLS = ("smoke-school", "regress-school")


def classify(reason: str) -> str | None:
    r = reason or ""
    if "暂停" in r:
        return "密钥暂停"
    if "502" in r:
        return "502"
    if "429" in r or "繁忙" in r or "busy" in r.lower():
        return "429·繁忙"
    if "finish_reason" in r:
        return "断流"
    if "403" in r:
        return "403 无正文"
    return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default="/app/data/pico.db")
    ap.add_argument("--days", type=float, default=3.0)
    args = ap.parse_args()
    since = (datetime.now(UTC) - timedelta(days=args.days)).strftime("%Y-%m-%d %H:%M:%S")
    con = sqlite3.connect(f"file:{args.db}?mode=ro", uri=True)
    rows = con.execute(
        "select r.id, e.payload_json, t.school_id, t.conversation_id is not null "
        "from events e join runs r on r.id = e.run_id join tasks t on t.id = r.task_id "
        "where e.type = 'run.status' and e.created_at >= ? "
        "and json_extract(e.payload_json, '$.status') = 'failed'",
        (since,),
    ).fetchall()
    total = con.execute("select count(*) from runs where created_at >= ?", (since,)).fetchone()[0]
    agg: Counter = Counter()
    teacher: list[str] = []
    for run_id, payload, school, conv in rows:
        kind = classify(str(json.loads(payload or "{}").get("reason") or ""))
        if kind is None:
            continue
        types = {t for (t,) in con.execute("select type from events where run_id = ?", (run_id,))}
        path = "Pi" if "run.model" in types else "直答"
        out = "有输出" if types & {"message.delta", "message.stream"} or any(t.startswith("tool.") for t in types) else "没输出"
        test = str(school).startswith(TEST_SCHOOLS)
        who = "测试校" if test else ("老师对话" if conv else "服务端调用")
        agg[(kind, path, out, who)] += 1
        if who == "老师对话":
            teacher.append(run_id[:8])
    print(f"近 {args.days:g} 天（{since} UTC 起）共 {total} 次运行，上游原因失败 {sum(agg.values())} 次")
    for (kind, path, out, who), n in agg.most_common():
        print(f"  {n:4d}  {kind} · {path} · {out} · {who}")
    if teacher:
        print(f"❌ 老师对话里看到上游报错 {len(teacher)} 次：{', '.join(teacher[:20])}")
        return 1
    print("✅ 老师对话里上游报错 0 次")
    return 0


if __name__ == "__main__":
    sys.exit(main())
