"""Class ranking for one subject."""

from __future__ import annotations

from .models import PARTS, Student


def _score(student: Student, subject: str) -> float | None:
    vals = [v for v in (student.part(subject, p) for p in PARTS) if v is not None]
    return round(sum(vals) / len(vals), 1) if vals else None


def _letter(score: float | None) -> str:
    if score is None:
        return "缺考"
    if score >= 85:
        return "A"
    if score >= 75:
        return "B"
    if score >= 65:
        return "C"
    if score >= 60:
        return "D"
    return "E"


def rank_class(students: list[Student], subject: str) -> list[tuple[str, float | None, str]]:
    """``[(姓名, 总评, 等级)]`` best first; no score sorts last, then by name."""
    rows = [(s.name, _score(s, subject)) for s in students if subject in s.scores]
    rows.sort(key=lambda r: (r[1] is None, -(r[1] or 0.0), r[0]))
    return [(name, score, _letter(score)) for name, score in rows]
