"""#1183 / #1186: per-request `reasoning_effort`, Pi fast lane thinking off on
the wire for Gemini flash, and `revision` on the tip/health probes."""

from __future__ import annotations

import json
from pathlib import Path

from app.openai_compat import (
    ChatCompletionRequest,
    _caps_with_request_thinking,
    _caps_with_sidebar_thinking,
    _direct_thinking,
    _thinking_override,
)
from pico_orchestrator.provider import GEMINI_FLASH_THINKING_OFF_BODY, thinking_extra_body
from pico_orchestrator.run_types import RunCaps
from pico_orchestrator.true_pi.client import SubprocessTransport, true_pi_models_document


def test_request_accepts_openai_reasoning_effort_field() -> None:
    body = ChatCompletionRequest.model_validate(
        {"messages": [{"role": "user", "content": "转写"}], "reasoning_effort": "none"}
    )
    assert body.reasoning_effort == "none"
    assert ChatCompletionRequest.model_validate({"messages": []}).reasoning_effort is None


def test_thinking_override_values() -> None:
    assert _thinking_override(None) is None
    assert _thinking_override("") is None
    assert _thinking_override("none") is False
    assert _thinking_override("NONE") is False
    assert _thinking_override("off") is False
    for level in ("minimal", "low", "medium", "high", "xhigh"):
        assert _thinking_override(level) is True
    # Unknown words never flip the lane.
    assert _thinking_override("banana") is None


def test_direct_path_thinking_choice() -> None:
    # json_only propose stays off whatever the request says.
    assert _direct_thinking(json_only=True, override=None) is False
    assert _direct_thinking(json_only=True, override=True) is False
    # Old callers (no field) keep the lane default.
    assert _direct_thinking(json_only=False, override=None) is None
    assert _direct_thinking(json_only=False, override=False) is False
    assert _direct_thinking(json_only=False, override=True) is True


def test_pi_caps_honor_request_and_sidebar_still_wins() -> None:
    fast = RunCaps(thinking_on=False)
    deep = RunCaps(thinking_on=True)
    assert _caps_with_request_thinking(fast, None) is fast
    assert _caps_with_request_thinking(deep, False).thinking_on is False
    assert _caps_with_request_thinking(fast, True).thinking_on is True
    # A sidebar turn only paints content: a request "medium" cannot turn it on.
    rail = _caps_with_sidebar_thinking(_caps_with_request_thinking(fast, True), edu_sidebar=True)
    assert rail.thinking_on is False


def test_direct_and_pi_share_one_gemini_flash_off_body() -> None:
    assert thinking_extra_body("gemini-3.8-flash", thinking=False) == GEMINI_FLASH_THINKING_OFF_BODY
    doc = true_pi_models_document(
        provider="openai",
        model="gemini-3.8-flash",
        max_context=128_000,
        max_tokens=8_000,
        base_url="http://127.0.0.1:3000/v1",
        api="openai-completions",
        thinking=False,
    )
    model = doc["providers"]["openai"]["models"][0]
    assert model["reasoning"] is False
    assert model["samplingParams"] == GEMINI_FLASH_THINKING_OFF_BODY
    assert model["samplingParams"] is not GEMINI_FLASH_THINKING_OFF_BODY  # overlay owns its copy


def test_pi_deep_lane_and_non_flash_do_not_pin_budget_zero() -> None:
    deep = true_pi_models_document(
        provider="openai",
        model="gemini-3.8-flash",
        max_context=256_000,
        max_tokens=32_000,
        api="openai-completions",
        thinking=True,
    )["providers"]["openai"]["models"][0]
    assert deep["reasoning"] is True
    assert "samplingParams" not in deep
    pro = true_pi_models_document(
        provider="openai",
        model="gemini-3.8-pro",
        max_context=128_000,
        max_tokens=8_000,
        api="openai-completions",
        thinking=False,
    )["providers"]["openai"]["models"][0]
    assert "samplingParams" not in pro
    gpt = true_pi_models_document(
        provider="openai",
        model="gpt-5.6-sol",
        max_context=128_000,
        max_tokens=8_000,
        api="openai-responses",
        thinking=False,
    )["providers"]["openai"]["models"][0]
    assert "samplingParams" not in gpt


def test_written_models_json_carries_budget_zero(tmp_path: Path) -> None:
    t = SubprocessTransport(
        session_dir=tmp_path / "sess-flash-off",
        tool_url="http://127.0.0.1:1",
        tool_token="tok",
        run_id="r-flash-off",
        provider="openai",
        model="gemini-3.8-flash",
        thinking=False,
        max_context=128_000,
        max_tokens=8_000,
        base_url="http://127.0.0.1:3000/v1",
        api="openai-completions",
    )
    written = json.loads((t.prepare_agent_home() / "models.json").read_text(encoding="utf-8"))
    sp = written["providers"]["openai"]["models"][0]["samplingParams"]
    assert sp["extra_body"]["google"]["thinking_config"]["thinking_budget"] == 0


def test_tip_and_health_expose_revision() -> None:
    import asyncio

    from app import main as m

    tip = asyncio.run(m.meta_tip())
    assert tip["revision"] == tip["git_sha"]
    assert len(tip["git_sha"]) >= 7
