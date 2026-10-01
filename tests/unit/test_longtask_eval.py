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
    cases = lte.load_cases("office")
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
    for case in lte.load_cases("office"):
        expect = case.get("expect") or {}
        assert 1 <= lte.pass_bar(expect) <= lte.max_points(expect), case["id"]
    by_id = {c["id"]: c.get("expect") or {} for c in lte.load_cases()}
    assert lte.max_points(by_id["LT4"]) == 2 and lte.pass_bar(by_id["LT4"]) == 2
    assert lte.pass_bar(by_id["LT6"]) == 3


def test_fake_green_flagged_explicitly() -> None:
    """Baseline #1091: 5 runs said succeeded with 0 files. Now a column, never a pass."""
    res = lte.CaseResult(case="LT9", title="t", ok=True, auto_score=3, max_score=5, artifacts=0)
    lte.flag_fake_green(res, "succeeded")
    assert res.fake_green is True and res.ok is False
    with_files = lte.CaseResult(case="LT9", title="t", ok=True, auto_score=3, artifacts=2)
    lte.flag_fake_green(with_files, "succeeded")
    assert with_files.fake_green is False and with_files.ok is True
    table = lte.render_markdown([res, with_files])
    assert "假绿" in table and "| 是 |" in table and "假绿：1" in table


def test_coding_suite_cases_and_checkers() -> None:
    """#1090 v3.1: coding sits beside office. Every LC case names a hidden checker."""
    cases = lte.load_cases("coding")
    assert [c["id"] for c in cases] == ["LC1", "LC2", "LC3", "LC4", "LC5"]
    assert [c["id"] for c in lte.load_cases()][:8] == [f"LT{i}" for i in range(1, 9)]
    assert len(lte.load_cases("office")) + len(cases) == 13
    assert any(len(c.get("turns") or []) >= 3 for c in cases)
    for c in cases:
        check = c["expect"]["check"]
        assert (lte.CHECKS_DIR / check["script"]).is_file(), c["id"]
        assert lte.max_points(c["expect"]) == len(c["expect"]["files"] and [1]) + check["max"]
        for turn in c["turns"]:
            for att in turn.get("attachments") or []:
                assert lte._attachment_bytes(att), (c["id"], att["name"])
        assert 1 <= len(c["score_points"]) <= 5


def test_hard_suite_cases_and_checkers() -> None:
    """LT/LC saturated at 13/13 on two models; LH cases exist to tell them apart."""
    cases = lte.load_cases("hard")
    assert [c["id"] for c in cases] == ["LH1", "LH2", "LH3"]
    assert [c["id"] for c in lte.load_cases()][-3:] == ["LH1", "LH2", "LH3"]
    assert any(len(c["turns"]) >= 6 for c in cases)
    for c in cases:
        check = c["expect"]["check"]
        assert (lte.CHECKS_DIR / check["script"]).is_file(), c["id"]
        assert lte.max_points(c["expect"]) == 1 + check["max"]
        assert int(c["timeout_s"]) >= 1800
        for turn in c["turns"]:
            for att in turn.get("attachments") or []:
                assert lte._attachment_bytes(att), (c["id"], att["name"])


def test_grade_book_is_seeded_and_carries_traps() -> None:
    import io

    from openpyxl import load_workbook

    def cells(raw: bytes) -> list[list[object]]:
        wb = load_workbook(io.BytesIO(raw))
        return [[c.value for c in row] for ws in wb.worksheets for row in ws.iter_rows()]

    raw = lte._grade_book()
    assert cells(raw) == cells(lte._grade_book())
    wb = load_workbook(io.BytesIO(raw))
    mid, fin = wb["期中"], wb["期末"]
    assert mid.max_row == 271 and fin.max_row == 270
    names = [r[0].value for r in mid.iter_rows(min_row=2)]
    assert len({n.strip() for n in names}) == 6 and len(set(names)) > 6
    marks = [c.value for row in fin.iter_rows(min_row=2) for c in row[3:]]
    assert "作废" in marks and "缺考" in marks and None in marks
    ids_mid = [r[1].value for r in mid.iter_rows(min_row=2)]
    ids_fin = [r[1].value for r in fin.iter_rows(min_row=2)]
    assert ids_fin != sorted(ids_fin) and len(set(ids_mid) - set(ids_fin)) == 1


