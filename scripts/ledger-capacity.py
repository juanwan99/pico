#!/usr/bin/env python3
"""C2/C3: SQLite size + lock pragmas + share of runs longer than 300s. Read-only.

On ECS:
  docker cp scripts/ledger-capacity.py pico-pico-api-1:/tmp/cap.py \\
    && docker exec pico-pico-api-1 python3 /tmp/cap.py --db /app/data/pico.db

Postgres 只在过阈后换 URL+驱动，不重写账本。本脚本只出数。
"""

from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path
from typing import Any

DB_MB_THRESHOLD = 4096
LOCK_BUSY_THRESHOLD = 0.05
LONG_S = 300


def inspect_sqlite(db: Path, *, days: int = 7) -> dict[str, Any]:
    size_mb = db.stat().st_size / (1024 * 1024) if db.is_file() else 0.0
    wal = Path(str(db) + "-wal")
    wal_mb = wal.stat().st_size / (1024 * 1024) if wal.is_file() else 0.0
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    journal = con.execute("PRAGMA journal_mode").fetchone()[0]
    busy = con.execute("PRAGMA busy_timeout").fetchone()[0]
    tables: dict[str, int] = {}
    for (name,) in con.execute("SELECT name FROM sqlite_master WHERE type='table'"):
        tables[str(name)] = int(con.execute(f"SELECT COUNT(*) FROM {name}").fetchone()[0])
    long_share = _long_run_share(con, days=days)
    con.close()
    recommend = size_mb >= DB_MB_THRESHOLD
    return {
        "db": str(db),
        "db_mb": round(size_mb, 2),
        "wal_mb": round(wal_mb, 2),
        "journal_mode": journal,
        "busy_timeout_ms": busy,
        "tables": tables,
        "long_runs": long_share,
        "recommend_postgres": recommend,
        "threshold": {
            "db_mb": DB_MB_THRESHOLD,
            "lock_busy_rate": LOCK_BUSY_THRESHOLD,
            "long_s": LONG_S,
        },
        "lock_busy_rate": None,
        "notes": [
            "lock_busy_rate not sampled (read-only; no write storm)",
            "switch Postgres only when recommend_postgres or measured lock_busy_rate>=5%",
        ],
    }


def _long_run_share(con: sqlite3.Connection, *, days: int) -> dict[str, Any]:
    names = {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    if "runs" not in names:
        return {"ok": False, "reason": "no runs table"}
    rows = con.execute(
        """
        SELECT status,
               (julianday(ended_at) - julianday(started_at)) * 86400 AS wall_s
        FROM runs
        WHERE created_at >= datetime('now', ?)
          AND started_at IS NOT NULL
          AND ended_at IS NOT NULL
        """,
        (f"-{int(days)} day",),
    ).fetchall()
    walls = [float(r[1]) for r in rows if r[1] is not None and r[1] >= 0]
    long_n = sum(1 for w in walls if w > LONG_S)
    total = len(walls)
    return {
        "ok": True,
        "days": days,
        "ended_runs": total,
        "gt_300s": long_n,
        "share_gt_300s": round((long_n / total), 4) if total else 0.0,
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Pico ledger capacity snapshot")
    p.add_argument("--db", type=Path, required=True)
    p.add_argument("--days", type=int, default=7)
    args = p.parse_args(argv)
    print(json.dumps(inspect_sqlite(args.db, days=args.days), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
