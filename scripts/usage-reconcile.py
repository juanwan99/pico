#!/usr/bin/env python3
"""C1: New API logs ↔ Pico usage_events ↔ export. Read-only. Not a wallet.

On ECS (typical):
  python3 scripts/usage-reconcile.py \\
    --pico-db /opt/pico/data/pico.db \\
    --newapi-db /home/ops/new-api/data/one-api.db \\
    --hours 24

edu 钱包实扣不在本仓。第三本 = export 行（与 usage_events 应逐行同）。
unknown token 单独列，不当 0。偏差门槛默认 1%。
头条 ok 只看可对的聊天/精排车道；查询嵌入不混进头条。
聊天按 Pico run 窗口对齐 New API completion（一轮多 completion）；窗外调用单列，不进头条。
"""

from __future__ import annotations

import argparse
import json
import sqlite3
from collections import defaultdict
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

THRESHOLD = 0.01
RUN_SLACK_S = 2


def deviation(a: float, b: float) -> float:
    if a == 0 and b == 0:
        return 0.0
    return abs(a - b) / max(abs(a), abs(b))


def _connect_ro(path: Path) -> sqlite3.Connection:
    return sqlite3.connect(f"file:{path}?mode=ro", uri=True)


def _table_names(con: sqlite3.Connection) -> set[str]:
    rows = con.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    return {str(r[0]) for r in rows}


def _cols(con: sqlite3.Connection, table: str) -> set[str]:
    return {str(r[1]) for r in con.execute(f"PRAGMA table_info({table})")}


def read_pico_usage(
    db: Path, *, since: datetime, until: datetime
) -> dict[str, Any]:
    con = _connect_ro(db)
    if "usage_events" not in _table_names(con):
        return {"ok": False, "reason": "no usage_events table", "rows": []}
    cols = _cols(con, "usage_events")
    select_cols = [
        "id",
        "kind",
        "model",
        "prompt_tokens",
        "completion_tokens",
        "total_tokens",
        "tokens_unknown",
        "idempotency_key",
        "extra_json",
    ]
    if "source" in cols:
        select_cols.append("source")
    if "run_id" in cols:
        select_cols.append("run_id")
    if "created_at" in cols:
        select_cols.append("created_at")
    rows = con.execute(
        f"""
        SELECT {", ".join(select_cols)}
        FROM usage_events
        WHERE created_at >= ? AND created_at < ?
        """,
        (since.replace(tzinfo=None).isoformat(sep=" "), until.replace(tzinfo=None).isoformat(sep=" ")),
    ).fetchall()
    con.close()
    out_rows = []
    for row in rows:
        extra = {}
        if row[8]:
            try:
                extra = json.loads(row[8])
            except json.JSONDecodeError:
                extra = {}
        rec = {
            "id": row[0],
            "kind": row[1],
            "model": row[2],
            "prompt_tokens": row[3],
            "completion_tokens": row[4],
            "total_tokens": row[5],
            "tokens_unknown": bool(row[6]),
            "idempotency_key": row[7],
            "extra": extra,
        }
        idx = 9
        if "source" in cols:
            rec["source"] = row[idx]
            idx += 1
        if "run_id" in cols:
            rec["run_id"] = row[idx]
            idx += 1
        if "created_at" in cols:
            rec["created_at"] = row[idx]
        out_rows.append(rec)
    return {"ok": True, "rows": out_rows}


