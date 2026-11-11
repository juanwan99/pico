#!/usr/bin/env python3
"""edu-core#5225 侧栏 AI 一句话时间花在哪：近 N 天侧栏运行逐段拆时。只读。

    docker exec -i pico-pico-api-1 python - --days 1 < /opt/pico/scripts/pico-sidebar-latency-report.py

侧栏运行 = Pi 运行且可见工具里有 propose_page_mutation。每句拆成：
起步（运行开始 → run.model，含起容器）、模型（每轮 model → turn_end 之和）、
工具（tool.call → tool.result 之和）、收尾（agent.end → run.status）、合计。
--max-median 给了就判：合计中位超线 ❌ 退出 1（#5224 a2 验收用 4）。
带 run.timing（#5227 起）的运行再按 Pico 当场打的时间点细拆：就绪（到容器起命令）/
Pi 起（就绪 → Pi 第一个事件）/ 首字合计（每轮开始 → 模型第一个输出之和）/
生成与工具（其余到 agent_end）/ 收尾（agent_end → 完）/ 其中等落盘。
首字再拆（带 llm_ms 且一轮一次模型请求的句子）：Pi 发请求（每轮开始 → 请求到 pico-api，
含盒子 → runner 一跳）/ 上游首包（到 pico-api → New API 回第一块）/ 首包到首字（→ Pi 报第一个输出）。
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from collections import Counter
from datetime import datetime, timedelta, timezone

SEGMENTS = ("合计", "起步", "模型", "工具", "收尾")
FINE = ("就绪", "Pi 起", "首字合计", "其中Pi发请求", "其中上游首包", "其中首包到首字", "生成与工具", "收尾", "等落盘")


def at(s: str) -> datetime:
    return datetime.fromisoformat(s)


def split_timing(p: dict) -> dict | None:
    ms, rounds = p.get("ms") or {}, p.get("rounds_ms") or []
    need = ("ready", "pi_first", "agent_end", "done")
    if any(ms.get(k) is None for k in need) or not rounds:
        return None
    ttfb = sum((b - a) for a, b in rounds if b is not None)
    fine = {
        "就绪": ms["ready"],
        "Pi 起": ms["pi_first"] - ms["ready"],
        "首字合计": ttfb,
        "生成与工具": ms["agent_end"] - rounds[0][0] - ttfb,
        "收尾": ms["done"] - ms["agent_end"],
        "等落盘": ms["landed"] - ms["agent_end"] if ms.get("landed") is not None else None,
        "其中Pi发请求": None,
        "其中上游首包": None,
        "其中首包到首字": None,
    }
    calls = p.get("llm_ms") or []
    if len(calls) == len(rounds) and all(b is not None for _a, b in rounds):
        # One model call per round (no retry / resume): split each round's first token.
        fine["其中Pi发请求"] = sum(c[0] - r[0] for c, r in zip(calls, rounds))
        fine["其中上游首包"] = sum(c[1] - c[0] for c in calls)
        fine["其中首包到首字"] = sum(r[1] - c[1] for c, r in zip(calls, rounds))
    return {k: (None if v is None else v / 1000) for k, v in fine.items()}


def split_run(started: str, ended: str, events: list[tuple[str, str, str]]) -> dict | None:
    t0, t1 = at(started), at(ended)
    seg = {"合计": (t1 - t0).total_seconds(), "起步": None, "模型": 0.0, "工具": 0.0, "收尾": None}
    rounds = 0
    model_at = None
    calls: dict[str, datetime] = {}
    end_at = None
    tools: list[str] = []
    fine = None
    for kind, created, payload in events:
        p = json.loads(payload or "{}")
        now = at(created)
        if kind == "run.model" and seg["起步"] is None:
            seg["起步"] = (now - t0).total_seconds()
        elif kind == "agent.step" and p.get("phase") == "model":
            model_at = now
            rounds += 1
        elif kind == "agent.step" and p.get("phase") == "turn_end" and model_at is not None:
            seg["模型"] += (now - model_at).total_seconds()
            model_at = None
        elif kind == "tool.call":
            calls[str(p.get("call_id") or p.get("tool"))] = now
            tools.append(str(p.get("tool")))
        elif kind == "tool.result":
            key = str(p.get("call_id") or p.get("tool"))
            if key in calls:
                seg["工具"] += (now - calls.pop(key)).total_seconds()
        elif kind == "agent.end":
            end_at = now
        elif kind == "run.timing":
            fine = split_timing(p)
        elif kind == "run.status" and p.get("status") == "succeeded" and end_at is not None:
            seg["收尾"] = (now - end_at).total_seconds()
    if seg["起步"] is None:
        return None
    return {"seg": seg, "rounds": rounds, "tools": tools, "fine": fine}


def pct(xs: list[float], q: float) -> float:
    xs = sorted(xs)
    return xs[min(len(xs) - 1, int(len(xs) * q))] if xs else 0.0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default="/app/data/pico.db")
    ap.add_argument("--days", type=float, default=1.0)
    ap.add_argument("--since", help="UTC 起点 YYYY-MM-DD HH:MM:SS，给了就不看 --days（量发版后）")
    ap.add_argument("--max-median", type=float, help="合计中位上限（秒），超了退出 1")
    args = ap.parse_args()
    now = datetime.now(timezone.utc)  # noqa: UP017 — also runs on the host (python 3.10)
    since = args.since or (now - timedelta(days=args.days)).strftime("%Y-%m-%d %H:%M:%S")
    con = sqlite3.connect(f"file:{args.db}?mode=ro", uri=True)
    runs = con.execute(
        "select r.id, r.started_at, r.ended_at from runs r "
        "where r.started_at >= ? and r.ended_at is not null and exists ("
        "select 1 from events e where e.run_id = r.id and e.type = 'run.model' "
        "and e.payload_json like '%propose_page_mutation%') "
        "and exists (select 1 from events e where e.run_id = r.id and e.type = 'run.status' "
        "and json_extract(e.payload_json, '$.status') = 'succeeded')",
        (since,),
    ).fetchall()
    rows = []
    for run_id, started, ended in runs:
        events = con.execute(
            "select type, created_at, payload_json from events where run_id = ? order by seq", (run_id,)
        ).fetchall()
        got = split_run(started, ended, events)
        if got is not None:
            rows.append(got)
    print(f"{since} UTC 起侧栏成功运行 {len(rows)} 句（秒）")
    if not rows:
        print("没有侧栏运行")
        return 1 if args.max_median is not None else 0
    print("  段      中位    p90    均值")
    for name in SEGMENTS:
        xs = [r["seg"][name] for r in rows if r["seg"][name] is not None]
        print(f"  {name}  {pct(xs, .5):6.2f} {pct(xs, .9):6.2f} {sum(xs) / len(xs):6.2f}")
    fine = [r["fine"] for r in rows if r["fine"]]
    if fine:
        print(f"  细拆（带 run.timing 的 {len(fine)} 句）")
        for name in FINE:
            xs = [f[name] for f in fine if f[name] is not None]
            if xs:
                print(f"  {name:<6}{pct(xs, .5):6.2f} {pct(xs, .9):6.2f} {sum(xs) / len(xs):6.2f}")
    rounds = Counter(r["rounds"] for r in rows)
    print("  模型轮数：" + "、".join(f"{k} 轮 {v} 句" for k, v in sorted(rounds.items())))
    tools = Counter(t for r in rows for t in r["tools"])
    print("  工具次数：" + "、".join(f"{k} {v}" for k, v in tools.most_common(8)))
    if args.max_median is None:
        return 0
    med = pct([r["seg"]["合计"] for r in rows], .5)
    if med > args.max_median:
        print(f"❌ 合计中位 {med:.2f} s 超过 {args.max_median:g} s")
        return 1
    print(f"✅ 合计中位 {med:.2f} s ≤ {args.max_median:g} s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
