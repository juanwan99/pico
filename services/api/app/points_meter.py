"""Teacher-facing points derived from this-turn work, not the toolbox.

Scale lives in this module only. Never import from LibreChat client code.
Never persist quote guesses onto usage_events token columns.
Never store a wallet or balance.
Provider prompt/total stay on the ledger for ops; they are the always-on
system+tools suitcase and must not become 积分.
"""

from __future__ import annotations

from typing import Any

# Millipoints (0.001 积分) per billable unit. Keep out of UI payloads.
_PER_TOKEN_MILLI = 3
_QUOTE_INPUT_CAP = 200_000
_EXTRA_USER_CHARS = "user_chars"


def format_millipoints(milli: int) -> str:
    milli = max(0, int(milli))
    return f"{milli // 1000}.{milli % 1000:03d}"


def points_from_tokens(tokens: int) -> str:
    return format_millipoints(max(0, int(tokens)) * _PER_TOKEN_MILLI)


def quote_units_from_input_len(n: int) -> int:
    """Same units as the composer 预计. Not a token-column write."""
    n = max(0, min(int(n or 0), _QUOTE_INPUT_CAP))
    if n <= 0:
        return 0
    return max(1, (n + 3) // 4) * 2


def quote_points_from_input_len(n: int) -> str:
    """UX quote only. Not a ledger write. Factors stay here."""
    n = max(0, min(int(n or 0), _QUOTE_INPUT_CAP))
    if n <= 0:
        return format_millipoints(0)
    return points_from_tokens(quote_units_from_input_len(n))


def extra_user_chars(prompt: str | None) -> dict[str, int]:
    n = len(prompt or "")
    if n <= 0:
        return {}
    return {_EXTRA_USER_CHARS: n}


def tokens_from_row(
    *,
    tokens_unknown: bool,
    total_tokens: int | None = None,
    prompt_tokens: int | None = None,
    completion_tokens: int | None = None,
    extra: dict[str, Any] | None = None,
) -> int | None:
    """Billable units for 积分.

    Unknown stays None (not 0). Provider prompt/total are ignored — they
    include the always-on suitcase. This-turn work = model output + teacher
    text (same units as 预计).
    """
    del total_tokens, prompt_tokens
    if tokens_unknown:
        return None
    if completion_tokens is None:
        return None
    work = max(0, int(completion_tokens))
    blob = extra if isinstance(extra, dict) else {}
    raw_chars = blob.get(_EXTRA_USER_CHARS)
    try:
        chars = int(raw_chars) if raw_chars is not None else 0
    except (TypeError, ValueError):
        chars = 0
    if chars > 0:
        work += quote_units_from_input_len(chars)
    return work
