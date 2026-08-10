"""Phase-2 true-Pi: canary, default, rollback, history, R-matrix (FakeTransport)."""

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
from pico_orchestrator.runtime import run_agent_runtime
from pico_orchestrator.true_pi.client import FakeTransport
from pico_orchestrator.true_pi.config import (
    HOSTED_LOOP_ENV,
    TRUE_PI_CANARY_ENV,
    TRUE_PI_DEFAULT_ENV,
    canary_allows_principal,
    default_runtime_for_health,
    health_fields,
    should_use_true_pi,
)
from pico_orchestrator.true_pi.runtime import _compose_prompt, run_true_pi_agent


@dataclass
class Principal:
    school_id: str = "school-a"
    membership_id: str = "member-a"
    scopes: list[str] | None = None


async def _not_cancelled() -> bool:
    return False


async def _noop_emit(_k: str, _p: dict[str, Any]) -> None:
    return None


def test_canary_and_default_gates(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(HOSTED_LOOP_ENV, raising=False)
    monkeypatch.delenv(TRUE_PI_DEFAULT_ENV, raising=False)
    monkeypatch.delenv(TRUE_PI_CANARY_ENV, raising=False)
    monkeypatch.delenv("PICO_TRUE_PI_BYPASS", raising=False)

    assert should_use_true_pi(school_id="s", membership_id="m") is False
    assert default_runtime_for_health() == "pi-agent"

    monkeypatch.setenv(TRUE_PI_CANARY_ENV, "school-a:member-a")
    assert canary_allows_principal(school_id="school-a", membership_id="member-a") is True
    assert canary_allows_principal(school_id="school-a", membership_id="other") is False
    assert should_use_true_pi(school_id="school-a", membership_id="member-a") is True
    # Global default label still hosted when only canary
    assert default_runtime_for_health() == "pi-agent"

    monkeypatch.setenv(TRUE_PI_DEFAULT_ENV, "1")
    assert should_use_true_pi(school_id="x", membership_id="y") is True
    assert default_runtime_for_health() == "pi-true"

    monkeypatch.setenv(HOSTED_LOOP_ENV, "1")
    assert should_use_true_pi(school_id="school-a", membership_id="member-a") is False
    assert default_runtime_for_health() == "pi-agent"


def test_compose_prompt_includes_history_and_tools() -> None:
    text = _compose_prompt(
        prompt="写文件",
        skill="use workspace_write_file",
        min_arts=1,
        history=[
            {"role": "user", "content": "你好"},
            {"role": "assistant", "content": "您好"},
            {"role": "user", "content": "继续"},
        ],
        allowed_tools=["workspace_write_file", "generate_html_document"],
    )
    assert "workspace_write_file" in text
    assert "use workspace_write_file" in text
    assert "Recent conversation" in text
    assert "你好" in text
    assert "Landing requirement" in text


@pytest.mark.asyncio
async def test_r5_false_green_still_blocked() -> None:
    events: list[tuple[str, dict[str, Any]]] = []

    async def emit(k: str, p: dict[str, Any]) -> None:
        events.append((k, p))

    transport = FakeTransport(
        scripted=[
            {"type": "agent_start"},
            {
                "type": "message_end",
                "message": {"role": "assistant", "content": "已生成多文件。"},
            },
            {"type": "agent_settled"},
        ],
        assistant_text="已生成多文件。",
    )
    result = await run_true_pi_agent(
        prompt="多文件交付",
        principal=Principal(),
        emit=emit,
        is_cancelled=_not_cancelled,
        caps=RunCaps(min_artifacts=2, max_seconds=20),
        transport=transport,
    )
    assert result.status == "failed"


@pytest.mark.asyncio
async def test_r1_multi_file_scripted() -> None:
    scripted = [
        {"type": "agent_start"},
        {"type": "turn_start"},
    ]
    for i, title in enumerate(["a.md", "b.md", "c.md"], start=1):
        scripted.extend(
            [
                {
                    "type": "tool_execution_start",
                    "toolName": "workspace_write_file",
                    "toolCallId": f"w{i}",
                    "args": {"title": title, "content": "x"},
                },
                {
                    "type": "tool_execution_end",
                    "toolName": "workspace_write_file",
                    "toolCallId": f"w{i}",
                    "isError": False,
                    "result": {
                        "content": [{"type": "text", "text": f'{{"title":"{title}"}}'}]
                    },
                },
            ]
        )
    scripted.extend(
        [
            {
                "type": "message_end",
                "message": {"role": "assistant", "content": "三文件已落盘。"},
            },
            {"type": "agent_settled"},
        ]
    )
    transport = FakeTransport(scripted=scripted, assistant_text="三文件已落盘。")
    result = await run_true_pi_agent(
        prompt="三个独立文件",
        principal=Principal(),
        emit=_noop_emit,
        is_cancelled=_not_cancelled,
        caps=RunCaps(min_artifacts=3, max_seconds=30),
        transport=transport,
    )
    assert result.status == "succeeded"


@pytest.mark.asyncio
async def test_r7_hosted_rollback_dispatch(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(TRUE_PI_DEFAULT_ENV, "1")
    monkeypatch.setenv(HOSTED_LOOP_ENV, "1")
    calls: list[str] = []

    async def hosted(**_k: Any) -> RunResult:
        calls.append("hosted")
        return RunResult(status="succeeded", final_text="hosted")

    import pico_orchestrator.runtime as rt

    monkeypatch.setattr(rt, "_PI_IMPL", hosted)
    result = await run_agent_runtime(
        use_pi_agent=True,
        pi_agent_allow_all=True,
        principal=Principal(),
        prompt="hello",
        emit=_noop_emit,
        is_cancelled=_not_cancelled,
    )
    assert result.final_text == "hosted"
    assert calls == ["hosted"]


@pytest.mark.asyncio
async def test_default_dispatches_true_pi_when_flag(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(TRUE_PI_DEFAULT_ENV, "1")
    monkeypatch.delenv(HOSTED_LOOP_ENV, raising=False)
    # Patch availability + true path
    monkeypatch.setattr(
        "pico_orchestrator.true_pi.config.true_pi_available",
        lambda: True,
    )
    calls: list[str] = []

    async def true_impl(**_k: Any) -> RunResult:
        calls.append("true")
        return RunResult(status="succeeded", final_text="true")

    monkeypatch.setattr(
        "pico_orchestrator.true_pi.runtime.run_true_pi_agent",
        true_impl,
    )
    # Ensure _PI_IMPL is None so dispatch uses true path
    import pico_orchestrator.runtime as rt

    monkeypatch.setattr(rt, "_PI_IMPL", None)
    result = await run_agent_runtime(
        use_pi_agent=True,
        pi_agent_allow_all=True,
        principal=Principal(),
        prompt="hello",
        emit=_noop_emit,
        is_cancelled=_not_cancelled,
    )
    assert result.final_text == "true"
    assert calls == ["true"]


def test_health_fields_phase2(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(HOSTED_LOOP_ENV, raising=False)
    monkeypatch.setenv(TRUE_PI_DEFAULT_ENV, "1")
    hf = health_fields()
    assert hf["true_pi_default_enabled"] is True
    assert hf["true_pi_rollback_flag"] == HOSTED_LOOP_ENV
    assert hf["true_pi_phase"] == "p2-default"


def test_health_phase_hosted_rollback_overrides_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(TRUE_PI_DEFAULT_ENV, "1")
    monkeypatch.setenv(HOSTED_LOOP_ENV, "1")
    hf = health_fields()
    assert hf["true_pi_hosted_loop_forced"] is True
    assert hf["true_pi_default_enabled"] is True
    assert hf["true_pi_phase"] == "hosted-rollback"
    assert default_runtime_for_health() == "pi-agent"


def test_health_phase_canary_only(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(HOSTED_LOOP_ENV, raising=False)
    monkeypatch.delenv(TRUE_PI_DEFAULT_ENV, raising=False)
    monkeypatch.delenv("PICO_TRUE_PI_BYPASS", raising=False)
    monkeypatch.setenv(TRUE_PI_CANARY_ENV, "school-a:member-a")
    hf = health_fields()
    assert hf["true_pi_phase"] == "p2-canary"
    assert default_runtime_for_health() == "pi-agent"


def test_health_endpoint_default_runtime_true(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(TRUE_PI_DEFAULT_ENV, "1")
    monkeypatch.delenv(HOSTED_LOOP_ENV, raising=False)
    from app.main import app
    from fastapi.testclient import TestClient

    body = TestClient(app).get("/health").json()
    assert body["default_runtime"] == "pi-true"
    assert body["true_pi_default_enabled"] is True


def test_health_endpoint_default_stays_hosted_without_flag(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv(TRUE_PI_DEFAULT_ENV, raising=False)
    monkeypatch.delenv(HOSTED_LOOP_ENV, raising=False)
    monkeypatch.delenv("PICO_TRUE_PI_BYPASS", raising=False)
    from app.main import app
    from fastapi.testclient import TestClient

    body = TestClient(app).get("/health").json()
    assert body["default_runtime"] == "pi-agent"
