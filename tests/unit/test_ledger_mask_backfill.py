"""pico#1324: old tool.call rows get the same masking new rows get on write."""

from __future__ import annotations

import importlib.util
import json
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "ledger_mask_backfill", ROOT / "scripts" / "ledger-mask-backfill.py"
)
backfill = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(backfill)


def _db(tmp_path: Path) -> Path:
    path = tmp_path / "pico.db"
    conn = sqlite3.connect(path)
    conn.execute(
        "CREATE TABLE events (id TEXT PRIMARY KEY, run_id TEXT, seq INT, type TEXT, payload_json TEXT, created_at TEXT)"
    )
    rows = [
        (
            "1",
            "tool.call",
            {"tool": "sandbox_browser_type", "arguments": {"ref": "e5", "text": "677294"}},
        ),
        (
            "2",
            "tool.call",
            {
                "tool": "sandbox_browser_fill_form",
                "arguments": {"fields": [{"ref": "e3", "value": "13800138000"}]},
            },
        ),
        (
            "3",
            "tool.call",
            {"tool": "sandbox_browser_navigate", "arguments": {"url": "https://a.cn/l?token=zz"}},
        ),
        (
            "4",
            "tool.call",
            {"tool": "sandbox_browser_open", "arguments": {"url": "https://www.baidu.com"}},
        ),
        (
            "5",
            "tool.call",
            {"tool": "sandbox_browser_type", "arguments": {"ref": "e5", "text": "***"}},
        ),
        ("6", "tool.result", {"tool": "sandbox_browser_type", "result": "ok"}),
        ("7", "tool.call", {"tool": "bash", "arguments": {"command": "echo 677294"}}),
    ]
    conn.executemany(
        "INSERT INTO events VALUES (?, 'r', 1, ?, ?, '')",
        [(i, t, json.dumps(p, ensure_ascii=False)) for i, t, p in rows],
    )
    conn.commit()
    conn.close()
    return path


def test_backfill_masks_only_rows_that_change(tmp_path, monkeypatch, capsys) -> None:
    db = _db(tmp_path)
    monkeypatch.setattr("sys.argv", ["x", "--db", str(db), "--dry-run"])
    assert backfill.main() == 0
    assert json.loads(capsys.readouterr().out)["rows"] == 3
    monkeypatch.setattr("sys.argv", ["x", "--db", str(db)])
    assert backfill.main() == 2  # no backup, no write
    bak = tmp_path / "pico.db.bak"
    monkeypatch.setattr("sys.argv", ["x", "--db", str(db), "--backup", str(bak)])
    assert backfill.main() == 0
    blob = " ".join(
        r[0]
        for r in sqlite3.connect(db).execute(
            "SELECT payload_json FROM events WHERE id IN ('1','2','3')"
        )
    )
    assert "677294" not in blob and "13800138000" not in blob and "token=zz" not in blob
    kept = dict(
        sqlite3.connect(db).execute("SELECT id, payload_json FROM events WHERE id IN ('4','7')")
    )
    assert "https://www.baidu.com" in kept["4"] and "echo 677294" in kept["7"]
    assert "677294" in " ".join(
        r[0] for r in sqlite3.connect(bak).execute("SELECT payload_json FROM events")
    )
