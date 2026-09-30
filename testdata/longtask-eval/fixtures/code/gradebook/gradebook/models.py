"""Data types."""

from __future__ import annotations

from dataclasses import dataclass, field

PARTS = ("平时", "期中", "期末")


@dataclass
class Student:
    sid: str
    name: str
    cls: str
    scores: dict[str, dict[str, float | None]] = field(default_factory=dict)

    def subjects(self) -> list[str]:
        return sorted(self.scores)

    def part(self, subject: str, part: str) -> float | None:
        return self.scores.get(subject, {}).get(part)
