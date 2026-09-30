"""Read the long-format score CSV: 学号,姓名,班级,科目,平时,期中,期末."""

from __future__ import annotations

import csv

from .models import PARTS, Student

MISSING = {"", "缺考", "-", "—"}


def _num(text: str | None) -> float | None:
    text = (text or "").strip()
    if text in MISSING:
        return None
    return float(text)


def load_csv(path: str) -> list[Student]:
    students: dict[str, Student] = {}
    with open(path, encoding="utf-8-sig", newline="") as fh:
        for row in csv.DictReader(fh):
            sid = row["学号"].strip()
            st = students.get(sid)
            if st is None:
                st = Student(sid=sid, name=row["姓名"].strip(), cls=row["班级"].strip())
                students[sid] = st
            st.scores[row["科目"].strip()] = {p: _num(row.get(p)) for p in PARTS}
    return list(students.values())


def by_class(students: list[Student]) -> dict[str, list[Student]]:
    out: dict[str, list[Student]] = {}
    for s in students:
        out.setdefault(s.cls, []).append(s)
    return out


def find(students: list[Student], sid: str) -> Student | None:
    for s in students:
        if s.sid == sid:
            return s
    return None
