"""账本：一条记录一笔钱。收入为正（家长交的班费等），支出为负。"""

import csv
from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class Entry:
    day: date
    amount_fen: int
    category: str
    sid: str = ""  # 学号；全班的开支留空
    note: str = ""


class Ledger:
    def __init__(self, entries=()):
        self.entries: list[Entry] = []
        for e in entries:
            self.add(e)

    def add(self, entry: Entry) -> None:
        if not isinstance(entry.amount_fen, int):
            raise TypeError("amount_fen 必须是分的整数")
        self.entries.append(entry)

    def balance(self) -> int:
        return sum(e.amount_fen for e in self.entries)

    def entries_for(self, sid: str) -> list[Entry]:
        return [e for e in self.entries if e.sid == sid]

    def paid_by(self, sid: str) -> int:
        """这个学生交进来的钱（只算正数）。"""
        return sum(e.amount_fen for e in self.entries_for(sid) if e.amount_fen > 0)


def load_csv(path: str) -> Ledger:
    """读 日期,学号,金额(分),类别,备注 五列的 csv。"""
    ledger = Ledger()
    with open(path, encoding="utf-8", newline="") as fh:
        for row in csv.DictReader(fh):
            ledger.add(
                Entry(
                    day=date.fromisoformat(row["日期"]),
                    amount_fen=int(row["金额(分)"]),
                    category=row["类别"],
                    sid=row["学号"],
                    note=row["备注"],
                )
            )
    return ledger


def save_csv(ledger: Ledger, path: str) -> None:
    with open(path, "w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["日期", "学号", "金额(分)", "类别", "备注"])
        for e in ledger.entries:
            w.writerow([e.day.isoformat(), e.sid, e.amount_fen, e.category, e.note])
