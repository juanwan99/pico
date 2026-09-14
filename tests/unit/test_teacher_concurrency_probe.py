"""scripts/teacher-concurrency-probe.py helpers — no live HTTP."""

from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "teacher-concurrency-probe.py"

_spec = importlib.util.spec_from_file_location("teacher_concurrency_probe", SCRIPT)
assert _spec is not None and _spec.loader is not None
mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(mod)


def test_summarize_counts_busy_and_ok() -> None:
    rows = [
        {
            "label": "a",
            "status": 200,
            "code": "",
            "wall_s": 1.0,
            "ok": True,
            "busy": False,
            "rpm": False,
            "err": "",
        },
        {
            "label": "b",
            "status": 429,
            "code": "concurrency_limit",
            "wall_s": 0.05,
            "ok": False,
            "busy": True,
            "rpm": False,
            "err": "",
        },
        {
            "label": "c",
            "status": 200,
            "code": "",
            "wall_s": 3.0,
            "ok": True,
            "busy": False,
            "rpm": False,
            "err": "",
        },
    ]
    summary = mod.summarize(rows)
    assert summary["ok"] == 2
    assert summary["busy_429"] == 1
    assert summary["p50_s"] == 2.0
    md = mod.render_markdown("same teacher", summary, cap=2)
    assert "busy_429=1" in md
    assert "cap (health) = `2`" in md


def test_percentile_bounds() -> None:
    assert mod._percentile([1.0, 2.0, 3.0, 4.0], 0.95) == 4.0
    assert mod._percentile([10.0], 0.95) == 10.0
