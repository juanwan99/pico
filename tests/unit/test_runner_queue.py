"""pi-runner shared budget + wait line (card #1135)."""

from __future__ import annotations

import asyncio
import json
import sys
import time
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services"))
sys.path.insert(0, str(ROOT / "services" / "orchestrator"))

from pi_runner import app as runner_app
from pi_runner.app import Runner, build_control_app
from pi_runner.policy import (
    PolicyError,
    RunnerSettings,
    WorkspaceKey,
    docker_run_argv,
    mem_available_mb,
    queue_order,
)

TOKEN = "r" * 32
A, B = "a" * 32, "b" * 32


def _key(school: str, conv: str) -> WorkspaceKey:
    return WorkspaceKey.parse(school, "e" * 32, conv * 32)


def _runner(tmp_path: Path, **kw: Any) -> Runner:
    settings = RunnerSettings(token=TOKEN, workspace_root=tmp_path / "ws", min_free_mb=0, min_avail_mb=0, **kw)
    return Runner(settings)


# --- pure policy ---------------------------------------------------------------


def test_queue_order_fewest_running_school_first_then_fifo() -> None:
    waiting = [("A", 1.0), ("B", 2.0), ("A", 0.5), ("C", 3.0)]
    assert queue_order(waiting, {"A": 2, "B": 1}) == [3, 1, 2, 0]
    assert queue_order(waiting, {}) == [2, 0, 1, 3]


def test_mem_available_mb_parses_meminfo() -> None:
    text = "MemTotal:       31917720 kB\nMemFree: 1 kB\nMemAvailable:   23692852 kB\n"
    assert mem_available_mb(text) == 23137
    assert mem_available_mb("MemTotal: 1 kB\n") is None


def test_boxes_go_under_the_shared_slice(tmp_path: Path) -> None:
    settings = RunnerSettings(token=TOKEN, workspace_root=tmp_path)
    argv = docker_run_argv(
        settings, run_id="r1", key=_key(A, "c"), pi_args=["--mode", "rpc"], env_file=tmp_path / "e", with_memory=False
    )
    assert argv[argv.index("--cgroup-parent") + 1] == "pico-ws.slice"
    assert argv[argv.index("--runtime") + 1] == "runsc"
    off = RunnerSettings(token=TOKEN, workspace_root=tmp_path, cgroup_parent="")
    argv = docker_run_argv(
        off, run_id="r1", key=_key(A, "c"), pi_args=["--mode", "rpc"], env_file=tmp_path / "e", with_memory=False
    )
    assert "--cgroup-parent" not in argv


def test_defaults_scale_past_six(monkeypatch) -> None:
    monkeypatch.setenv("PICO_RUNNER_TOKEN", TOKEN)
    s = RunnerSettings.from_env()
    assert (s.max_sessions, s.max_per_school, s.queue_wait_s, s.cgroup_parent) == (32, 24, 1200, "pico-ws.slice")
    monkeypatch.setenv("PICO_RUNNER_CGROUP_PARENT", "")
    assert RunnerSettings.from_env().cgroup_parent == ""


# --- admit / line ----------------------------------------------------------------


@pytest.mark.asyncio
async def test_full_runner_queues_then_grants_on_release(tmp_path: Path) -> None:
    runner = _runner(tmp_path, max_sessions=1)
    first = await runner.admit(_key(A, "1"))
    told: list[int] = []

    async def on_queued(ahead: int) -> None:
        told.append(ahead)

    second = asyncio.create_task(runner.admit(_key(B, "2"), on_queued))
    await asyncio.sleep(0.05)
    assert not second.done() and told == [0]
    await runner.release(first)
    waiter = await asyncio.wait_for(second, timeout=1)
    assert waiter.key == _key(B, "2") and runner.granted == [waiter] and not runner.waiting


@pytest.mark.asyncio
async def test_freed_slot_goes_to_the_school_running_fewest(tmp_path: Path) -> None:
    runner = _runner(tmp_path, max_sessions=2)
    a1 = await runner.admit(_key(A, "1"))
    await runner.admit(_key(A, "2"))
    a3 = asyncio.create_task(runner.admit(_key(A, "3")))
    await asyncio.sleep(0.01)
    b1 = asyncio.create_task(runner.admit(_key(B, "4")))
    await asyncio.sleep(0.01)
    await runner.release(a1)
    await asyncio.wait_for(b1, timeout=1)
    assert not a3.done()
    a3.cancel()


