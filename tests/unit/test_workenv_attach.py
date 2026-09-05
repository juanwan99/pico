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


def test_workenv_exec_keeps_workspace_and_exec_hides_generate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from pico_orchestrator.capability_loading import resolve_visible_tools

    monkeypatch.setenv("PICO_WORKENV", "exec")
    empty = resolve_visible_tools([])
    assert empty == []
    names = resolve_visible_tools(None)
    assert "workspace_write_file" in names
    assert "workspace_read_file" in names
    assert "workspace_list_files" in names
    assert "sandbox_workspace_exec" in names
    assert "generate_xlsx_document" not in names
    assert "sandbox_pptx_lib" not in names


@pytest.mark.asyncio
async def test_collect_rejects_remote_html() -> None:
    gate = WorkenvCancelGate()
    store = MemoryArtifactStore()
    html = b"<!doctype html><script src='https://cdn.example/x.js'></script>"
    with pytest.raises(WorkenvCollectRejected):
        await gate.ingest_collect(
            Principal(), store, [{"name": "page.html", "bytes": html}]
        )
    assert store.rows == []


def test_t12_oracles_reject_false_green() -> None:
    import importlib.util

    path = ROOT / "scripts" / "workenv-pico-api-t12.py"
    spec = importlib.util.spec_from_file_location("t12", path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    assert mod._formula_40_60("=C2*40%+B2*60%") is True
    assert mod._formula_40_60("=B2*0.6+C2*0.4") is True
    assert mod._formula_40_60("=B2*0.6+C2") is False
    assert mod._formula_40_60("=B2*40%+C2*60%") is False
    assert mod._formula_40_60("=C2*0.49+B2*0.61") is False
    assert mod._formula_40_60("=C2*40%-B2*60%") is False
    assert mod._formula_40_60("=1") is False
    assert mod._group_count("红4人 蓝3人 绿3人", "红", 4) is True
    assert mod._group_count("红 4 蓝 3 绿 3", "红", 4) is True
    assert mod._group_count("14人红 13人蓝 13人绿", "红", 4) is False
    r1 = {
        "status": "succeeded",
        "files": [{"xlsx": {"d2": "=C2*40%+B2*60%", "title": "x", "shared": [], "sheets": [], "inline": []}}],
    }
    r2_bad = {
        "status": "succeeded",
        "files": [{"xlsx": {"d2": "=B2*0.6+C2", "title": "三年二班", "shared": ["三年二班"], "sheets": [], "inline": []}}],
    }
    assert mod._t1_pass(r1, r2_bad) is False
    t2 = {
        "status": "succeeded",
        "files": [
            {"kind": "xlsx", "title": "g.xlsx", "xlsx": {"shared": ["红", "蓝", "绿"], "sheets": [], "inline": []}},
            {"kind": "docx", "title": "n.docx", "docx_text": "14人红 13人蓝 13人绿"},
        ],
    }
    assert mod._t2_pass(t2) is False
    t2_ok = {
        "status": "succeeded",
        "files": [
            {"kind": "xlsx", "title": "g.xlsx", "xlsx": {"shared": ["红4", "蓝3", "绿3"], "sheets": ["汇总"], "inline": []}},
            {"kind": "docx", "title": "n.docx", "docx_text": "红4人，蓝3人，绿3人"},
        ],
    }
    assert mod._t2_pass(t2_ok) is True
    t2_cells = {
        "status": "succeeded",
        "files": [
            {
                "kind": "xlsx",
                "title": "组别人数汇总.xlsx",
                "xlsx": {
                    "shared": [],
                    "sheets": ["组别汇总"],
                    "inline": ["按组别汇总人数", "组别", "人数", "红", "4", "蓝", "3", "绿", "3", "合计"],
                    "title": "组别汇总",
                },
            },
            {
                "kind": "docx",
                "title": "各组人数说明.docx",
                "docx_text": "组别人数红4蓝3绿3汇总：红组 4 人，蓝组 3 人，绿组 3 人",
            },
        ],
    }
    assert mod._t2_pass(t2_cells) is True


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
    sidecar_mod._state["destroyed"] = set()
    sidecar_mod._state["conversation_key"] = None
    sidecar_mod._state["owner_key"] = None
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


def test_provider_error_blocks_success_ignores_collected_n() -> None:
    from pico_orchestrator.true_pi.runtime import provider_error_blocks_success

    assert provider_error_blocks_success("没有可用token", collected_n=0) is True
    assert provider_error_blocks_success("没有可用token", collected_n=1) is True
    assert provider_error_blocks_success("", collected_n=0) is False
    assert provider_error_blocks_success("", collected_n=4) is False


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


def test_create_run_rejects_dotdot(tmp_path: Path) -> None:
    import sidecar as sidecar_mod

    sidecar_mod.WORK_ROOT = tmp_path / "work"
    sidecar_mod.WORK_ROOT.mkdir()
    sidecar_mod.AGENT_HOME = tmp_path / "agent-home"
    sidecar_mod.write_agent_home()
    sidecar_mod._state["runs"] = {}
    sidecar_mod._state["destroyed"] = set()
    sidecar_mod._state["conversation_key"] = None
    sidecar_mod._state["owner_key"] = None
    bad = sidecar_mod.create_run({"workspace_id": "../escape", "conversation_id": "c1"})
    assert bad["ok"] is False
    assert bad["error"] == "workspace_id.invalid"
    nested = sidecar_mod.create_run({"workspace_id": "a/b", "conversation_id": "c1"})
    assert nested["ok"] is False
    ok = sidecar_mod.create_run({"workspace_id": "run-ok", "conversation_id": "c1"})
    assert ok["ok"] is True
    assert (tmp_path / "work" / "run-ok").is_dir()
    assert not (tmp_path / "escape").exists()


def test_exec_python_in_work_dir(tmp_path: Path) -> None:
    import sidecar as sidecar_mod

    sidecar_mod.WORK_ROOT = tmp_path / "work"
    sidecar_mod.WORK_ROOT.mkdir()
    sidecar_mod.AGENT_HOME = tmp_path / "agent-home"
    sidecar_mod.write_agent_home()
    sidecar_mod._state["runs"] = {}
    sidecar_mod._state["destroyed"] = set()
    sidecar_mod._state["conversation_key"] = None
    sidecar_mod._state["owner_key"] = None
    created = sidecar_mod.create_run(
        {"workspace_id": "exec1", "conversation_id": "c1", "mode": "workdir"}
    )
    assert created["ok"] is True
    (tmp_path / "work" / "exec1" / "n.txt").write_text("ok\n", encoding="utf-8")
    out = sidecar_mod.exec_work(
        {
            "workspace_id": "exec1",
            "source": "from pathlib import Path\nprint(Path('n.txt').read_text())\n",
        }
    )
    assert out["ok"] is True
    assert out["executed"] is True
    assert "ok" in out["stdout"]
    listed = sidecar_mod.list_work_files({"workspace_id": "exec1"})
    names = [f["name"] for f in listed["files"]]
    assert "n.txt" in names
    read = sidecar_mod.read_work_file({"workspace_id": "exec1", "name": "n.txt"})
    assert read["ok"] is True
    assert "ok" in __import__("base64").b64decode(read["bytes_b64"]).decode()


def test_collect_skips_symlink(tmp_path: Path) -> None:
    import sidecar as sidecar_mod

    work_root = tmp_path / "work"
    work_root.mkdir()
    sidecar_mod.WORK_ROOT = work_root
    sidecar_mod.AGENT_HOME = tmp_path / "agent-home"
    sidecar_mod.write_agent_home()
    sidecar_mod._state["runs"] = {}
    sidecar_mod._state["destroyed"] = set()
    sidecar_mod._state["conversation_key"] = None
    sidecar_mod._state["owner_key"] = None
    created = sidecar_mod.create_run({"workspace_id": "r1", "conversation_id": "c1"})
    assert created["ok"] is True
    secret = tmp_path / "host-secret.xlsx"
    secret.write_bytes(b"PK\x03\x04HOST")
    link = work_root / "r1" / "leaked.xlsx"
    link.symlink_to(secret)
    real = work_root / "r1" / "ok.xlsx"
    real.write_bytes(b"PK\x03\x04OK")
    out = sidecar_mod.collect_files({"workspace_id": "r1", "glob": ["*.xlsx"]})
    names = [f["name"] for f in out["files"]]
    assert "ok.xlsx" in names
    assert "leaked.xlsx" not in names


def test_destroy_ok_matches_destroyed(tmp_path: Path) -> None:
    import sidecar as sidecar_mod

    sidecar_mod.WORK_ROOT = tmp_path / "work"
    sidecar_mod.WORK_ROOT.mkdir()
    sidecar_mod.AGENT_HOME = tmp_path / "agent-home"
    sidecar_mod.write_agent_home()
    sidecar_mod._state["runs"] = {}
    sidecar_mod._state["destroyed"] = set()
    sidecar_mod._state["conversation_key"] = None
    sidecar_mod._state["owner_key"] = None
    sidecar_mod.create_run({"workspace_id": "gone", "conversation_id": "c1"})
    body = sidecar_mod.destroy_run({"workspace_id": "gone"})
    assert body["ok"] is True
    assert body["destroyed"] is True
    assert not (tmp_path / "work" / "gone").exists()


def test_kill_pg_signals_group_after_parent_exit(tmp_path: Path) -> None:
    import os
    import signal
    import subprocess
    import time

    import sidecar as sidecar_mod

    marker = tmp_path / "child.pid"
    script = tmp_path / "pg.py"
    script.write_text(
        "import os, sys, time\n"
        "from pathlib import Path\n"
        "marker = Path(sys.argv[1])\n"
        "child = os.fork()\n"
        "if child == 0:\n"
        "    marker.write_text(str(os.getpid()))\n"
        "    time.sleep(30)\n"
        "    raise SystemExit(0)\n"
        "raise SystemExit(0)\n",
        encoding="utf-8",
    )
    proc = subprocess.Popen(
        [sys.executable, str(script), str(marker)],
        start_new_session=True,
    )
    deadline = time.time() + 3
    child = 0
    while time.time() < deadline:
        if proc.poll() is not None and marker.is_file():
            try:
                child = int(marker.read_text().strip() or "0")
            except ValueError:
                child = 0
            if child:
                break
        time.sleep(0.05)
    assert proc.poll() is not None
    assert child > 0
    sidecar_mod._kill_pg(proc, grace=1.0)
    dead = False
    deadline = time.time() + 2
    while time.time() < deadline:
        try:
            os.kill(child, 0)
        except ProcessLookupError:
            dead = True
            break
        time.sleep(0.05)
    if not dead:
        try:
            os.kill(child, signal.SIGKILL)
        except ProcessLookupError:
            dead = True
    assert dead


@pytest.mark.asyncio
async def test_ingest_collect_rechecks_cancel_before_each_write() -> None:
    gate = WorkenvCancelGate()
    store = MemoryArtifactStore()
    xlsx = (ROOT / "testdata" / "workenv" / "gradebook.xlsx").read_bytes()

    class FlipStore(MemoryArtifactStore):
        async def write(self, principal, *, title, content, kind):  # type: ignore[no-untyped-def]
            gate.begin_cancel()
            return await super().write(principal, title=title, content=content, kind=kind)

    flip = FlipStore()
    with pytest.raises(WorkenvCollectRejected):
        await gate.ingest_collect(
            Principal(),
            flip,
            [
                {"name": "a.xlsx", "bytes": xlsx},
                {"name": "b.xlsx", "bytes": xlsx},
            ],
        )
    assert len(flip.rows) == 0


@pytest.mark.asyncio
async def test_exec_mode_write_list_read_hit_overlay(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from pico_orchestrator.tools_builtin import build_default_gateway
    from pico_orchestrator.usage_hook import bind_usage_context, reset_usage_context

    monkeypatch.setenv("PICO_WORKENV", "exec")
    posted: list[dict[str, Any]] = []

    async def fake_post(path: str, payload: dict, timeout: float = 30.0) -> dict:
        del timeout
        posted.append({"path": path, "payload": payload})
        if str(path).endswith("/ls"):
            return {"ok": True, "files": [{"name": "n.txt", "n": 3}]}
        if str(path).endswith("/read"):
            return {
                "ok": True,
                "name": "n.txt",
                "bytes_b64": __import__("base64").b64encode(b"ok\n").decode("ascii"),
            }
        return {"ok": True}

    monkeypatch.setattr("pico_orchestrator.true_pi.workenv_http.workenv_post", fake_post)
    store = MemoryArtifactStore()
    store._run_id = "run-exec"  # type: ignore[attr-defined]
    gw = build_default_gateway(store)
    tok = bind_usage_context(
        school_id="school-a",
        membership_id="member-a",
        run_id="run-exec",
        conversation_id="convo-keep",
    )
    try:
        written = await gw.invoke(
            Principal(),
            "workspace_write_file",
            {"title": "n.txt", "content": "ok\n"},
        )
        listed = await gw.invoke(Principal(), "workspace_list_files", {"limit": 10})
        read = await gw.invoke(Principal(), "workspace_read_file", {"title": "n.txt"})
        executed = await gw.invoke(
            Principal(),
            "sandbox_workspace_exec",
            {"source": "print(open('n.txt').read())"},
        )
    finally:
        reset_usage_context(tok)
    assert written.get("overlay") is True
    assert listed.get("count") == 1
    assert read["artifact"]["overlay"] is True
    assert executed.get("overlay") is True
    paths = [p["path"] for p in posted]
    assert "/v1/internal/workenv/create" in paths
    assert "/v1/internal/workenv/attach" in paths
    assert "/v1/internal/workenv/ls" in paths
    assert "/v1/internal/workenv/read" in paths
    assert "/v1/internal/workenv/exec" in paths
    created = next(p for p in posted if p["path"].endswith("/create"))
    assert created["payload"]["conversation_id"] == "convo-keep"
    assert created["payload"]["workspace_id"] == "run-exec"


@pytest.mark.asyncio
async def test_destroy_false_fails_runtime(monkeypatch: pytest.MonkeyPatch) -> None:
    from pico_orchestrator.true_pi.client import FakeTransport
    from pico_orchestrator.true_pi.runtime import run_true_pi_agent

    def make_attach(*_a: Any, **_k: Any) -> FakeTransport:
        return FakeTransport(
            scripted=[
                {"type": "agent_start"},
                {"type": "turn_start"},
                {"type": "agent_end", "willRetry": False},
            ],
            assistant_text="done",
        )

    monkeypatch.setenv("PICO_WORKENV", "pi")
    monkeypatch.setattr("pico_orchestrator.true_pi.runtime.AttachTransport", make_attach)
    monkeypatch.delenv("PICO_WORKENV_FIXTURE_DIR", raising=False)

    async def fake_post(path: str, payload: dict, timeout: float = 30.0) -> dict:
        del payload, timeout
        if str(path).endswith("/collect"):
            return {"ok": True, "files": []}
        if str(path).endswith("/destroy-run"):
            return {"ok": True, "destroyed": False}
        return {"ok": True}

    monkeypatch.setattr("pico_orchestrator.true_pi.workenv_http.workenv_post", fake_post)
    events: list[tuple[str, dict[str, Any]]] = []

    async def emit(kind: str, payload: dict[str, Any]) -> None:
        events.append((kind, payload))

    result = await run_true_pi_agent(
        prompt="hi",
        principal=Principal(),
        emit=emit,
        is_cancelled=_not_cancelled,
        caps=RunCaps(min_artifacts=0, max_seconds=8),
        transport=None,
        artifact_store=MemoryArtifactStore(),
        run_id="destroy-false",
    )
    assert result.status == "failed"
    assert any(
        p.get("code") == "sandbox.workenv_destroy_failed"
        for k, p in events
        if k == "run.error"
    )


def test_destroy_clears_conversation_key(tmp_path: Path) -> None:
    import sidecar as sidecar_mod

    sidecar_mod.WORK_ROOT = tmp_path / "work"
    sidecar_mod.WORK_ROOT.mkdir()
    sidecar_mod.SESSION_ROOT = tmp_path / "session"
    sidecar_mod.SESSION_ROOT.mkdir()
    sidecar_mod.AGENT_HOME = tmp_path / "agent-home"
    sidecar_mod.write_agent_home()
    sidecar_mod._state["runs"] = {}
    sidecar_mod._state["destroyed"] = set()
    sidecar_mod._state["conversation_key"] = None
    sidecar_mod._state["owner_key"] = None
    first = sidecar_mod.create_run({"workspace_id": "r-t1", "conversation_id": "t1-api"})
    assert first["ok"] is True
    mismatch = sidecar_mod.create_run({"workspace_id": "r-t2", "conversation_id": "t2-api"})
    assert mismatch["ok"] is False
    assert mismatch["error"] == "box.conversation_mismatch"
    gone = sidecar_mod.destroy_run({"workspace_id": "r-t1"})
    assert gone["destroyed"] is True
    assert sidecar_mod._state["conversation_key"] is None
    second = sidecar_mod.create_run({"workspace_id": "r-t2", "conversation_id": "t2-api"})
    assert second["ok"] is True
    session = sidecar_mod.SESSION_ROOT / "pico.jsonl"
    assert session.exists()
    assert session.read_text(encoding="utf-8") == ""


def test_create_run_rejects_owner_mismatch(tmp_path: Path) -> None:
    import sidecar as sidecar_mod

    sidecar_mod.WORK_ROOT = tmp_path / "work"
    sidecar_mod.WORK_ROOT.mkdir()
    sidecar_mod.SESSION_ROOT = tmp_path / "session"
    sidecar_mod.SESSION_ROOT.mkdir()
    sidecar_mod.AGENT_HOME = tmp_path / "agent-home"
    sidecar_mod.write_agent_home()
    sidecar_mod._state["runs"] = {}
    sidecar_mod._state["destroyed"] = set()
    sidecar_mod._state["conversation_key"] = None
    sidecar_mod._state["owner_key"] = None
    first = sidecar_mod.create_run(
        {
            "workspace_id": "r-a",
            "conversation_id": "c1",
            "school_id": "school-a",
            "membership_id": "m1",
        }
    )
    assert first["ok"] is True
    other = sidecar_mod.create_run(
        {
            "workspace_id": "r-b",
            "conversation_id": "c1",
            "school_id": "school-b",
            "membership_id": "m2",
        }
    )
    assert other["ok"] is False
    assert other["error"] == "box.owner_mismatch"


@pytest.mark.asyncio
async def test_invalid_ooxml_collect_fails_closed() -> None:
    gate = WorkenvCancelGate()
    store = MemoryArtifactStore()
    with pytest.raises(WorkenvCollectRejected):
        await gate.ingest_collect(
            Principal(),
            store,
            [{"name": "bad.xlsx", "bytes": b"PK\x03\x04not-ooxml"}],
        )
    assert store.rows == []


@pytest.mark.asyncio
async def test_empty_xlsx_collect_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    from pico_orchestrator.true_pi.runtime import _collect_workenv_into_store

    async def fake_post(path: str, payload: dict, timeout: float = 30.0) -> dict:
        del path, payload, timeout
        return {"ok": True, "files": [{"name": "bad.xlsx", "bytes_b64": ""}]}

    monkeypatch.setattr("pico_orchestrator.true_pi.workenv_http.workenv_post", fake_post)
    store = MemoryArtifactStore()
    with pytest.raises(WorkenvCollectRejected):
        await _collect_workenv_into_store(
            workspace_id="run-empty",
            principal=Principal(),
            store=store,
            gate=WorkenvCancelGate(),
        )
    assert store.rows == []


@pytest.mark.asyncio
async def test_overlay_collects_files_but_provider_error_fails_run(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import base64

    from pico_orchestrator.true_pi.client import FakeTransport
    from pico_orchestrator.true_pi.runtime import run_true_pi_agent

    scripted = [
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
    ]

    def make_attach(*_a: Any, **_k: Any) -> FakeTransport:
        return FakeTransport(scripted=scripted, assistant_text="")

    monkeypatch.setenv("PICO_WORKENV", "pi")
    monkeypatch.setattr("pico_orchestrator.true_pi.runtime.AttachTransport", make_attach)
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

    result = await run_true_pi_agent(
        prompt="把 D2:D7 写成公式",
        principal=Principal(),
        emit=emit,
        is_cancelled=_not_cancelled,
        caps=RunCaps(min_artifacts=0, max_seconds=8),
        transport=None,
        artifact_store=store,
        run_id="t1-token-phrase",
    )
    assert result.status == "failed"
    assert store.rows and store.rows[0]["title"] == "gradebook.xlsx"
    assert "failed" in [p.get("status") for k, p in events if k == "run.status"]


@pytest.mark.asyncio
async def test_exec_mode_uses_run_token_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from pico_orchestrator.true_pi.client import FakeTransport
    from pico_orchestrator.true_pi.runtime import run_true_pi_agent

    token = tmp_path / "run.token"
    token.write_text("tok-isolated\n", encoding="utf-8")
    monkeypatch.setenv("PICO_WORKENV", "exec")
    monkeypatch.setenv("PICO_RUN_TOKEN_FILE", str(token))
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.delenv("KIMI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("PICO_RUN_TOKEN", raising=False)
    monkeypatch.delenv("PICO_WORKENV_FIXTURE_DIR", raising=False)

    async def fake_post(path: str, payload: dict, timeout: float = 30.0) -> dict:
        del path, payload, timeout
        return {"ok": True, "destroyed": True, "files": []}

    monkeypatch.setattr("pico_orchestrator.true_pi.workenv_http.workenv_post", fake_post)

    class CaptureTransport(FakeTransport):
        last_env: dict[str, str] = {}

        def __init__(self, **kwargs: Any) -> None:
            CaptureTransport.last_env = dict(kwargs.get("env") or {})
            super().__init__(
                scripted=[
                    {"type": "agent_start"},
                    {"type": "turn_start"},
                    {"type": "agent_end", "willRetry": False},
                ],
                assistant_text="ok",
            )

    monkeypatch.setattr("pico_orchestrator.true_pi.runtime.SubprocessTransport", CaptureTransport)

    async def emit(kind: str, payload: dict[str, Any]) -> None:
        del kind, payload

    result = await run_true_pi_agent(
        prompt="hi",
        principal=Principal(),
        emit=emit,
        is_cancelled=_not_cancelled,
        caps=RunCaps(min_artifacts=0, max_seconds=8),
        transport=None,
        artifact_store=MemoryArtifactStore(),
        run_id="exec-token",
        conversation_id="c-exec",
    )
    assert result.status == "succeeded"
    assert CaptureTransport.last_env.get("OPENAI_API_KEY") == "tok-isolated"


@pytest.mark.asyncio
async def test_remote_html_collect_fails_run(monkeypatch: pytest.MonkeyPatch) -> None:
    import base64

    from pico_orchestrator.true_pi.client import FakeTransport
    from pico_orchestrator.true_pi.runtime import run_true_pi_agent

    def make_attach(*_a: Any, **_k: Any) -> FakeTransport:
        return FakeTransport(
            scripted=[
                {"type": "agent_start"},
                {"type": "turn_start"},
                {"type": "agent_end", "willRetry": False},
            ],
            assistant_text="page ready",
        )

    monkeypatch.setenv("PICO_WORKENV", "pi")
    monkeypatch.setattr("pico_orchestrator.true_pi.runtime.AttachTransport", make_attach)
    monkeypatch.delenv("PICO_WORKENV_FIXTURE_DIR", raising=False)
    html = b"<!doctype html><script src='https://cdn.example/x.js'></script><body>x</body>"

    async def fake_post(path: str, payload: dict, timeout: float = 30.0) -> dict:
        del payload, timeout
        if str(path).endswith("/collect"):
            return {
                "ok": True,
                "files": [
                    {
                        "name": "page.html",
                        "bytes_b64": base64.b64encode(html).decode("ascii"),
                    }
                ],
            }
        return {"ok": True, "destroyed": True}

    monkeypatch.setattr("pico_orchestrator.true_pi.workenv_http.workenv_post", fake_post)

    async def emit(kind: str, payload: dict[str, Any]) -> None:
        del kind, payload

    result = await run_true_pi_agent(
        prompt="做网页",
        principal=Principal(),
        emit=emit,
        is_cancelled=_not_cancelled,
        caps=RunCaps(min_artifacts=0, max_seconds=8),
        transport=None,
        artifact_store=MemoryArtifactStore(),
        run_id="html-cdn",
    )
    assert result.status == "failed"
