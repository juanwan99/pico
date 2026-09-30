"""Per-class, per-subject summary: mean, pass rate, letter counts."""

from __future__ import annotations

from collections import Counter
from typing import Any

from .loader import by_class
from .models import Student


def class_summary(students: list[Student]) -> dict[str, dict[str, dict[str, Any]]]:
    out: dict[str, dict[str, dict[str, Any]]] = {}
    for cls, members in sorted(by_class(students).items()):
        subjects = sorted({sub for s in members for sub in s.scores})
        info: dict[str, dict[str, Any]] = {}
        for sub in subjects:
            totals: list[float] = []
            letters: Counter[str] = Counter()
            for s in members:
                parts = s.scores.get(sub)
                if not parts:
                    continue
                vals = [v for v in parts.values() if v is not None]
                if not vals:
                    letters["缺考"] += 1
                    continue
                t = sum(vals) / len(vals)
                totals.append(t)
                if t >= 90:
                    letters["A"] += 1
                elif t >= 80:
                    letters["B"] += 1
                elif t >= 70:
                    letters["C"] += 1
                elif t > 60:
                    letters["D"] += 1
                else:
                    letters["E"] += 1
            info[sub] = {
                "mean": round(sum(totals) / len(totals), 1) if totals else None,
                "pass_rate": round(sum(1 for t in totals if t > 60) / len(totals), 3) if totals else None,
                "letters": dict(letters),
            }
        out[cls] = info
    return out
