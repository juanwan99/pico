"""pico#1318: the teacher speaks while a turn still runs — Pi changes course, nothing done is lost.

The new message goes into Pi's own steer queue (after the running tools,
before the next model call). No live turn in this process → 409, and the
caller falls back to the #1250 takeover.
"""

from __future__ import annotations

import asyncio
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "api"))
sys.path.insert(0, str(ROOT / "services" / "orchestrator"))

from pico_orchestrator.run_types import RunCaps
from pico_orchestrator.true_pi import steer as teacher_steer
from pico_orchestrator.true_pi.client import FakeTransport, RpcEvent
from pico_orchestrator.true_pi.runtime import run_true_pi_agent

KEY = ("school-a", "member-a", "conv-1")


class Principal:
    def __init__(self) -> None:
        self.school_id = "school-a"
        self.membership_id = "member-a"
        self.scopes = ["ai:run"]


async def _not_cancelled() -> bool:
    return False


def _done(text: str) -> list[dict[str, Any]]:
    msg = {"role": "assistant", "content": [{"type": "text", "text": text}]}
    return [{"type": "message_end", "message": msg}, {"type": "turn_end", "message": msg}]


def _user(text: str) -> list[dict[str, Any]]:
    msg = {"role": "user", "content": [{"type": "text", "text": text}]}
    return [{"type": "message_start", "message": msg}, {"type": "message_end", "message": msg}]


END = [{"type": "agent_end", "willRetry": False, "messages": []}]
TOOL = [
    {"type": "tool_execution_start", "toolName": "bash", "toolCallId": "c1", "args": {"command": "ls"}},
    {
        "type": "tool_execution_end",
        "toolName": "bash",
        "toolCallId": "c1",
        "isError": False,
        "result": {"content": [{"type": "text", "text": "ok"}]},
    },
]


@dataclass
class SteerablePi(FakeTransport):
    """Holds the turn open until the teacher steers, then plays ``after_steer``."""

    after_steer: list[dict[str, Any]] = field(default_factory=list)

    async def start(self) -> None:
        for item in self.scripted:
            await self._event_q.put(RpcEvent(item))

    async def send(self, command: Any) -> None:
        await super().send(command)
        if dict(command).get("type") == "steer" and self.after_steer:
            for item in self.after_steer:
                await self._event_q.put(RpcEvent(item))
            self.after_steer = []


async def _run(transport: FakeTransport, events: list[tuple[str, dict[str, Any]]]):
    async def emit(kind: str, payload: dict[str, Any]) -> None:
        events.append((kind, payload))

    return await run_true_pi_agent(
        prompt="做一份通知",
        principal=Principal(),
        emit=emit,
        is_cancelled=_not_cancelled,
        caps=RunCaps(min_artifacts=0, max_seconds=8),
        transport=transport,
        run_id="steer-t",
        conversation_id="conv-1",
    )


async def _steer_when_live(text: str) -> bool:
    for _ in range(200):
        live = teacher_steer._LIVE.get(KEY)
        if live is not None and live.open:
            return await teacher_steer.steer(KEY, text)
        await asyncio.sleep(0.01)
    raise AssertionError("turn never went live")


@pytest.mark.asyncio
async def test_steer_changes_course_and_keeps_what_was_done() -> None:
    said = "改成表格"
    transport = SteerablePi(
        scripted=[{"type": "agent_start"}, {"type": "turn_start"}, *TOOL],
        after_steer=[*_done("先写了一段。"), {"type": "turn_start"}, *_user(said), *_done("已改成表格。"), *END],
    )
    events: list[tuple[str, dict[str, Any]]] = []
    run = asyncio.create_task(_run(transport, events))
    assert await _steer_when_live(said) is True
    result = await run

    assert [c["message"] for c in transport.sent if c.get("type") == "steer"] == [said]
    assert ("run.steer", {"text": said, "runtime": "pi-true"}) in events
    # The step done before the steer stays in the run; the answer is the steered one.
    kinds = [k for k, _ in events]
    assert kinds.index("tool.result") < kinds.index("run.steer")
    assert result.status == "succeeded" and result.final_text == "已改成表格。"
    # One turn, one prompt: the steer rode the running turn, no takeover.
    assert sum(1 for c in transport.sent if c.get("type") == "prompt") == 1
    assert KEY not in teacher_steer._LIVE


