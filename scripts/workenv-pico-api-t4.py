#!/usr/bin/env python3
"""T4 against isolated pico-api (PICO_WORKENV=pi). Never live 18765."""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

PROMPT = "把 D2:D7 写成期末40%加平时60%的公式，保存为 xlsx。"


def _req(method: str, url: str, token: str | None, body: dict[str, Any] | None = None) -> tuple[int, Any]:
    data = None if body is None else json.dumps(body).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read().decode("utf-8")
            return int(resp.status), json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        try:
            parsed: Any = json.loads(raw) if raw else {}
        except json.JSONDecodeError:
            parsed = {"raw": raw[:400]}
        return int(exc.code), parsed


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", default="http://127.0.0.1:18775")
    parser.add_argument("--out", default="/tmp/workenv-poc/pico-api-t4.json")
    args = parser.parse_args()
    base = args.base.rstrip("/")

    code, health = _req("GET", base + "/health", None)
    if code != 200 or not health.get("ok"):
        print(json.dumps({"error": "health", "code": code, "body": health}, ensure_ascii=False))
        return 2
    if health.get("workenv_mode") != "pi":
        print(json.dumps({"error": "workenv_mode", "health": health}, ensure_ascii=False))
        return 2

    code, tok = _req(
        "POST",
        base + "/v1/dev/token",
        None,
        {"school_id": "school-poc", "membership_id": "member-poc"},
    )
    if code != 200:
        print(json.dumps({"error": "token", "code": code, "body": tok}, ensure_ascii=False))
        return 2
    token = str(tok.get("access_token") or "")
    hdr = token

    code, created = _req(
        "POST",
        base + "/v1/tasks",
        hdr,
        {"title": "t4-pico-api", "prompt": PROMPT},
    )
    if code != 200:
        print(json.dumps({"error": "create", "code": code, "body": created}, ensure_ascii=False))
        return 2
    run_id = str((created.get("run") or {}).get("id") or "")
    if not run_id:
        print(json.dumps({"error": "no_run", "body": created}, ensure_ascii=False))
        return 2

    abort_at_tool = False
    first_tool = None
    cancel_http = None
    deadline = time.time() + 180
    events: list[dict[str, Any]] = []
    while time.time() < deadline:
        code, body = _req("GET", f"{base}/v1/runs/{run_id}/events", hdr)
        rows = body.get("events") if isinstance(body, dict) else []
        events = rows if isinstance(rows, list) else []
        for ev in events:
            if ev.get("type") == "tool.call" and not abort_at_tool:
                first_tool = (ev.get("payload") or {}).get("tool")
                abort_at_tool = True
                cancel_http = _req("POST", f"{base}/v1/runs/{run_id}/cancel", hdr, {})
                break
        run = _req("GET", f"{base}/v1/runs/{run_id}", hdr)[1]
        status = str((run.get("run") or {}).get("status") or "")
        if abort_at_tool and status in {"cancelled", "failed", "succeeded"}:
            break
        if status in {"cancelled", "failed", "succeeded"} and abort_at_tool:
            break
        if status in {"failed", "succeeded"} and not abort_at_tool:
            break
        time.sleep(0.4)

    run = _req("GET", f"{base}/v1/runs/{run_id}", hdr)[1]
    arts = _req("GET", f"{base}/v1/artifacts", hdr)[1]
    report = {
        "health_workenv": health.get("workenv_mode"),
        "health_runtime": health.get("default_runtime"),
        "run_id": run_id,
        "first_tool": first_tool,
        "abort_at_tool": abort_at_tool,
        "cancel_http": cancel_http,
        "run": run.get("run") if isinstance(run, dict) else run,
        "artifacts": arts.get("artifacts") if isinstance(arts, dict) else arts,
        "event_types": [e.get("type") for e in events],
    }
    Path(args.out).write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({
        "run_id": run_id,
        "first_tool": first_tool,
        "abort_at_tool": abort_at_tool,
        "status": (report["run"] or {}).get("status") if isinstance(report["run"], dict) else None,
        "n_artifacts": len(report["artifacts"] or []) if isinstance(report["artifacts"], list) else None,
        "workenv": health.get("workenv_mode"),
    }, ensure_ascii=False))
    status = (report["run"] or {}).get("status") if isinstance(report["run"], dict) else ""
    n_art = len(report["artifacts"] or []) if isinstance(report["artifacts"], list) else 99
    ok = abort_at_tool and status == "cancelled" and n_art == 0
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
