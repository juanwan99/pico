"""Points meter: channel cost × 2.5 × 1000, no wallet."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "api"))

from app.channel_rates import reset_rate_card
from app.points_meter import (
    milli_from_row,
    points_from_row,
    points_from_tokens,
    quote_points_from_input_len,
    quote_units_from_input_len,
    resident_quote_floor,
    tokens_from_row,
)

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
            "cache_read_yuan_per_million": 40,
            "cache_write_yuan_per_million": 500,
        }
    ],
}


@pytest.fixture(autouse=True)
def _rates(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PICO_CHANNEL_RATES", json.dumps(SIMPLE))
    reset_rate_card()
    yield
    reset_rate_card()


def test_thousand_fresh_input_is_one_yuan_sell() -> None:
    assert points_from_tokens(1000) == "1000.000"


def test_zero_tokens() -> None:
    assert points_from_tokens(0) == "0.000"


def test_unknown_row_has_no_tokens() -> None:
    assert (
        tokens_from_row(
            tokens_unknown=True,
            total_tokens=12,
            prompt_tokens=4,
            completion_tokens=8,
        )
        is None
    )
    assert (
        points_from_row(
            tokens_unknown=True,
            total_tokens=12,
            prompt_tokens=4,
            completion_tokens=8,
            kind="llm",
            model="gpt-5.6-sol",
        )
        is None
    )


def test_quote_covers_resident_even_when_empty() -> None:
    empty = quote_points_from_input_len(0)
    short = quote_points_from_input_len(14)
    assert empty != "0.000"
    assert short != empty
    assert empty.count(".") == 1


def test_quote_teacher_text_alone_is_opt_in() -> None:
    assert quote_points_from_input_len(0, resident_tokens=0) == "0.000"
    quoted = quote_points_from_input_len(40, resident_tokens=0)
    assert quoted != "0.000"
    assert quote_units_from_input_len(14) == 8


def test_quote_does_not_expose_scale_in_string() -> None:
    quoted = quote_points_from_input_len(1000)
    assert "×" not in quoted
    assert "token" not in quoted.lower()
    assert str(resident_quote_floor()) not in quoted


def test_physical_tokens_keep_provider_total() -> None:
    n = tokens_from_row(
        tokens_unknown=False,
        prompt_tokens=8393,
        completion_tokens=25,
        total_tokens=8418,
    )
    assert n == 8418


def test_cache_hit_cheaper_than_fresh() -> None:
    fresh = points_from_row(
        tokens_unknown=False,
        prompt_tokens=8000,
        completion_tokens=0,
        total_tokens=8000,
        extra={"cached_tokens": 0},
        kind="llm",
        model="gpt-5.6-sol",
    )
    cached = points_from_row(
        tokens_unknown=False,
        prompt_tokens=8000,
        completion_tokens=0,
        total_tokens=8000,
        extra={"cached_tokens": 7680},
        kind="llm",
        model="gpt-5.6-sol",
    )
    assert fresh is not None and cached is not None
    assert float(cached) < float(fresh)


def test_reasoning_is_not_billed_again() -> None:
    extra = {"cached_tokens": 0, "reasoning_tokens": 25}
    assert (
        points_from_row(
            tokens_unknown=False,
            prompt_tokens=10,
            completion_tokens=25,
            total_tokens=35,
            extra=extra,
            kind="llm",
            model="gpt-5.6-sol",
        )
        == points_from_row(
            tokens_unknown=False,
            prompt_tokens=10,
            completion_tokens=25,
            total_tokens=35,
            extra={"cached_tokens": 0},
            kind="llm",
            model="gpt-5.6-sol",
        )
    )


def test_quote_tracks_last_weighted_bill() -> None:
    actual = points_from_row(
        tokens_unknown=False,
        prompt_tokens=8393,
        completion_tokens=25,
        total_tokens=8418,
        kind="llm",
        model="gpt-5.6-sol",
    )
    milli = milli_from_row(
        tokens_unknown=False,
        prompt_tokens=8393,
        completion_tokens=25,
        total_tokens=8418,
        kind="llm",
        model="gpt-5.6-sol",
    )
    quoted = quote_points_from_input_len(14, resident_milli=milli)
    assert actual is not None and quoted is not None
    assert float(quoted) >= float(actual)
