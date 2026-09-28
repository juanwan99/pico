"""pi-runner control API + pico-api side of the workspace box (card #1093)."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services"))

from pi_runner.app import Runner, build_control_app
from pi_runner.policy import RunnerSettings
from pico_orchestrator.true_pi import runner as tp_runner
from pico_orchestrator.true_pi.runner import (
    ProxyEntry,
    RunnerSpec,
    RunnerTransport,
    WorkspaceKey,
    land_outputs,
    register_proxy,
    unregister_proxy,
)

TOKEN = "r" * 32
S, M, C = "a" * 32, "b" * 32, "c" * 32
BASE = f"/v1/ws/{S}/{M}/{C}"
H = {"x-pico-runner-token": TOKEN}


@pytest.fixture()
def control(tmp_path: Path):
    settings = RunnerSettings(token=TOKEN, workspace_root=tmp_path / "ws", min_free_mb=0)
    runner = Runner(settings)
    client = TestClient(build_control_app(runner))
    client.runner = runner  # type: ignore[attr-defined]
    return client, tmp_path / "ws" / S / M / C


def test_control_requires_runner_token(control) -> None:
    client, _ = control
    assert client.get(f"{BASE}/outputs").status_code == 401
    assert client.get(f"{BASE}/outputs", headers={"x-pico-runner-token": "nope"}).status_code == 401


def test_upload_list_download_roundtrip(control) -> None:
    client, ws = control
    r = client.put(f"{BASE}/file", params={"path": "attachments/a.txt"}, content=b"hi", headers=H)
    assert r.status_code == 200, r.text
    assert (ws / "attachments" / "a.txt").read_bytes() == b"hi"
    (ws / "outputs" / "report.docx").write_bytes(b"PK..")
    rows = client.get(f"{BASE}/outputs", headers=H).json()["files"]
    assert [r["path"] for r in rows] == ["outputs/report.docx"]
    got = client.get(f"{BASE}/file", params={"path": "outputs/report.docx"}, headers=H)
    assert got.content == b"PK.."


def test_upload_only_into_attachments(control) -> None:
    client, _ = control
    for path in ("outputs/x", ".pi/settings.json", "../x", "attachments/../../x"):
        r = client.put(f"{BASE}/file", params={"path": path}, content=b"x", headers=H)
        assert r.status_code == 400, path


def test_download_refuses_symlink_escape(control, tmp_path: Path) -> None:
    client, ws = control
    client.put(f"{BASE}/file", params={"path": "attachments/seed"}, content=b"x", headers=H)
    secret = tmp_path / "secret.txt"
    secret.write_text("host secret")
    os.symlink(secret, ws / "outputs" / "leak.txt")
    r = client.get(f"{BASE}/file", params={"path": "outputs/leak.txt"}, headers=H)
    assert r.status_code == 400
    listed = client.get(f"{BASE}/outputs", headers=H).json()["files"]
    assert listed == []


def test_upload_does_not_follow_symlinked_dir(control, tmp_path: Path) -> None:
    client, ws = control
    client.put(f"{BASE}/file", params={"path": "attachments/seed"}, content=b"x", headers=H)
    outside = tmp_path / "outside"
    outside.mkdir()
    # Model replaces attachments/ with a link pointing out of the box.
    (ws / "attachments" / "seed").unlink()
    (ws / "attachments").rmdir()
    os.symlink(outside, ws / "attachments")
    r = client.put(f"{BASE}/file", params={"path": "attachments/b.txt"}, content=b"y", headers=H)
    assert r.status_code == 200
    assert not (outside / "b.txt").exists()
    assert (ws / "attachments" / "b.txt").read_bytes() == b"y"


# --- pico-api side -----------------------------------------------------------


def _transport(tmp_path: Path, **kw: Any) -> RunnerTransport:
    key = WorkspaceKey.for_run(
        school_id="s1", membership_id="m1", conversation_id="c1", run_id="run1"
    )
    ext = ROOT / "services" / "true_pi_bridge" / "pico-gateway-tools.ts"
    return RunnerTransport(
        runner=RunnerSpec(key=key, llm_upstream="http://127.0.0.1:3000/v1", llm_key="REAL-KEY"),
        session_dir=tmp_path,
        tool_url="http://127.0.0.1:5555",
        tool_token="tooltok",
        run_id="run1",
        provider="openai",
        model="gemini-3.8-flash",
        api="openai-completions",
        ext=ext,
        system_prompt_text="SYS",
        env={"PICO_TRUE_PI_VISIBLE_TOOLS": "web_search", "DEEPSEEK_API_KEY": "REAL-KEY"},
        **kw,
    )


def test_transport_turns_builtins_on_in_box(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("PICO_RUNNER_PROXY_URL", "http://172.30.250.1:18791")
    t = _transport(tmp_path, session_file=tmp_path / "tree.jsonl")
    args = t.pi_args()
    assert "--no-builtin-tools" not in args
    assert args[args.index("--session-dir") + 1] == "/workspace/.pico/session"
    assert args[args.index("--session") + 1] == "/workspace/.pico/session/tree.jsonl"
    assert args[args.index("-e") + 1] == "/opt/pico/true_pi_bridge/pico-gateway-tools.ts"


def test_transport_box_env_has_no_real_key(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("PICO_RUNNER_PROXY_URL", "http://172.30.250.1:18791")
    t = _transport(tmp_path)
    env = t.container_env()
    assert "REAL-KEY" not in json.dumps(env)
    assert env["OPENAI_API_KEY"] == t.llm_token
    assert env["PICO_TRUE_PI_TOOL_URL"] == "http://172.30.250.1:18791/t/run1"
    t.prepare_agent_home()
    models = json.loads(t._seed[".pico/agent/models.json"])
    assert "REAL-KEY" not in json.dumps(models)
    assert "http://172.30.250.1:18791/l/run1/v1" in json.dumps(models)
    assert t._seed[".pi/SYSTEM.md"].startswith("SYS")


def test_workspace_key_is_hashed_per_conversation() -> None:
    a = WorkspaceKey.for_run(school_id="s", membership_id="m", conversation_id="c", run_id="r1")
    b = WorkspaceKey.for_run(school_id="s", membership_id="m", conversation_id="c", run_id="r2")
    c = WorkspaceKey.for_run(school_id="s", membership_id="m2", conversation_id="c", run_id="r1")
    assert a == b and a != c
    assert "s" not in a.path().split("/") and len(a.school) == 32


# --- ws-proxy router ---------------------------------------------------------


@pytest.fixture()
def proxy_client(monkeypatch):
    from app import ws_proxy_router as mod
    from fastapi import FastAPI

    monkeypatch.setenv("PICO_RUNNER_TOKEN", TOKEN)
    seen: dict[str, Any] = {}

    async def fake_stream(method, target, headers, body):
        from fastapi.responses import JSONResponse

        seen.update(method=method, target=target, headers=headers, body=body)
        return JSONResponse({"ok": True})

    monkeypatch.setattr(mod, "_stream", fake_stream)
    monkeypatch.setattr(mod, "request_on_loopback_socket", lambda request: True)
    app = FastAPI()
    app.include_router(mod.router)
    register_proxy(
        ProxyEntry(
            run_id="run9",
            llm_token="boxtok",
            llm_upstream="http://127.0.0.1:3000/v1",
            llm_key="REAL-KEY",
            tool_url="http://127.0.0.1:5555",
            tool_token="tooltok",
            model="gemini-3.8-flash",
        )
    )
    yield TestClient(app), seen
    unregister_proxy("run9")


def test_proxy_swaps_box_token_for_real_key(proxy_client) -> None:
    client, seen = proxy_client
    r = client.post(
        "/internal/ws-proxy/l/run9/v1/chat/completions",
        headers={**H, "authorization": "Bearer boxtok"},
        json={"model": "gemini-3.8-flash"},
    )
    assert r.status_code == 200
    assert seen["target"] == "http://127.0.0.1:3000/v1/chat/completions"
    assert seen["headers"]["authorization"] == "Bearer REAL-KEY"


@pytest.mark.parametrize(
    "headers,run",
    [
        ({"authorization": "Bearer boxtok"}, "run9"),  # no runner token
        ({**H, "authorization": "Bearer wrong"}, "run9"),  # wrong box token
        ({**H, "authorization": "Bearer boxtok"}, "run-gone"),  # run not alive
    ],
)
def test_proxy_denies(proxy_client, headers, run) -> None:
    client, seen = proxy_client
    r = client.post(f"/internal/ws-proxy/l/{run}/v1/responses", headers=headers, json={})
    assert r.status_code in {401, 403}
    assert "target" not in seen


def test_proxy_pins_run_model_and_paths(proxy_client) -> None:
    client, seen = proxy_client
    auth = {**H, "authorization": "Bearer boxtok"}
    r = client.post("/internal/ws-proxy/l/run9/v1/chat/completions", headers=auth, json={"model": "gpt-5.6-sol"})
    assert r.status_code == 403
    for path in ("images/generations", "embeddings", "admin/gateway"):
        assert client.post(f"/internal/ws-proxy/l/run9/v1/{path}", headers=auth, json={}).status_code == 404
    r = client.post(
        "/internal/ws-proxy/l/run9/v1/..%2F..%2Fadmin", headers=auth, json={"model": "gemini-3.8-flash"}
    )
    assert r.status_code == 404
    assert "target" not in seen


def test_tool_proxy_only_tool_path(proxy_client) -> None:
    client, seen = proxy_client
    assert client.post("/internal/ws-proxy/t/run9/admin", headers=H).status_code == 404
    r = client.post(
        "/internal/ws-proxy/t/run9/v1/tool", headers={**H, "authorization": "Bearer tooltok"}, json={}
    )
    assert r.status_code == 200
    assert seen["target"] == "http://127.0.0.1:5555/v1/tool"


# --- outputs → ledger --------------------------------------------------------


class _Store:
    def __init__(self) -> None:
        self.rows: list[dict[str, Any]] = []

    async def write(self, principal, *, title, content, kind):
        row = {"artifact_id": f"a{len(self.rows)}", "title": title, "kind": kind}
        self.rows.append({**row, "content": content})
        return row


def _docx() -> bytes:
    import io

    from docx import Document

    buf = io.BytesIO()
    Document().save(buf)
    return buf.getvalue()


async def _fake_listing(monkeypatch, files: dict[str, bytes], mtimes: dict[str, float] | None = None):
    import hashlib

    async def fake_list(k):
        return {
            p: {"path": p, "sha256": hashlib.sha256(b).hexdigest(), "mtime": (mtimes or {}).get(p, 2000.0)}
            for p, b in files.items()
        }

    async def fake_fetch(k, path):
        return files[path]

    monkeypatch.setattr(tp_runner, "list_outputs", fake_list)
    monkeypatch.setattr(tp_runner, "fetch_output", fake_fetch)


async def test_land_outputs_new_changed_and_invalid(monkeypatch) -> None:
    import hashlib

    key = WorkspaceKey.for_run(school_id="s", membership_id="m", conversation_id="c", run_id="r")
    files = {"outputs/old.txt": b"same", "outputs/new.docx": _docx(), "outputs/fake.xlsx": b"text"}
    await _fake_listing(monkeypatch, files)
    before = {"outputs/old.txt": {"sha256": hashlib.sha256(b"same").hexdigest()}}
    store = _Store()
    results = await land_outputs(
        key=key, before=before, since=0.0, artifact_store=store, principal=object()
    )
    by_title = {r["title"]: r for _, r in results}
    assert set(by_title) == {"new.docx", "fake.xlsx"}
    assert by_title["new.docx"]["artifact_id"] == "a0"
    assert "error" in by_title["fake.xlsx"]
    assert [r["title"] for r in store.rows] == ["new.docx"]


async def test_land_outputs_without_snapshot_uses_mtime(monkeypatch) -> None:
    key = WorkspaceKey.for_run(school_id="s", membership_id="m", conversation_id="c", run_id="r")
    files = {"outputs/old.md": b"old", "outputs/new.md": b"new"}
    await _fake_listing(monkeypatch, files, {"outputs/old.md": 100.0, "outputs/new.md": 2000.0})
    store = _Store()
    results = await land_outputs(key=key, before=None, since=1000.0, artifact_store=store, principal=object())
    assert [r["title"] for _, r in results] == ["new.md"]


def test_workspace_key_fail_closed_without_tenant() -> None:
    from pico_orchestrator.true_pi.client import TruePiClientError

    with pytest.raises(TruePiClientError):
        WorkspaceKey.for_run(school_id="", membership_id="m", conversation_id="c", run_id="r")
    with pytest.raises(TruePiClientError):
        WorkspaceKey.for_run(school_id="s", membership_id=" ", conversation_id="c", run_id="r")


def test_control_refuses_files_while_box_runs(control) -> None:
    from types import SimpleNamespace

    from pi_runner.policy import WorkspaceKey as RKey

    client, _ = control
    client.runner.sessions["live"] = SimpleNamespace(key=RKey.parse(S, M, C))
    try:
        assert client.get(f"{BASE}/outputs", headers=H).status_code == 409
        assert client.get(f"{BASE}/file", params={"path": "outputs/a"}, headers=H).status_code == 409
        r = client.put(f"{BASE}/file", params={"path": "attachments/a"}, content=b"x", headers=H)
        assert r.status_code == 409
    finally:
        client.runner.sessions.clear()


@pytest.mark.parametrize(
    "lane,path,raw,ok",
    [
        ("l", "v1/chat/completions", b"/l/r/v1/chat/completions", True),
        ("l", "v1/responses", b"/l/r/v1/responses", True),
        ("t", "v1/tool", b"/t/r/v1/tool", True),
        ("l", "v1/../../v1/admin/gateway", b"/l/r/v1/..%2F..%2Fv1%2Fadmin%2Fgateway", False),
        ("l", "v1/admin", b"/l/r/v1/admin", False),
        ("l", "v1/chat/completions", b"/l/r/v1/chat%2Fcompletions", False),
        ("t", "v1/tool/../x", b"/t/r/v1/tool/../x", False),
        ("x", "v1/tool", b"/x/r/v1/tool", False),
    ],
)
def test_runner_proxy_path_allowlist(lane, path, raw, ok) -> None:
    from pi_runner.app import proxy_path_ok

    assert proxy_path_ok(lane, path, raw) is ok


def test_fifo_and_symlink_never_read(tmp_path: Path) -> None:
    from pathlib import PurePosixPath

    from pi_runner import fsafe

    ws = tmp_path / "ws"
    (ws / "outputs").mkdir(parents=True)
    os.mkfifo(ws / "outputs" / "pipe.docx")
    os.symlink("/proc/self/environ", ws / "outputs" / "env.txt")
    (ws / "outputs" / "ok.txt").write_text("fine")
    rows, truncated = fsafe.list_regular(ws, "outputs", max_files=10, max_total=1 << 20, max_file=1 << 20)
    assert [r.path for r in rows] == ["outputs/ok.txt"] and not truncated
    for bad in ("outputs/pipe.docx", "outputs/env.txt"):
        with pytest.raises(OSError):
            fsafe.read_file(ws, PurePosixPath(bad), max_bytes=1 << 20)


def test_listing_caps_across_nested_dirs(tmp_path: Path) -> None:
    from pi_runner import fsafe

    ws = tmp_path / "ws"
    for i in range(5):
        d = ws / "outputs" / f"d{i}" / "x"
        d.mkdir(parents=True)
        for j in range(5):
            (d / f"f{j}.txt").write_text("x")
    rows, truncated = fsafe.list_regular(ws, "outputs", max_files=7, max_total=1 << 20, max_file=1 << 20)
    assert len(rows) == 7 and truncated


def test_runner_enabled_allowlist(monkeypatch) -> None:
    from pico_orchestrator.true_pi.runner import runner_enabled

    monkeypatch.delenv("PICO_RUNNER_URL", raising=False)
    assert not runner_enabled("m1")
    monkeypatch.setenv("PICO_RUNNER_URL", "http://127.0.0.1:18790")
    monkeypatch.delenv("PICO_RUNNER_MEMBERSHIPS", raising=False)
    assert runner_enabled("anyone")
    monkeypatch.setenv("PICO_RUNNER_MEMBERSHIPS", "m1, m2")
    assert runner_enabled("m2") and not runner_enabled("m3")