@pytest.mark.asyncio
async def test_per_school_cap_does_not_block_other_schools(tmp_path: Path) -> None:
    runner = _runner(tmp_path, max_sessions=4, max_per_school=1)
    await runner.admit(_key(A, "1"))
    a2 = asyncio.create_task(runner.admit(_key(A, "2")))
    b = await asyncio.wait_for(runner.admit(_key(B, "3")), timeout=1)
    assert b.key.school == B and not a2.done()
    a2.cancel()


@pytest.mark.asyncio
async def test_line_times_out_and_gives_place_back(tmp_path: Path) -> None:
    runner = _runner(tmp_path, max_sessions=1, queue_wait_s=0)
    await runner.admit(_key(A, "1"))
    with pytest.raises(PolicyError) as exc:
        await runner.admit(_key(B, "2"))
    assert exc.value.code == "runner.busy" and not runner.waiting


@pytest.mark.asyncio
async def test_cancel_in_line_leaves_line(tmp_path: Path) -> None:
    runner = _runner(tmp_path, max_sessions=1)
    await runner.admit(_key(A, "1"))
    t = asyncio.create_task(runner.admit(_key(B, "2")))
    await asyncio.sleep(0.02)
    assert len(runner.waiting) == 1
    t.cancel()
    with pytest.raises(asyncio.CancelledError):
        await t
    assert not runner.waiting


@pytest.mark.asyncio
async def test_same_conversation_in_line_is_refused_at_once(tmp_path: Path) -> None:
    runner = _runner(tmp_path, max_sessions=1)
    await runner.admit(_key(A, "1"))
    t = asyncio.create_task(runner.admit(_key(B, "2")))
    await asyncio.sleep(0.02)
    with pytest.raises(PolicyError) as exc:
        await runner.admit(_key(B, "2"))
    assert exc.value.code == "runner.workspace_busy"
    t.cancel()


@pytest.mark.asyncio
async def test_low_host_memory_queues_instead_of_starting(tmp_path: Path, monkeypatch) -> None:
    runner = _runner(tmp_path, max_sessions=8)
    runner.settings = RunnerSettings(token=TOKEN, workspace_root=tmp_path / "ws", min_free_mb=0, min_avail_mb=4096)
    avail = {"mb": 1000}
    monkeypatch.setattr(runner, "avail_mb", lambda: avail["mb"])
    monkeypatch.setattr(runner_app, "QUEUE_TICK_S", 0.01)
    t = asyncio.create_task(runner.admit(_key(A, "1")))
    await asyncio.sleep(0.05)
    assert not t.done()
    avail["mb"] = 8000
    await asyncio.wait_for(t, timeout=1)


@pytest.mark.asyncio
async def test_full_line_refuses(tmp_path: Path) -> None:
    runner = _runner(tmp_path, max_sessions=1, queue_max=1)
    await runner.admit(_key(A, "1"))
    t = asyncio.create_task(runner.admit(_key(A, "2")))
    await asyncio.sleep(0.02)
    with pytest.raises(PolicyError) as exc:
        await runner.admit(_key(B, "3"))
    assert exc.value.code == "runner.busy"
    t.cancel()


# --- /v1/session over the wire (sh stands in for docker) ---------------------------


@pytest.fixture()
def wired(tmp_path: Path, monkeypatch):
    runner = _runner(tmp_path, max_sessions=1)

    def fake_argv(*_a: Any, **_k: Any) -> list[str]:
        return ["sh", "-c", "read line; echo ok"]

    async def gone(_name: str) -> bool:
        return False

    async def quiet(*_a: Any, **_k: Any) -> tuple[int, str]:
        return 0, ""

    monkeypatch.setattr(runner_app, "docker_run_argv", fake_argv)
    monkeypatch.setattr(runner_app, "_container_exists", gone)
    monkeypatch.setattr(runner_app, "_docker", quiet)
    monkeypatch.setattr(runner_app, "QUEUE_TICK_S", 0.02)
    return runner, TestClient(build_control_app(runner))


def _start(run_id: str, school: str, conv: str) -> str:
    return json.dumps(
        {
            "type": "start",
            "run_id": run_id,
            "key": {"school": school, "member": "e" * 32, "conv": conv * 32},
            "args": ["--mode", "rpc"],
        }
    )


