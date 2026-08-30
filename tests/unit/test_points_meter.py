"""Points meter: one conversion, three decimals, no wallet."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "api"))

from app.points_meter import (
    points_from_tokens,
    quote_points_from_input_len,
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


def test_quote_is_not_zero_for_short_input() -> None:
    assert quote_points_from_input_len(0) == "0.000"
    quoted = quote_points_from_input_len(40)
    assert quoted.count(".") == 1
    assert len(quoted.split(".")[1]) == 3
    assert quoted != "0.000"


def test_quote_does_not_expose_scale_in_string() -> None:
    quoted = quote_points_from_input_len(1000)
    assert "×" not in quoted
    assert "token" not in quoted.lower()
