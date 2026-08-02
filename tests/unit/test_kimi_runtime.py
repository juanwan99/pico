from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any, Self

import pytest
from app.settings import Settings
from kimi_agent_sdk import (
    RunCancelled,
    StatusUpdate,
    StepBegin,
    TextPart,
    TokenUsage,
    ToolCall,
    ToolCallPart,
    ToolOk,
    ToolResult,
    TurnBegin,
    TurnEnd,
)
from pico_orchestrator.gateway import AllowlistGateway, ToolSpec
from pico_orchestrator.kimi_tools import (
    EchoParams,
    FakeEduListClasses,
    ListClassesParams,
    PicoEcho,
    bind_gateway_tools,
)
from pico_orchestrator.provider import ProviderConfig
from pico_orchestrator.runner import RunCaps, RunResult
from pico_orchestrator.runtime import run_agent_runtime


@dataclass
class Principal:
    school_id: str = "school-a"
    membership_id: str = "member-a"
    scopes: list[str] | None = None


async def _not_cancelled() -> bool:
    return False


async def _emit_to(events: list[tuple[str, dict[str, Any]]], kind: str, payload: dict[str, Any]) -> None:
    events.append((kind, payload))


@pytest.mark.asyncio
async def test_runtime_canary_gate_is_fail_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []

    async def old_loop(**_kwargs: Any) -> RunResult:
        calls.append("old")
        return RunResult(status="succeeded", final_text="old")

    async def kimi_loop(**_kwargs: Any) -> RunResult:
        calls.append("kimi")
        return RunResult(status="succeeded", final_text="kimi")

    monkeypatch.setattr("pico_orchestrator.runner.run_agent_loop", old_loop)
    monkeypatch.setattr("pico_orchestrator.kimi_runtime.run_kimi_agent", kimi_loop)

    principal = Principal()
    gate_off = await run_agent_runtime(
        use_kimi_agent=False,
        kimi_agent_canary_membership_ids={principal.membership_id},
        principal=principal,
        prompt="hello",
    )
    not_allowlisted = await run_agent_runtime(
        use_kimi_agent=True,
        kimi_agent_canary_membership_ids={"member-b"},
        principal=principal,
        prompt="hello",
    )
    allowlisted = await run_agent_runtime(
        use_kimi_agent=True,
        kimi_agent_canary_membership_ids={principal.membership_id},
        principal=principal,
        prompt="hello",
    )

    assert (gate_off.final_text, not_allowlisted.final_text, allowlisted.final_text) == (
        "old",
        "old",
        "kimi",
    )
    assert calls == ["old", "old", "kimi"]


def test_settings_flag_is_false_by_default_and_explicitly_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("PICO_KIMI_AGENT_RUNTIME", raising=False)
    monkeypatch.delenv("PICO_KIMI_AGENT_CANARY_MEMBERSHIP_IDS", raising=False)
    defaults = Settings(_env_file=None)
    assert defaults.pico_kimi_agent_runtime is False
    assert defaults.kimi_agent_canary_membership_id_set == frozenset()

    monkeypatch.setenv("PICO_KIMI_AGENT_RUNTIME", "1")
    monkeypatch.setenv(
        "PICO_KIMI_AGENT_CANARY_MEMBERSHIP_IDS",
        " member-a,member-b,member-a ",
    )
    enabled = Settings(_env_file=None)
    assert enabled.pico_kimi_agent_runtime is True
    assert enabled.kimi_agent_canary_membership_id_set == {"member-a", "member-b"}


@pytest.mark.asyncio
async def test_kimi_path_maps_mock_session_without_network(monkeypatch: pytest.MonkeyPatch) -> None:
    from pico_orchestrator import kimi_runtime

    created: dict[str, Any] = {}
    prompt_options: dict[str, Any] = {}

    class FakeSession:
        async def __aenter__(self) -> Self:
            return self

        async def __aexit__(self, *_args: object) -> None:
            return None

        async def prompt(self, user_input: str, **kwargs: Any):
            prompt_options.update(user_input=user_input, **kwargs)
            yield TurnBegin(user_input=user_input)
            yield StepBegin(n=1)
            yield TextPart(text="hello from Kimi")
            yield StepBegin(n=2)
            yield TurnEnd()

        def cancel(self) -> None:
            raise AssertionError("cancel should not be called")

    async def create(**kwargs: Any) -> FakeSession:
        agent_file = kwargs["agent_file"]
        assert agent_file.is_absolute()
        assert agent_file.parent.name == "agent"
        assert "system_prompt_path: ./system.md" in agent_file.read_text()
        assert (agent_file.parent / "system.md").read_text()
        created.update(kwargs)
        return FakeSession()

    monkeypatch.setattr(kimi_runtime.Session, "create", create)
    monkeypatch.setattr(
        kimi_runtime,
        "resolve_provider",
        lambda: ProviderConfig("kimi", "test-only", "https://example.invalid/v1", "kimi-test"),
    )
    events: list[tuple[str, dict[str, Any]]] = []

    result = await kimi_runtime.run_kimi_agent(
        prompt="hello",
        principal=Principal(),
        emit=lambda kind, payload: _emit_to(events, kind, payload),
        is_cancelled=_not_cancelled,
        caps=RunCaps(max_seconds=5, max_steps=2),
    )

    assert result.status == "succeeded"
    assert result.final_text == "hello from Kimi"
    assert prompt_options["merge_wire_messages"] is True
    assert created["yolo"] is False
    assert created["mcp_configs"] == []
    assert created["agent_file"].name == "pico-kimi-runtime.yaml"
    assert events == [
        ("run.status", {"status": "running", "runtime": "kimi-agent"}),
        ("agent.step", {"step": 1, "phase": "model"}),
        ("message.delta", {"text": "hello from Kimi"}),
        ("agent.step", {"step": 2, "phase": "model"}),
        ("run.status", {"status": "succeeded", "runtime": "kimi-agent"}),
    ]


