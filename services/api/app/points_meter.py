"""Teacher-facing points derived from usage_events tokens.

Scale lives in this module only. Never import from LibreChat client code.
Never persist quote guesses onto usage_events token columns.
Never store a wallet or balance.

积分 = 提供方全量（系统提示词 / 工具 schema / 本轮说话都算 token）。
预计 must cover the always-on resident package, not just teacher chars.
"""

from __future__ import annotations

# Millipoints (0.001 积分) per provider token. Keep out of UI payloads.
_PER_TOKEN_MILLI = 3
_QUOTE_INPUT_CAP = 200_000
# UX floor only — not a token-column write. Live CORE+SYSTEM first-turn ~8393.
_RESIDENT_QUOTE_FLOOR = 8400


def format_millipoints(milli: int) -> str:
    milli = max(0, int(milli))
    return f"{milli // 1000}.{milli % 1000:03d}"


def points_from_tokens(tokens: int) -> str:
    return format_millipoints(max(0, int(tokens)) * _PER_TOKEN_MILLI)


def tokens_from_row(
    *,
    tokens_unknown: bool,
    total_tokens: int | None,
    prompt_tokens: int | None,
    completion_tokens: int | None,
) -> int | None:
    """Billable units: provider total (suitcase included). Unknown stays None.

    Coverage: never bill less than prompt+completion when those landed.
    """
    if tokens_unknown:
        return None
    summed: int | None = None
    if prompt_tokens is not None or completion_tokens is not None:
        summed = max(0, int(prompt_tokens or 0) + int(completion_tokens or 0))
    if total_tokens is not None:
        billed = max(0, int(total_tokens))
        if summed is not None:
            return max(billed, summed)
        return billed
    return summed


def quote_units_from_input_len(n: int) -> int:
    """Teacher-text units only. Not a token-column write."""
    n = max(0, min(int(n or 0), _QUOTE_INPUT_CAP))
    if n <= 0:
        return 0
    return max(1, (n + 3) // 4) * 2


def quote_units_with_resident(n: int, resident_tokens: int) -> int:
    return max(0, int(resident_tokens or 0)) + quote_units_from_input_len(n)


def quote_points_from_input_len(
    n: int,
    *,
    resident_tokens: int | None = None,
) -> str:
    """UX quote only. Not a ledger write. Factors stay here.

    Default resident floor covers the always-on package so 预计 is the
    same order of magnitude as 实际. Pass resident_tokens=0 to quote
    teacher text alone (tests).
    """
    n = max(0, min(int(n or 0), _QUOTE_INPUT_CAP))
    if resident_tokens is None:
        resident = _RESIDENT_QUOTE_FLOOR
    else:
        resident = max(0, int(resident_tokens))
    units = quote_units_with_resident(n, resident)
    return points_from_tokens(units)


def resident_quote_floor() -> int:
    return _RESIDENT_QUOTE_FLOOR
