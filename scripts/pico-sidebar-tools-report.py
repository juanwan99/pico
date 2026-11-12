#!/usr/bin/env python3
"""edu-core#5324 侧栏只挂学校业务工具：近 N 小时入口 sidebar.* 的运行用了哪些工具、给了哪些工具。只读。

    docker exec -i pico-pico-api-1 python - --hours 24 < /opt/pico/scripts/pico-sidebar-tools-report.py

侧栏运行 = usage_events 里 entry 以 sidebar. 开头的 run（edu 票上的入口，#5288）。
出：句数、工具次数、第一轮输入 token 中位、给模型的工具表里 / 实际调用里越界的（bash / read / write /
edit / sandbox_* / generate_* / web_* / workspace_write_file / read_office_skill）。
--check 给了就判：有越界 ❌ 退出 1。--until 配 --since 量发版前的底数。
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from collections import Counter
from datetime import datetime, timedelta, timezone

OFF = {"bash", "read", "write", "edit", "workspace_write_file", "read_office_skill", "ask_user"}
OFF_PREFIX = ("sandbox_", "generate_", "web_")


def off(name: str) -> bool:
    return name in OFF or name.startswith(OFF_PREFIX)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default="/app/data/pico.db")
    ap.add_argument("--hours", type=float, default=24)
    ap.add_argument("--since", help="UTC 起点 YYYY-MM-DD HH:MM:SS，给了就不看 --hours（量发版后）")
    ap.add_argument("--until", help="UTC 终点，不给 = 现在")
    ap.add_argument("--check", action="store_true", help="有越界工具就退出 1")
    args = ap.parse_args()
    now = datetime.now(timezone.utc)  # noqa: UP017 — also runs on the host (python 3.10)
    since = args.since or (now - timedelta(hours=args.hours)).strftime("%Y-%m-%d %H:%M:%S")
    until = args.until or now.strftime("%Y-%m-%d %H:%M:%S")
    con = sqlite3.connect(f"file:{args.db}?mode=ro", uri=True)
    runs = [
        r[0]
        for r in con.execute(
            "select distinct run_id from usage_events where created_at >= ? and created_at < ? "
            "and run_id is not null and json_extract(extra_json, '$.entry') like 'sidebar.%'",
            (since, until),
        )
    ]
    calls: Counter[str] = Counter()
    shown_off: Counter[str] = Counter()
    first_in: list[int] = []
    pi_runs = 0
    for run_id in runs:
        events = con.execute(
            "select type, payload_json from events where run_id = ? order by seq", (run_id,)
        ).fetchall()
        first = None
        for kind, payload in events:
            p = json.loads(payload or "{}")
            if kind == "run.model":
                pi_runs += 1
                for name in p.get("visible_tools") or []:
                    if off(str(name)):
                        shown_off[str(name)] += 1
            elif kind == "tool.call":
                calls[str(p.get("tool"))] += 1
            elif kind == "agent.step" and p.get("phase") == "turn_end" and first is None:
                first = int((p.get("usage") or {}).get("prompt_tokens") or 0) or None
        if first:
            first_in.append(first)
    print(f"{since} — {until} UTC 侧栏（entry sidebar.*）{len(runs)} 句，其中进 Pi {pi_runs} 句")
    print("  工具次数：" + ("、".join(f"{k} {v}" for k, v in calls.most_common()) or "（无）"))
    if first_in:
        first_in.sort()
        print(f"  第一轮输入 token：中位 {first_in[len(first_in) // 2]}，{len(first_in)} 句")
    bad_calls = {k: v for k, v in calls.items() if off(k)}
    print("  越界调用：" + ("、".join(f"{k} {v}" for k, v in bad_calls.items()) or "无"))
    print("  工具表里越界：" + ("、".join(f"{k} {v}" for k, v in shown_off.most_common(6)) or "无"))
    if not args.check:
        return 0
    if bad_calls or shown_off:
        print("❌ 侧栏还有学校业务以外的工具")
        return 1
    if not pi_runs:
        print("❌ 这段时间没有侧栏运行，判不了")
        return 1
    print("✅ 侧栏只有学校业务工具")
    return 0


if __name__ == "__main__":
    sys.exit(main())
