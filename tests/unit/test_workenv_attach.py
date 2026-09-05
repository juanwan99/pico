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

from typing import Any

from pico_orchestrator.run_types import RunCaps
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


async def _not_cancelled() -> bool:
    return False


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


@pytest.mark.asyncio
async def test_create_task_keeps_conversation_id(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from app import db as db_mod
    from app.auth import Principal as AuthPrincipal
    from app.db import init_db
    from app.run_service import create_task

    db_path = tmp_path / "pico.db"
    monkeypatch.setenv("PICO_DATABASE_URL", f"sqlite+aiosqlite:///{db_path}")
    db_mod._engine = None
    db_mod._Session = None
    await init_db()
    principal = AuthPrincipal(
        school_id="school-a",
        membership_id="m1",
        scopes=["ai:run", "ai:read"],
        iss="t",
        aud="pico-api",
        exp=9999999999,
        raw={},
    )
    factory = db_mod.session_factory()
    async with factory() as session:
        task, run = await create_task(
            session,
            principal,
            "t4",
            "prompt",
            conversation_id="t4-api",
        )
        assert task.conversation_id == "t4-api"
        assert run.task_id == task.id


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
    assert (tmp_path / "session" / "pico.jsonl").is_file()
    assert not (tmp_path / "session" / "pico-t4x.jsonl").exists()


def test_sidecar_session_is_conversation_pico_jsonl(tmp_path: Path) -> None:
    import sidecar as sidecar_mod

    sidecar_mod.SESSION_ROOT = tmp_path / "session"
    sidecar_mod.SESSION_ROOT.mkdir()
    path = sidecar_mod._session_file("run-uuid-1")
    assert path == tmp_path / "session" / "pico.jsonl"
    assert sidecar_mod._session_file("run-uuid-2") == path


def test_retarget_session_cwd_rewrites_header(tmp_path: Path) -> None:
    import json

    import sidecar as sidecar_mod

    session = tmp_path / "pico.jsonl"
    old = tmp_path / "old-run"
    new = tmp_path / "new-run"
    session.write_text(
        json.dumps(
            {
                "type": "session",
                "version": 3,
                "id": "s1",
                "cwd": str(old),
            }
        )
        + "\n"
        + json.dumps({"type": "message", "id": "m1"})
        + "\n",
        encoding="utf-8",
    )
    sidecar_mod._retarget_session_cwd(session, new)
    first = json.loads(session.read_text(encoding="utf-8").splitlines()[0])
    assert first["cwd"] == str(new)
    assert first["id"] == "s1"
    second = json.loads(session.read_text(encoding="utf-8").splitlines()[1])
    assert second["type"] == "message"


@pytest.mark.asyncio
async def test_attach_prefers_prior_collect_over_fixture(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from pico_orchestrator.true_pi.runtime import _attach_workenv_fixtures
    from pico_orchestrator.true_pi.workenv_ledger import MemoryArtifactStore

    fixture = tmp_path / "fix"
    fixture.mkdir()
    fixture.joinpath("gradebook.xlsx").write_bytes(b"FIXTURE")
    monkeypatch.setenv("PICO_WORKENV_FIXTURE_DIR", str(fixture))
    store = MemoryArtifactStore()
    await store.write(
        Principal(), title="gradebook.xlsx", content=b"PRIOR-ROUND", kind="xlsx"
    )
    posted: list[dict] = []

    async def fake_post(path: str, payload: dict, timeout: float = 30.0) -> dict:
        del timeout
        posted.append({"path": path, "payload": payload})
        return {"ok": True}

    monkeypatch.setattr(
        "pico_orchestrator.true_pi.workenv_http.workenv_post", fake_post
    )
    await _attach_workenv_fixtures(
        "run-2", principal=Principal(), artifact_store=store
    )
    files = posted[0]["payload"]["files"]
    names = [f["name"] for f in files]
    assert names.count("gradebook.xlsx") == 1
    import base64

    raw = base64.b64decode(files[0]["bytes_b64"])
    assert raw == b"PRIOR-ROUND"


def test_provider_error_blocks_success_only_without_collect() -> None:
    from pico_orchestrator.true_pi.runtime import provider_error_blocks_success

    assert provider_error_blocks_success("没有可用token", collected_n=0) is True
    assert provider_error_blocks_success("没有可用token", collected_n=1) is False
    assert provider_error_blocks_success("", collected_n=0) is False


@pytest.mark.asyncio
async def test_collect_keeps_modified_xlsx_skips_fixture(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import base64
    import hashlib

    from pico_orchestrator.true_pi.runtime import _collect_workenv_into_store

    fixture = tmp_path / "fix"
    fixture.mkdir()
    frozen = b"PK\x03\x04FIXTURE-BYTES"
    fixture.joinpath("gradebook.xlsx").write_bytes(frozen)
    monkeypatch.setenv("PICO_WORKENV_FIXTURE_DIR", str(fixture))
    xlsx = ROOT / "testdata" / "workenv" / "gradebook.xlsx"
    changed = xlsx.read_bytes()
    assert hashlib.sha256(changed).hexdigest() != hashlib.sha256(frozen).hexdigest()
    posted: list[str] = []

    async def fake_post(path: str, payload: dict, timeout: float = 30.0) -> dict:
        del payload, timeout
        posted.append(path)
        return {
            "ok": True,
            "files": [
                {
                    "name": "gradebook.xlsx",
                    "bytes_b64": base64.b64encode(changed).decode("ascii"),
                }
            ],
        }

    monkeypatch.setattr("pico_orchestrator.true_pi.workenv_http.workenv_post", fake_post)
    store = MemoryArtifactStore()
    n = await _collect_workenv_into_store(
        workspace_id="run-1",
        principal=Principal(),
        store=store,
        gate=WorkenvCancelGate(),
    )
    assert n == 1
    assert store.rows[0]["title"] == "gradebook.xlsx"
    assert posted == ["/v1/internal/workenv/collect"]


@pytest.mark.asyncio
async def test_overlay_lands_collect_despite_token_phrase(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import base64

    from pico_orchestrator.true_pi.client import FakeTransport
    from pico_orchestrator.true_pi.runtime import run_true_pi_agent

    monkeypatch.setattr(
        "pico_orchestrator.true_pi.runtime.AttachTransport", FakeTransport
    )
    monkeypatch.delenv("PICO_WORKENV_FIXTURE_DIR", raising=False)
    xlsx = (ROOT / "testdata" / "workenv" / "gradebook.xlsx").read_bytes()

    async def fake_post(path: str, payload: dict, timeout: float = 30.0) -> dict:
        del payload, timeout
        if str(path).endswith("/collect"):
            return {
                "ok": True,
                "files": [
                    {
                        "name": "gradebook.xlsx",
                        "bytes_b64": base64.b64encode(xlsx).decode("ascii"),
                    }
                ],
            }
        return {"ok": True, "destroyed": True}

    monkeypatch.setattr("pico_orchestrator.true_pi.workenv_http.workenv_post", fake_post)
    store = MemoryArtifactStore()
    events: list[tuple[str, dict[str, Any]]] = []

    async def emit(kind: str, payload: dict[str, Any]) -> None:
        events.append((kind, payload))

    transport = FakeTransport(
        scripted=[
            {"type": "agent_start"},
            {"type": "turn_start"},
            {
                "type": "tool_execution_start",
                "toolName": "bash",
                "toolCallId": "c1",
                "args": {"command": "python save xlsx"},
            },
            {
                "type": "tool_execution_end",
                "toolName": "bash",
                "toolCallId": "c1",
                "isError": False,
                "result": {"content": [{"type": "text", "text": "saved"}]},
            },
            {
                "type": "message_end",
                "message": {
                    "role": "assistant",
                    "content": [],
                    "stopReason": "error",
                    "errorMessage": "没有可用token",
                },
            },
            {"type": "agent_end", "willRetry": False},
        ],
        assistant_text="",
    )
    result = await run_true_pi_agent(
        prompt="把 D2:D7 写成公式",
        principal=Principal(),
        emit=emit,
        is_cancelled=_not_cancelled,
        caps=RunCaps(min_artifacts=0, max_seconds=8),
        transport=transport,
        artifact_store=store,
        run_id="t1-token-phrase",
    )
    assert result.status == "succeeded"
    assert store.rows and store.rows[0]["title"] == "gradebook.xlsx"
    assert "failed" not in [p.get("status") for k, p in events if k == "run.status"]
