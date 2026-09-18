"""C1 usage-reconcile: token books, export match, cancel not double-counted."""

from __future__ import annotations

import importlib.util
import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "usage-reconcile.py"

_spec = importlib.util.spec_from_file_location("usage_reconcile", SCRIPT)
assert _spec is not None and _spec.loader is not None
ur = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ur)


def test_deviation_zero_and_one_percent() -> None:
    assert ur.deviation(0, 0) == 0.0
    assert ur.deviation(100, 100) == 0.0
    assert ur.deviation(100, 101) < 0.02
    assert ur.deviation(100, 90) == 0.1


def test_unknown_tokens_excluded_from_sums() -> None:
    book = ur.pico_token_book(
        [
            {
                "kind": "llm",
                "prompt_tokens": 100,
                "completion_tokens": 20,
                "tokens_unknown": False,
                "idempotency_key": "llm:r1",
            },
            {
                "kind": "llm",
                "prompt_tokens": None,
                "completion_tokens": None,
                "tokens_unknown": True,
                "idempotency_key": "llm:r2",
            },
        ]
    )
    assert book["unknown"] == 1
    assert book["known"] == 1
    assert book["total_tokens"] == 120
    assert book["duplicate_idempotency"] == 0


def test_cancel_same_run_is_one_idempotency_key() -> None:
    book = ur.pico_token_book(
        [
            {
                "kind": "llm",
                "prompt_tokens": 10,
                "completion_tokens": 2,
                "tokens_unknown": False,
                "idempotency_key": "llm:run-a",
            },
            {
                "kind": "llm",
                "prompt_tokens": 10,
                "completion_tokens": 2,
                "tokens_unknown": False,
                "idempotency_key": "llm:run-a",
            },
        ]
    )
    assert book["duplicate_idempotency"] == 1
    report = ur.reconcile(pico_book=book, newapi_book=None, export_vs_ledger=None)
    assert report["ok"] is False


def test_reconcile_under_one_percent() -> None:
    pico = {
        "total_tokens": 1000,
        "duplicate_idempotency": 0,
    }
    newapi = {"ok": True, "total_tokens": 1005}
    export = ur.export_matches_ledger(["a", "b"], ["a", "b"])
    report = ur.reconcile(pico_book=pico, newapi_book=newapi, export_vs_ledger=export)
    assert export["deviation"] == 0.0
    assert report["ok"] is True
    assert report["token_deviation"] is not None
    assert report["token_deviation"] < 0.01


def test_newapi_missing_is_honest_not_zero_billed() -> None:
    pico = {"total_tokens": 100, "duplicate_idempotency": 0}
    report = ur.reconcile(
        pico_book=pico,
        newapi_book={"ok": False, "reason": "no logs table", "total_tokens": 0},
        export_vs_ledger=None,
    )
    assert report["token_deviation"] is None
    assert report["ok"] is True


def test_read_pico_and_newapi_sqlite(tmp_path: Path) -> None:
    pico = tmp_path / "pico.db"
    con = sqlite3.connect(pico)
    con.execute(
        """
        CREATE TABLE usage_events (
            id TEXT, kind TEXT, model TEXT, prompt_tokens INT, completion_tokens INT,
            total_tokens INT, tokens_unknown INT, idempotency_key TEXT, extra_json TEXT,
            created_at TEXT
        )
        """
    )
    now = datetime.now(UTC).replace(tzinfo=None)
    con.execute(
        "INSERT INTO usage_events VALUES (?,?,?,?,?,?,?,?,?,?)",
        ("e1", "llm", "gpt-5.6-sol", 80, 20, 100, 0, "llm:r1", "{}", now.isoformat(sep=" ")),
    )
    con.commit()
    con.close()

    newapi = tmp_path / "one-api.db"
    con = sqlite3.connect(newapi)
    con.execute(
        """
        CREATE TABLE logs (
            created_at INT, prompt_tokens INT, completion_tokens INT,
            model_name TEXT, token_name TEXT, type INT
        )
        """
    )
    ts = int(now.timestamp())
    con.execute(
        "INSERT INTO logs VALUES (?,?,?,?,?,?)",
        (ts, 80, 20, "gpt-5.6-sol", "pico-gateway", 2),
    )
    con.commit()
    con.close()

    since = now - timedelta(hours=1)
    until = now + timedelta(hours=1)
    pico_rows = ur.read_pico_usage(pico, since=since, until=until)
    assert pico_rows["ok"] is True
    assert len(pico_rows["rows"]) == 1
    na = ur.read_newapi_logs(
        newapi,
        since_unix=ts - 10,
        until_unix=ts + 10,
        token_name="pico-gateway",
    )
    assert na["ok"] is True
    book_p = ur.pico_token_book(pico_rows["rows"])
    book_n = ur.newapi_token_book(na["rows"])
    report = ur.reconcile(pico_book=book_p, newapi_book=book_n, export_vs_ledger=None)
    assert report["ok"] is True
    assert report["token_deviation"] == 0.0
