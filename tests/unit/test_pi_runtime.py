"""Pi Agent runtime — product default multi-step kernel."""

from __future__ import annotations

from dataclasses import dataclass
from types import SimpleNamespace
from typing import Any

import pytest
from app.settings import Settings
from pico_orchestrator.provider import ProviderConfig
from pico_orchestrator.run_types import RunCaps, RunResult
from pico_orchestrator.runtime import run_agent_runtime, should_use_pi_agent


@dataclass
class Principal:
    school_id: str = "school-a"
    membership_id: str = "member-a"
    scopes: list[str] | None = None


async def _not_cancelled() -> bool:
    return False


async def _noop_emit(_kind: str, _payload: dict[str, Any]) -> None:
    return None


async def _emit_to(events: list[tuple[str, dict[str, Any]]], kind: str, payload: dict[str, Any]) -> None:
    events.append((kind, payload))


@pytest.mark.asyncio
async def test_pi_is_default_dispatch(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []

    async def pi_loop(**_kwargs: Any) -> RunResult:
        calls.append("pi")
        return RunResult(status="succeeded", final_text="pi-ok")

    async def kimi_loop(**_kwargs: Any) -> RunResult:
        calls.append("kimi")
        return RunResult(status="succeeded", final_text="kimi-ok")

    import pico_orchestrator.runtime as rt
    monkeypatch.setattr(rt, "_PI_IMPL", pi_loop)
    monkeypatch.setattr(rt, "_KIMI_IMPL", kimi_loop)

    result = await run_agent_runtime(
        use_pi_agent=True,
        pi_agent_allow_all=True,
        use_kimi_agent=True,  # both on → Pi wins
        kimi_agent_allow_all=True,
        principal=Principal(),
        prompt="hello",
        emit=_noop_emit,
        is_cancelled=_not_cancelled,
    )
    assert result.final_text == "pi-ok"
    assert calls == ["pi"]


@pytest.mark.asyncio
async def test_pi_gate_off_fails_closed_without_legacy(monkeypatch: pytest.MonkeyPatch) -> None:
    async def pi_loop(**_kwargs: Any) -> RunResult:
        return RunResult(status="succeeded", final_text="should-not")

    monkeypatch.setattr("pico_orchestrator.pi_runtime.run_pi_agent", pi_loop)
    result = await run_agent_runtime(
        use_pi_agent=False,
        use_kimi_agent=False,
        principal=Principal(),
        prompt="hello",
        emit=_noop_emit,
        is_cancelled=_not_cancelled,
    )
    assert result.status == "failed"
    assert "no multi-step runtime" in (result.error or "")


@pytest.mark.asyncio
async def test_legacy_kimi_when_pi_off(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []

    async def kimi_loop(**_kwargs: Any) -> RunResult:
        calls.append("kimi")
        return RunResult(status="succeeded", final_text="kimi")

    import pico_orchestrator.runtime as rt
    monkeypatch.setattr(rt, "_KIMI_IMPL", kimi_loop)
    result = await run_agent_runtime(
        use_pi_agent=False,
        use_kimi_agent=True,
        kimi_agent_allow_all=True,
        principal=Principal(),
        prompt="hello",
        emit=_noop_emit,
        is_cancelled=_not_cancelled,
    )
    assert result.final_text == "kimi"
    assert calls == ["kimi"]


def test_should_use_pi_agent_defaults() -> None:
    assert should_use_pi_agent(use_pi_agent=True, pi_agent_allow_all=True)
    assert not should_use_pi_agent(use_pi_agent=False, pi_agent_allow_all=True)
    assert not should_use_pi_agent(
        use_pi_agent=True,
        pi_agent_allow_all=False,
        canary_principals=(),
    )
    assert should_use_pi_agent(
        use_pi_agent=True,
        school_id="s",
        membership_id="m",
        pi_agent_allow_all=False,
        canary_principals={("s", "m")},
    )


def test_settings_pi_default_on(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("PICO_PI_AGENT_RUNTIME", raising=False)
    monkeypatch.delenv("PICO_LEGACY_KIMI_AGENT_RUNTIME", raising=False)
    monkeypatch.delenv("PICO_KIMI_AGENT_RUNTIME", raising=False)
    s = Settings(_env_file=None)
    assert s.pico_pi_agent_runtime is True
    assert s.pi_agent_scope == "all"
    assert s.pi_agent_default_all is True
    assert s.legacy_kimi_enabled is False
    assert s.kimi_agent_scope == "off"


@pytest.mark.asyncio
async def test_pi_path_text_only_without_network(monkeypatch: pytest.MonkeyPatch) -> None:
    """Mock OpenAI client: one assistant text turn → succeeded + ledger events."""

    class _FakeCompletions:
        async def create(self, **_kwargs: Any) -> Any:
            return SimpleNamespace(
                choices=[
                    SimpleNamespace(
                        message=SimpleNamespace(content="你好，任务已完成。", tool_calls=None)
                    )
                ],
                usage=SimpleNamespace(prompt_tokens=10, completion_tokens=5),
            )

    class _FakeClient:
        def __init__(self, **_kwargs: Any) -> None:
            self.chat = SimpleNamespace(completions=_FakeCompletions())

    monkeypatch.setattr(
        "pico_orchestrator.pi_runtime.resolve_provider",
        lambda: ProviderConfig(
            name="deepseek",
            api_key="sk-test",
            base_url="https://api.deepseek.com/v1",
            model="deepseek-chat",
        ),
    )
    monkeypatch.setattr("pico_orchestrator.pi_runtime.AsyncOpenAI", _FakeClient)

    events: list[tuple[str, dict[str, Any]]] = []

    async def emit(kind: str, payload: dict[str, Any]) -> None:
        events.append((kind, payload))

    from pico_orchestrator.pi_runtime import run_pi_agent

    result = await run_pi_agent(
        prompt="打个招呼",
        principal=Principal(),
        emit=emit,
        is_cancelled=_not_cancelled,
        caps=RunCaps(max_steps=4, max_seconds=30, max_tokens=8000),
    )
    assert result.status == "succeeded"
    assert "任务已完成" in result.final_text
    kinds = [k for k, _ in events]
    assert "run.status" in kinds
    assert "message.delta" in kinds
    assert any(p.get("runtime") == "pi-agent" for k, p in events if k == "run.status")


@pytest.mark.asyncio
async def test_pi_path_tool_call_loop(monkeypatch: pytest.MonkeyPatch) -> None:
    """Model requests calculator once, then final text."""

    step = {"n": 0}

    class _FakeCompletions:
        async def create(self, **kwargs: Any) -> Any:
            step["n"] += 1
            if step["n"] == 1:
                tc = SimpleNamespace(
                    id="call-calc-1",
                    function=SimpleNamespace(
                        name="calculator",
                        arguments='{"expression": "1+1"}',
                    ),
                )
                return SimpleNamespace(
                    choices=[
                        SimpleNamespace(
                            message=SimpleNamespace(content=None, tool_calls=[tc])
                        )
                    ],
                    usage=SimpleNamespace(prompt_tokens=5, completion_tokens=5),
                )
            return SimpleNamespace(
                choices=[
                    SimpleNamespace(
                        message=SimpleNamespace(content="结果是 2。", tool_calls=None)
                    )
                ],
                usage=SimpleNamespace(prompt_tokens=8, completion_tokens=4),
            )

    class _FakeClient:
        def __init__(self, **_kwargs: Any) -> None:
            self.chat = SimpleNamespace(completions=_FakeCompletions())

    monkeypatch.setattr(
        "pico_orchestrator.pi_runtime.resolve_provider",
        lambda: ProviderConfig(
            name="deepseek",
            api_key="sk-test",
            base_url="https://api.deepseek.com/v1",
            model="deepseek-chat",
        ),
    )
    monkeypatch.setattr("pico_orchestrator.pi_runtime.AsyncOpenAI", _FakeClient)

    events: list[tuple[str, dict[str, Any]]] = []

    async def emit(kind: str, payload: dict[str, Any]) -> None:
        events.append((kind, payload))

    from pico_orchestrator.pi_runtime import run_pi_agent

    result = await run_pi_agent(
        prompt="算一下 1+1",
        principal=Principal(),
        emit=emit,
        is_cancelled=_not_cancelled,
        caps=RunCaps(max_steps=6, max_seconds=60, max_tokens=8000),
    )
    assert result.status == "succeeded"
    assert "2" in result.final_text
    kinds = [k for k, _ in events]
    assert "tool.call" in kinds
    assert "tool.result" in kinds
    tool_calls = [p for k, p in events if k == "tool.call"]
    assert tool_calls[0]["tool"] == "calculator"


@pytest.mark.asyncio
async def test_pi_deep_lane_circuit_breaker_bails_on_no_progress(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Deep lane with no tool progress loops → circuit breaker bails honestly."""

    calls = {"n": 0}

    class _FakeCompletions:
        async def create(self, **kwargs: Any) -> Any:
            calls["n"] += 1
            # Always request a tool call that fails (ToolError) → no progress.
            tc = SimpleNamespace(
                id=f"call-loop-{calls['n']}",
                function=SimpleNamespace(
                    name="calculator",
                    arguments='{"expression": "1/0"}',
                ),
            )
            return SimpleNamespace(
                choices=[
                    SimpleNamespace(
                        message=SimpleNamespace(content=None, tool_calls=[tc])
                    )
                ],
                usage=SimpleNamespace(prompt_tokens=5, completion_tokens=5),
            )

    class _FakeClient:
        def __init__(self, **_kwargs: Any) -> None:
            self.chat = SimpleNamespace(completions=_FakeCompletions())

    monkeypatch.setattr(
        "pico_orchestrator.pi_runtime.resolve_provider",
        lambda: ProviderConfig(
            name="deepseek",
            api_key="sk-test",
            base_url="https://api.deepseek.com/v1",
            model="deepseek-v4-flash",
        ),
    )
    monkeypatch.setattr("pico_orchestrator.pi_runtime.AsyncOpenAI", _FakeClient)
    # calculator tool exists in the default gateway; make it raise ToolError.
    import pico_orchestrator.pi_runtime as pi_rt
    from pico_orchestrator.gateway import ToolError

    async def _boom(_principal, _name, _args):
        raise ToolError("calculator.error", "division by zero")

    class _FakeGateway:
        def __init__(self, *_a, **_k) -> None:
            self.tools = {
                "calculator": SimpleNamespace(
                    name="calculator", description="calc",
                )
            }

        def restricted_to(self, allowed_tools):
            return self

        async def invoke(self, principal, name, arguments):
            return await _boom(principal, name, arguments)

    monkeypatch.setattr(pi_rt, "build_default_gateway", lambda _store: _FakeGateway())

    events: list[tuple[str, dict[str, Any]]] = []

    async def emit(kind: str, payload: dict[str, Any]) -> None:
        events.append((kind, payload))

    from pico_orchestrator.pi_runtime import run_pi_agent

    result = await run_pi_agent(
        prompt="深度任务",
        principal=Principal(),
        emit=emit,
        is_cancelled=_not_cancelled,
        caps=RunCaps(
            max_steps=24,
            max_seconds=120,
            max_tokens=32000,
            thinking_on=True,
        ),
    )
    # Breaker trips after ~2 no-progress turns, not the full 24-step budget.
    assert result.status == "failed"
    assert "熔断" in (result.error or "")
    assert calls["n"] <= 6
    kinds = [k for k, _ in events]
    assert "circuit.breaker" in kinds
    assert any(k == "run.status" and p.get("status") == "failed" for k, p in events)
    failed_payloads = [p for k, p in events if k == "run.status" and p.get("status") == "failed"]
    assert failed_payloads and failed_payloads[0].get("code") == "pi.no_progress"


@pytest.mark.asyncio
async def test_pi_fast_lane_never_trips_circuit_breaker(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Fast lane (thinking off) keeps its own budget; breaker stays disarmed."""

    calls = {"n": 0}

    class _FakeCompletions:
        async def create(self, **kwargs: Any) -> Any:
            calls["n"] += 1
            tc = SimpleNamespace(
                id=f"call-{calls['n']}",
                function=SimpleNamespace(
                    name="calculator",
                    arguments='{"expression": "1/0"}',
                ),
            )
            return SimpleNamespace(
                choices=[
                    SimpleNamespace(
                        message=SimpleNamespace(content=None, tool_calls=[tc])
                    )
                ],
                usage=SimpleNamespace(prompt_tokens=5, completion_tokens=5),
            )

    class _FakeClient:
        def __init__(self, **_kwargs: Any) -> None:
            self.chat = SimpleNamespace(completions=_FakeCompletions())

    monkeypatch.setattr(
        "pico_orchestrator.pi_runtime.resolve_provider",
        lambda: ProviderConfig(
            name="deepseek",
            api_key="sk-test",
            base_url="https://api.deepseek.com/v1",
            model="deepseek-v4-flash",
        ),
    )
    monkeypatch.setattr("pico_orchestrator.pi_runtime.AsyncOpenAI", _FakeClient)

    import pico_orchestrator.pi_runtime as pi_rt
    from pico_orchestrator.gateway import ToolError

    class _FakeGateway:
        def __init__(self, *_a, **_k) -> None:
            self.tools = {
                "calculator": SimpleNamespace(
                    name="calculator", description="calc",
                )
            }

        def restricted_to(self, allowed_tools):
            return self

        async def invoke(self, principal, name, arguments):
            raise ToolError("calculator.error", "division by zero")

    monkeypatch.setattr(pi_rt, "build_default_gateway", lambda _store: _FakeGateway())

    events: list[tuple[str, dict[str, Any]]] = []

    async def emit(kind: str, payload: dict[str, Any]) -> None:
        events.append((kind, payload))

    from pico_orchestrator.pi_runtime import run_pi_agent

    result = await run_pi_agent(
        prompt="快速任务",
        principal=Principal(),
        emit=emit,
        is_cancelled=_not_cancelled,
        caps=RunCaps(
            max_steps=3,
            max_seconds=60,
            max_tokens=8000,
            thinking_on=False,
        ),
    )
    # No breaker in fast lane → run ends by max_steps, no circuit.breaker event.
    assert result.status == "failed"
    assert "no_progress" not in (result.error or "")
    kinds = [k for k, _ in events]
    assert "circuit.breaker" not in kinds


def test_provider_prefers_deepseek(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-ds")
    monkeypatch.setenv("KIMI_API_KEY", "sk-kimi")
    monkeypatch.setenv("PICO_MODEL_PROVIDER", "deepseek")
    from pico_orchestrator.provider import resolve_provider

    cfg = resolve_provider()
    assert cfg is not None
    assert cfg.name == "deepseek"


def test_provider_kimi_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.setenv("KIMI_API_KEY", "sk-kimi")
    monkeypatch.delenv("PICO_MODEL_PROVIDER", raising=False)
    from pico_orchestrator.provider import resolve_provider

    cfg = resolve_provider()
    assert cfg is not None
    assert cfg.name == "kimi"
