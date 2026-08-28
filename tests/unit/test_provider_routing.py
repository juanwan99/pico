"""E0/E1/E2: default-path model routing — never send Kimi ids to DeepSeek."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "orchestrator"))

from pico_orchestrator.provider import (
    DEFAULT_DEEPSEEK_MODEL,
    owned_by_for_model,
    resolve_model_id,
    resolve_provider,
    resolve_provider_for_model,
    runtime_policy_for_model,
    should_circuit_break,
    thinking_extra_body,
)


@pytest.fixture
def deepseek_only(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-deepseek-test")
    monkeypatch.setenv("DEEPSEEK_MODEL", "deepseek-v4-flash")
    monkeypatch.setenv("PICO_MODEL_PROVIDER", "deepseek")
    monkeypatch.delenv("KIMI_API_KEY", raising=False)
    monkeypatch.delenv("MOONSHOT_API_KEY", raising=False)


@pytest.fixture
def both_keys(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-deepseek-test")
    monkeypatch.setenv("DEEPSEEK_MODEL", "deepseek-v4-flash")
    monkeypatch.setenv("KIMI_API_KEY", "sk-kimi-test")
    monkeypatch.setenv("KIMI_MODEL", "kimi-k2.6")
    monkeypatch.setenv("PICO_MODEL_PROVIDER", "deepseek")


def test_product_default_provider_is_deepseek(deepseek_only: None) -> None:
    cfg = resolve_provider()
    assert cfg is not None
    assert cfg.name == "deepseek"
    assert cfg.model == "deepseek-v4-flash"


def test_kimi_ui_default_remounts_to_deepseek_when_no_kimi_key(
    deepseek_only: None,
) -> None:
    """Owner repro: default kimi-k2.6 + DeepSeek-only server must not 404."""
    cfg = resolve_provider_for_model("kimi-k2.6")
    assert cfg is not None
    assert cfg.name == "deepseek"
    model_id = resolve_model_id("kimi-k2.6", cfg)
    assert model_id == DEFAULT_DEEPSEEK_MODEL
    assert model_id != "kimi-k2.6"


def test_deepseek_model_stays_on_deepseek(deepseek_only: None) -> None:
    cfg = resolve_provider_for_model("deepseek-chat")
    assert cfg is not None
    assert cfg.name == "deepseek"
    assert resolve_model_id("deepseek-chat", cfg) == "deepseek-chat"
    assert resolve_model_id("deepseek-reasoner", cfg) == "deepseek-reasoner"


def test_agent_model_uses_product_default(deepseek_only: None) -> None:
    cfg = resolve_provider_for_model("pico-agent")
    assert cfg is not None
    assert cfg.name == "deepseek"
    assert resolve_model_id("pico-agent", cfg) == "deepseek-v4-flash"


def test_pico_fast_flash_deep_reasoner(deepseek_only: None) -> None:
    cfg = resolve_provider_for_model("pico-fast")
    assert cfg is not None
    assert cfg.name == "deepseek"
    assert resolve_model_id("pico-fast", cfg) == "deepseek-v4-flash"
    assert resolve_model_id("pico-deep", cfg) == "deepseek-reasoner"


def test_kimi_model_uses_kimi_when_key_present(both_keys: None) -> None:
    cfg = resolve_provider_for_model("kimi-k2.6")
    assert cfg is not None
    assert cfg.name == "kimi"
    assert resolve_model_id("kimi-k2.6", cfg) == "kimi-k2.6"


def test_preferred_deepseek_when_both_keys(both_keys: None) -> None:
    cfg = resolve_provider()
    assert cfg is not None
    assert cfg.name == "deepseek"


def test_owned_by_is_honest() -> None:
    assert owned_by_for_model("deepseek-chat") == "deepseek"
    assert owned_by_for_model("kimi-k2.6") == "kimi"
    assert owned_by_for_model("pico-agent") == "pico"
    # Never brand DeepSeek rows as pico-kimi
    assert owned_by_for_model("deepseek-chat") != "pico-kimi"


def test_runtime_policy_dual_mode_contract() -> None:
    """Pico 快速 = flash; Pico 深度 = reasoner; thinking differs."""
    fast = runtime_policy_for_model("pico-fast")
    deep = runtime_policy_for_model("pico-deep")
    assert fast["ui_model"] == "pico-fast"
    assert deep["ui_model"] == "pico-deep"
    assert fast["backend_model"] == "deepseek-v4-flash"
    assert deep["backend_model"] == "deepseek-reasoner"
    # fast: thinking off, tighter budget; deep: thinking on, breaker armed.
    assert fast["thinking"] is False
    assert deep["thinking"] is True
    assert fast["max_steps"] < deep["max_steps"]
    assert fast["max_tokens"] < deep["max_tokens"]
    assert fast["max_context"] == 128000
    assert deep["max_context"] == 256000
    assert fast["max_tokens"] != 128000
    assert deep["max_tokens"] != 256000
    assert fast["fallback"] == "deepseek-v4-flash"
    assert deep["fallback"] == "deepseek-reasoner"
    # Direct HTTPS must send this: v4-flash thinks by default and can return 200 empty.
    assert thinking_extra_body("pico-fast") == {"thinking": {"type": "disabled"}}
    assert thinking_extra_body("pico-deep") == {"thinking": {"type": "enabled"}}
    assert thinking_extra_body("pico-deep", thinking=False) == {
        "thinking": {"type": "disabled"}
    }


def test_circuit_breaker_only_in_thinking_on_lane() -> None:
    # Fast lane never trips regardless of repeated empties.
    assert not should_circuit_break(
        tool_exec_count=0,
        repeated_no_progress=10,
        wall_seconds=500.0,
        thinking_on=False,
    )
    # Deep lane: no tool progress twice → trip.
    assert should_circuit_break(
        tool_exec_count=0,
        repeated_no_progress=2,
        wall_seconds=10.0,
        thinking_on=True,
    )
    # Deep lane: long stall with zero tool exec → trip.
    assert should_circuit_break(
        tool_exec_count=0,
        repeated_no_progress=0,
        wall_seconds=200.0,
        thinking_on=True,
    )
    # Deep lane: repeated_no_progress >= 4 → trip even with some tool exec.
    assert should_circuit_break(
        tool_exec_count=1,
        repeated_no_progress=4,
        wall_seconds=20.0,
        thinking_on=True,
    )
    # Healthy deep lane: tool progress resets the counter → no trip.
    assert not should_circuit_break(
        tool_exec_count=3,
        repeated_no_progress=1,
        wall_seconds=60.0,
        thinking_on=True,
    )


def test_coerce_legacy_kimi_pref_onto_deepseek_allowlist() -> None:
    sys.path.insert(0, str(ROOT / "services" / "api"))
    from app.openai_compat import _coerce_default_model
    from app.settings import Settings

    settings = Settings(
        _env_file=None,
        pico_env="production",
        deepseek_api_key="sk-ds",
        pico_model_provider="deepseek",
        pico_allowed_models="pico-fast,pico-deep",
    )
    assert _coerce_default_model("kimi-k2.6", settings) == "deepseek-v4-flash"
    assert _coerce_default_model("deepseek-chat", settings) == "deepseek-chat"
    # When Kimi remains allowlisted, keep it
    dual = Settings(
        _env_file=None,
        pico_env="production",
        deepseek_api_key="sk-ds",
        kimi_api_key="sk-kimi",
        pico_model_provider="deepseek",
        pico_allowed_models="deepseek-v4-flash,kimi-k2.6,pico-fast",
    )
    assert _coerce_default_model("kimi-k2.6", dual) == "kimi-k2.6"


def test_list_models_filters_to_dual_mode_only() -> None:
    """F4: /v1/models exposes exactly pico-fast / pico-deep — old SKUs filtered."""
    import asyncio

    sys.path.insert(0, str(ROOT / "services" / "api"))
    from app.auth import issue_test_token
    from app.openai_compat import list_models
    from app.settings import Settings

    settings = Settings(
        _env_file=None,
        pico_env="production",
        deepseek_api_key="sk-ds",
        pico_model_provider="deepseek",
        # Deliberately broad allowlist including legacy SKUs — must be filtered.
        pico_allowed_models="deepseek-chat,deepseek-reasoner,kimi-k2.6,pico-agent,pico-fast,pico-deep",
    )
    token = issue_test_token(
        school_id="school-a",
        membership_id="member-a",
        settings=settings,
    )

    async def _call() -> dict:
        return await list_models(f"Bearer {token}", settings)

    result = asyncio.run(_call())
    ids = [m["id"] for m in result["data"]]
    assert ids == ["pico-fast", "pico-deep"]
    assert "deepseek-chat" not in ids
    assert "deepseek-reasoner" not in ids
    assert "kimi-k2.6" not in ids
    assert "pico-agent" not in ids

    # Even with no allowlist, the list stays the two product modes.
    dev = Settings(
        _env_file=None,
        pico_env="development",
        deepseek_api_key="sk-ds",
        pico_model_provider="deepseek",
    )
    dev_token = issue_test_token(
        school_id="school-a",
        membership_id="member-a",
        settings=dev,
    )

    async def _call_dev() -> dict:
        return await list_models(f"Bearer {dev_token}", dev)

    dev_result = asyncio.run(_call_dev())
    dev_ids = [m["id"] for m in dev_result["data"]]
    assert set(dev_ids) == {"pico-fast", "pico-deep"}


def test_openai_responses_brain_keeps_gpt_model(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-aiproxy-test")
    monkeypatch.setenv("DEEPSEEK_MODEL", "gpt-5.6-sol")
    monkeypatch.setenv("DEEPSEEK_BASE_URL", "https://superaichao.xin/openai")
    monkeypatch.setenv("PICO_MODEL_PROVIDER", "deepseek")
    monkeypatch.delenv("KIMI_API_KEY", raising=False)
    from pico_orchestrator.provider import (
        product_backend_model,
        resolve_model_id,
        resolve_provider,
        runtime_policy_for_model,
        uses_openai_responses_brain,
    )

    cfg = resolve_provider()
    assert cfg is not None
    assert uses_openai_responses_brain(cfg)
    assert product_backend_model(deep=False) == "gpt-5.6-sol"
    assert product_backend_model(deep=True) == "gpt-5.6-sol"
    assert resolve_model_id("pico-fast", cfg) == "gpt-5.6-sol"
    assert resolve_model_id("pico-deep", cfg) == "gpt-5.6-sol"
    assert runtime_policy_for_model("pico-fast")["backend_model"] == "gpt-5.6-sol"
    assert runtime_policy_for_model("pico-deep")["backend_model"] == "gpt-5.6-sol"


def test_deepseek_url_does_not_count_as_openai_responses(
    deepseek_only: None,
) -> None:
    from pico_orchestrator.provider import resolve_provider, uses_openai_responses_brain

    cfg = resolve_provider()
    assert cfg is not None
    assert not uses_openai_responses_brain(cfg)


def test_responses_input_splits_system_from_turns() -> None:
    from pico_orchestrator.provider import _responses_instructions_and_input

    instructions, items = _responses_instructions_and_input(
        [
            {"role": "system", "content": "附属，不是用户要求"},
            {"role": "user", "content": "你能看到当前界面吗"},
        ]
    )
    assert instructions == "附属，不是用户要求"
    assert items == [{"role": "user", "content": "你能看到当前界面吗"}]


def test_responses_text_delta_ignores_reasoning() -> None:
    from types import SimpleNamespace

    from pico_orchestrator.provider import _responses_text_delta

    assert (
        _responses_text_delta(
            SimpleNamespace(type="response.output_text.delta", delta="高一期末")
        )
        == "高一期末"
    )
    assert (
        _responses_text_delta(
            {"type": "response.reasoning_text.delta", "delta": "think"}
        )
        == ""
    )


def test_responses_kwargs_skip_reasoning_when_thinking_off() -> None:
    from pico_orchestrator.provider import _responses_create_kwargs

    kwargs = _responses_create_kwargs(
        model_id="gpt-5.6-sol",
        messages=[{"role": "user", "content": "hi"}],
        max_tokens=64,
        thinking=False,
    )
    assert kwargs["model"] == "gpt-5.6-sol"
    assert kwargs["stream"] is True
    assert kwargs["max_output_tokens"] == 64
    assert "reasoning" not in kwargs
    assert "extra_body" not in kwargs

    on = _responses_create_kwargs(
        model_id="gpt-5.6-sol",
        messages=[{"role": "user", "content": "hi"}],
        max_tokens=64,
        thinking=True,
    )
    assert on["reasoning"] == {"effort": "medium"}


@pytest.mark.asyncio
async def test_stream_chat_uses_responses_for_gpt_brain(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Edu sidebar is use_direct + gpt-5.6-sol; Chat Completions 404s as 'Not Found'."""
    from types import SimpleNamespace

    import pico_orchestrator.provider as provider

    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-aiproxy-test")
    monkeypatch.setenv("DEEPSEEK_MODEL", "gpt-5.6-sol")
    monkeypatch.setenv("DEEPSEEK_BASE_URL", "https://superaichao.xin/openai")
    monkeypatch.setenv("PICO_MODEL_PROVIDER", "deepseek")
    monkeypatch.delenv("KIMI_API_KEY", raising=False)

    calls: dict[str, object] = {}

    class FakeStream:
        def __init__(self, events):
            self._events = list(events)

        def __aiter__(self):
            return self

        async def __anext__(self):
            if not self._events:
                raise StopAsyncIteration
            return self._events.pop(0)

    class FakeResponses:
        async def create(self, **kwargs):
            calls["responses"] = kwargs
            return FakeStream(
                [SimpleNamespace(type="response.output_text.delta", delta="成绩观察板")]
            )

    class FakeCompletions:
        async def create(self, **kwargs):
            calls["chat"] = kwargs
            raise AssertionError("gpt-5.6-sol must not use chat.completions")

    class FakeClient:
        def __init__(self, **kwargs):
            calls["client"] = kwargs
            self.responses = FakeResponses()
            self.chat = SimpleNamespace(completions=FakeCompletions())

    monkeypatch.setattr(provider, "AsyncOpenAI", FakeClient)
    parts: list[str] = []
    async for piece in provider.stream_chat(
        "你能看到当前界面吗",
        max_tokens=32,
        model="pico-fast",
        system="附属，不是用户要求",
        thinking=False,
    ):
        parts.append(piece)
    assert "".join(parts) == "成绩观察板"
    assert "chat" not in calls
    sent = calls["responses"]
    assert sent["model"] == "gpt-5.6-sol"
    assert sent["instructions"] == "附属，不是用户要求"
    assert sent["input"] == [{"role": "user", "content": "你能看到当前界面吗"}]
