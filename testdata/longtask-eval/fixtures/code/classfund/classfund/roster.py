"""花名册：学号 -> 姓名。姓名只给老师自己看，不进任何给家长的东西。"""

import csv


def load_roster(path: str) -> dict[str, str]:
    """读 学号,姓名 两列的 csv，按学号排好返回。"""
    with open(path, encoding="utf-8", newline="") as fh:
        rows = {row["学号"].strip(): row["姓名"].strip() for row in csv.DictReader(fh)}
    return dict(sorted(rows.items()))
