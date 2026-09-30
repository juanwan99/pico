"""LC1: grade_stats.py on a hidden CSV + the model's own unittest."""

import csv
import json
import os
import random
import sys

sys.path.insert(0, "/w/check")
from _common import Score, find, run, tail, workdir

SUBJECTS = ["语文", "数学", "英语"]


def hidden_rows():
    rng = random.Random(4242)
    rows, totals = [], set()
    k = 0
    while len(rows) < 23:
        k += 1
        cells = [str(rng.randint(30, 100)) for _ in SUBJECTS]
        if k in (3, 11):
            cells[0] = "缺考"
        if k == 7:
            cells[2] = ""
        tot = sum(int(c) for c in cells if c.isdigit())
        if tot in totals:
            continue
        totals.add(tot)
        rows.append([f"学生{k:02d}", "甲乙丙"[k % 3]] + cells)
    return rows


def expected(rows):
    groups, passed = {}, {s: 0 for s in SUBJECTS}
    totals = []
    for name, g, *cells in rows:
        tot = 0
        for s, c in zip(SUBJECTS, cells):
            if c.isdigit():
                groups.setdefault(g, {}).setdefault(s, []).append(int(c))
                tot += int(c)
                passed[s] += int(c) >= 60
        totals.append((tot, name))
    means = {g: {s: round(sum(v) / len(v), 1) for s, v in d.items()} for g, d in groups.items()}
    rate = {s: passed[s] / len(rows) for s in SUBJECTS}
    top3 = [n for _t, n in sorted(totals, reverse=True)[:3]]
    return means, rate, top3


def close(a, b, tol):
    try:
        return abs(float(a) - float(b)) <= tol
    except (TypeError, ValueError):
        return False


def main():
    sc = Score()
    tool = find("grade_stats.py")
    if not tool:
        sc.fail("grade_stats.py not delivered")
        sc.emit()
    work = workdir(os.path.dirname(tool))
    rows = hidden_rows()
    path = os.path.join(work, "hidden.csv")
    with open(path, "w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["姓名", "组别"] + SUBJECTS)
        w.writerows(rows)
    proc = run([sys.executable, "grade_stats.py", path, "--json"], cwd=work)
    data = None
    try:
        data = json.loads(proc.stdout)
    except ValueError:
        pass
    if not sc.check(
        isinstance(data, dict),
        f"--json not JSON (rc={proc.returncode}): {tail(proc.stdout + proc.stderr)}",
    ):
        sc.emit()
    means, rate, top3 = expected(rows)
    bad = []
    got_g = data.get("groups") or {}
    for g, subj in means.items():
        for s, v in subj.items():
            if not close((got_g.get(g) or {}).get(s), v, 0.051):
                bad.append(f"groups[{g}][{s}]={((got_g.get(g) or {}).get(s))}≠{v}")
    got_r = data.get("pass_rate") or {}
    for s, v in rate.items():
        x = got_r.get(s)
        try:
            x = float(str(x).rstrip("%")) / (100 if float(str(x).rstrip("%")) > 1 else 1)
        except ValueError:
            x = None
        if not close(x, v, 0.006):
            bad.append(f"pass_rate[{s}]={got_r.get(s)}≠{v:.3f}")
    if list(data.get("top3") or []) != top3:
        bad.append(f"top3={data.get('top3')}≠{top3}")
    sc.check(not bad, "numbers: " + "; ".join(bad[:5]))
    tests = find("test_grade_stats.py")
    if tests and os.path.dirname(tests) != os.path.dirname(tool):
        tests = None
    if sc.check(bool(tests), "test_grade_stats.py not delivered next to the tool"):
        t = run([sys.executable, "-m", "unittest", "test_grade_stats"], cwd=work)
        sc.check(t.returncode == 0, f"own tests fail: {tail(t.stderr)}")
    sc.emit()


main()