@dataclass
class InjectBeforeAckPi(SteerablePi):
    """Pi injects the steer and the consumer sees it before the steer ack lands."""

    after_ack: list[dict[str, Any]] = field(default_factory=list)

    async def wait_response(
        self, command_type: str, *, req_id: str | None = None, timeout: float = 30.0
    ) -> dict[str, Any]:
        if command_type == "steer":
            while not self._event_q.empty():
                await asyncio.sleep(0.01)
            await asyncio.sleep(0.05)
        resp = await super().wait_response(command_type, req_id=req_id, timeout=timeout)
        if command_type == "steer":
            for item in self.after_ack:
                await self._event_q.put(RpcEvent(item))
            self.after_ack = []
        return resp


@pytest.mark.asyncio
async def test_steer_injected_before_its_ack_runs_once() -> None:
    said = "改成表格"
    transport = InjectBeforeAckPi(
        scripted=[{"type": "agent_start"}, {"type": "turn_start"}, *TOOL],
        after_steer=[*_done("先写了一段。"), {"type": "turn_start"}, *_user(said), *_done("已改成表格。")],
        after_ack=END,
    )
    events: list[tuple[str, dict[str, Any]]] = []
    run = asyncio.create_task(_run(transport, events))
    assert await _steer_when_live(said) is True
    result = await run

    sent = [c.get("type") for c in transport.sent]
    assert sent.count("prompt") == 1 and "clear_queue" not in sent
    assert ("run.steer", {"text": said, "runtime": "pi-true"}) in events
    assert result.status == "succeeded" and result.final_text == "已改成表格。"


@pytest.mark.asyncio
async def test_steer_that_missed_the_end_is_said_as_the_next_prompt() -> None:
    said = "再加一行签名"
    transport = SteerablePi(
        scripted=[{"type": "agent_start"}, {"type": "turn_start"}, *TOOL],
        # Pi ended without injecting the steer (it arrived as agent_end went out).
        after_steer=[*_done("做好了。"), *END],
        scripted_after_prompt=[
            [{"type": "agent_start"}, {"type": "turn_start"}, *_user(said), *_done("已加签名。"), *END]
        ],
    )
    events: list[tuple[str, dict[str, Any]]] = []
    run = asyncio.create_task(_run(transport, events))
    assert await _steer_when_live(said) is True
    result = await run

    kinds = [c.get("type") for c in transport.sent]
    assert kinds.index("clear_queue") < len(kinds) - 1 - kinds[::-1].index("prompt")
    assert [c["message"] for c in transport.sent if c.get("type") == "prompt"][-1] == said
    assert ("run.steer", {"text": said, "late": True, "runtime": "pi-true"}) in events
    assert "已加签名。" in result.final_text


@pytest.mark.asyncio
async def test_no_live_turn_refuses_so_caller_takes_over() -> None:
    assert await teacher_steer.steer(KEY, "hi") is False
    assert await teacher_steer.steer(None, "hi") is False
    assert teacher_steer.turn_key("s", "m", "") is None


@pytest.mark.asyncio
async def test_settled_turn_refuses() -> None:
    class Client:
        def __init__(self) -> None:
            self.sent: list[str] = []

        async def steer(self, text: str) -> None:
            self.sent.append(text)

    client = Client()
    live = teacher_steer.register(KEY, client)
    try:
        assert await teacher_steer.steer(KEY, "x") is False  # not driving yet
        live.open = True
        assert await teacher_steer.steer(KEY, "  ") is False
        assert await teacher_steer.steer(KEY, "x") is True
        assert client.sent == ["x"] and live.pending == ["x"]
    finally:
        teacher_steer.unregister(KEY, live)
    assert KEY not in teacher_steer._LIVE


def test_steer_route(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.main import app
    from app.settings import Settings, get_settings

    got: list[tuple[Any, str]] = []

    async def fake_steer(key: Any, text: str) -> bool:
        got.append((key, text))
        return text == "live"

    monkeypatch.setattr(teacher_steer, "steer", fake_steer)
    settings = Settings(
        _env_file=None,
        pico_env="test",
        pico_openai_proxy_key="pico-dev",
        pico_accept_test_issuer=True,
    )
    app.dependency_overrides[get_settings] = lambda: settings
    try:
        client = TestClient(app)
        headers = {
            "Authorization": "Bearer pico-dev",
            "X-Pico-Membership-Id": "test-member",
            "X-Conversation-Id": "conv-9",
        }
        ok = client.post("/v1/chat/steer", headers=headers, json={"text": "live"})
        assert ok.status_code == 202 and ok.json() == {"steered": True}
        miss = client.post("/v1/chat/steer", headers=headers, json={"text": "idle"})
        assert miss.status_code == 409 and miss.json()["code"] == "steer.no_live_run"
        assert all(key and key[2] == "conv-9" for key, _ in got)
    finally:
        app.dependency_overrides.pop(get_settings, None)
