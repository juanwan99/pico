"""Attendance roll-up by class (separate CSV: 学号,日期,状态)."""

from __future__ import annotations

import csv
from collections import Counter

from .models import Student

STATES = ("到", "迟到", "请假", "旷课")


def load_attendance(path: str) -> dict[str, Counter[str]]:
    out: dict[str, Counter[str]] = {}
    with open(path, encoding="utf-8-sig", newline="") as fh:
        for row in csv.DictReader(fh):
            state = row["状态"].strip()
            if state not in STATES:
                raise ValueError(f"unknown state {state!r}")
            out.setdefault(row["学号"].strip(), Counter())[state] += 1
    return out


def class_attendance(students: list[Student], records: dict[str, Counter[str]]) -> dict[str, dict[str, int]]:
    out: dict[str, Counter[str]] = {}
    for s in students:
        out.setdefault(s.cls, Counter()).update(records.get(s.sid, Counter()))
    return {cls: {k: c[k] for k in STATES} for cls, c in sorted(out.items())}
