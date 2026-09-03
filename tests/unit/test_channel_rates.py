"""Channel price tags: missing tag locks; points = cost × 2.5 × 1000."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "api"))

from app.channel_rates import (
    cost_micro_yuan,
    load_rate_card,
    require_rate,
    reset_rate_card,
    sell_millipoints,
)
from app.points_meter import format_millipoints, points_from_row
from pico_orchestrator.gateway import ToolError

SIMPLE = {
    "sell_markup": 2.5,
    "points_per_yuan": 1000,
    "channels": [
        {
            "id": "t:llm",
            "kind": "llm",
            "model": "gpt-5.6-sol",
            "input_yuan_per_million": 400,
            "output_yuan_per_million": 400,
        },
        {
            "id": "t:image",
            "kind": "image",
            "model": "gemini-3.1-flash-image",
            "per_image_yuan": 0.4,
        },
    ],
}


@pytest.fixture(autouse=True)
def _rates(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PICO_CHANNEL_RATES", json.dumps(SIMPLE))
    reset_rate_card()
    yield
    reset_rate_card()


def test_thousand_input_tokens_cost_point_four_yuan_sells_one_yuan() -> None:
    # 1000 tokens × 400元/百万 = 0.4 元成本 × 2.5 = 1 元 = 1000 积分
    assert (
        points_from_row(
            tokens_unknown=False,
            prompt_tokens=1000,
            completion_tokens=0,
            total_tokens=1000,
            kind="llm",
            model="gpt-5.6-sol",
        )
        == "1000.000"
    )


def test_image_without_tokens_uses_per_image_yuan() -> None:
    # 0.4 元成本 × 2.5 = 1 元 = 1000 积分
    assert (
        points_from_row(
            tokens_unknown=True,
            prompt_tokens=None,
            completion_tokens=None,
            total_tokens=None,
            extra={"ok": True},
            kind="image",
            model="gemini-3.1-flash-image",
        )
        == "1000.000"
    )


def test_unpriced_model_locks() -> None:
    with pytest.raises(ToolError) as exc:
        require_rate(kind="llm", model="unknown-model")
    assert exc.value.code == "channel.unpriced"


def test_seed_card_thousand_input_tokens(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("PICO_CHANNEL_RATES", raising=False)
    reset_rate_card()
    # Live: 36.5 元/百万输入 × 1000 token = 0.0365 元成本 × 2.5 = 91.250 积分
    assert (
        points_from_row(
            tokens_unknown=False,
            prompt_tokens=1000,
            completion_tokens=0,
            total_tokens=1000,
            kind="llm",
            model="gpt-5.6-sol",
        )
        == "91.250"
    )


def test_sell_markup_two_point_five() -> None:
    card = load_rate_card()
    rate = card.find(kind="llm", model="gpt-5.6-sol")
    assert rate is not None
    cost = cost_micro_yuan(
        rate,
        kind="llm",
        tokens_unknown=False,
        prompt_tokens=1000,
        completion_tokens=0,
        total_tokens=1000,
    )
    assert cost == 400_000  # 0.40 yuan
    assert sell_millipoints(cost) == 1_000_000  # 1000.000 points
    assert format_millipoints(1_000_000) == "1000.000"
