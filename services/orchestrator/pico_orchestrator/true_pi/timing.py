"""Where one turn's seconds go (edu-core#5227): wall marks for the ``run.timing`` event.

Ledger rows before the model's first output are held by the failover gate and
stamped at flush, so their ``created_at`` cannot split boot from first token.
These marks are taken on the loop clock as things happen, in ms from turn start.
"""

from __future__ import annotations

from typing import Any

# First sign of model output inside a round (Pi streams these as it reads tokens).
_OUTPUT_KINDS = frozenset({"text_delta", "thinking_delta", "toolcall_progress"})


class TurnTiming:
    def __init__(self, t0: float) -> None:
        self.t0 = t0
        self.marks: dict[str, float] = {}
        self.rounds: list[list[float | None]] = []

    def mark(self, name: str, now: float) -> None:
        self.marks.setdefault(name, now)

    def see(self, kind: str, raw: dict[str, Any], now: float) -> None:
        """One Pi RPC event off the transport queue."""
        if kind == "response":
            return
        self.mark("pi_first", now)
        if kind == "turn_start":
            self.rounds.append([now, None])
        elif kind == "agent_end":
            self.mark("agent_end", now)
        elif self.rounds and self.rounds[-1][1] is None and _is_output(kind, raw):
            self.rounds[-1][1] = now

    def payload(self, now: float, llm: list[tuple[float, float]] | None = None) -> dict[str, Any]:
        """``llm`` = this run's model calls as pico-api saw them: (reached us, relay's first chunk)."""

        def ms(t: float | None) -> int | None:
            return None if t is None else round((t - self.t0) * 1000)

        marks = {k: ms(v) for k, v in sorted(self.marks.items(), key=lambda kv: kv[1])}
        marks["done"] = ms(now)
        out: dict[str, Any] = {"ms": marks, "rounds_ms": [[ms(a), ms(b)] for a, b in self.rounds]}
        calls = [[ms(a), ms(b)] for a, b in (llm or []) if a >= self.t0]
        if calls:
            out["llm_ms"] = calls
        return out


def _is_output(kind: str, raw: dict[str, Any]) -> bool:
    if kind in _OUTPUT_KINDS:
        return True
    if kind in {"message_start", "message_end"}:
        # The teacher's own prompt also starts and ends a message: not model output.
        msg = raw.get("message")
        return isinstance(msg, dict) and msg.get("role") == "assistant"
    return False
