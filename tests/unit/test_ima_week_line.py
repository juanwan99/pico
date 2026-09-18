from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "ima-week-line.py"
_spec = importlib.util.spec_from_file_location("ima_week_line", SCRIPT)
assert _spec is not None and _spec.loader is not None
wl = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(wl)


def test_render_three_lines() -> None:
    md = wl.render(
        {"overall": {"n": 47, "file@5": 0.947, "p95_ms": 1612}},
        {"pass": True, "results": [{"ok": True}] * 10},
        {"windows": [{"hours": 24, "runs": 80, "fail_rate": 0.05, "fail_buckets": {"timeout": 2}}]},
    )
    assert "file@5=0.947" in md
    assert "10/10" in md
    assert "5.0%" in md
    assert "timeout 2" in md
