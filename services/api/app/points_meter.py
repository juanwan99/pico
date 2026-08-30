"""Teacher-facing points derived from usage_events tokens.

Scale lives in this module only. Never import from LibreChat client code.
Never persist quote guesses onto usage_events token columns.
Never store a wallet or balance.
"""

from __future__ import annotations

# Millipoints (0.001 积分) per provider token. Keep out of UI payloads.
_PER_TOKEN_MILLI = 3
_QUOTE_INPUT_CAP = 200_000


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
    if tokens_unknown:
        return None
    if total_tokens is not None:
        return max(0, int(total_tokens))
    if prompt_tokens is None and completion_tokens is None:
        return None
    return max(0, int(prompt_tokens or 0) + int(completion_tokens or 0))


def quote_points_from_input_len(n: int) -> str:
    """UX quote only. Not a ledger write. Factors stay here."""
    n = max(0, min(int(n or 0), _QUOTE_INPUT_CAP))
    if n <= 0:
        return format_millipoints(0)
    units = max(1, (n + 3) // 4) * 2
    return points_from_tokens(units)
