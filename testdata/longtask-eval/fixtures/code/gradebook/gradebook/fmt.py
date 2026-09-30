"""Small text helpers shared by the CLI."""

from __future__ import annotations


def pct(x: float | None) -> str:
    return "—" if x is None else f"{x * 100:.1f}%"


def num(x: float | None) -> str:
    return "—" if x is None else f"{x:.1f}"


def table(rows: list[list[str]]) -> str:
    if not rows:
        return ""
    widths = [max(len(str(r[i])) for r in rows) for i in range(len(rows[0]))]
    return "\n".join("  ".join(str(c).ljust(w) for c, w in zip(r, widths)) for r in rows)
