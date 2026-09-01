"""OpenAI-compat shell never exposes token numbers to teachers."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "api"))
sys.path.insert(0, str(ROOT / "services" / "orchestrator"))

from app.openai_compat import _compat_usage_payload, _title_completion_payload


def test_compat_usage_omits_all_counts_from_teacher_shell() -> None:
    assert _compat_usage_payload("你好", "世界", None) is None
    assert _compat_usage_payload("你好", "世界", {}) is None
    assert (
        _compat_usage_payload(
            "你好",
            "世界",
            {"prompt_tokens": 2, "completion_tokens": 4, "estimated": True},
        )
        is None
    )
    assert (
        _compat_usage_payload(
            "x",
            "y",
            {"prompt_tokens": 80, "completion_tokens": 20, "total_tokens": 100},
        )
        is None
    )
    assert (
        _compat_usage_payload(
            "x",
            "y",
            {"input": 8, "output": 2, "totalTokens": 10, "cost": {"total": 0.01}},
        )
        is None
    )


def test_title_payload_has_no_usage() -> None:
    payload = _title_completion_payload(
        completion_id="c1",
        created=1,
        model="pico-fast",
        title="短标题",
        prompt="Analyze this conversation",
    )
    assert "usage" not in payload
    assert payload["choices"][0]["message"]["content"] == "短标题"
