#!/usr/bin/env python3
"""T4 product-shaped cancel on isolated overlay. Do not run against live ECS nft."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
from pathlib import Path
from typing import Any

from pico_orchestrator.true_pi.client import TruePiRpcClient
from pico_orchestrator.true_pi.workenv_attach import AttachTransport
from pico_orchestrator.true_pi.workenv_http import decode_collect_files, workenv_post
from pico_orchestrator.true_pi.workenv_ledger import (
    MemoryArtifactStore,
    WorkenvCancelGate,
    WorkenvCollectRejected,
)


class Principal:
    school_id = "school-poc"
    membership_id = "member-poc"
    scopes: tuple[str, ...] = ()


PROMPT = "把 D2:D7 写成期末40%加平时60%的公式，保存为 xlsx。"


async def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace", default="t4api")
    parser.add_argument("--fixture", default="testdata/workenv/gradebook.xlsx")
    parser.add_argument("--out", default="/tmp/workenv-poc/t4api-report.json")
    args = parser.parse_args()
    workspace = args.workspace
    fixture = Path(args.fixture)
    raw = fixture.read_bytes()
    gate = WorkenvCancelGate()
    store = MemoryArtifactStore()
    events: list[dict[str, Any]] = []

    created = await workenv_post(
        "/v1/internal/workenv/create",
        {
            "workspace_id": workspace,
            "run_id": workspace,
            "conversation_id": "t4-api",
            "mode": "pi",
        },
    )
    import base64

    await workenv_post(
        "/v1/internal/workenv/attach",
        {
            "workspace_id": workspace,
            "files": [{"name": fixture.name, "bytes_b64": base64.b64encode(raw).decode("ascii")}],
        },
    )
    transport = AttachTransport(run_id=workspace, box_id=str(created.get("box_id") or "box-1"))
    client = TruePiRpcClient(transport)
    await client.start()
    await client.prompt(PROMPT)
    abort_sent = False
    first_tool = None
    try:
        async for event in client.events():
            kind = event.type
            slim = {"type": kind, "toolName": event.raw.get("toolName")}
            events.append(slim)
            if kind == "tool_execution_start" and not abort_sent:
                first_tool = event.raw.get("toolName")
                gate.begin_cancel()
                await client.abort()
                abort_sent = True
            if kind in {"agent_end", "agent_settled"}:
                break
    finally:
        await client.close(kill=True)

    collect_error = None
    artifacts: list[Any] = []
    try:
        collected = await workenv_post(
            "/v1/internal/workenv/collect",
            {"workspace_id": workspace, "glob": ["*.xlsx", "*.docx", "*.pptx", "*.html"]},
        )
        files = decode_collect_files(collected)
        artifacts = await gate.ingest_collect(Principal(), store, files)
    except WorkenvCollectRejected as exc:
        collect_error = str(exc)
    except Exception as exc:  # noqa: BLE001
        collect_error = f"{type(exc).__name__}:{exc}"

    destroyed = await workenv_post(
        "/v1/internal/workenv/destroy-run",
        {"workspace_id": workspace},
        timeout=15.0,
    )
    if destroyed.get("ok"):
        gate.finish_cancel()
    else:
        gate.fail_destroy()

    report = {
        "abort_sent": abort_sent,
        "first_tool": first_tool,
        "events": events[:40],
        "collect_error": collect_error,
        "artifacts": artifacts,
        "ledger_status": gate.status,
        "store_rows": store.rows,
        "destroyed": destroyed,
    }
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: report[k] for k in ("abort_sent", "first_tool", "collect_error", "ledger_status", "store_rows", "destroyed")}, ensure_ascii=False))
    return 0 if abort_sent and gate.status == "cancelled" and not store.rows else 1


if __name__ == "__main__":
    os.environ.setdefault("PICO_WORKENV_ATTACH_URL", "ws://127.0.0.1:18768/v1/internal/workenv/attach-rpc")
    os.environ.setdefault("PICO_WORKENV_HTTP_URL", "http://127.0.0.1:18768")
    raise SystemExit(asyncio.run(main()))
