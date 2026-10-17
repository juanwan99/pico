#!/usr/bin/env python3
"""Mask typed values and URL queries in old tool.call ledger rows (pico#1324).

New rows are masked on write (db.append_event → public_tool_args). Rows written
before that still hold what the AI typed into pages and full opened URLs. This
rewrites only tool.call rows whose arguments change under public_tool_args.

Run inside pico-api (it has the module and the database; scripts/ is not in the
image, so pipe it in); back up first:

  docker exec -i pico-pico-api-1 python - --dry-run < scripts/ledger-mask-backfill.py
  docker exec -i pico-pico-api-1 python - --backup data/pico.db.bak-1324 < scripts/ledger-mask-backfill.py

Prints counts per tool, never the values.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from collections import Counter
from pathlib import Path

# Repo checkout (tests) or the pico-api image (/app), whichever this runs from.
ROOT = Path(__file__).resolve().parents[1] if __file__ != "<stdin>" else Path("/app")
sys.path.insert(0, str(ROOT / "services" / "orchestrator"))

from pico_orchestrator.sandbox_session_event import public_tool_args

TOOLS = (
    "sandbox_browser_type",
    "sandbox_browser_fill_form",
    "sandbox_browser_open",
    "sandbox_browser_navigate",
)


def masked_rows(conn: sqlite3.Connection) -> list[tuple[str, str, str]]:
    """(id, tool, new payload_json) for every tool.call row that masking changes."""
    marks = " OR ".join("payload_json LIKE ?" for _ in TOOLS)
    rows = conn.execute(
        f"SELECT id, payload_json FROM events WHERE type = 'tool.call' AND ({marks})",
        [f'%"{t}"%' for t in TOOLS],
    ).fetchall()
    out: list[tuple[str, str, str]] = []
    for row_id, raw in rows:
        try:
            payload = json.loads(raw)
        except ValueError:
            continue
        args = payload.get("arguments")
        tool = str(payload.get("tool") or "")
        if not isinstance(args, dict):
            continue
        masked = public_tool_args(tool, args)
        if masked != args:
            out.append(
                (row_id, tool, json.dumps({**payload, "arguments": masked}, ensure_ascii=False))
            )
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--db", default="data/pico.db")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument(
        "--backup", help="copy the database here before writing (required unless --dry-run)"
    )
    a = ap.parse_args()
    conn = sqlite3.connect(a.db, timeout=30)
    todo = masked_rows(conn)
    print(
        json.dumps(
            {"rows": len(todo), "by_tool": Counter(t for _, t, _ in todo)}, ensure_ascii=False
        )
    )
    if a.dry_run or not todo:
        return 0
    if not a.backup:
        print("refusing to write without --backup", file=sys.stderr)
        return 2
    dest = sqlite3.connect(a.backup)
    conn.backup(dest)
    dest.close()
    with conn:
        conn.executemany(
            "UPDATE events SET payload_json = ? WHERE id = ?", [(p, i) for i, _, p in todo]
        )
    left = masked_rows(conn)
    print(json.dumps({"written": len(todo), "left": len(left), "backup": a.backup}))
    return 0 if not left else 1


if __name__ == "__main__":
    raise SystemExit(main())