@pytest.mark.asyncio
async def test_kimi_path_completes_split_tool_call_without_contract_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from pico_orchestrator import kimi_runtime

    class PartialToolSession:
        async def __aenter__(self) -> Self:
            return self

        async def __aexit__(self, *_args: object) -> None:
            return None

        async def prompt(self, user_input: str, **_kwargs: Any):
            yield TurnBegin(user_input=user_input)
            yield ToolCall(
                id="split-call",
                function=ToolCall.FunctionBody(
                    name="calculator", arguments=None
                ),
            )
            yield ToolCallPart(arguments_part='{"expression":"6 * 7"}')
            yield ToolResult(
                tool_call_id="split-call", return_value=ToolOk(output="42")
            )
            yield TextPart(text="42")
            yield TurnEnd()

        def cancel(self) -> None:
            raise AssertionError("cancel should not be called")

    async def create(**_kwargs: Any) -> PartialToolSession:
        return PartialToolSession()

    monkeypatch.setattr(kimi_runtime.Session, "create", create)
    monkeypatch.setattr(
        kimi_runtime,
        "resolve_provider",
        lambda: ProviderConfig(
            "kimi", "test-only", "https://example.invalid/v1", "kimi-test"
        ),
    )
    events: list[tuple[str, dict[str, Any]]] = []

    result = await kimi_runtime.run_kimi_agent(
        prompt="calculate",
        principal=Principal(),
        emit=lambda kind, payload: _emit_to(events, kind, payload),
        is_cancelled=_not_cancelled,
        caps=RunCaps(max_seconds=5),
    )

    assert result.status == "succeeded"
    assert result.final_text == "42"
    assert [kind for kind, _payload in events if kind.startswith("tool.")] == [
        "tool.call",
        "tool.result",
    ]
    assert all(kind != "run.error" for kind, _payload in events)


@pytest.mark.asyncio
async def test_kimi_tool_wrapper_has_no_bypass_around_gateway() -> None:
    calls: list[tuple[str, str, dict[str, Any]]] = []

    async def echo(principal: Principal, arguments: dict[str, Any]) -> dict[str, Any]:
        calls.append((principal.school_id, "pico_echo", arguments))
        return {"echo": arguments["text"]}

    gateway = AllowlistGateway()
    gateway.register(
        ToolSpec(name="pico_echo", description="test", handler=echo, school_scoped=False)
    )
    with bind_gateway_tools(gateway, Principal()) as context:
        result = await PicoEcho()(EchoParams(text="hello"))

    assert result.is_error is False
    assert calls == [("school-a", "pico_echo", {"text": "hello"})]
    assert context.results == [("pico_echo", {"echo": "hello"})]