def test_second_box_waits_in_line_then_runs(wired) -> None:
    _runner, client = wired
    h = {"x-pico-runner-token": TOKEN}
    with client.websocket_connect("/v1/session", headers=h) as one:
        one.send_text(_start("r1", A, "1"))
        assert json.loads(one.receive_text())["type"] == "ready"
        with client.websocket_connect("/v1/session", headers=h) as two:
            two.send_text(_start("r2", B, "2"))
            assert json.loads(two.receive_text()) == {"type": "queued", "ahead": 0}
            one.send_text(json.dumps({"type": "in", "line": "go"}))
            assert json.loads(one.receive_text()) == {"type": "out", "line": "ok"}
            assert json.loads(one.receive_text())["type"] == "exit"
            frame = json.loads(two.receive_text())
            while frame["type"] == "queued":
                frame = json.loads(two.receive_text())
            assert frame["type"] == "ready"
            two.send_text(json.dumps({"type": "in", "line": "go"}))
            assert json.loads(two.receive_text()) == {"type": "out", "line": "ok"}


def test_client_gone_while_queued_leaves_line(wired) -> None:
    runner, client = wired
    h = {"x-pico-runner-token": TOKEN}
    with client.websocket_connect("/v1/session", headers=h) as one:
        one.send_text(_start("r1", A, "1"))
        assert json.loads(one.receive_text())["type"] == "ready"
        with client.websocket_connect("/v1/session", headers=h) as two:
            two.send_text(_start("r2", B, "2"))
            assert json.loads(two.receive_text())["type"] == "queued"
        deadline = time.monotonic() + 2
        while runner.waiting and time.monotonic() < deadline:
            time.sleep(0.02)
        assert not runner.waiting
        one.send_text(json.dumps({"type": "close"}))


# --- pico-api side: transport + runtime ------------------------------------------


class _FakeWs:
    def __init__(self, frames: list[dict[str, Any]], *, hang: bool = False) -> None:
        self.frames = [json.dumps(f) for f in frames]
        self.hang = hang
        self.closed = False

    async def recv(self) -> str:
        if self.frames:
            return self.frames.pop(0)
        if self.hang:
            await asyncio.sleep(3600)
        raise RuntimeError("closed")

    async def close(self) -> None:
        self.closed = True


def _transport(tmp_path: Path):
    from pico_orchestrator.true_pi.runner import RunnerSpec, RunnerTransport
    from pico_orchestrator.true_pi.runner import WorkspaceKey as TKey

    key = TKey.for_run(school_id="s1", membership_id="m1", conversation_id="c1", run_id="run1")
    return RunnerTransport(
        runner=RunnerSpec(key=key, llm_upstream="http://127.0.0.1:3000/v1", llm_key="K"),
        session_dir=tmp_path,
        tool_url="http://127.0.0.1:5555",
        tool_token="t",
        run_id="run1",
        provider="openai",
        model="m",
        ext=ROOT / "services" / "true_pi_bridge" / "pico-gateway-tools.ts",
    )


@pytest.mark.asyncio
async def test_transport_reports_line_position_once_per_change(tmp_path: Path) -> None:
    tr = _transport(tmp_path)
    seen: list[int] = []

    async def on_queued(ahead: int) -> None:
        seen.append(ahead)

    tr.on_queued = on_queued
    tr._ws = _FakeWs(
        [
            {"type": "queued", "ahead": 2},
            {"type": "queued", "ahead": 2},
            {"type": "queued", "ahead": 1},
            {"type": "queued", "ahead": 0},
            {"type": "ready"},
        ]
    )
    assert (await tr._await_ready())["type"] == "ready"
    assert seen == [2, 1, 0]


@pytest.mark.asyncio
async def test_transport_cancel_in_line_closes_socket(tmp_path: Path, monkeypatch) -> None:
    import websockets.asyncio.client as wsc
    from pico_orchestrator.true_pi import runner as tp_runner

    tr = _transport(tmp_path)
    fake = _FakeWs([{"type": "queued", "ahead": 3}], hang=True)

    async def fake_connect(*_a: Any, **_k: Any) -> Any:
        async def send(_t: str) -> None:
            return None

        fake.send = send  # type: ignore[attr-defined]
        return fake

    monkeypatch.setattr(wsc, "connect", fake_connect)
    monkeypatch.setenv("PICO_RUNNER_URL", "http://127.0.0.1:1")
    tr.prepare_agent_home()
    task = asyncio.create_task(tr.start())
    await asyncio.sleep(0.05)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert fake.closed and tp_runner.proxy_entry("run1") is None


