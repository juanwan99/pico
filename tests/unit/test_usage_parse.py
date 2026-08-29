"""Canonical usage mapping — native provider tokens, never money."""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "orchestrator"))

from pico_orchestrator.provider import _responses_completed_usage
from pico_orchestrator.usage_parse import (
    add_usage,
    billed_model_id,
    is_ui_lane,
    parse_usage_blob,
)


def test_parse_openai_aliases_and_zeros_are_unknown() -> None:
    assert parse_usage_blob(None) is None
    assert parse_usage_blob({"skill_snapshot": {"id": "x"}}) is None
    assert parse_usage_blob({"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}) is None
    parsed = parse_usage_blob({"prompt_tokens": 10, "completion_tokens": 4})
    assert parsed is not None
    assert parsed["prompt_tokens"] == 10
    assert parsed["completion_tokens"] == 4
    assert parsed["total_tokens"] == 14
    assert "estimated" not in parsed


def test_parse_responses_details() -> None:
    parsed = parse_usage_blob(
        {
            "input_tokens": 100,
            "output_tokens": 50,
            "total_tokens": 150,
            "input_tokens_details": {"cached_tokens": 20},
            "output_tokens_details": {"reasoning_tokens": 30},
        }
    )
    assert parsed is not None
    assert parsed["cached_tokens"] == 20
    assert parsed["reasoning_tokens"] == 30
    assert parsed["prompt_tokens"] == 100


def test_add_usage_sums_calls() -> None:
    a = parse_usage_blob({"input_tokens": 10, "output_tokens": 2, "total_tokens": 12})
    b = parse_usage_blob({"input_tokens": 3, "output_tokens": 1, "total_tokens": 4})
    merged = add_usage(a, b)
    assert merged is not None
    assert merged["prompt_tokens"] == 13
    assert merged["completion_tokens"] == 3
    assert merged["total_tokens"] == 16


def test_billed_model_never_keeps_lane_when_backend_known() -> None:
    assert is_ui_lane("pico-fast")
    assert billed_model_id("pico-fast", "gpt-5.6-sol") == "gpt-5.6-sol"
    assert billed_model_id("gpt-5.6-sol") == "gpt-5.6-sol"


def test_responses_completed_usage_from_sdk_object() -> None:
    event = SimpleNamespace(
        type="response.completed",
        response=SimpleNamespace(
            output=[],
            usage=SimpleNamespace(
                input_tokens=80,
                output_tokens=20,
                total_tokens=100,
                input_tokens_details=SimpleNamespace(cached_tokens=8),
                output_tokens_details=SimpleNamespace(reasoning_tokens=12),
            ),
        ),
    )
    parsed = _responses_completed_usage(event)
    assert parsed is not None
    assert parsed["prompt_tokens"] == 80
    assert parsed["completion_tokens"] == 20
    assert parsed["cached_tokens"] == 8
    assert parsed["reasoning_tokens"] == 12
    assert _responses_completed_usage(SimpleNamespace(type="response.output_text.delta")) is None
