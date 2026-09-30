"""Read a class roster CSV (姓名,组别,分数)."""

import csv


def load_students(path):
    """Return ``[{'name', 'group', 'score'}]``.

    Files saved by Excel may start with a BOM; names may carry stray spaces.
    A blank 分数 means absent and becomes ``None``.
    """
    rows = []
    with open(path, newline="", encoding="utf-8") as fh:
        for rec in csv.DictReader(fh):
            raw = rec["分数"]
            rows.append(
                {
                    "name": rec["姓名"],
                    "group": rec["组别"].strip(),
                    "score": float(raw) if raw.strip() else None,
                }
            )
    return rows