def read_pico_runs(db: Path, *, since: datetime, until: datetime) -> dict[str, dict[str, Any]]:
    con = _connect_ro(db)
    if "runs" not in _table_names(con):
        con.close()
        return {}
    cols = _cols(con, "runs")
    need = {"id", "started_at", "ended_at", "created_at"}
    if not need.issubset(cols):
        con.close()
        return {}
    select = ["id", "started_at", "ended_at", "created_at"]
    if "status" in cols:
        select.append("status")
    rows = con.execute(
        f"""
        SELECT {", ".join(select)}
        FROM runs
        WHERE COALESCE(ended_at, created_at) >= ?
          AND COALESCE(started_at, created_at) < ?
        """,
        (since.replace(tzinfo=None).isoformat(sep=" "), until.replace(tzinfo=None).isoformat(sep=" ")),
    ).fetchall()
    con.close()
    out: dict[str, dict[str, Any]] = {}
    for row in rows:
        rec = {select[i]: row[i] for i in range(len(select))}
        rid = str(rec.get("id") or "").strip()
        if rid:
            out[rid] = rec
    return out


def pico_token_book(rows: list[dict[str, Any]]) -> dict[str, Any]:
    prompt = 0
    completion = 0
    total = 0
    unknown = 0
    known = 0
    by_kind: dict[str, int] = defaultdict(int)
    keys = [str(r.get("idempotency_key") or "") for r in rows]
    dup_keys = len(keys) - len({k for k in keys if k})
    for row in rows:
        kind = str(row.get("kind") or "other")
        by_kind[kind] += 1
        if row.get("tokens_unknown"):
            unknown += 1
            continue
        known += 1
        pt = int(row.get("prompt_tokens") or 0)
        ct = int(row.get("completion_tokens") or 0)
        tt = int(row.get("total_tokens") or 0)
        prompt += pt
        completion += ct
        # Gemini stores reasoning in extra; New API folds it into prompt+completion.
        # Ledger total_tokens is the billed amount when present.
        total += tt if tt > 0 else (pt + ct)
    return {
        "events": len(rows),
        "known": known,
        "unknown": unknown,
        "prompt_tokens": prompt,
        "completion_tokens": completion,
        "total_tokens": total,
        "by_kind": dict(by_kind),
        "duplicate_idempotency": max(0, dup_keys),
    }


def read_newapi_logs(
    db: Path,
    *,
    since_unix: int,
    until_unix: int,
    token_name: str | None = None,
) -> dict[str, Any]:
    con = _connect_ro(db)
    names = _table_names(con)
    if "logs" not in names:
        con.close()
        return {"ok": False, "reason": "no logs table", "rows": []}
    cols = _cols(con, "logs")
    need = {"created_at", "prompt_tokens", "completion_tokens"}
    if not need.issubset(cols):
        con.close()
        return {"ok": False, "reason": f"logs missing {sorted(need - cols)}", "rows": []}
    select = [
        "created_at",
        "prompt_tokens",
        "completion_tokens",
    ]
    if "id" in cols:
        select.append("id")
    if "model_name" in cols:
        select.append("model_name")
    if "token_name" in cols:
        select.append("token_name")
    if "type" in cols:
        select.append("type")
    sql = f"SELECT {', '.join(select)} FROM logs WHERE created_at >= ? AND created_at < ?"
    args: list[Any] = [since_unix, until_unix]
    if token_name and "token_name" in cols:
        sql += " AND token_name = ?"
        args.append(token_name)
    raw = con.execute(sql, args).fetchall()
    con.close()
    rows = []
    for item in raw:
        rec = {select[i]: item[i] for i in range(len(select))}
        # one-api consume type is typically 2; if type exists, keep consume-like rows.
        typ = rec.get("type")
        if typ is not None and int(typ) not in {0, 2}:
            continue
        rows.append(rec)
    return {"ok": True, "rows": rows}


def newapi_token_book(rows: list[dict[str, Any]]) -> dict[str, Any]:
    prompt = 0
    completion = 0
    for row in rows:
        prompt += int(row.get("prompt_tokens") or 0)
        completion += int(row.get("completion_tokens") or 0)
    return {
        "events": len(rows),
        "prompt_tokens": prompt,
        "completion_tokens": completion,
        "total_tokens": prompt + completion,
    }


def _parse_dt(value: Any) -> datetime | None:
    if value is None or value == "":
        return None
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(int(value), tz=UTC)
    text = str(value).replace("T", " ").removesuffix("Z")
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed


