"""Teacher-facing points derived from usage_events × channel cost.

Scale lives here only. Never import from LibreChat client code.
Never persist quote guesses onto usage_events token columns.
Never store a wallet or balance.

Token columns stay provider-accurate. 积分 = 成本人民币 × 2.5 × 1000
(1 元 = 1000 积分). Rate card is config/channel-rates.json.
"""

from __future__ import annotations

from typing import Any

from app.channel_rates import (
    cost_micro_yuan,
    load_rate_card,
    sell_millipoints,
)

_QUOTE_INPUT_CAP = 200_000
# UX floor only — not a token-column write. Live CORE+SYSTEM first-turn ~8393.
_RESIDENT_QUOTE_FLOOR = 8400


def format_millipoints(milli: int) -> str:
    milli = max(0, int(milli))
    return f"{milli // 1000}.{milli % 1000:03d}"


def points_from_tokens(tokens: int) -> str:
    """Bill ``tokens`` as llm fresh input on the default chat rate."""
    milli = milli_from_row(
        tokens_unknown=False,
        prompt_tokens=max(0, int(tokens)),
        completion_tokens=0,
        total_tokens=max(0, int(tokens)),
        kind="llm",
        model="gpt-5.6-sol",
    )
    if milli is None:
        return "0.000"
    return format_millipoints(milli)


def _extra_int(extra: dict[str, Any] | None, *keys: str) -> int:
    if not isinstance(extra, dict):
        return 0
    for key in keys:
        raw = extra.get(key)
        if raw is None or isinstance(raw, bool):
            continue
        if isinstance(raw, int):
            return max(0, raw)
        if isinstance(raw, float) and raw.is_integer():
            return max(0, int(raw))
        if isinstance(raw, str) and raw.strip().lstrip("-").isdigit():
            return max(0, int(raw.strip()))
    return 0


def normalize_token_counts(
    *,
    prompt_tokens: int | None,
    completion_tokens: int | None,
    total_tokens: int | None,
    cached_tokens: int | None = None,
    cache_write_tokens: int | None = None,
) -> dict[str, int | None]:
    """Make prompt the full input (cache reads included) when the provider split them."""
    prompt = None if prompt_tokens is None else max(0, int(prompt_tokens))
    completion = None if completion_tokens is None else max(0, int(completion_tokens))
    total = None if total_tokens is None else max(0, int(total_tokens))
    cached = max(0, int(cached_tokens or 0))
    write = max(0, int(cache_write_tokens or 0))
    if prompt is not None and cached and prompt < cached and total is not None:
        reconstructed = prompt + cached + (completion or 0)
        if abs(reconstructed - total) <= 1:
            prompt = prompt + cached
    if total is None and prompt is not None and completion is not None:
        total = prompt + completion
    return {
        "prompt_tokens": prompt,
        "completion_tokens": completion,
        "total_tokens": total,
        "cached_tokens": cached or None,
        "cache_write_tokens": write or None,
    }


def split_billable_buckets(
    *,
    prompt_tokens: int | None,
    completion_tokens: int | None,
    total_tokens: int | None,
    extra: dict[str, Any] | None = None,
) -> tuple[int, int, int, int] | None:
    """fresh_input, cache_read, cache_write, output. None means unknown row."""
    cached = _extra_int(extra, "cached_tokens", "cache_read", "cacheRead")
    write = _extra_int(extra, "cache_write_tokens", "cache_write", "cacheWrite")
    norm = normalize_token_counts(
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=total_tokens,
        cached_tokens=cached,
        cache_write_tokens=write,
    )
    prompt = norm["prompt_tokens"]
    completion = norm["completion_tokens"]
    cached = int(norm["cached_tokens"] or 0)
    write = int(norm["cache_write_tokens"] or 0)
    if prompt is None and completion is None and total_tokens is None:
        return None
    prompt_n = 0 if prompt is None else prompt
    output_n = 0 if completion is None else completion
    cached = min(cached, prompt_n)
    write = min(write, max(0, prompt_n - cached))
    fresh = max(0, prompt_n - cached - write)
    return fresh, cached, write, output_n


def milli_from_buckets(fresh: int, cache_read: int, cache_write: int, output: int) -> int:
    """Legacy 1×/0.1×/1.25×/6× units. Prefer milli_from_row (rate card)."""
    milli = max(0, int(fresh)) * 3
    milli += (max(0, int(cache_read)) * 3) // 10
    milli += (max(0, int(cache_write)) * 15) // 4
    milli += max(0, int(output)) * 18
    return milli


