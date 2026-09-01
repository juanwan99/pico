"""Points meter: one conversion, three decimals, no wallet."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "api"))

from app.points_meter import (
    points_from_tokens,
    quote_points_from_input_len,
    quote_units_from_input_len,
    resident_quote_floor,
    tokens_from_row,
)


def test_owner_example_thousand_tokens_is_three_points() -> None:
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


def test_quote_covers_resident_even_when_empty() -> None:
    empty = quote_points_from_input_len(0)
    short = quote_points_from_input_len(14)
    assert empty == "25.200"
    assert short == "25.224"
    assert empty.count(".") == 1
    assert len(short.split(".")[1]) == 3


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


def test_owner_screenshot_bills_full_provider_total() -> None:
    n = tokens_from_row(
        tokens_unknown=False,
        prompt_tokens=8393,
        completion_tokens=25,
        total_tokens=8418,
    )
    assert n == 8418
    assert points_from_tokens(n) == "25.254"


def test_prompt_plus_completion_when_total_missing() -> None:
    n = tokens_from_row(
        tokens_unknown=False,
        prompt_tokens=8393,
        completion_tokens=25,
        total_tokens=None,
    )
    assert n == 8418
    assert points_from_tokens(n) == "25.254"


def test_never_bill_less_than_prompt_plus_completion() -> None:
    n = tokens_from_row(
        tokens_unknown=False,
        prompt_tokens=8393,
        completion_tokens=25,
        total_tokens=1000,
    )
    assert n == 8418
    assert points_from_tokens(n) == "25.254"


def test_quote_with_last_billable_total_matches_actual_order() -> None:
    quoted = quote_points_from_input_len(14, resident_tokens=8418)
    actual = points_from_tokens(8418)
    assert quoted == "25.278"
    assert actual == "25.254"
    assert quoted.startswith("25.")
    assert actual.startswith("25.")
