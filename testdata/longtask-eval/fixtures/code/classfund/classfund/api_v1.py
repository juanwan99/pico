"""家长小程序接口 v1（2026-09-01 上线）。

小程序按这里的字段名和格式解析，已上线的版本改不了，所以这个文件冻结。
"""


def _yuan(fen):
    sign = "-" if fen < 0 else ""
    y, f = divmod(abs(fen), 100)
    return f"{sign}¥{y}.{f:02d}"


def get_balance(ledger):
    bal = ledger.balance()
    return {"balance_fen": bal, "balance": _yuan(bal)}


def list_entries(ledger, sid):
    return [
        {
            "date": f"{e.day.year}/{e.day.month}/{e.day.day}",
            "amount_fen": e.amount_fen,
            "amount": _yuan(e.amount_fen),
            "category": e.category,
        }
        for e in ledger.entries_for(sid)
    ]