@pytest.mark.asyncio
async def test_kimi_gateway_cross_school_rejection_emits_auth_deny_and_tool_result(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from pico_orchestrator import kimi_runtime

    class DenySession:
        async def __aenter__(self) -> Self:
            return self

        async def __aexit__(self, *_args: object) -> None:
            return None

        async def prompt(self, user_input: str, **_kwargs: Any):
            yield TurnBegin(user_input=user_input)
            yield ToolCall(
                id="deny-call",
                function=ToolCall.FunctionBody(
                    name="fake_edu_list_classes",
                    arguments='{"school_id":"school-b"}',
                ),
            )
            result = await FakeEduListClasses()(
                ListClassesParams(school_id="school-b")
            )
            yield ToolResult(tool_call_id="deny-call", return_value=result)
            yield TurnEnd()

        def cancel(self) -> None:
            raise AssertionError("cancel should not be called")

    async def create(**_kwargs: Any) -> DenySession:
        return DenySession()

    monkeypatch.setattr(kimi_runtime.Session, "create", create)
    monkeypatch.setattr(
        kimi_runtime,
        "resolve_provider",
        lambda: ProviderConfig("kimi", "test-only", "https://example.invalid/v1", "kimi-test"),
    )
    events: list[tuple[str, dict[str, Any]]] = []

    result = await kimi_runtime.run_kimi_agent(
        prompt="hello",
        principal=Principal(),
        emit=lambda kind, payload: _emit_to(events, kind, payload),
        is_cancelled=_not_cancelled,
        caps=RunCaps(max_seconds=5),
    )

    assert result.status == "succeeded"
    assert [(kind, payload.get("ok")) for kind, payload in events if kind == "tool.result"] == [
        ("tool.result", False)
    ]
    assert [payload for kind, payload in events if kind == "auth.deny"] == [
        {
            "code": "tenant.cross_school",
            "message": "Cross-school deny: token=school-a tool=school-b",
            "token_school_id": "school-a",
            "tool": "fake_edu_list_classes",
            "arguments": {"school_id": "school-b"},
        }
    ]


@pytest.mark.asyncio
async def test_kimi_usage_accumulates_across_steps_and_fails_over_cap(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from pico_orchestrator import kimi_runtime

    class TokenCapSession:
        cancelled = False

        async def __aenter__(self) -> Self:
            return self

        async def __aexit__(self, *_args: object) -> None:
            return None

        async def prompt(self, user_input: str, **_kwargs: Any):
            yield TurnBegin(user_input=user_input)
            yield StepBegin(n=1)
            yield StatusUpdate(
                message_id="step-1",
                token_usage=TokenUsage(input_other=30, output=20),
            )
            yield StepBegin(n=2)
            yield StatusUpdate(
                message_id="step-2",
                token_usage=TokenUsage(input_other=40, output=20),
            )
            if self.cancelled:
                raise RunCancelled()
            yield TurnEnd()

        def cancel(self) -> None:
            self.cancelled = True

    session = TokenCapSession()

    async def create(**_kwargs: Any) -> TokenCapSession:
        return session

    monkeypatch.setattr(kimi_runtime.Session, "create", create)
    monkeypatch.setattr(
        kimi_runtime,
        "resolve_provider",
        lambda: ProviderConfig("kimi", "test-only", "https://example.invalid/v1", "kimi-test"),
    )
    events: list[tuple[str, dict[str, Any]]] = []

    result = await kimi_runtime.run_kimi_agent(
        prompt="hello",
        principal=Principal(),
        emit=lambda kind, payload: _emit_to(events, kind, payload),
        is_cancelled=_not_cancelled,
        caps=RunCaps(max_seconds=5, max_tokens=100),
    )

    usage_events = [payload for kind, payload in events if kind == "run.usage"]
    assert [payload["total_tokens"] for payload in usage_events] == [50, 60]
    assert [payload["cumulative_total_tokens"] for payload in usage_events] == [50, 110]
    assert session.cancelled is True
    assert result.status == "failed"
    assert result.error == "Kimi Agent token cap exceeded: 100"
    assert result.token_usage == {"total_tokens": 110}
    expected_user_message = "本次回答超出长度上限，请缩短问题或新开对话后再试。"
    assert (
        "run.error",
        {
            "code": "token_cap",
            "error": result.error,
            "user_message": expected_user_message,
        },
    ) in events
    terminal = [
        payload for kind, payload in events if kind == "run.status" and payload["status"] != "running"
    ]
    assert terminal == [
        {
            "status": "failed",
            "reason": result.error,
            "code": "token_cap",
            "runtime": "kimi-agent",
            "user_message": expected_user_message,
        }
    ]


@pytest.mark.asyncio
async def test_cancel_request_calls_session_cancel_and_emits_cancelled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from pico_orchestrator import kimi_runtime

    class BlockingSession:
        cancelled = False

        async def __aenter__(self) -> Self:
            return self

        async def __aexit__(self, *_args: object) -> None:
            return None

        async def prompt(self, user_input: str, **_kwargs: Any):
            yield TurnBegin(user_input=user_input)
            while not self.cancelled:
                await asyncio.sleep(0.01)
            raise RunCancelled()

        def cancel(self) -> None:
            self.cancelled = True

    session = BlockingSession()

    async def create(**_kwargs: Any) -> BlockingSession:
        return session

    checks = 0

    async def cancelled() -> bool:
        nonlocal checks
        checks += 1
        return checks > 1

    monkeypatch.setattr(kimi_runtime.Session, "create", create)
    monkeypatch.setattr(
        kimi_runtime,
        "resolve_provider",
        lambda: ProviderConfig("kimi", "test-only", "https://example.invalid/v1", "kimi-test"),
    )
    events: list[tuple[str, dict[str, Any]]] = []

    result = await kimi_runtime.run_kimi_agent(
        prompt="hello",
        principal=Principal(),
        emit=lambda kind, payload: _emit_to(events, kind, payload),
        is_cancelled=cancelled,
        caps=RunCaps(max_seconds=5),
    )

    assert session.cancelled is True
    assert result.status == "cancelled"
    assert events[-1] == ("run.status", {"status": "cancelled", "runtime": "kimi-agent"})
    assert sum(1 for kind, payload in events if kind == "run.status" and payload["status"] == "cancelled") == 1
