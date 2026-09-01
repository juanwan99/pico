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
    usage_blobs_from_rpc_event,
    usage_extra_bits,
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


def test_parse_true_pi_aliases_and_strips_cost() -> None:
    parsed = parse_usage_blob(
        {
            "input": 8,
            "output": 7,
            "cacheRead": 3,
            "cacheWrite": 1,
            "totalTokens": 15,
            "reasoning": 4,
            "cost": {"input": 0.01, "output": 0.02, "total": 0.03},
        }
    )
    assert parsed is not None
    assert parsed["prompt_tokens"] == 8
    assert parsed["completion_tokens"] == 7
    assert parsed["total_tokens"] == 15
    assert parsed["cached_tokens"] == 3
    assert parsed["reasoning_tokens"] == 4
    assert "cost" not in parsed
    assert parse_usage_blob({"input": 0, "output": 0, "totalTokens": 0}) is None
    assert parse_usage_blob({"totalTokens": 42}) is not None
    assert parse_usage_blob({"totalTokens": 42})["total_tokens"] == 42
    # models.json modalities — list-valued input is not a token count
    assert parse_usage_blob({"input": ["text", "image"], "output": ["text"]}) is None
    extra = usage_extra_bits(
        {
            "input": 8,
            "output": 7,
            "totalTokens": 15,
            "cacheRead": 3,
            "reasoning": 4,
            "cost": {"total": 1},
            "ui_model": "pico-fast",
        }
    )
    assert extra["cached_tokens"] == 3
    assert extra["reasoning_tokens"] == 4
    assert extra["ui_model"] == "pico-fast"
    assert "cost" not in extra


def test_usage_blobs_from_rpc_event_only_terminal_kinds() -> None:
    pi_usage = {"input": 8, "output": 2, "totalTokens": 10, "cost": {"total": 0}}
    streaming = {
        "type": "message_update",
        "message": {"role": "assistant", "usage": pi_usage},
        "usage": pi_usage,
    }
    assert usage_blobs_from_rpc_event("message_update", streaming) == []
    assert usage_blobs_from_rpc_event("message_end", {"message": {"usage": pi_usage}}) == []
    agent = {
        "messages": [
            {"role": "user", "content": "hi"},
            {"role": "assistant", "usage": pi_usage},
            {
                "role": "assistant",
                "usage": {"input": 3, "output": 1, "totalTokens": 4},
            },
        ]
    }
    blobs = usage_blobs_from_rpc_event("agent_end", agent)
    assert len(blobs) == 2
    merged = None
    for blob in blobs:
        merged = add_usage(merged, blob)
    assert merged is not None
    assert merged["total_tokens"] == 14
    compact = usage_blobs_from_rpc_event(
        "compaction_end", {"result": {"usage": {"input": 20, "output": 5, "totalTokens": 25}}}
    )
    assert len(compact) == 1
    parsed = parse_usage_blob(compact[0])
    assert parsed is not None
    assert parsed["total_tokens"] == 25


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