def test_fixture_projects_ship_their_test_data() -> None:
    """.gitignore has ``data/``: tests/data CSVs were never committed (LH1 2026-10-01)."""
    import subprocess

    tracked = subprocess.run(
        ["git", "ls-files", "testdata/longtask-eval/fixtures/code"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.split()
    for name in (
        "roster/tests/data/class.csv",
        "gradebook/tests/data/sample.csv",
        "gradebook/tests/data/attendance.csv",
    ):
        assert f"testdata/longtask-eval/fixtures/code/{name}" in tracked, name


def test_new_fixture_data_is_not_gitignored() -> None:
    """A new fixture's tests/data must not need ``git add -f`` again."""
    import subprocess

    probe = "testdata/longtask-eval/fixtures/code/new-project/tests/data/x.csv"
    rc = subprocess.run(["git", "check-ignore", "-q", probe], cwd=ROOT, check=False).returncode
    assert rc == 1, "fixture tests/data is still ignored"
    assert subprocess.run(["git", "check-ignore", "-q", "data/pico.db"], cwd=ROOT, check=False).returncode == 0


def test_zip_dir_skips_pycache(tmp_path: Path) -> None:
    import io
    import zipfile

    raw = lte._zip_dir("fixtures/code/gradebook")
    names = zipfile.ZipFile(io.BytesIO(raw)).namelist()
    assert "gradebook/gradebook/models.py" in names and "gradebook/tests/test_loader.py" in names
    assert not any("__pycache__" in n for n in names)


def test_zip_dir_is_deterministic_project() -> None:
    import io
    import zipfile

    a = lte._zip_dir("fixtures/code/roster")
    assert a == lte._zip_dir("fixtures/code/roster")
    names = zipfile.ZipFile(io.BytesIO(a)).namelist()
    assert "roster/tests/test_roster.py" in names and "roster/roster/stats.py" in names


def test_delivered_files_skip_uploads_and_summary() -> None:
    arts = [
        {"id": "1", "title": "bank.json", "kind": "file", "created_at": "1"},
        {"id": "2", "title": "roster.zip", "kind": "edu_office", "created_at": "1"},
        {"id": "3", "title": "回复摘要", "kind": "doc", "created_at": "1"},
        {"id": "4", "title": "quiz.py", "kind": "py", "created_at": "1"},
        {"id": "5", "title": "quiz.py", "kind": "py", "created_at": "2"},
    ]
    latest = lte._latest_by_title(arts)
    assert list(latest) == ["quiz.py"] and latest["quiz.py"]["id"] == "5"


def test_unzip_skips_entries_escaping_dest(tmp_path: Path) -> None:
    import io
    import zipfile

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("ok/a.py", "x = 1")
        zf.writestr("../evil.py", "boom")
    lte._unzip_into(buf.getvalue(), tmp_path / "out")
    assert (tmp_path / "out" / "ok" / "a.py").is_file()
    assert not (tmp_path / "evil.py").exists()


def test_coding_case_fails_when_files_missing() -> None:
    case = {"id": "LCX", "expect": {"files": ["a.py", "b.py"]}}
    res = lte.CaseResult(case="LCX")
    lte.score_code(case, {"a.py": b"x"}, res, "img", "runc")
    assert res.ok is False and res.auto_score == 0 and "missing files: b.py" in res.notes
    done = lte.CaseResult(case="LCX")
    lte.score_code(case, {"a.py": b"x", "b.py": b"y"}, done, "img", "runc")
    assert done.ok is True and done.auto_score == 1


def test_follow_waits_out_an_api_restart(monkeypatch) -> None:
    """#1133: the stream drops on deploy; the run is followed until it ends."""
    import httpx

    monkeypatch.setattr(lte.time, "sleep", lambda _s: None)
    replies = iter(
        [
            httpx.ConnectError("api down"),
            [{"latest_run": {"status": "running"}}],
            [{"latest_run": {"status": "succeeded"}}],
        ]
    )

    def tasks(_cid: str):
        r = next(replies)
        if isinstance(r, Exception):
            raise r
        return r

    pico = lte.Pico.__new__(lte.Pico)
    pico.tasks = tasks
    assert pico.follow("c", timeout_s=60) >= 0
    assert next(replies, None) is None
