#!/usr/bin/env python3
"""Loopback chat concurrency probe (#1003 T-FOUNDATION-S3).

Not CI. Hits pico-api with a synthetic proxy tenant and a one-word prompt.
Never prints tokens, prompts, or response bodies — only status / latency / codes.

On the ECS after (or before) changing PICO_CHAT_MAX_CONCURRENT:

  set -a && . /opt/pico/.env && set +a
  python3 scripts/teacher-concurrency-probe.py --base http://127.0.0.1:18765

Exit 0 always when the HTTP fan-out completed (the Issue owns PASS/FAIL).
Exit 2 on local setup errors (missing key, unreachable health).
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

import httpx

SHORT_PROMPT = "只回复一个字：好。不要用工具。"


def _proxy_key() -> str:
    key = (os.environ.get("PICO_OPENAI_PROXY_KEY") or "").strip()
    if len(key) < 32:
        raise SystemExit("missing PICO_OPENAI_PROXY_KEY (load /opt/pico/.env)")
    return key


def _headers(key: str, membership: str, conversation_id: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {key}",
        "X-Pico-Membership-Id": membership,
        "X-Conversation-Id": conversation_id,
        "Accept": "text/event-stream",
    }


def one_chat(
    *,
    base: str,
    key: str,
    membership: str,
    model: str,
    timeout_s: float,
    label: str,
) -> dict[str, Any]:
    conv = f"s3probe-{uuid.uuid4()}"
    started = time.perf_counter()
    status = 0
    code = ""
    bytes_out = 0
    err = ""
    try:
        with httpx.Client(
            timeout=httpx.Timeout(timeout_s, connect=10.0), trust_env=False
        ) as client:
            with client.stream(
                "POST",
                f"{base.rstrip('/')}/v1/chat/completions",
                headers=_headers(key, membership, conv),
                json={
                    "model": model,
                    "stream": True,
                    "messages": [{"role": "user", "content": SHORT_PROMPT}],
                },
            ) as resp:
                status = resp.status_code
                if status == 429:
                    try:
                        body = json.loads(resp.read().decode("utf-8", "replace"))
                    except Exception:
                        body = {}
                    detail = body.get("detail") or {}
                    if isinstance(detail, dict):
                        code = str(detail.get("code") or "")
                    else:
                        code = "http_429"
                else:
                    for chunk in resp.iter_bytes():
                        bytes_out += len(chunk)
    except httpx.HTTPError as exc:
        err = type(exc).__name__
        status = status or 0
    wall_s = round(time.perf_counter() - started, 3)
    return {
        "label": label,
        "status": status,
        "code": code,
        "wall_s": wall_s,
        "bytes": bytes_out,
        "err": err,
        "ok": status == 200 and not err,
        "busy": status == 429 and code == "concurrency_limit",
        "rpm": status == 429 and code == "rate_limit",
    }


def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    walls = [r["wall_s"] for r in rows if r["ok"]]
    return {
        "n": len(rows),
        "ok": sum(1 for r in rows if r["ok"]),
        "busy_429": sum(1 for r in rows if r["busy"]),
        "rpm_429": sum(1 for r in rows if r["rpm"]),
        "other_fail": sum(1 for r in rows if not r["ok"] and not r["busy"] and not r["rpm"]),
        "p50_s": round(statistics.median(walls), 3) if walls else None,
        "p95_s": round(_percentile(walls, 0.95), 3) if walls else None,
        "max_s": round(max(walls), 3) if walls else None,
        "rows": [
            {
                "label": r["label"],
                "status": r["status"],
                "code": r["code"],
                "wall_s": r["wall_s"],
                "ok": r["ok"],
                "err": r["err"],
            }
            for r in rows
        ],
    }


def _percentile(values: list[float], q: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    idx = min(len(ordered) - 1, max(0, int(round(q * (len(ordered) - 1)))))
    return ordered[idx]


def render_markdown(title: str, summary: dict[str, Any], cap: int | None) -> str:
    lines = [
        f"### {title}",
        "",
        f"- cap (health) = `{cap}`" if cap is not None else "- cap (health) = unknown",
        f"- n={summary['n']} ok={summary['ok']} busy_429={summary['busy_429']} "
        f"rpm_429={summary['rpm_429']} other_fail={summary['other_fail']}",
        f"- ok p50={summary['p50_s']}s p95={summary['p95_s']}s max={summary['max_s']}s",
        "",
        "| label | status | code | wall_s | ok |",
        "|---|---|---|---|---|",
    ]
    for row in summary["rows"]:
        lines.append(
            f"| {row['label']} | {row['status']} | {row['code'] or '—'} | "
            f"{row['wall_s']} | {row['ok']} |"
        )
    return "\n".join(lines) + "\n"


def _health(base: str) -> dict[str, Any]:
    try:
        resp = httpx.get(f"{base.rstrip('/')}/health", timeout=5.0, trust_env=False)
        resp.raise_for_status()
        return resp.json()
    except httpx.HTTPError as exc:
        raise SystemExit(f"health unreachable: {type(exc).__name__}") from exc


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", default="http://127.0.0.1:18765")
    parser.add_argument("--model", default=os.environ.get("PICO_ALLOWED_MODELS", "pico-fast").split(",")[0])
    parser.add_argument("--timeout", type=float, default=180.0)
    parser.add_argument("--teachers", type=int, default=8)
    parser.add_argument("--same-n", type=int, default=4, dest="same_n")
    parser.add_argument("--skip-multi", action="store_true")
    parser.add_argument("--skip-same", action="store_true")
    args = parser.parse_args()

    health = _health(args.base)
    cap = int((health.get("rate_limit") or {}).get("chat_max_concurrent") or 0)
    key = _proxy_key()
    stamp = time.strftime("%Y%m%dT%H%M%S")
    school = f"s3probe-{stamp}"

    report: dict[str, Any] = {
        "git_sha": health.get("git_sha"),
        "inflight_before": health.get("inflight_runs"),
        "chat_max_concurrent": cap,
        "model": args.model,
    }

    def fanout(jobs: list[tuple[str, str]]) -> list[dict[str, Any]]:
        barrier = threading.Barrier(len(jobs), timeout=30)
        rows: list[dict[str, Any]] = []

        def run(label: str, membership: str) -> dict[str, Any]:
            barrier.wait()
            return one_chat(
                base=args.base,
                key=key,
                membership=membership,
                model=args.model,
                timeout_s=args.timeout,
                label=label,
            )

        with ThreadPoolExecutor(max_workers=len(jobs)) as pool:
            futs = [pool.submit(run, label, mid) for label, mid in jobs]
            for fut in as_completed(futs):
                rows.append(fut.result())
        rows.sort(key=lambda r: r["label"])
        return rows

    md_parts: list[str] = [
        f"## T1/T2 concurrency probe `{stamp}`",
        "",
        f"- tip `{report['git_sha']}` · health cap `{cap}` · model `{args.model}`",
        "",
    ]

    if not args.skip_multi:
        jobs = [
            (f"t{i:02d}", f"{school}:teacher-{i:02d}")
            for i in range(1, args.teachers + 1)
        ]
        multi = summarize(fanout(jobs))
        report["multi_teachers"] = {k: v for k, v in multi.items() if k != "rows"}
        report["multi_teachers_rows"] = multi["rows"]
        md_parts.append(render_markdown(f"{args.teachers} 个不同老师各 1 路", multi, cap))

    if not args.skip_same:
        member = f"{school}:same-teacher"
        jobs = [(f"same-{i}", member) for i in range(1, args.same_n + 1)]
        same = summarize(fanout(jobs))
        report["same_teacher"] = {k: v for k, v in same.items() if k != "rows"}
        report["same_teacher_rows"] = same["rows"]
        md_parts.append(render_markdown(f"同一老师 {args.same_n} 路并行", same, cap))

    print(json.dumps(report, ensure_ascii=False, indent=2))
    print()
    print("\n".join(md_parts))
    return 0


if __name__ == "__main__":
    sys.exit(main())
