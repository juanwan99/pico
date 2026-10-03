"""Pi reports input without cache; prompt must hold the whole input whatever the sizes (#1173)."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "orchestrator"))
sys.path.insert(0, str(ROOT / "services" / "api"))

from app.points_meter import normalize_token_counts
from pico_orchestrator.usage_parse import add_usage, parse_usage_blob


def _pi(fresh: int, cache_read: int, output: int, cache_write: int = 0) -> dict:
    # Pi 0.84.4 openai-completions parseChunkUsage shape.
    return {
        "input": fresh,
        "output": output,
        "cacheRead": cache_read,
        "cacheWrite": cache_write,
        "totalTokens": fresh + output + cache_read + cache_write,
    }


def test_fresh_bigger_than_cache_still_adds_the_cache_back() -> None:
    got = parse_usage_blob(_pi(fresh=7904, cache_read=4096, output=300))
    assert got["prompt_tokens"] == 12000
    assert got["cached_tokens"] == 4096


def test_fresh_smaller_than_cache_adds_back_as_before() -> None:
    assert parse_usage_blob(_pi(fresh=500, cache_read=9000, output=50))["prompt_tokens"] == 9500


def test_cache_write_counts_as_input_too() -> None:
    got = parse_usage_blob(_pi(fresh=1000, cache_read=0, output=10, cache_write=2000))
    assert got["prompt_tokens"] == 3000


def test_openai_shape_prompt_already_holds_the_cache() -> None:
    blob = {
        "prompt_tokens": 12000,
        "completion_tokens": 300,
        "total_tokens": 12300,
        "prompt_tokens_details": {"cached_tokens": 4096},
    }
    assert parse_usage_blob(blob)["prompt_tokens"] == 12000


def test_a_run_of_mixed_calls_sums_whole_inputs() -> None:
    run = None
    for piece in (_pi(7904, 4096, 300), _pi(500, 9000, 50), _pi(2000, 0, 20)):
        run = add_usage(run, piece)
    assert run["prompt_tokens"] == 12000 + 9500 + 2000
    assert run["total_tokens"] == run["prompt_tokens"] + run["completion_tokens"]


def test_read_side_normalizer_matches() -> None:
    norm = normalize_token_counts(
        prompt_tokens=7904, completion_tokens=300, total_tokens=12300, cached_tokens=4096
    )
    assert norm["prompt_tokens"] == 12000
    full = normalize_token_counts(
        prompt_tokens=12000, completion_tokens=300, total_tokens=12300, cached_tokens=4096
    )
    assert full["prompt_tokens"] == 12000
