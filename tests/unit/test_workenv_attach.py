"""Workenv AttachTransport + cancel ledger. Experiment branch only; do not merge."""

from __future__ import annotations

import os
import socket
import sys
import threading
import time
from dataclasses import dataclass
from http.server import ThreadingHTTPServer
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "api"))
sys.path.insert(0, str(ROOT / "services" / "orchestrator"))
sys.path.insert(0, str(ROOT / "services" / "workenv_sidecar"))

from pico_orchestrator.true_pi.client import TruePiRpcClient
from pico_orchestrator.true_pi.workenv_attach import AttachTransport
from pico_orchestrator.true_pi.workenv_ledger import (
    MemoryArtifactStore,
    WorkenvCancelGate,
    WorkenvCollectRejected,
)


@dataclass
class Principal:
    school_id: str = "school-a"
    membership_id: str = "member-a"
    scopes: list[str] | None = None


def test_workenv_pi_hides_list_l(monkeypatch: pytest.MonkeyPatch) -> None:
    from pico_orchestrator.capability_loading import (
        CORE_VISIBLE_TOOLS,
        WORKENV_HIDDEN_L,
        resolve_visible_tools,
    )

    monkeypatch.delenv("PICO_WORKENV", raising=False)
    core = resolve_visible_tools(None)
    assert "generate_xlsx_document" in core
    monkeypatch.setenv("PICO_WORKENV", "pi")
    hidden = resolve_visible_tools(None)
    assert not (set(hidden) & WORKENV_HIDDEN_L)
    expected = [n for n in CORE_VISIBLE_TOOLS if n not in WORKENV_HIDDEN_L]
    assert hidden == expected


def test_collect_after_cancel_discards_bytes() -> None:
    gate = WorkenvCancelGate()
    store = MemoryArtifactStore()
    gate.begin_cancel()
    with pytest.raises(WorkenvCollectRejected):
        import asyncio

        asyncio.run(
            gate.ingest_collect(
                Principal(),
                store,
                [{"name": "out.xlsx", "bytes": b"PK\x03\x04fake"}],
            )
        )
    assert store.rows == []
    gate.finish_cancel()
    assert gate.status == "cancelled"


@pytest.mark.asyncio
async def test_collect_valid_xlsx_writes_row(tmp_path: Path) -> None:
    from pico_orchestrator.artifact_types import is_valid_ooxml_package

    xlsx = ROOT / "testdata" / "workenv" / "gradebook.xlsx"
    raw = xlsx.read_bytes()
    assert is_valid_ooxml_package(raw, ".xlsx")
    gate = WorkenvCancelGate()
    store = MemoryArtifactStore()
    rows = await gate.ingest_collect(Principal(), store, [{"name": "gradebook.xlsx", "bytes": raw}])
    assert len(rows) == 1
    assert store.rows[0]["title"] == "gradebook.xlsx"


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _start_sidecar(tmp_path: Path, *, pi_bin: str, token: str) -> tuple[ThreadingHTTPServer, int]:
    os.environ["PICO_SANDBOX_TOKEN"] = token
    os.environ["PICO_WORKENV_WORK"] = str(tmp_path / "work")
    os.environ["PICO_WORKENV_SESSION"] = str(tmp_path / "session")
    os.environ["PI_CODING_AGENT_DIR"] = str(tmp_path / "agent-home")
    os.environ["PICO_TRUE_PI_BIN"] = pi_bin
    os.environ["PICO_MODEL"] = "gpt-5.6-sol"
    import sidecar as sidecar_mod

    sidecar_mod.TOKEN = token
    sidecar_mod.WORK_ROOT = tmp_path / "work"
    sidecar_mod.SESSION_ROOT = tmp_path / "session"
    sidecar_mod.AGENT_HOME = tmp_path / "agent-home"
    sidecar_mod.PI_BIN = pi_bin
    sidecar_mod._state["runs"] = {}
    sidecar_mod._state["conversation_key"] = None
    sidecar_mod.write_agent_home()
    port = _free_port()
    httpd = ThreadingHTTPServer(("127.0.0.1", port), sidecar_mod.Handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    deadline = time.time() + 2
    while time.time() < deadline:
        with socket.socket() as sock:
            if sock.connect_ex(("127.0.0.1", port)) == 0:
                break
        time.sleep(0.02)
    return httpd, port


def _write_fake_pi(tmp_path: Path) -> Path:
    path = tmp_path / "fake-pi"
    path.write_text(
        "#!/usr/bin/env python3\n"
        "import os\n"
        "os.environ['PYTHONUNBUFFERED']='1'\n"
        "import json, sys\n"
        "line = sys.stdin.readline()\n"
        "obj = json.loads(line)\n"
        "rid = obj.get('id')\n"
        "print(json.dumps({'type':'response','command':'prompt','id':rid,'success':True}), flush=True)\n"
        "print(json.dumps({'type':'agent_start'}), flush=True)\n"
        "print(json.dumps({'type':'turn_start'}), flush=True)\n"
        "print(json.dumps({'type':'tool_execution_start','toolName':'bash','toolCallId':'c1','args':{'command':'sleep 9'}}), flush=True)\n"
        "for raw in sys.stdin:\n"
        "    msg = json.loads(raw)\n"
        "    if msg.get('type') == 'abort':\n"
        "        print(json.dumps({'type':'response','command':'abort','id':msg.get('id'),'success':True}), flush=True)\n"
        "        print(json.dumps({'type':'tool_execution_end','toolName':'bash','toolCallId':'c1','isError':True,'result':{'content':[{'type':'text','text':'Command aborted'}]}}), flush=True)\n"
        "        print(json.dumps({'type':'agent_end','willRetry':False}), flush=True)\n"
        "        break\n",
        encoding="utf-8",
    )
    path.chmod(0o755)
    return path


@pytest.mark.asyncio
async def test_attach_transport_abort_on_first_tool(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    token = "tok-test"
    fake = _write_fake_pi(tmp_path)
    httpd, port = _start_sidecar(tmp_path, pi_bin=str(fake), token=token)
    monkeypatch.setenv("PICO_SANDBOX_TOKEN", token)
    monkeypatch.setenv("PICO_WORKENV_HTTP_URL", f"http://127.0.0.1:{port}")
    monkeypatch.setenv(
        "PICO_WORKENV_ATTACH_URL",
        f"ws://127.0.0.1:{port}/v1/internal/workenv/attach-rpc",
    )
    from pico_orchestrator.true_pi.workenv_http import workenv_post

    created = await workenv_post(
        "/v1/internal/workenv/create",
        {"workspace_id": "t4x", "run_id": "t4x", "conversation_id": "c1", "mode": "pi"},
    )
    assert created["ok"] is True
    transport = AttachTransport(run_id="t4x", box_id=str(created.get("box_id") or "box-1"))
    client = TruePiRpcClient(transport)
    await client.start()
    await client.prompt("write formulas", req_id="p-test")
    seen: list[str] = []
    abort_ack = False
    async for event in client.events():
        seen.append(event.type)
        if event.type == "tool_execution_start":
            await client.abort()
            abort_ack = True
        if event.type == "agent_end":
            break
    await client.close()
    httpd.shutdown()
    assert "tool_execution_start" in seen
    assert abort_ack
    assert "agent_end" in seen or "tool_execution_end" in seen
