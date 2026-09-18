"""C2/C3 ledger-capacity: size, WAL flags, >300s share, postgres threshold."""

from __future__ import annotations

import importlib.util
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "ledger-capacity.py"

_spec = importlib.util.spec_from_file_location("ledger_capacity", SCRIPT)
assert _spec is not None and _spec.loader is not None
cap = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(cap)


def test_inspect_sqlite_long_run_share_and_no_false_postgres(tmp_path: Path) -> None:
    db = tmp_path / "pico.db"
    con = sqlite3.connect(db)
    con.execute("PRAGMA journal_mode=WAL")
    con.execute(
        """
        CREATE TABLE runs (
            id TEXT, status TEXT, started_at TEXT, ended_at TEXT, created_at TEXT
        )
        """
    )
    con.execute(
        "INSERT INTO runs VALUES (?,?,?,?, datetime('now'))",
        ("r1", "succeeded", "2026-09-18 00:00:00", "2026-09-18 00:01:00"),
    )
    con.execute(
        "INSERT INTO runs VALUES (?,?,?,?, datetime('now'))",
        ("r2", "succeeded", "2026-09-18 00:00:00", "2026-09-18 00:10:00"),
    )
    con.commit()
    con.close()

    info = cap.inspect_sqlite(db, days=7)
    assert info["tables"]["runs"] == 2
    assert info["long_runs"]["ended_runs"] == 2
    assert info["long_runs"]["gt_300s"] == 1
    assert info["long_runs"]["share_gt_300s"] == 0.5
    assert info["recommend_postgres"] is False
    assert info["threshold"]["db_mb"] == 4096
    assert info["lock_busy_rate"] is None


def test_host_compose_pins_session_root_on_data_volume() -> None:
    text = (ROOT / "docker-compose.host.yml").read_text()
    assert "PICO_TRUE_PI_SESSION_ROOT: /app/data/pi-sessions" in text
    assert "PICO_TRUE_PI_MEMORY_ROOT: /app/data/pi-memory" in text
    assert "PICO_CHAT_SCHOOL_MAX_CONCURRENT" in text
