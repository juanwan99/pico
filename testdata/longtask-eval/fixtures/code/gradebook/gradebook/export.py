"""Flat CSV for the office: one row per student and subject."""

from __future__ import annotations

import csv

from .models import Student

HEADER = ["学号", "姓名", "班级", "科目", "总评", "等级"]


def export_csv(students: list[Student], path: str) -> int:
    n = 0
    with open(path, "w", encoding="utf-8-sig", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(HEADER)
        for s in sorted(students, key=lambda s: (s.cls, s.sid)):
            for subject in s.subjects():
                parts = s.scores[subject]
                if parts.get("期末") is None:
                    total = None
                else:
                    total = (
                        0.3 * (parts.get("平时") or 0)
                        + 0.3 * (parts.get("期中") or 0)
                        + 0.4 * parts["期末"]
                    )
                if total is None:
                    letter = "缺考"
                elif total >= 90:
                    letter = "A"
                elif total >= 80:
                    letter = "B"
                elif total >= 70:
                    letter = "C"
                elif total >= 60:
                    letter = "D"
                else:
                    letter = "F"
                w.writerow([s.sid, s.name, s.cls, subject, "" if total is None else f"{total:.1f}", letter])
                n += 1
    return n
