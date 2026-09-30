"""Short parent notice, one sentence per subject."""

from __future__ import annotations

from .models import Student

LEVELS = [(90, "A"), (80, "B"), (70, "C"), (60, "D")]


def _level(score: float | None) -> str:
    if score is None:
        return "缺考"
    for line, name in LEVELS:
        if score > line:
            return name
    return "E"


def parent_message(student: Student) -> str:
    """``张三家长您好：本学期 语文等级 B；数学等级 A。``"""
    bits = []
    for subject in student.subjects():
        final = student.part(subject, "期末")
        bits.append(f"{subject}等级 {_level(final)}")
    return f"{student.name}家长您好：本学期 " + "；".join(bits) + "。"
