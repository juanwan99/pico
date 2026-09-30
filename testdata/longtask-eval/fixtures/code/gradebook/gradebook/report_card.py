"""Per-student report card (text)."""

from __future__ import annotations

from .models import Student


def _grade(score: float | None) -> str:
    if score is None:
        return "缺考"
    if score >= 90:
        return "A"
    if score >= 80:
        return "B"
    if score >= 70:
        return "C"
    if score >= 60:
        return "D"
    return "E"


def render_card(student: Student) -> str:
    """One line per subject: ``语文  总评 88.5  等级 B``."""
    lines = [f"{student.name}（{student.cls}）成绩单"]
    for subject in student.subjects():
        final = student.part(subject, "期末")
        shown = "—" if final is None else f"{final:.1f}"
        lines.append(f"{subject}  总评 {shown}  等级 {_grade(final)}")
    return "\n".join(lines)
