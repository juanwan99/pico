"""LC4: attendance merge/clean — output rows, per-person summary, script reruns from raw."""

import csv
import io
import json
import os
import shutil
import sys
from pathlib import Path

sys.path.insert(0, "/w/check")
from _common import IN, Score, find, run, tail, workdir

STATUSES = ["出勤", "迟到", "缺勤", "请假"]
EXPECTED = {
    tuple(r) for r in json.loads(Path("/w/check/lc4_expected.json").read_text(encoding="utf-8"))
}


def read_csv(path):
    raw = Path(path).read_bytes()
    for enc in ("utf-8-sig", "gbk"):
        try:
            return list(csv.DictReader(io.StringIO(raw.decode(enc))))
        except UnicodeDecodeError:
            continue
    return []


def clean_rows(path):
    out = set()
    for rec in read_csv(path):
        rec = {str(k).strip(): str(v or "").strip() for k, v in rec.items() if k}
        out.add((rec.get("日期", ""), rec.get("姓名", ""), rec.get("状态", "")))
    return out


def diff_note(got):
    missing, extra = EXPECTED - got, got - EXPECTED
    sample = sorted(extra)[:2] or sorted(missing)[:2]
    return f"rows {len(got)} vs {len(EXPECTED)}: missing {len(missing)}, extra {len(extra)} e.g. {sample}"


def expected_summary():
    table = {}
    for _d, name, st in EXPECTED:
        table.setdefault(name, {s: 0 for s in STATUSES})[st] += 1
    return table


def main():
    sc = Score()
    cleaned = find("attendance_clean.csv")
    if not cleaned:
        sc.fail("attendance_clean.csv not delivered")
        sc.emit()
    got = clean_rows(cleaned)
    sc.check(got == EXPECTED, "clean csv: " + diff_note(got))
    summary = find("summary.csv")
    want = expected_summary()
    ok = False
    if summary:
        table = {}
        for rec in read_csv(summary):
            rec = {str(k).strip(): str(v or "").strip() for k, v in rec.items() if k}
            try:
                table[rec["姓名"]] = {s: int(float(rec[s])) for s in STATUSES}
            except (KeyError, ValueError):
                break
        ok = table == want
    sc.check(ok, "summary.csv missing or counts differ (columns 姓名,出勤,迟到,缺勤,请假)")
    script = find("clean.py")
    if sc.check(bool(script), "clean.py not delivered"):
        work = workdir(os.path.dirname(script))
        src = os.path.join(work, "_raw")
        os.makedirs(src)
        for name in os.listdir(IN):
            if name.endswith(".csv"):
                shutil.copy(os.path.join(IN, name), src)
        dst = os.path.join(work, "_again")
        proc = run([sys.executable, "clean.py", src, dst], cwd=work, timeout=120)
        again = os.path.join(dst, "attendance_clean.csv")
        if os.path.exists(again):
            sc.check(clean_rows(again) == EXPECTED, "rerun: " + diff_note(clean_rows(again)))
        else:
            sc.fail(
                f"python clean.py <in> <out> wrote no attendance_clean.csv (rc={proc.returncode}): {tail(proc.stderr)}"
            )
    sc.check(bool(find("README.md")), "README.md not delivered", essential=False)
    sc.emit()


main()