@pytest.mark.asyncio
async def test_failover_gate_shows_queue_at_once() -> None:
    from pico_orchestrator.true_pi.runtime import _FailoverGate

    out: list[str] = []

    async def emit(kind: str, _p: dict[str, Any]) -> None:
        out.append(kind)

    gate = _FailoverGate(emit, "")
    await gate.emit("run.model", {})
    await gate.emit("run.queued", {"ahead": 1})
    assert out == ["run.queued"]


def _queued_transport(*, release: asyncio.Event | None):
    from pico_orchestrator.true_pi.client import FakeTransport

    class Queued(FakeTransport):
        async def start(self) -> None:
            await self.on_queued(2)
            await self.on_queued(1)
            if release is not None:
                await release.wait()
            else:
                await asyncio.sleep(3600)
            await super().start()

    t = Queued(scripted=[{"type": "agent_start"}, {"type": "agent_end", "messages": []}], assistant_text="好")
    t.runner = SimpleNamespace(key=SimpleNamespace(path=lambda: "x/y/z"))
    t.on_queued = None
    return t


@pytest.mark.asyncio
async def test_runtime_shows_queue_then_runs(monkeypatch) -> None:
    from pico_orchestrator.run_types import RunCaps
    from pico_orchestrator.true_pi import runner as tp_runner
    from pico_orchestrator.true_pi import runtime as rt

    async def no_listing(_key: Any) -> dict[str, Any]:
        return {}

    async def no_landing(**_k: Any) -> list[Any]:
        return []

    monkeypatch.setattr(tp_runner, "list_outputs", no_listing)
    monkeypatch.setattr(rt, "_land_workspace_outputs", no_landing)
    events: list[tuple[str, dict[str, Any]]] = []

    async def emit(kind: str, payload: dict[str, Any]) -> None:
        events.append((kind, payload))

    async def not_cancelled() -> bool:
        return False

    release = asyncio.Event()
    release.set()
    await rt.run_true_pi_agent(
        prompt="hi",
        principal=SimpleNamespace(school_id="s", membership_id="m", scopes=None),
        emit=emit,
        is_cancelled=not_cancelled,
        caps=RunCaps(max_seconds=30),
        transport=_queued_transport(release=release),
    )
    queued = [p for k, p in events if k == "run.queued"]
    assert [q["ahead"] for q in queued] == [2, 1, 0] and queued[-1]["started"] is True
    kinds = [k for k, _ in events]
    assert kinds.index("run.queued") < kinds.index("run.model")


@pytest.mark.asyncio
async def test_runtime_stop_while_queued_cancels(monkeypatch) -> None:
    from pico_orchestrator.run_types import RunCaps
    from pico_orchestrator.true_pi import runner as tp_runner
    from pico_orchestrator.true_pi import runtime as rt

    async def no_listing(_key: Any) -> dict[str, Any]:
        return {}

    monkeypatch.setattr(tp_runner, "list_outputs", no_listing)
    monkeypatch.setattr(rt, "_QUEUE_CANCEL_POLL", 0.02)
    events: list[tuple[str, dict[str, Any]]] = []

    async def emit(kind: str, payload: dict[str, Any]) -> None:
        events.append((kind, payload))

    calls = {"n": 0}

    async def cancelled_later() -> bool:
        calls["n"] += 1
        return calls["n"] > 2

    result = await asyncio.wait_for(
        rt.run_true_pi_agent(
            prompt="hi",
            principal=SimpleNamespace(school_id="s", membership_id="m", scopes=None),
            emit=emit,
            is_cancelled=cancelled_later,
            caps=RunCaps(max_seconds=30),
            transport=_queued_transport(release=None),
        ),
        timeout=5,
    )
    assert result.status == "cancelled"
    assert ("run.status", {"status": "cancelled", "runtime": "pi-true"}) in events
    assert "run.model" not in [k for k, _ in events]
