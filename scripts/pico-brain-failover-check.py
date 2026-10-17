#!/usr/bin/env python3
"""pico#1336 对账：主模型坏了，备用模型接不接得住。只打一次性栈（pico-ruler-stack.sh）。

    python3 scripts/pico-brain-failover-check.py --stack fo --idx 1 --relay-dir <dir> [--n 10]

由 scripts/pico-brain-failover-check.sh 调用：它先起 scripts/pico-fault-upstream.py，再起栈
（DEEPSEEK_BASE_URL 指向假上游），跑完拆掉。三种错（502 / 429 / 密钥暂停）× 三条路
（快档 pico-fast、深档 pico-deep、直答 json_only）各发 n 次，每次核：
  - 运行 succeeded；
  - 这一轮的用量记在备用模型上（不是主模型）；
  - 老师收到的流里有正文、没有报错事件；
  - 假上游确实对主模型注入过这种错（不然这一项不算数）。
换错型前重启栈里的 pico-api，清掉上一种错留下的「主模型暂时下线」记忆。
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import subprocess
import sys
import time
import urllib.request
import uuid
from pathlib import Path

MODES = ("502", "429", "suspended")
LANES = {
    "fast": ("pico-fast", {}, "用一句话说明什么是质数。"),
    "deep": ("pico-deep", {}, "用一句话说明什么是质数。"),
    "direct": ("pico-fast", {"X-Pico-Output": "json_only_no_files"},
               '只回 JSON：{"answer": "<用一句话说明什么是质数>"}'),
}
MEMBERSHIP = "regress-school:ruler"


def chat(base: str, key: str, model: str, extra: dict, text: str, cid: str) -> tuple[str, list[str]]:
    body = json.dumps({"model": model, "stream": True,
                       "messages": [{"role": "user", "content": text}]}).encode()
    req = urllib.request.Request(f"{base}/v1/chat/completions", data=body, method="POST", headers={
        "Authorization": f"Bearer {key}", "X-Pico-Membership-Id": MEMBERSHIP,
        "X-Conversation-Id": cid, "Content-Type": "application/json", **extra})
    content, errors = [], []
    with urllib.request.urlopen(req, timeout=600) as resp:  # local throwaway stack
        for raw in resp:
            line = raw.decode("utf-8", "replace").strip()
            if not line.startswith("data:") or line == "data: [DONE]":
                continue
            try:
                ev = json.loads(line[5:])
            except ValueError:
                continue
            if ev.get("error"):
                errors.append(json.dumps(ev["error"], ensure_ascii=False)[:160])
            for ch in ev.get("choices") or []:
                content.append(str((ch.get("delta") or {}).get("content") or ""))
    return "".join(content), errors


def run_of(db: str, cid: str) -> tuple[str, str, list[str]]:
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    row = con.execute("select r.id, r.status, coalesce(r.error,'') from runs r join tasks t on t.id=r.task_id "
                      "where t.conversation_id=? order by r.created_at desc limit 1", (cid,)).fetchone()
    if not row:
        return "", "missing", []
    models = [m for (m,) in con.execute(
        "select model from usage_events where run_id=? and kind='llm'", (row[0],)) if m]
    return row[1], row[2][:120], models


def injected(log: Path, since: float, mode: str) -> int:
    if not log.exists():
        return 0
    n = 0
    for line in log.read_text(encoding="utf-8").splitlines():
        row = json.loads(line)
        if row["t"] >= since and row["action"] == f"inject_{mode}":
            n += 1
    return n


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--stack", required=True)
    ap.add_argument("--idx", type=int, default=1)
    ap.add_argument("--root", default=str(Path.home() / "pico-ruler"))
    ap.add_argument("--relay-dir", required=True)
    ap.add_argument("--head", default="")
    ap.add_argument("--n", type=int, default=10)
    ap.add_argument("--modes", default=",".join(MODES))
    ap.add_argument("--lanes", default=",".join(LANES))
    args = ap.parse_args()

    d = Path(args.root) / args.stack
    env = dict(line.split("=", 1) for line in (d / "api.env").read_text().splitlines() if "=" in line)
    key, head = env.get("PICO_OPENAI_PROXY_KEY", ""), args.head or env.get("DEEPSEEK_MODEL", "")
    base, db = f"http://127.0.0.1:{18800 + args.idx * 10}", str(d / "data" / "pico.db")
    relay = Path(args.relay_dir)
    print(f"主模型 {head} · 备用 {env.get('PICO_BRAIN_FALLBACKS', '')} · 每格 {args.n} 次")
    bad_total = 0
    for mode in args.modes.split(","):
        subprocess.run(["docker", "restart", f"ruler-{args.stack}-api"], check=True, capture_output=True)
        for _ in range(60):
            try:
                urllib.request.urlopen(f"{base}/health", timeout=3)
                break
            except OSError:
                time.sleep(2)
        (relay / "fault.json").write_text(json.dumps({"mode": mode, "head": head}), encoding="utf-8")
        for lane in args.lanes.split(","):
            model, extra, text = LANES[lane]
            since, ok, misses = time.time(), 0, []
            for i in range(args.n):
                cid = f"fo-{mode}-{lane}-{i}-{uuid.uuid4().hex[:6]}"
                try:
                    content, errors = chat(base, key, model, extra, text, cid)
                except OSError as exc:
                    content, errors = "", [f"http {type(exc).__name__}: {exc}"[:160]]
                status, error, models = run_of(db, cid)
                on_backup = bool(models) and all(m.split("/")[-1] != head for m in models)
                good = status == "succeeded" and on_backup and content.strip() and not errors
                if good:
                    ok += 1
                else:
                    misses.append(f"#{i} status={status} models={models} errors={errors[:1]} {error}")
            hit = injected(relay / "fault.jsonl", since, mode)
            mark = "✅" if ok == args.n and hit else "❌"
            bad_total += 0 if mark == "✅" else 1
            print(f"{mark} {mode:9s} × {lane:6s}：{ok}/{args.n} 在备用模型上做完 · 主模型被注入 {hit} 次")
            for m in misses[:3]:
                print(f"     {m}")
    (relay / "fault.json").write_text(json.dumps({"mode": "off"}), encoding="utf-8")
    print("—— 全部 ✅" if not bad_total else f"—— {bad_total} 格 ❌")
    return 0 if not bad_total else 1


if __name__ == "__main__":
    sys.exit(main())
