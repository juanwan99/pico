"""P1 matrix for true-Pi thin bridge + shadow (T-PACK-PI-TRUE-KERNEL-P1).

Uses FakeTransport — no real pi binary required for CI.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "api"))
sys.path.insert(0, str(ROOT / "services" / "orchestrator"))

from pico_orchestrator.run_types import RunCaps, RunResult
from pico_orchestrator.runtime import run_agent_runtime, should_use_pi_agent
from pico_orchestrator.true_pi.client import FakeTransport, scripted_open_domain_success
from pico_orchestrator.true_pi.config import (
    ALLOWED_GATEWAY_TOOLS,
    RUNTIME_LABEL,
    health_fields,
    shadow_enabled,
)
from pico_orchestrator.true_pi.events import EventMapState, map_event
from pico_orchestrator.true_pi.runtime import run_true_pi_agent
from pico_orchestrator.true_pi.shadow import maybe_shadow_after_hosted, shadow_diff
from pico_orchestrator.true_pi.tool_server import ToolServer


@dataclass
class Principal:
    school_id: str = "school-a"
    membership_id: str = "member-a"
    scopes: list[str] | None = None


async def _not_cancelled() -> bool:
    return False


@pytest.mark.asyncio
async def test_p1_t1_open_domain_write_and_tools() -> None:
    """P1-T1: open domain ≥1 real write tool event · gate ok."""
    events: list[tuple[str, dict[str, Any]]] = []

    async def emit(kind: str, payload: dict[str, Any]) -> None:
        events.append((kind, payload))

    transport = FakeTransport(
        scripted=scripted_open_domain_success(),
        assistant_text="已写入 notes.md，请下载。",
    )
    result = await run_true_pi_agent(
        prompt="写一个可下载的 notes.md，内容 hello",
        principal=Principal(),
        emit=emit,
        is_cancelled=_not_cancelled,
        caps=RunCaps(min_artifacts=1, max_seconds=30, max_steps=8),
        transport=transport,
        run_id="p1-t1",
    )
    assert result.status == "succeeded"
    kinds = [k for k, _ in events]
    assert "tool.call" in kinds
    assert "tool.result" in kinds
    assert any(
        p.get("runtime") == RUNTIME_LABEL for k, p in events if k == "run.status"
    )
    assert any(
        p.get("tool") == "workspace_write_file" for k, p in events if k == "tool.call"
    )


@pytest.mark.asyncio
async def test_p1_t2_html_person_page() -> None:
    """P1-T2: HTML path uses generate_html_document tool events."""
    events: list[tuple[str, dict[str, Any]]] = []

    async def emit(kind: str, payload: dict[str, Any]) -> None:
        events.append((kind, payload))

    scripted = [
        {"type": "agent_start"},
        {"type": "turn_start"},
        {
            "type": "tool_execution_start",
            "toolName": "generate_html_document",
            "toolCallId": "h1",
            "args": {"title": "page.html", "body": "<html><body>hi</body></html>"},
        },
        {
            "type": "tool_execution_end",
            "toolName": "generate_html_document",
            "toolCallId": "h1",
            "isError": False,
            "result": {
                "content": [
                    {
                        "type": "text",
                        "text": '{"title":"page.html","kind":"html"}',
                    }
                ]
            },
        },
        {
            "type": "tool_execution_start",
            "toolName": "verify_html_document",
            "toolCallId": "h2",
            "args": {"title": "page.html"},
        },
        {
            "type": "tool_execution_end",
            "toolName": "verify_html_document",
            "toolCallId": "h2",
            "isError": False,
            "result": {"content": [{"type": "text", "text": '{"overall":"ok"}'}]},
        },
        {
            "type": "message_end",
            "message": {
                "role": "assistant",
                "content": "人页 page.html 已生成，请打开下载。",
            },
        },
        {"type": "agent_settled"},
    ]
    transport = FakeTransport(
        scripted=scripted,
        assistant_text="人页 page.html 已生成，请打开下载。",
    )
    result = await run_true_pi_agent(
        prompt="做一个可打开的 HTML 人页",
        principal=Principal(),
        emit=emit,
        is_cancelled=_not_cancelled,
        caps=RunCaps(min_artifacts=1, max_seconds=30),
        transport=transport,
    )
    assert result.status == "succeeded"
    tools = [p.get("tool") for k, p in events if k == "tool.call"]
    assert "generate_html_document" in tools
    assert "verify_html_document" in tools


@pytest.mark.asyncio
async def test_p1_t3_cancel() -> None:
    """P1-T3: cancel before settle · default path unpolluted (hosted separate)."""

    async def always_cancelled() -> bool:
        return True

    events: list[tuple[str, dict[str, Any]]] = []

    async def emit(kind: str, payload: dict[str, Any]) -> None:
        events.append((kind, payload))

    # No events needed — cancelled before prompt consumption.
    transport = FakeTransport(scripted=[], assistant_text="")
    result = await run_true_pi_agent(
        prompt="long task",
        principal=Principal(),
        emit=emit,
        is_cancelled=always_cancelled,
        caps=RunCaps(max_seconds=30),
        transport=transport,
    )
    assert result.status == "cancelled"
    assert any(p.get("status") == "cancelled" for k, p in events if k == "run.status")


@pytest.mark.asyncio
async def test_p1_t3_timeout() -> None:
    """P1-T3 alt: timeout when agent never settles."""
    events: list[tuple[str, dict[str, Any]]] = []

    async def emit(kind: str, payload: dict[str, Any]) -> None:
        events.append((kind, payload))

    # agent_start only — never agent_settled
    transport = FakeTransport(
        scripted=[{"type": "agent_start"}],
        assistant_text="",
    )
    result = await run_true_pi_agent(
        prompt="hang",
        principal=Principal(),
        emit=emit,
        is_cancelled=_not_cancelled,
        caps=RunCaps(max_seconds=1, max_steps=2),
        transport=transport,
    )
    assert result.status == "failed"
    assert result.error is not None
    assert "timeout" in (result.error or "").lower() or any(
        p.get("code") == "timeout" for k, p in events if k == "run.status"
    )


@pytest.mark.asyncio
async def test_p1_t4_false_green_blocked() -> None:
    """P1-T4: min≥2 wording must not succeed with 0 write tools."""
    events: list[tuple[str, dict[str, Any]]] = []

    async def emit(kind: str, payload: dict[str, Any]) -> None:
        events.append((kind, payload))

    scripted = [
        {"type": "agent_start"},
        {
            "type": "message_end",
            "message": {
                "role": "assistant",
                "content": "已生成两个文件 a.md 和 b.md，请下载。",
            },
        },
        {"type": "agent_settled"},
    ]
    transport = FakeTransport(
        scripted=scripted,
        assistant_text="已生成两个文件 a.md 和 b.md，请下载。",
    )
    result = await run_true_pi_agent(
        prompt="请分别落盘两个独立文件",
        principal=Principal(),
        emit=emit,
        is_cancelled=_not_cancelled,
        caps=RunCaps(min_artifacts=2, max_seconds=20),
        transport=transport,
    )
    assert result.status == "failed"
    assert any(
        p.get("code") == "delivery.missing_artifact"
        for k, p in events
        if k in {"run.status", "run.error"}
    )


@pytest.mark.asyncio
async def test_p1_t5_default_path_unchanged_when_shadow_off(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """P1-T5: without shadow flag, dispatch remains hosted pi-agent."""
    monkeypatch.delenv("PICO_TRUE_PI_SHADOW", raising=False)
    assert shadow_enabled() is False
    assert should_use_pi_agent(use_pi_agent=True, pi_agent_allow_all=True) is True

    calls: list[str] = []

    async def pi_loop(**_kwargs: Any) -> RunResult:
        calls.append("hosted")
        return RunResult(status="succeeded", final_text="hosted-ok")

    async def noop_emit(_k: str, _p: dict[str, Any]) -> None:
        return None

    import pico_orchestrator.runtime as rt

    monkeypatch.setattr(rt, "_PI_IMPL", pi_loop)
    result = await run_agent_runtime(
        use_pi_agent=True,
        pi_agent_allow_all=True,
        principal=Principal(),
        prompt="hello",
        emit=noop_emit,
        is_cancelled=_not_cancelled,
    )
    assert result.status == "succeeded"
    assert result.final_text == "hosted-ok"
    assert calls == ["hosted"]

    hf = health_fields()
    # No DEFAULT/CANARY/SHADOW/HOSTED → idle (not a fake p1-shadow label)
    assert hf["true_pi_phase"] == "idle"
    assert hf["true_pi_shadow_enabled"] is False


def test_bridge_allowlist_is_thin() -> None:
    assert "bash" not in ALLOWED_GATEWAY_TOOLS
    assert "workspace_write_file" in ALLOWED_GATEWAY_TOOLS
    assert "web_search" in ALLOWED_GATEWAY_TOOLS
    assert "web_fetch" in ALLOWED_GATEWAY_TOOLS
    assert "kb_search" in ALLOWED_GATEWAY_TOOLS
    assert "sandbox_preview_inspect" in ALLOWED_GATEWAY_TOOLS
    assert "sandbox_browser_open" in ALLOWED_GATEWAY_TOOLS
    assert "sandbox_document_open" in ALLOWED_GATEWAY_TOOLS
    assert "edit_docx_document" in ALLOWED_GATEWAY_TOOLS
    assert "edit_pptx_document" in ALLOWED_GATEWAY_TOOLS
    assert "generate_image" in ALLOWED_GATEWAY_TOOLS
    assert len(ALLOWED_GATEWAY_TOOLS) == 18


def test_shadow_diff_flags_false_green() -> None:
    report = shadow_diff(
        hosted_status="succeeded",
        shadow_status="succeeded",
        hosted_events=[
            ("tool.call", {}),
            ("tool.result", {}),
            ("run.status", {"status": "succeeded"}),
        ],
        shadow_events=[("run.status", {"status": "succeeded"})],
        hosted_writes=1,
        shadow_writes=0,
    )
    assert report.ok_for_phase1 is False
    assert any("without_tool" in n or "without_writes" in n for n in report.notes)


@pytest.mark.asyncio
async def test_shadow_force_with_fake(tmp_path: Path) -> None:
    hosted = RunResult(status="succeeded", final_text="hosted")
    transport = FakeTransport(
        scripted=scripted_open_domain_success(),
        assistant_text="shadow notes",
    )
    report = await maybe_shadow_after_hosted(
        prompt="写 notes.md",
        principal=Principal(),
        hosted_result=hosted,
        caps=RunCaps(min_artifacts=1, max_seconds=20),
        transport=transport,
        report_dir=tmp_path,
        force=True,
    )
    assert report is not None
    assert report.shadow_status == "succeeded"
    assert (tmp_path / f"{report.run_id}.json").is_file()


@pytest.mark.asyncio
async def test_tool_server_denies_bash() -> None:
    from pico_orchestrator.tools_builtin import build_default_gateway

    class MemStore:
        async def write(self, principal, *, title, content, kind):
            return {"title": title, "kind": kind}

        async def read(self, principal, *, artifact_id, title):
            return None

        async def list(self, principal, *, limit):
            return []

    gw = build_default_gateway(MemStore())  # type: ignore[arg-type]
    server = ToolServer(principal=Principal(), gateway=gw, run_id="deny-test")
    await server.start()
    try:
        # Manual HTTP via asyncio
        import asyncio
        import json as _json

        async def post(tool: str) -> tuple[int, dict]:
            reader, writer = await asyncio.open_connection("127.0.0.1", server.port)
            body = _json.dumps({"tool": tool, "arguments": {"command": "id"}}).encode()
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
            return status, _json.loads(rest.decode() or "{}")

        status, payload = await post("bash")
        assert status == 403
        assert payload.get("ok") is False
        assert payload.get("code") == "tool.not_allowlisted"

        search_status, search_payload = await post("web_search")
        assert search_status == 400
        assert search_payload.get("code") == "tool.invalid_arguments"
        assert search_payload.get("code") != "tool.not_allowlisted"

        fetch_body_status, fetch_payload = await post("web_fetch")
        assert fetch_body_status == 400
        assert fetch_payload.get("code") == "tool.invalid_arguments"
    finally:
        await server.stop()


@pytest.mark.asyncio
async def test_event_map_tool_and_status() -> None:
    events: list[tuple[str, dict[str, Any]]] = []

    async def emit(kind: str, payload: dict[str, Any]) -> None:
        events.append((kind, payload))

    state = EventMapState()
    from pico_orchestrator.true_pi.client import RpcEvent

    await map_event(RpcEvent({"type": "agent_start"}), emit=emit, state=state)
    await map_event(
        RpcEvent(
            {
                "type": "tool_execution_start",
                "toolName": "workspace_write_file",
                "toolCallId": "x",
                "args": {"title": "a.md"},
            }
        ),
        emit=emit,
        state=state,
    )
    await map_event(
        RpcEvent(
            {
                "type": "tool_execution_end",
                "toolName": "workspace_write_file",
                "toolCallId": "x",
                "isError": False,
                "result": {"content": [{"type": "text", "text": '{"title":"a.md"}'}]},
            }
        ),
        emit=emit,
        state=state,
    )
    await map_event(RpcEvent({"type": "agent_settled"}), emit=emit, state=state)
    assert state.settled is True
    assert state.tool_results[0][0] == "workspace_write_file"
    kinds = [k for k, _ in events]
    assert kinds == ["run.status", "tool.call", "tool.result", "agent.settled"]


def test_health_endpoint_includes_true_pi_fields() -> None:
    from app.main import app
    from fastapi.testclient import TestClient

    body = TestClient(app).get("/health").json()
    assert body["default_runtime"] == "pi-agent"
    assert body["true_pi_phase"] == "idle"
    assert "true_pi_shadow_enabled" in body
    assert body["true_pi_runtime_label"] == "pi-true"
