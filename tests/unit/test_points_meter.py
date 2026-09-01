"""Points meter: weighted conversion, precise buckets, no wallet."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "api"))

from app.points_meter import (
    milli_from_row,
    normalize_token_counts,
    points_from_row,
    points_from_tokens,
    quote_points_from_input_len,
    quote_units_from_input_len,
    resident_quote_floor,
    tokens_from_row,
)


def test_owner_example_thousand_fresh_tokens_is_three_points() -> None:
    assert points_from_tokens(1000) == "3.000"


def test_one_token_is_three_thousandths() -> None:
    assert points_from_tokens(1) == "0.003"


def test_zero_and_negative() -> None:
    assert points_from_tokens(0) == "0.000"
    assert points_from_tokens(-8) == "0.000"


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
        )
        is None
    )


def test_quote_covers_resident_even_when_empty() -> None:
    empty = quote_points_from_input_len(0)
    short = quote_points_from_input_len(14)
    assert empty == "25.200"
    assert short == "25.224"


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


def test_no_cache_bills_output_six_times_fresh() -> None:
    # 8393×1 + 25×6 = 8543 1×-units → 25.629
    assert (
        points_from_row(
            tokens_unknown=False,
            prompt_tokens=8393,
            completion_tokens=25,
            total_tokens=8418,
            extra={"cached_tokens": 0},
        )
        == "25.629"
    )


def test_live_cache_hit_is_one_tenth() -> None:
    # Live row: prompt 1058 (uncached) + cache 7680 + out 78 = 8816
    norm = normalize_token_counts(
        prompt_tokens=1058,
        completion_tokens=78,
        total_tokens=8816,
        cached_tokens=7680,
    )
    assert norm["prompt_tokens"] == 8738
    assert (
        points_from_row(
            tokens_unknown=False,
            prompt_tokens=1058,
            completion_tokens=78,
            total_tokens=8816,
            extra={"cached_tokens": 7680},
        )
        == "6.882"
    )
    assert (
        points_from_row(
            tokens_unknown=False,
            prompt_tokens=8738,
            completion_tokens=78,
            total_tokens=8816,
            extra={"cached_tokens": 7680},
        )
        == "6.882"
    )


def test_live_no_cache_turns_from_screenshot() -> None:
    assert (
        points_from_row(
            tokens_unknown=False,
            prompt_tokens=8430,
            completion_tokens=240,
            total_tokens=8670,
        )
        == "29.610"
    )
    assert (
        points_from_row(
            tokens_unknown=False,
            prompt_tokens=8680,
            completion_tokens=49,
            total_tokens=8729,
        )
        == "26.922"
    )


def test_cache_write_premium_not_double_fresh() -> None:
    # prompt 8 includes cacheRead 3 + cacheWrite 1; output 7 (Pi aliases)
    assert (
        milli_from_row(
            tokens_unknown=False,
            prompt_tokens=8,
            completion_tokens=7,
            total_tokens=15,
            extra={"cached_tokens": 3, "cache_write_tokens": 1},
        )
        == (4 * 3) + (3 * 3) // 10 + (1 * 15) // 4 + (7 * 18)
    )


def test_reasoning_is_not_billed_again() -> None:
    extra = {"cached_tokens": 0, "reasoning_tokens": 25}
    assert (
        points_from_row(
            tokens_unknown=False,
            prompt_tokens=10,
            completion_tokens=25,
            total_tokens=35,
            extra=extra,
        )
        == points_from_row(
            tokens_unknown=False,
            prompt_tokens=10,
            completion_tokens=25,
            total_tokens=35,
            extra={"cached_tokens": 0},
        )
    )


def test_quote_tracks_last_weighted_bill() -> None:
    actual = points_from_row(
        tokens_unknown=False,
        prompt_tokens=8393,
        completion_tokens=25,
        total_tokens=8418,
    )
    milli = milli_from_row(
        tokens_unknown=False,
        prompt_tokens=8393,
        completion_tokens=25,
        total_tokens=8418,
    )
    quoted = quote_points_from_input_len(14, resident_milli=milli)
    assert actual == "25.629"
    assert quoted == "25.653"
    assert quoted.startswith("25.")
    assert actual.startswith("25.")
