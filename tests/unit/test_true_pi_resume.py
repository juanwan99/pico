"""Same-session resume (#1104): one upstream error mid-run must not fail the task.

Round 3 of longtask-eval (2026-09-29): LT3/LT4/LT6 died on a single
``content_filter`` / ``Stream ended without finish_reason`` after the model
had already written most of the files. Pi keeps the turn in its session, so
Pico re-prompts the same process to carry on instead of failing.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "api"))
sys.path.insert(0, str(ROOT / "services" / "orchestrator"))

from pico_orchestrator.run_types import RunCaps
from pico_orchestrator.true_pi.client import (
    PI_RETRY_MAX,
    FakeTransport,
    official_compaction_settings,
)
from pico_orchestrator.true_pi.config import resume_max
from pico_orchestrator.true_pi.runtime import run_true_pi_agent

_CUT = "Stream ended without finish_reason"


class Principal:
    def __init__(self) -> None:
        self.school_id = "school-a"
        self.membership_id = "member-a"
        self.scopes = ["ai:run"]


async def _not_cancelled() -> bool:
    return False


def _error_turn(msg: str = _CUT) -> dict[str, Any]:
    return {"role": "assistant", "content": [], "stopReason": "error", "errorMessage": msg}


def _write_events() -> list[dict[str, Any]]:
    return [
        {
            "type": "tool_execution_start",
            "toolName": "workspace_write_file",
            "toolCallId": "c1",
            "args": {"title": "a.md", "content": "part 1"},
        },
        {
            "type": "tool_execution_end",
            "toolName": "workspace_write_file",
            "toolCallId": "c1",
            "isError": False,
            "result": {"content": [{"type": "text", "text": '{"title":"a.md"}'}]},
        },
    ]


def _error_after_work(msg: str = _CUT, **agent_end: Any) -> list[dict[str, Any]]:
    return [
        {"type": "agent_start"},
        {"type": "turn_start"},
        *_write_events(),
        {"type": "message_end", "message": _error_turn(msg)},
        {"type": "agent_end", "willRetry": False, "messages": [], **agent_end},
    ]


def _error_after_work_with_trailing_settle() -> list[dict[str, Any]]:
    """Pi 0.84 shape on prod: agent_end (retries exhausted) then agent_settled."""
    return [*_error_after_work(), {"type": "agent_settled"}]


def _error_before_work() -> list[dict[str, Any]]:
    return [
        {"type": "agent_start"},
        {"type": "turn_start"},
        {"type": "message_end", "message": _error_turn()},
        {"type": "agent_end", "willRetry": False, "messages": []},
    ]


def _finish() -> list[dict[str, Any]]:
    done = {"role": "assistant", "content": [{"type": "text", "text": "已补齐 a.md。"}]}
    return [
        {"type": "agent_start"},
        {"type": "turn_start"},
        {"type": "message_end", "message": done},
        {"type": "turn_end", "message": done},
        {"type": "agent_end", "willRetry": False, "messages": []},
    ]


async def _run(transport: FakeTransport, events: list[tuple[str, dict[str, Any]]]):
    async def emit(kind: str, payload: dict[str, Any]) -> None:
        events.append((kind, payload))

    return await run_true_pi_agent(
        prompt="做一份长报告",
        principal=Principal(),
        emit=emit,
        is_cancelled=_not_cancelled,
        caps=RunCaps(min_artifacts=0, max_seconds=30),
        transport=transport,
        run_id="resume-t",
    )


def _prompts(transport: FakeTransport) -> list[str]:
    return [str(c.get("message") or "") for c in transport.sent if c.get("type") == "prompt"]


@pytest.mark.asyncio
async def test_error_after_output_resumes_same_session_and_succeeds() -> None:
    events: list[tuple[str, dict[str, Any]]] = []
    transport = FakeTransport(
        scripted=_error_after_work(), scripted_after_prompt=[_finish()], assistant_text=""
    )
    result = await _run(transport, events)
    assert result.status == "succeeded", result.error
    prompts = _prompts(transport)
    assert len(prompts) == 2
    assert "继续" in prompts[1] and _CUT in prompts[1]
    assert "不要重做" in prompts[1]
    resumes = [p for k, p in events if k == "run.resume"]
    assert resumes and resumes[0]["attempt"] == 1 and resumes[0]["reason"] == _CUT
    assert any("续跑" in str(p.get("text")) for k, p in events if k == "message.delta")
    assert [k for k, _ in events if k == "run.status"][-1:] == ["run.status"]
    assert [p["status"] for k, p in events if k == "run.status"][-1] == "succeeded"
    assert not any(k == "run.error" for k, _ in events)


@pytest.mark.asyncio
async def test_error_before_any_output_does_not_resume() -> None:
    """Pre-output failures stay with brain-HA failover (another model, fresh start)."""
    events: list[tuple[str, dict[str, Any]]] = []
    transport = FakeTransport(scripted=_error_before_work(), scripted_after_prompt=[_finish()])
    result = await _run(transport, events)
    assert result.status == "failed"
    assert len(_prompts(transport)) == 1
    assert not any(k == "run.resume" for k, _ in events)


@pytest.mark.asyncio
async def test_resume_budget_exhausted_fails_honestly(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PICO_RUN_RESUME_MAX", "2")
    assert resume_max() == 2
    events: list[tuple[str, dict[str, Any]]] = []
    transport = FakeTransport(
        scripted=_error_after_work(),
        scripted_after_prompt=[_error_after_work("content_filter"), _error_after_work("503")],
        assistant_text="",
    )
    result = await _run(transport, events)
    assert result.status == "failed"
    assert len(_prompts(transport)) == 3
    attempts = [p["attempt"] for k, p in events if k == "run.resume"]
    assert attempts == [1, 2]
    fail = [p for k, p in events if k == "run.error"]
    assert fail and fail[-1]["code"] == "true_pi.assistant_error"
    assert "503" in str(fail[-1]["error"])


@pytest.mark.asyncio
async def test_resume_off_keeps_old_fail_on_first_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PICO_RUN_RESUME_MAX", "0")
    events: list[tuple[str, dict[str, Any]]] = []
    transport = FakeTransport(scripted=_error_after_work(), scripted_after_prompt=[_finish()])
    result = await _run(transport, events)
    assert result.status == "failed"
    assert len(_prompts(transport)) == 1


@pytest.mark.asyncio
async def test_runner_limit_error_is_not_resumed() -> None:
    """The box is being killed (runner.limit): nothing to prompt."""
    events: list[tuple[str, dict[str, Any]]] = []
    transport = FakeTransport(
        scripted=_error_after_work("workspace over 2048MB", runnerCode="runner.limit"),
        scripted_after_prompt=[_finish()],
    )
    result = await _run(transport, events)
    assert result.status == "failed"
    assert len(_prompts(transport)) == 1


@pytest.mark.asyncio
async def test_usage_limit_is_not_resumed() -> None:
    events: list[tuple[str, dict[str, Any]]] = []
    transport = FakeTransport(
        scripted=_error_after_work("The usage limit has been reached"),
        scripted_after_prompt=[_finish()],
    )
    result = await _run(transport, events)
    assert result.status == "failed"
    assert len(_prompts(transport)) == 1
    fail = [p for k, p in events if k == "run.error"]
    assert fail[-1]["code"] == "model.usage_limit"


def test_pi_settings_carry_retry_knobs() -> None:
    blob = official_compaction_settings(256_000)
    assert blob["retry"]["enabled"] is True
    assert blob["retry"]["maxRetries"] == PI_RETRY_MAX >= 3
    assert blob["retry"]["baseDelayMs"] >= 2_000
    assert blob["httpIdleTimeoutMs"] == 900_000


def test_resume_max_default_and_clamp(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("PICO_RUN_RESUME_MAX", raising=False)
    assert resume_max() == 3
    monkeypatch.setenv("PICO_RUN_RESUME_MAX", "99")
    assert resume_max() == 10
    monkeypatch.setenv("PICO_RUN_RESUME_MAX", "x")
    assert resume_max() == 3


@pytest.mark.asyncio
async def test_stale_settle_from_failed_turn_does_not_end_the_resumed_turn() -> None:
    """Prod run 2fb28c1a (#1104): the leftover agent_settled made the resume a blank success."""
    events: list[tuple[str, dict[str, Any]]] = []
    transport = FakeTransport(
        scripted=_error_after_work_with_trailing_settle(),
        scripted_after_prompt=[_finish()],
        assistant_text="",
    )
    result = await _run(transport, events)
    assert result.status == "succeeded", result.error
    assert len(_prompts(transport)) == 2
    # The resumed turn really ran: a new agent step after run.resume.
    kinds = [k for k, _ in events]
    assert kinds.index("run.resume") < len(kinds) - 1 - kinds[::-1].index("agent.step")
    assert [p["status"] for k, p in events if k == "run.status"][-1] == "succeeded"


@pytest.mark.asyncio
async def test_resume_with_no_new_turn_is_not_a_success() -> None:
    """Box gone / prompt ignored after resume: fail honestly, never blank green."""
    events: list[tuple[str, dict[str, Any]]] = []
    transport = FakeTransport(
        scripted=_error_after_work_with_trailing_settle(),
        scripted_after_prompt=[[]],
        assistant_text="",
    )

    async def emit(kind: str, payload: dict[str, Any]) -> None:
        events.append((kind, payload))

    async def run_it():
        return await run_true_pi_agent(
            prompt="做一份长报告",
            principal=Principal(),
            emit=emit,
            is_cancelled=_not_cancelled,
            caps=RunCaps(min_artifacts=0, max_seconds=3),
            transport=transport,
            run_id="resume-t2",
        )

    import asyncio

    task = asyncio.create_task(run_it())
    await asyncio.sleep(0.3)
    await transport.close()  # stream ends with no new turn
    result = await task
    assert result.status == "failed"
    fail = [p for k, p in events if k == "run.error"]
    assert fail and "no new turn" in str(fail[-1]["error"])


def _retry_start(msg: str, attempt: int = 1) -> dict[str, Any]:
    return {
        "type": "auto_retry_start",
        "attempt": attempt,
        "maxAttempts": PI_RETRY_MAX,
        "delayMs": 3000,
        "errorMessage": msg,
    }


_OVERLOADED = '503: {"message":"system cpu overloaded (current: 100.0%, threshold: 90%)"}'
_NO_CHANNEL = "503 No available channel for model gemini-3.8-flash under group default"


@pytest.mark.asyncio
async def test_overload_retry_is_logged_and_waited_out() -> None:
    """New API sheds load with 503 for minutes (#1135); Pi retries, the run lives."""
    events: list[tuple[str, dict[str, Any]]] = []
    finish = _finish()
    transport = FakeTransport(
        scripted=[*finish[:2], _retry_start(_OVERLOADED), _retry_start(_OVERLOADED, 2), *finish[2:]],
        assistant_text="已补齐 a.md。",
    )
    result = await _run(transport, events)
    assert result.status == "succeeded", result.error
    retries = [p for k, p in events if k == "model.retry"]
    assert [p["attempt"] for p in retries] == [1, 2]
    assert retries[0]["max_retries"] == PI_RETRY_MAX
    assert "overloaded" in retries[0]["error"]
    assert not any(k == "run.error" for k, _ in events)


@pytest.mark.asyncio
async def test_dead_channel_fails_over_without_waiting_out_retries() -> None:
    """No channel for the model: retrying cannot help, hand over to brain-HA at once."""
    from pico_orchestrator.brain_ha import should_failover

    events: list[tuple[str, dict[str, Any]]] = []
    transport = FakeTransport(scripted=[*_finish()[:2], _retry_start(_NO_CHANNEL)])
    result = await _run(transport, events)
    assert result.status == "failed"
    assert should_failover(result)
    assert any(c.get("type") == "abort" for c in transport.sent)
    fail = [p for k, p in events if k == "run.error"]
    assert fail[-1]["code"] == "model.unconfigured"


@pytest.mark.asyncio
async def test_dead_channel_after_output_keeps_retrying() -> None:
    """Mid-task there is no failover (the teacher saw output); let Pi keep trying."""
    events: list[tuple[str, dict[str, Any]]] = []
    finish = _finish()
    transport = FakeTransport(
        scripted=[*finish[:2], *_write_events(), _retry_start(_NO_CHANNEL), *finish[2:]],
        assistant_text="已补齐 a.md。",
    )
    result = await _run(transport, events)
    assert result.status == "succeeded", result.error
    assert not any(c.get("type") == "abort" for c in transport.sent)
