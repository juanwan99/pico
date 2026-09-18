#!/usr/bin/env python3
"""Compose this week's ima numbers for #1005. Not CI. Not a second ledger.

  python3 scripts/ima-week-line.py \\
    --kb-eval /tmp/kb-eval.json \\
    --office-regress /tmp/office.json \\
    --failure-rate /tmp/fail.json
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def _load(path: Path | None) -> dict[str, Any] | None:
    if path is None:
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def kb_line(data: dict[str, Any] | None) -> str:
    if not data:
        return "kb-eval：未跑"
    overall = data.get("overall") if isinstance(data.get("overall"), dict) else data
    file5 = overall.get("file@5")
    p95 = overall.get("p95_ms")
    n = overall.get("n")
    return f"kb-eval held-out：n={n} file@5={file5} p95={p95}ms"


def office_line(data: dict[str, Any] | None) -> str:
    if not data:
        return "office-regress：未跑"
    results = data.get("results") if isinstance(data.get("results"), list) else []
    ok = sum(1 for r in results if isinstance(r, dict) and r.get("ok"))
    return f"office-regress：{ok}/{len(results)} 绿" + ("（全绿）" if data.get("pass") else "")


def fail_line(data: dict[str, Any] | None) -> str:
    if not data:
        return "teacher-failure-rate：未跑"
    windows = data.get("windows") if isinstance(data.get("windows"), list) else []
    w24 = next((w for w in windows if w.get("hours") == 24), windows[0] if windows else None)
    if not isinstance(w24, dict):
        return "teacher-failure-rate：无窗口"
    rate = float(w24.get("fail_rate") or 0) * 100
    buckets = w24.get("fail_buckets") if isinstance(w24.get("fail_buckets"), dict) else {}
    top = ", ".join(f"{k} {v}" for k, v in list(buckets.items())[:4]) or "—"
    return f"teacher-failure-rate 24h：{w24.get('runs')} 轮 · {rate:.1f}% · {top}"


def render(kb: dict[str, Any] | None, office: dict[str, Any] | None, fail: dict[str, Any] | None) -> str:
    return "\n".join(
        [
            "本周持续线（#1005 / #1052 T4）",
            "",
            f"- {kb_line(kb)}",
            f"- {office_line(office)}",
            f"- {fail_line(fail)}",
        ]
    )


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--kb-eval", type=Path)
    ap.add_argument("--office-regress", type=Path)
    ap.add_argument("--failure-rate", type=Path)
    args = ap.parse_args()
    print(
        render(
            _load(args.kb_eval),
            _load(args.office_regress),
            _load(args.failure_rate),
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
