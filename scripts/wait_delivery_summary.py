#!/usr/bin/env python3
"""H4: poll run terminal status + delivery.summary (prefer over stream timeout).

Usage:
  PICO_BASE=http://127.0.0.1:18765 \\
  PICO_TOKEN=<jwt> \\
  python scripts/wait_delivery_summary.py <run_id>

Exit codes:
  0  terminal + summary ok (or summary absent but status succeeded and min_required=0)
  1  terminal failed / delivery.summary ok=false
  2  usage / network / timeout
"""

from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.request


def _req(base: str, path: str, token: str | None, timeout: float = 30.0) -> dict:
    headers = {"Accept": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(f"{base.rstrip('/')}{path}", headers=headers)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.load(resp)


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print("usage: wait_delivery_summary.py <run_id>", file=sys.stderr)
        return 2
    run_id = argv[1].strip()
    base = os.environ.get("PICO_BASE", "http://127.0.0.1:18765")
    token = os.environ.get("PICO_TOKEN") or os.environ.get("PICO_DEMO_TOKEN")
    max_wait = int(os.environ.get("PICO_WAIT_SECONDS", "180"))
    poll = float(os.environ.get("PICO_POLL_SECONDS", "2"))

    deadline = time.time() + max_wait
    status = "unknown"
    while time.time() < deadline:
        try:
            body = _req(base, f"/v1/runs/{run_id}", token)
        except urllib.error.HTTPError as exc:
            print(f"HTTP {exc.code} GET /v1/runs/{run_id}", file=sys.stderr)
            return 2
        except Exception as exc:  # noqa: BLE001 — surface probe errors
            print(f"network: {exc}", file=sys.stderr)
            return 2
        run = body.get("run") if isinstance(body, dict) else None
        if not isinstance(run, dict):
            run = body if isinstance(body, dict) else {}
        status = str(run.get("status") or "unknown")
        if status in ("succeeded", "failed", "cancelled"):
            break
        time.sleep(poll)
    else:
        print(f"timeout status={status} after {max_wait}s", file=sys.stderr)
        return 2

    try:
        events_body = _req(base, f"/v1/runs/{run_id}/events", token)
    except Exception as exc:  # noqa: BLE001
        print(f"events fetch failed: {exc}", file=sys.stderr)
        return 2
    events = events_body.get("events") if isinstance(events_body, dict) else events_body
    if not isinstance(events, list):
        events = []

    summary = None
    for ev in reversed(events):
        if not isinstance(ev, dict):
            continue
        et = ev.get("type") or ev.get("event_type")
        if et == "delivery.summary":
            summary = ev.get("payload") or ev.get("data") or ev
            break

    out = {
        "run_id": run_id,
        "status": status,
        "delivery_summary": summary,
        "human_titles": (summary or {}).get("human_titles")
        or (summary or {}).get("titles"),
        "ok": None,
    }
    if isinstance(summary, dict) and "ok" in summary:
        out["ok"] = bool(summary.get("ok")) and status == "succeeded"
    else:
        out["ok"] = status == "succeeded"
        out["note"] = "no delivery.summary event; fell back to run.status only"

    print(json.dumps(out, ensure_ascii=False, indent=2))
    if status != "succeeded":
        return 1
    if isinstance(summary, dict) and summary.get("ok") is False:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