def pico_billed_tokens(row: dict[str, Any]) -> int | None:
    if row.get("tokens_unknown"):
        return None
    total = int(row.get("total_tokens") or 0)
    if total > 0:
        return total
    return int(row.get("prompt_tokens") or 0) + int(row.get("completion_tokens") or 0)


def na_row_tokens(row: dict[str, Any]) -> int:
    return int(row.get("prompt_tokens") or 0) + int(row.get("completion_tokens") or 0)


def join_newapi_to_llm_runs(
    pico_rows: list[dict[str, Any]],
    runs: dict[str, dict[str, Any]],
    newapi_rows: list[dict[str, Any]],
    *,
    slack_s: int = RUN_SLACK_S,
) -> dict[str, Any] | None:
    """Assign chat completions to Pico llm runs by [started, ended] ± slack.

    One Pico llm row per run; many New API rows. Returns None when there is
    nothing to join (no run_id / no runs table) so callers keep the old gate.
    """
    windows: list[dict[str, Any]] = []
    for row in pico_rows:
        if str(row.get("kind") or "") != "llm":
            continue
        rid = str(row.get("run_id") or "").strip()
        if not rid:
            continue
        run = runs.get(rid) or {}
        started = _parse_dt(run.get("started_at")) or _parse_dt(row.get("created_at"))
        ended = _parse_dt(run.get("ended_at"))
        if started is None:
            continue
        if ended is None:
            ended = started + timedelta(seconds=120)
        st_u = int(started.timestamp()) - slack_s
        en_u = int(ended.timestamp()) + slack_s
        windows.append(
            {
                "run_id": rid,
                "model": _model_key(row.get("model")),
                "unknown": bool(row.get("tokens_unknown")),
                "pico_tokens": pico_billed_tokens(row),
                "st_u": st_u,
                "en_u": en_u,
                "dur": max(0, en_u - st_u),
            }
        )
    if not windows:
        return None

    per_run: dict[str, dict[str, Any]] = {}
    for window in windows:
        rec = per_run.setdefault(
            window["run_id"],
            {
                "model": window["model"],
                "unknown": window["unknown"],
                "pico_tokens": window["pico_tokens"],
                "na_events": 0,
                "na_tokens": 0,
            },
        )
        rec["model"] = window["model"]
        rec["unknown"] = window["unknown"]
        rec["pico_tokens"] = window["pico_tokens"]

    assigned: list[dict[str, Any]] = []
    unattributed: list[dict[str, Any]] = []
    for idx, raw in enumerate(newapi_rows):
        if model_lane(raw.get("model_name")) != "chat":
            continue
        log = dict(raw)
        log["_idx"] = log.get("id") if log.get("id") is not None else f"i{idx}"
        ts = int(log.get("created_at") or 0)
        model = _model_key(log.get("model_name"))
        hits = [
            window
            for window in windows
            if window["model"] == model and window["st_u"] <= ts <= window["en_u"]
        ]
        if not hits:
            unattributed.append(log)
            continue
        known_hits = [window for window in hits if not window["unknown"]]
        if not known_hits:
            rec = per_run[hits[0]["run_id"]]
            rec["na_events"] += 1
            rec["na_tokens"] += na_row_tokens(log)
            continue
        known_hits.sort(key=lambda window: (window["dur"], window["st_u"]))
        chosen = known_hits[0]
        rec = per_run[chosen["run_id"]]
        rec["na_events"] += 1
        rec["na_tokens"] += na_row_tokens(log)
        assigned.append(log)

    assigned_tokens = sum(na_row_tokens(row) for row in assigned)
    unattr_tokens = sum(na_row_tokens(row) for row in unattributed)
    by_model: dict[str, dict[str, Any]] = defaultdict(
        lambda: {
            "known_runs": 0,
            "unknown_runs": 0,
            "pico_tokens": 0,
            "assigned_events": 0,
            "assigned_tokens": 0,
            "unattributed_events": 0,
            "unattributed_tokens": 0,
        }
    )
    for rec in per_run.values():
        bucket = by_model[rec["model"]]
        if rec["unknown"]:
            bucket["unknown_runs"] += 1
        else:
            bucket["known_runs"] += 1
            bucket["pico_tokens"] += int(rec["pico_tokens"] or 0)
            bucket["assigned_events"] += rec["na_events"]
            bucket["assigned_tokens"] += rec["na_tokens"]
    unattr_by_model: dict[str, dict[str, int]] = defaultdict(
        lambda: {"events": 0, "tokens": 0}
    )
    for log in unattributed:
        bucket = unattr_by_model[_model_key(log.get("model_name"))]
        bucket["events"] += 1
        bucket["tokens"] += na_row_tokens(log)
        by_model[_model_key(log.get("model_name"))]["unattributed_events"] += 1
        by_model[_model_key(log.get("model_name"))]["unattributed_tokens"] += na_row_tokens(
            log
        )
    for name, bucket in by_model.items():
        pico_tok = int(bucket["pico_tokens"] or 0)
        assigned_tok = int(bucket["assigned_tokens"] or 0)
        bucket["token_deviation"] = (
            deviation(pico_tok, assigned_tok) if pico_tok or assigned_tok else 0.0
        )
        bucket["unattributed_events"] = int(unattr_by_model[name]["events"])
        bucket["unattributed_tokens"] = int(unattr_by_model[name]["tokens"])
    return {
        "slack_s": slack_s,
        "joined": True,
        "assigned_events": len(assigned),
        "unattributed_events": len(unattributed),
        "assigned_tokens": assigned_tokens,
        "unattributed_tokens": unattr_tokens,
        "known_runs": sum(1 for rec in per_run.values() if not rec["unknown"]),
        "unknown_runs": sum(1 for rec in per_run.values() if rec["unknown"]),
        "by_model": {name: dict(bucket) for name, bucket in sorted(by_model.items())},
        "assigned_rows": assigned,
    }