def milli_from_row(
    *,
    tokens_unknown: bool,
    total_tokens: int | None,
    prompt_tokens: int | None,
    completion_tokens: int | None,
    extra: dict[str, Any] | None = None,
    kind: str | None = None,
    model: str | None = None,
) -> int | None:
    extra = extra if isinstance(extra, dict) else {}
    kind_n = (kind or str(extra.get("kind") or "") or "llm").strip().lower()
    model_n = (model or str(extra.get("billed_model") or "")).strip() or None
    channel_id = str(extra.get("channel_id") or "").strip() or None
    card = load_rate_card()
    rate = card.find(kind=kind_n, model=model_n, channel_id=channel_id)
    if rate is None or not rate.priced():
        return None
    cached = _extra_int(extra, "cached_tokens", "cache_read", "cacheRead")
    write = _extra_int(extra, "cache_write_tokens", "cache_write", "cacheWrite")
    ok = extra.get("ok")
    cost = cost_micro_yuan(
        rate,
        kind=kind_n,
        tokens_unknown=bool(tokens_unknown),
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=total_tokens,
        cached_tokens=cached,
        cache_write_tokens=write,
        ok=ok is not False,
        image_count=max(1, _extra_int(extra, "image_count") or 1),
        call_count=max(1, _extra_int(extra, "query_count") or 1),
    )
    if cost is None:
        return None
    return sell_millipoints(cost)


def tokens_from_row(
    *,
    tokens_unknown: bool,
    total_tokens: int | None,
    prompt_tokens: int | None,
    completion_tokens: int | None,
) -> int | None:
    """Physical provider tokens (suitcase included). Unknown stays None.

    Not the bill. Use milli_from_row / points_from_row for 积分.
    """
    if tokens_unknown:
        return None
    extra = None
    buckets = split_billable_buckets(
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=total_tokens,
        extra=extra,
    )
    if buckets is None:
        return None
    fresh, cached, write, output = buckets
    physical = fresh + cached + write + output
    if total_tokens is not None:
        return max(physical, max(0, int(total_tokens)))
    return physical or None


def points_from_row(
    *,
    tokens_unknown: bool,
    total_tokens: int | None,
    prompt_tokens: int | None,
    completion_tokens: int | None,
    extra: dict[str, Any] | None = None,
    kind: str | None = None,
    model: str | None = None,
) -> str | None:
    milli = milli_from_row(
        tokens_unknown=tokens_unknown,
        total_tokens=total_tokens,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        extra=extra,
        kind=kind,
        model=model,
    )
    if milli is None:
        return None
    return format_millipoints(milli)


def quote_units_from_input_len(n: int) -> int:
    """Teacher-text units only (1×). Not a token-column write."""
    n = max(0, min(int(n or 0), _QUOTE_INPUT_CAP))
    if n <= 0:
        return 0
    return max(1, (n + 3) // 4) * 2


def quote_points_from_input_len(
    n: int,
    *,
    resident_milli: int | None = None,
    resident_tokens: int | None = None,
) -> str:
    """UX quote only. Not a ledger write. Factors stay here.

    Default resident floor is first-turn fresh input (no cache yet).
    Pass resident_milli=0 / resident_tokens=0 to quote teacher text alone.
    """
    n = max(0, min(int(n or 0), _QUOTE_INPUT_CAP))
    extra_units = quote_units_from_input_len(n)
    extra = milli_from_row(
        tokens_unknown=False,
        prompt_tokens=extra_units,
        completion_tokens=0,
        total_tokens=extra_units,
        kind="llm",
        model="gpt-5.6-sol",
    ) or 0
    if resident_milli is not None:
        base = max(0, int(resident_milli))
    elif resident_tokens is not None:
        base = milli_from_row(
            tokens_unknown=False,
            prompt_tokens=max(0, int(resident_tokens)),
            completion_tokens=0,
            total_tokens=max(0, int(resident_tokens)),
            kind="llm",
            model="gpt-5.6-sol",
        ) or 0
    else:
        base = resident_quote_floor_milli()
    return format_millipoints(base + extra)


def resident_quote_floor() -> int:
    return _RESIDENT_QUOTE_FLOOR


def resident_quote_floor_milli() -> int:
    return milli_from_row(
        tokens_unknown=False,
        prompt_tokens=_RESIDENT_QUOTE_FLOOR,
        completion_tokens=0,
        total_tokens=_RESIDENT_QUOTE_FLOOR,
        kind="llm",
        model="gpt-5.6-sol",
    ) or 0
