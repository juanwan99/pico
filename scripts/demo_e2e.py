#!/usr/bin/env python3
"""Phase 1 demo script — S4 → multi-step → artifact → cross-school → confirm."""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
try:
    from dotenv import load_dotenv

    load_dotenv(ROOT / ".env")
except ImportError:
    pass

BASE = os.environ.get("PICO_DEMO_BASE", "http://127.0.0.1:8000")


def req(method: str, path: str, body: dict | None = None, token: str | None = None):
    data = None if body is None else json.dumps(body).encode()
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    r = urllib.request.Request(f"{BASE}{path}", data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(r, timeout=120) as resp:
            return json.load(resp)
    except urllib.error.HTTPError as e:
        detail = e.read().decode()
        raise SystemExit(f"HTTP {e.code} {path}: {detail}") from e


def main() -> int:
    health = req("GET", "/health")
    print("health", health)

    safety = req("GET", "/v1/meta/agent-safety")
    assert safety["proof"]["dangerous_off"], safety
    print("safety OK")

    tok = req(
        "POST",
        "/v1/dev/token",
        {"school_id": "school-a", "membership_id": "demo-1"},
    )["access_token"]
    print("S4 token OK")

    created = req(
        "POST",
        "/v1/tasks",
        {
            "title": "demo classes",
            "prompt": "请调用工具列出我学校的班级，并一句话总结。",
        },
        tok,
    )
    run_id = created["run"]["id"]
    task_id = created["task"]["id"]
    print("run", run_id)

    status = "queued"
    for _ in range(90):
        time.sleep(1)
        status = req("GET", f"/v1/runs/{run_id}", token=tok)["run"]["status"]
        if status in ("succeeded", "failed", "cancelled"):
            break
    print("status", status)
    if status != "succeeded":
        ev = req("GET", f"/v1/runs/{run_id}/events", token=tok)["events"]
        print(json.dumps(ev, ensure_ascii=False, indent=2))
        return 1

    events = req("GET", f"/v1/runs/{run_id}/events", token=tok)["events"]
    types = [e["type"] for e in events]
    print("events", types)
    assert "tool.call" in types or "message.delta" in types

    arts = req("GET", f"/v1/tasks/{task_id}", token=tok)["artifacts"]
    print("artifacts", len(arts))

    cross = req("POST", "/v1/demo/cross-school-deny", {}, tok)
    assert cross["denied"] is True
    assert any(e["type"] == "auth.deny" for e in cross["events"])
    print("cross-school deny OK")

    ch = req(
        "POST",
        "/v1/changes",
        {"title": "demo change", "summary": "audit only", "payload": {"k": 1}},
        tok,
    )
    conf = req("POST", f"/v1/changes/{ch['change']['id']}/confirm", {}, tok)
    assert conf["change"]["status"] == "confirmed"
    print("S7 confirm OK")
    print("DEMO_OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
