"""scripts/longtask-eval.py — case pack + CLI, no live network."""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "longtask-eval.py"
CASES = ROOT / "testdata" / "longtask-eval"

_spec = importlib.util.spec_from_file_location("longtask_eval", SCRIPT)
assert _spec is not None and _spec.loader is not None
lte = importlib.util.module_from_spec(_spec)
sys.modules["longtask_eval"] = lte
_spec.loader.exec_module(lte)


def test_help_exits_zero() -> None:
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), "--help"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    assert "long-task" in proc.stdout.lower() or "Long-task" in proc.stdout
    assert "--base" in proc.stdout


def test_eight_cases_cover_required_shapes() -> None:
    cases = lte.load_cases()
    ids = [c["id"] for c in cases]
    assert ids == ["LT1", "LT2", "LT3", "LT4", "LT5", "LT6", "LT7", "LT8"]
    titles = " ".join(c["title"] for c in cases)
    assert "Word" in titles
    assert "Excel" in titles
    assert "PPT" in titles
    assert "续改" in titles
    assert "网页" in titles or "研究" in titles
    assert any(int(c.get("timeout_s") or 0) >= 1800 for c in cases)
    assert any(len(c.get("turns") or []) >= 3 for c in cases)
    assert any(
        "web" in json.dumps(c, ensure_ascii=False).lower() or "上网" in json.dumps(c, ensure_ascii=False)
        for c in cases
    )
    for c in cases:
        assert c.get("score_points"), c["id"]
        assert 1 <= len(c["score_points"]) <= 5
        for p in c["score_points"]:
            assert p.get("text")


def test_fixture_files_exist() -> None:
    for name in (
        "memo-a.md",
        "memo-b.md",
        "scores.csv",
        "unit-plan.md",
        "survey.md",
        "calendar.md",
    ):
        path = CASES / "fixtures" / name
        assert path.is_file() and path.stat().st_size > 20, name


def test_triple_workbook_has_three_sheets() -> None:
    import io

    from openpyxl import load_workbook

    raw = lte._triple_workbook()
    wb = load_workbook(io.BytesIO(raw))
    assert set(wb.sheetnames) >= {"成绩", "出勤", "问卷"}


def test_classify_fail_buckets() -> None:
    assert lte._classify_fail("failed", "run owner was lost during API restart") == "deploy_killed"
    assert lte._classify_fail("failed", "HTTP 524") == "upstream_model"
    assert lte._classify_fail("failed", "Tool not allowlisted: x") == "tool_error"
    assert lte._classify_fail("failed", "durable_max exceeded") == "wall_clock"
    assert lte._classify_fail("succeeded", "") == ""


def test_every_case_can_pass_when_all_checks_hold() -> None:
    """LT3/LT4/LT5 top out at 2 points; a fixed >=3 bar made them unpassable."""
    for case in lte.load_cases():
        expect = case.get("expect") or {}
        assert 1 <= lte.pass_bar(expect) <= lte.max_points(expect), case["id"]
    by_id = {c["id"]: c.get("expect") or {} for c in lte.load_cases()}
    assert lte.max_points(by_id["LT4"]) == 2 and lte.pass_bar(by_id["LT4"]) == 2
    assert lte.pass_bar(by_id["LT6"]) == 3
