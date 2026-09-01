"""T-ASK-USER · park until the teacher picks."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "orchestrator"))

from pico_orchestrator.ask_user import ASK_TIMEOUT_SEC, answer, cancel, park, pending
from pico_orchestrator.capability_loading import CORE_VISIBLE_TOOLS
from pico_orchestrator.true_pi.config import ALLOWED_GATEWAY_TOOLS
from pico_orchestrator.true_pi.runtime import _hitl_ask_timed_out


def test_ask_timeout_is_three_minutes_not_ten() -> None:
    assert ASK_TIMEOUT_SEC == 180.0


def test_ask_user_is_core_visible() -> None:
    assert "ask_user" in CORE_VISIBLE_TOOLS
    assert "ask_user" in ALLOWED_GATEWAY_TOOLS


def test_pi_ask_user_does_not_quiz_collect_backend() -> None:
    ts = (ROOT / "services" / "true_pi_bridge" / "pico-gateway-tools.ts").read_text(
        encoding="utf-8"
    )
    assert "Do not use this to quiz about a third-party form backend" in ts
    assert "试卷" not in ts
    assert "Supabase" not in ts
    assert "DeepSeek official" not in ts


def test_system_identity_is_pico_never_backend_model() -> None:
    system = (ROOT / "services/orchestrator/pico_orchestrator/agent_assets/system.md").read_text(
        encoding="utf-8"
    )
    assert "You are **Pico**" in system
    assert "Never identify as any other model" in system
    assert "say Pico" in system


async def test_park_resolves_on_answer() -> None:
    events: list[tuple[str, dict]] = []

    async def emit(kind: str, payload: dict) -> None:
        events.append((kind, payload))

    async def picker() -> None:
        for _ in range(50):
            if pending("run-ask"):
                assert answer("run-ask", "解释一下")
                return
            await asyncio.sleep(0.01)
        raise AssertionError("never parked")

    parked, _ = await asyncio.gather(
        park("run-ask", "你想做什么？", ["解释一下", "改文件"], emit, timeout=2),
        picker(),
    )
    assert parked == {"ok": True, "answer": "解释一下", "question": "你想做什么？"}
    kinds = [item[0] for item in events]
    assert kinds == ["ui.prompt.begin", "ui.prompt.end"]
    assert events[0][1]["options"] == ["解释一下", "改文件"]
    assert pending("run-ask") is None


async def test_park_timeout_is_error_not_answer() -> None:
    events: list[tuple[str, dict]] = []

    async def emit(kind: str, payload: dict) -> None:
        events.append((kind, payload))

    out = await park(
        "run-to",
        "计划好了，下一步？",
        ["确认执行", "先不执行"],
        emit,
        timeout=0.05,
    )
    assert out["ok"] is False
    assert out["error"] == "timeout"
    kinds = [item[0] for item in events]
    assert "ui.prompt.begin" in kinds
    assert events[-1][0] == "ui.prompt.end"
    assert events[-1][1]["text"] == "超时未选"
    assert pending("run-to") is None


async def test_park_rejects_one_option() -> None:
    out = await park("run-bad", "?", ["only"], None)
    assert out["ok"] is False
    assert pending("run-bad") is None


def test_hitl_timeout_flag_covers_tool_ask() -> None:
    assert _hitl_ask_timed_out(type("T", (), {})()) is False
    assert _hitl_ask_timed_out(type("T", (), {"ask_timed_out": True})()) is True
    assert _hitl_ask_timed_out(type("T", (), {"plan_ask_timed_out": True})()) is True


async def test_ask_user_timeout_is_http_409_not_200() -> None:
    from unittest.mock import AsyncMock, patch

    from pico_orchestrator.tools_builtin import build_default_gateway
    from pico_orchestrator.true_pi.tool_server import ToolServer

    class _Store:
        async def write(self, principal, *, title, content, kind):
            return {"title": title, "kind": kind}

        async def read(self, principal, *, artifact_id, title):
            return None

        async def list(self, principal, *, limit):
            return []

    class _Principal:
        def __init__(self) -> None:
            self.school_id = "school-a"
            self.membership_id = "member-a"
            self.scopes = ["ai:run"]

    hooks: list[bool] = []
    server = ToolServer(
        principal=_Principal(),
        gateway=build_default_gateway(_Store()),  # type: ignore[arg-type]
        run_id="ask-409",
    )
    server.ask_timeout_hook = lambda: hooks.append(True)
    parked = {"ok": False, "error": "timeout"}
    await server.start()
    try:
        import json as _json

        with patch("pico_orchestrator.ask_user.park", AsyncMock(return_value=parked)):
            reader, writer = await asyncio.open_connection("127.0.0.1", server.port)
            body = _json.dumps(
                {"tool": "ask_user", "arguments": {"question": "哪一步？", "options": ["A", "B"]}}
            ).encode()
            req = (
                f"POST /v1/tool HTTP/1.1\r\n"
                f"Host: 127.0.0.1\r\n"
                f"Authorization: Bearer {server.token}\r\n"
                f"Content-Type: application/json\r\n"
                f"Content-Length: {len(body)}\r\n"
                f"Connection: close\r\n\r\n"
            ).encode() + body
            writer.write(req)
            await writer.drain()
            data = await reader.read(65536)
            writer.close()
            await writer.wait_closed()
        header, _, rest = data.partition(b"\r\n\r\n")
        status = int(header.split()[1])
        payload = _json.loads(rest.decode() or "{}")
    finally:
        await server.stop()

    assert status == 409
    assert payload.get("ok") is False
    assert payload.get("code") == "ask.timeout"
    assert server.ask_timed_out is True
    assert hooks


async def test_cancel_drops_pending() -> None:
    async def emit(_kind: str, _payload: dict) -> None:
        return

    task = asyncio.create_task(
        park("run-cancel", "还做吗？", ["继续", "停下"], emit, timeout=2)
    )
    for _ in range(50):
        if pending("run-cancel"):
            break
        await asyncio.sleep(0.01)
    cancel("run-cancel")
    try:
        await task
    except asyncio.CancelledError:
        pass
    assert pending("run-cancel") is None
