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


def test_pico_token_book_prefers_ledger_total_with_reasoning() -> None:
    book = ur.pico_token_book(
        [
            {
                "kind": "llm",
                "prompt_tokens": 100,
                "completion_tokens": 20,
                "total_tokens": 150,
                "tokens_unknown": False,
                "idempotency_key": "llm:r1",
            }
        ]
    )
    assert book["prompt_tokens"] == 100
    assert book["completion_tokens"] == 20
    assert book["total_tokens"] == 150
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


def test_headline_ok_ignores_embed_mix() -> None:
    pico_rows = [
        {
            "kind": "llm",
            "model": "gpt-5.6-sol",
            "prompt_tokens": 800,
            "completion_tokens": 200,
            "tokens_unknown": False,
            "idempotency_key": "llm:r1",
        }
    ]
    newapi_rows = [
        {"model_name": "gpt-5.6-sol", "prompt_tokens": 800, "completion_tokens": 200},
        {"model_name": "embedding-3", "prompt_tokens": 400, "completion_tokens": 0},
    ]
    pico = ur.pico_token_book(pico_rows)
    newapi = ur.newapi_token_book(newapi_rows)
    blended = ur.deviation(pico["total_tokens"], newapi["total_tokens"])
    assert blended > 0.2
    report = ur.reconcile(
        pico_book=pico,
        newapi_book=newapi,
        export_vs_ledger=None,
        pico_rows=pico_rows,
        newapi_rows=newapi_rows,
    )
    assert report["ok"] is True
    assert report["by_model"]["gpt-5.6-sol"]["comparable"] is True
    assert report["by_model"]["embedding-3"]["comparable"] is False
    assert report["by_model"]["embedding-3"]["lane"] == "embed"


def test_run_join_two_completions_match_one_pico_row() -> None:
    pico_rows = [
        {
            "kind": "llm",
            "model": "gemini-3.8-flash",
            "run_id": "r1",
            "prompt_tokens": 80,
            "completion_tokens": 20,
            "total_tokens": 100,
            "tokens_unknown": False,
            "idempotency_key": "llm:r1",
            "created_at": "2026-09-20 00:00:10",
        }
    ]
    runs = {
        "r1": {
            "id": "r1",
            "started_at": "2026-09-20 00:00:00",
            "ended_at": "2026-09-20 00:01:00",
        }
    }
    t0 = int(datetime(2026, 9, 20, 0, 0, 10, tzinfo=UTC).timestamp())
    newapi_rows = [
        {
            "id": 1,
            "created_at": t0,
            "model_name": "gemini-3.8-flash",
            "prompt_tokens": 50,
            "completion_tokens": 10,
        },
        {
            "id": 2,
            "created_at": t0 + 20,
            "model_name": "gemini-3.8-flash",
            "prompt_tokens": 30,
            "completion_tokens": 10,
        },
        {
            "id": 3,
            "created_at": t0 + 3600,
            "model_name": "gemini-3.8-flash",
            "prompt_tokens": 999,
            "completion_tokens": 1,
        },
        {
            "id": 4,
            "created_at": t0,
            "model_name": "rerank-pro",
            "prompt_tokens": 40,
            "completion_tokens": 0,
        },
    ]
    joined = ur.join_newapi_to_llm_runs(pico_rows, runs, newapi_rows)
    assert joined is not None
    assert joined["assigned_events"] == 2
    assert joined["assigned_tokens"] == 100
    assert joined["unattributed_events"] == 1
    assert joined["unattributed_tokens"] == 1000
    pico = ur.pico_token_book(pico_rows)
    report = ur.reconcile(
        pico_book=pico,
        newapi_book=ur.newapi_token_book(newapi_rows),
        export_vs_ledger=None,
        pico_rows=pico_rows,
        newapi_rows=newapi_rows,
        run_join=joined,
    )
    assert report["ok"] is True
    assert report["by_model"]["gemini-3.8-flash"]["token_deviation"] == 0.0
    assert report["by_model"]["gemini-3.8-flash"]["newapi"]["events"] == 2
    assert report["run_join"]["unattributed_tokens"] == 1000
    assert "assigned_rows" not in report["run_join"]


def test_unknown_run_newapi_is_not_gated() -> None:
    pico_rows = [
        {
            "kind": "llm",
            "model": "gpt-5.6-sol",
            "run_id": "ok",
            "prompt_tokens": 10,
            "completion_tokens": 0,
            "total_tokens": 10,
            "tokens_unknown": False,
            "idempotency_key": "llm:ok",
            "created_at": "2026-09-20 00:00:05",
        },
        {
            "kind": "llm",
            "model": "gpt-5.6-sol",
            "run_id": "fail",
            "tokens_unknown": True,
            "idempotency_key": "llm:fail",
            "created_at": "2026-09-20 00:00:05",
        },
    ]
    runs = {
        "ok": {"started_at": "2026-09-20 00:00:00", "ended_at": "2026-09-20 00:00:10"},
        "fail": {"started_at": "2026-09-20 00:00:11", "ended_at": "2026-09-20 00:00:20"},
    }
    t_ok = int(datetime(2026, 9, 20, 0, 0, 5, tzinfo=UTC).timestamp())
    t_fail = int(datetime(2026, 9, 20, 0, 0, 15, tzinfo=UTC).timestamp())
    newapi_rows = [
        {"id": 1, "created_at": t_ok, "model_name": "gpt-5.6-sol", "prompt_tokens": 10, "completion_tokens": 0},
        {"id": 2, "created_at": t_fail, "model_name": "gpt-5.6-sol", "prompt_tokens": 80, "completion_tokens": 0},
    ]
    joined = ur.join_newapi_to_llm_runs(pico_rows, runs, newapi_rows)
    assert joined is not None
    report = ur.reconcile(
        pico_book=ur.pico_token_book(pico_rows),
        newapi_book=ur.newapi_token_book(newapi_rows),
        export_vs_ledger=None,
        pico_rows=pico_rows,
        newapi_rows=newapi_rows,
        run_join=joined,
    )
    assert report["ok"] is True
    assert report["by_model"]["gpt-5.6-sol"]["token_deviation"] == 0.0
    assert report["by_model"]["gpt-5.6-sol"]["newapi"]["total_tokens"] == 10


def test_run_join_skipped_without_run_id() -> None:
    pico_rows = [
        {
            "kind": "llm",
            "model": "gpt-5.6-sol",
            "prompt_tokens": 80,
            "completion_tokens": 20,
            "tokens_unknown": False,
            "idempotency_key": "llm:r1",
        }
    ]
    assert ur.join_newapi_to_llm_runs(pico_rows, {}, [{"model_name": "gpt-5.6-sol"}]) is None


def test_unknown_llm_breakdown_keeps_reason() -> None:
    rows = [
        {
            "kind": "llm",
            "model": "gpt-5.6-sol",
            "tokens_unknown": True,
            "source": "openai_compat",
            "extra": {"reason": "provider_usage_missing", "fail_without_usage": True},
        }
    ]
    out = ur.unknown_llm_breakdown(rows)
    assert len(out) == 1
    assert out[0]["reason"] == "provider_usage_missing"
    assert out[0]["fail_without_usage"] is True


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