def gate_newapi_rows(
    newapi_rows: list[dict[str, Any]],
    run_join: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    """Chat rows that landed in a run window + all non-chat rows (rerank/embed)."""
    if not run_join or not run_join.get("joined"):
        return list(newapi_rows)
    assigned_idx = {row.get("_idx") for row in run_join.get("assigned_rows") or []}
    out: list[dict[str, Any]] = []
    for idx, raw in enumerate(newapi_rows):
        lane = model_lane(raw.get("model_name"))
        if lane != "chat":
            out.append(raw)
            continue
        key = raw.get("id") if raw.get("id") is not None else f"i{idx}"
        if key in assigned_idx:
            out.append(raw)
    return out


def export_matches_ledger(export_ids: list[str], ledger_ids: list[str]) -> dict[str, Any]:
    a, b = set(export_ids), set(ledger_ids)
    return {
        "export": len(a),
        "ledger": len(b),
        "missing_in_export": len(b - a),
        "extra_in_export": len(a - b),
        "deviation": deviation(len(a), len(b)),
    }


def model_lane(name: str) -> str:
    n = (name or "").strip().lower()
    if "rerank" in n:
        return "rerank"
    if "embed" in n:
        return "embed"
    if not n or n in {"(none)", "none"}:
        return "other"
    return "chat"


def _model_key(value: Any) -> str:
    return str(value or "").strip() or "(none)"


def group_pico_by_model(rows: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    by: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by[_model_key(row.get("model"))].append(row)
    return by


def group_newapi_by_model(rows: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    by: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by[_model_key(row.get("model_name"))].append(row)
    return by


def books_by_model(
    pico_rows: list[dict[str, Any]],
    newapi_rows: list[dict[str, Any]],
    threshold: float,
) -> tuple[dict[str, Any], list[bool]]:
    pico_by = group_pico_by_model(pico_rows)
    na_by = group_newapi_by_model(newapi_rows)
    out: dict[str, Any] = {}
    comparable_ok: list[bool] = []
    for name in sorted(set(pico_by) | set(na_by)):
        lane = model_lane(name)
        pico = pico_token_book(pico_by.get(name, []))
        newapi = newapi_token_book(na_by[name]) if name in na_by else None
        token_dev = (
            deviation(pico["total_tokens"], newapi["total_tokens"])
            if newapi is not None
            else None
        )
        comparable = lane in {"chat", "rerank"} and pico["known"] > 0 and newapi is not None
        note = ""
        if lane == "embed":
            comparable = False
            note = "query embed is Meili-side; Pico does not invent tokens; not in headline ok"
        elif pico["known"] == 0 and newapi is not None:
            note = "pico has no known tokens (unknown-only or missing)"
        out[name] = {
            "lane": lane,
            "comparable": comparable,
            "token_deviation": token_dev,
            "pico": pico,
            "newapi": newapi,
            "note": note,
        }
        if comparable:
            comparable_ok.append(token_dev is not None and token_dev <= threshold)
    return out, comparable_ok


def unknown_llm_breakdown(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for row in rows:
        if str(row.get("kind") or "") != "llm" or not row.get("tokens_unknown"):
            continue
        extra = row.get("extra") if isinstance(row.get("extra"), dict) else {}
        out.append(
            {
                "model": row.get("model"),
                "source": row.get("source") or extra.get("tool"),
                "reason": extra.get("reason"),
                "fail_without_usage": bool(extra.get("fail_without_usage")),
            }
        )
    return out


def reconcile(
    *,
    pico_book: dict[str, Any],
    newapi_book: dict[str, Any] | None,
    export_vs_ledger: dict[str, Any] | None,
    threshold: float = THRESHOLD,
    pico_rows: list[dict[str, Any]] | None = None,
    newapi_rows: list[dict[str, Any]] | None = None,
    run_join: dict[str, Any] | None = None,
) -> dict[str, Any]:
    token_dev = None
    if newapi_book is not None and newapi_book.get("ok") is not False:
        token_dev = deviation(pico_book["total_tokens"], newapi_book["total_tokens"])
    by_model = None
    comparable_ok = None
    gate_rows = gate_newapi_rows(newapi_rows or [], run_join)
    if pico_rows is not None:
        by_model, comparable_ok = books_by_model(pico_rows, gate_rows, threshold)
        if run_join and run_join.get("joined") and by_model is not None:
            comparable_ok = []
            join_models = run_join.get("by_model") or {}
            for name, rec in by_model.items():
                if rec.get("lane") == "chat" and name in join_models:
                    stats = join_models[name]
                    rec["token_deviation"] = stats.get("token_deviation")
                    rec["note"] = (
                        "run-aligned: New API completions inside known Pico run windows"
                    )
                    rec["comparable"] = int(stats.get("known_runs") or 0) > 0
                    rec["pico"] = dict(rec.get("pico") or {})
                    rec["pico"]["known"] = int(stats.get("known_runs") or 0)
                    rec["pico"]["total_tokens"] = int(stats.get("pico_tokens") or 0)
                    rec["newapi"] = {
                        "events": int(stats.get("assigned_events") or 0),
                        "prompt_tokens": None,
                        "completion_tokens": None,
                        "total_tokens": int(stats.get("assigned_tokens") or 0),
                    }
                    if rec["comparable"]:
                        comparable_ok.append(
                            rec["token_deviation"] is not None
                            and rec["token_deviation"] <= threshold
                        )
                elif rec.get("comparable") and rec.get("lane") == "rerank":
                    comparable_ok.append(
                        rec.get("token_deviation") is not None
                        and rec["token_deviation"] <= threshold
                    )
    export_dev = None if export_vs_ledger is None else export_vs_ledger["deviation"]
    checks = []
    if comparable_ok is not None:
        if comparable_ok:
            checks.append(all(comparable_ok))
    elif token_dev is not None:
        checks.append(token_dev <= threshold)
    if export_dev is not None:
        checks.append(export_dev <= threshold)
    checks.append(int(pico_book.get("duplicate_idempotency") or 0) == 0)
    ok = all(checks) if checks else False
    notes = [
        "unknown token rows excluded from token sums (not billed as 0)",
        "edu wallet debit is not in this repo",
        "headline ok uses comparable chat/rerank lanes only; embed is listed not gated",
        "blended token_deviation is informational (do not mix embed into the gate)",
        "pico total_tokens prefers ledger total (reasoning) over prompt+completion",
    ]
    if run_join and run_join.get("joined"):
        notes.append(
            "chat headline uses New API completions inside Pico run windows; "
            "unattributed (probes / outside windows) listed under run_join, not gated"
        )
    else:
        notes.append(
            "Pico llm is one row per run; New API is one row per completion — "
            "compare tokens, not row counts (run join skipped: no run_id/runs)"
        )
    report = {
        "ok": ok,
        "threshold": threshold,
        "token_deviation": token_dev,
        "export_deviation": export_dev,
        "pico": pico_book,
        "newapi": newapi_book,
        "export_vs_ledger": export_vs_ledger,
        "notes": notes,
    }
    if by_model is not None:
        report["by_model"] = by_model
    if pico_rows is not None:
        report["unknown_llm"] = unknown_llm_breakdown(pico_rows)
    if run_join is not None:
        public_join = {
            key: value
            for key, value in run_join.items()
            if key != "assigned_rows"
        }
        report["run_join"] = public_join
    return report


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Reconcile New API logs with Pico usage_events")
    p.add_argument("--pico-db", type=Path, help="Pico sqlite (usage_events)")
    p.add_argument("--newapi-db", type=Path, help="New API sqlite (logs)")
    p.add_argument("--token-name", default="", help="New API token_name filter (e.g. pico-gateway)")
    p.add_argument("--hours", type=int, default=24)
    p.add_argument("--export-ids", type=Path, help="JSON list of export event ids")
    p.add_argument("--threshold", type=float, default=THRESHOLD)
    p.add_argument("--json", action="store_true")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    until = datetime.now(UTC)
    since = until - timedelta(hours=max(1, int(args.hours)))
    if not args.pico_db:
        print("need --pico-db", flush=True)
        return 2
    pico = read_pico_usage(args.pico_db, since=since, until=until)
    if not pico.get("ok"):
        print(json.dumps(pico, ensure_ascii=False))
        return 2
    pico_book = pico_token_book(pico["rows"])
    newapi_book = None
    newapi_rows: list[dict[str, Any]] = []
    if args.newapi_db:
        na = read_newapi_logs(
            args.newapi_db,
            since_unix=int(since.timestamp()),
            until_unix=int(until.timestamp()),
            token_name=args.token_name or None,
        )
        if na.get("ok"):
            newapi_rows = list(na.get("rows") or [])
            newapi_book = newapi_token_book(newapi_rows)
        else:
            newapi_book = {"ok": False, "reason": na.get("reason"), "events": 0, "total_tokens": 0}
    export_vs = None
    if args.export_ids:
        ids = json.loads(args.export_ids.read_text())
        export_vs = export_matches_ledger(list(ids), [r["id"] for r in pico["rows"]])
    runs = read_pico_runs(args.pico_db, since=since, until=until)
    run_join = join_newapi_to_llm_runs(pico["rows"], runs, newapi_rows)
    report = reconcile(
        pico_book=pico_book,
        newapi_book=newapi_book,
        export_vs_ledger=export_vs,
        threshold=float(args.threshold),
        pico_rows=pico["rows"],
        newapi_rows=newapi_rows,
        run_join=run_join,
    )
    report["window"] = {"since": since.isoformat(), "until": until.isoformat(), "hours": args.hours}
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
