"""scripts/teacher-failure-rate.py — read-only ledger metric for #994 stage 1."""

from __future__ import annotations

import importlib.util
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "teacher-failure-rate.py"

_spec = importlib.util.spec_from_file_location("teacher_failure_rate", SCRIPT)
assert _spec is not None and _spec.loader is not None
tfr = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(tfr)


def _seed(db: Path) -> None:
    con = sqlite3.connect(db)
    con.execute(
        """
        create table runs (
            id text primary key, task_id text, status text, model text, prompt text,
            error text, token_usage_json text, cancel_requested integer,
            started_at text, ended_at text, created_at text
        )
        """
    )
    rows = [
        ("r1", "succeeded", None, "-30 minute", 40),
        ("r2", "succeeded", None, "-2 hour", 60),
        ("r3", "failed", 'OpenAI API error (500): {"code":"do_request_failed"}', "-3 hour", 2),
        ("r4", "failed", "server_error: Our servers are currently overloaded.", "-5 hour", 3),
        ("r5", "failed", "run owner was lost during API restart", "-3 day", 10),
        ("r6", "succeeded", None, "-3 day", 50),
        ("r7", "cancelled", None, "-4 day", 5),
        ("r8", "failed", "something unmapped", "-20 day", 1),  # outside 7d
    ]
    for rid, status, err, offset, wall in rows:
        con.execute(
            """
            insert into runs values (?, ?, ?, 'pico-fast', '{"secret":"never printed"}', ?, null, 0,
                datetime('now', ?), datetime('now', ?, ?), datetime('now', ?))
            """,
            (rid, "t-" + rid, status, err, offset, offset, f"+{wall} second", offset),
        )
    con.commit()
    con.close()


def test_bucket_maps_known_causes() -> None:
    assert tfr.bucket('{"code":"do_request_failed"}') == "upstream_relay"
    assert tfr.bucket("HTTP 524: AIProxy service is temporarily unavailable") == "upstream_524"
    assert tfr.bucket("OpenAI API error (503): AIProxy service is temporarily unavailable") == "upstream_503"
    assert tfr.bucket("server_error: overloaded") == "upstream_overloaded"
    assert tfr.bucket("processing the request: terminated") == "deploy_killed"
    assert tfr.bucket("超时未选，没有继续") == "ask_timeout"
    assert tfr.bucket("模型调用过于频繁") == "rate_or_busy"
    assert tfr.bucket("") == "no_error_text"
    assert tfr.bucket("weird") == "other"


def test_report_counts_only_no_content(tmp_path: Path) -> None:
    db = tmp_path / "pico.db"
    _seed(db)
    report = tfr.build_report(str(db), days=7)
    w24, w7d = report["windows"]
    assert w24["runs"] == 4
    assert w24["status"]["failed"] == 2
    assert w24["fail_rate"] == 0.5
    assert w24["fail_buckets"] == {"upstream_relay": 1, "upstream_overloaded": 1}
    assert w24["ok_p50_s"] == 50.0
    assert w7d["runs"] == 7  # r8 is outside the 7-day window
    assert w7d["fail_buckets"]["deploy_killed"] == 1
    assert len(report["by_day"]) >= 2
    md = tfr.render_markdown(report)
    assert "失败率" in md
    assert "secret" not in md
    assert "do_request_failed" not in md  # buckets, never raw error text
