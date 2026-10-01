"""LH1: gradebook refactor — one grading policy for all five sites, cls → class_name.

Points (all essential): given tests green + untouched · term-score math ·
thresholds (default, argument, GRADEBOOK_GRADING file) · the five sites agree
with a reference on a hidden roster, under default and custom thresholds ·
rename with a warning alias and no student ``.cls`` left in the package.
"""

import json
import os
import re
import sys
import zipfile
from pathlib import Path

sys.path.insert(0, "/w/check")
from _common import OUT, Score, run, tail, workdir

HIDDEN_CSV = """学号,姓名,班级,科目,平时,期中,期末
9001,甲,一班,语文,80,90,85
9001,甲,一班,数学,80.5,80,80
9001,甲,一班,英语,60,60,60
9002,乙,一班,语文,80,,90
9002,乙,一班,数学,,,
9002,乙,一班,英语,95,95,
9003,丙,一班,语文,59.5,60,60.5
9003,丙,一班,数学,90,89.5,90
9003,丙,一班,英语,88,86,84
9004,丁,二班,语文,70,62,58
9004,丁,二班,数学,100,95,93
9004,丁,二班,英语,,70,50
9005,戊,二班,语文,64.5,65,65
9005,戊,二班,数学,84,86,85.5
9005,戊,二班,英语,75,74.5,75
"""

PROBE = r'''
import csv, io, json, os, sys, tempfile, warnings, dataclasses
from decimal import Decimal, ROUND_HALF_UP
group, csv_path = sys.argv[1], sys.argv[2]
out = {"ok": True, "why": []}

def bad(msg):
    out["ok"] = False
    out["why"].append(msg[:200])

W = {"平时": 30, "期中": 30, "期末": 40}

def ref_term(parts):
    got = {k: parts.get(k) for k in W if parts.get(k) is not None}
    if not got:
        return None
    val = sum(Decimal(str(v)) * W[k] for k, v in got.items()) / Decimal(sum(W[k] for k in got))
    return float(val.quantize(Decimal("0.1"), ROUND_HALF_UP))

def ref_letter(score, th):
    if score is None:
        return "缺考"
    for k in "ABCD":
        if score >= th[k]:
            return k
    return "E"

def same(a, b):
    if a is None or b is None:
        return a is None and b is None
    return abs(float(a) - float(b)) < 1e-6

try:
    if group == "math":
        from gradebook.grading import term_score
        cases = [
            ({"平时": 80, "期中": 90, "期末": 85}, 85.0),
            ({"平时": 80.5, "期中": 80, "期末": 80}, 80.2),
            ({"平时": 80, "期中": None, "期末": 90}, 85.7),
            ({"平时": None, "期中": None, "期末": 72}, 72.0),
            ({"平时": 59.5, "期中": 60, "期末": 60.5}, 60.1),
            ({"平时": None, "期中": None, "期末": None}, None),
        ]
        for parts, want in cases:
            got = term_score(parts)
            if not same(got, want):
                bad(f"term_score({parts}) = {got!r}, want {want!r}")
    elif group == "thresholds":
        from gradebook.grading import letter
        if os.environ.get("GRADEBOOK_GRADING"):
            if (letter(92), letter(95), letter(62)) != ("B", "A", "E"):
                bad(f"GRADEBOOK_GRADING ignored: letter(92/95/62) = {letter(92), letter(95), letter(62)}")
        else:
            for s, want in [(90, "A"), (89.9, "B"), (80, "B"), (70, "C"), (60, "D"), (59.9, "E"), (None, "缺考")]:
                if letter(s) != want:
                    bad(f"letter({s}) = {letter(s)!r}, want {want}")
        custom = {"A": 95, "B": 85, "C": 75, "D": 65}
        if letter(92, custom) != "B":
            bad(f"letter(92, custom) = {letter(92, custom)!r}, want B")
    elif group == "sites":
        th = json.loads(os.environ.get("PROBE_TH") or '{"A": 90, "B": 80, "C": 70, "D": 60}')
        from gradebook.export import export_csv
        from gradebook.loader import by_class, load_csv
        from gradebook.notify import parent_message
        from gradebook.ranking import rank_class
        from gradebook.report_card import render_card
        from gradebook.summary import class_summary
        import re
        students = load_csv(csv_path)
        raw = {}
        with open(csv_path, encoding="utf-8") as fh:
            for row in csv.DictReader(fh):
                parts = {k: (float(row[k]) if row[k] else None) for k in W}
                raw[(row["学号"], row["科目"])] = parts
        want = {}
        for key, parts in raw.items():
            t = ref_term(parts)
            want[key] = (t, ref_letter(t, th))
        for st in students:
            card = render_card(st)
            seen = {}
            for line in card.splitlines()[1:]:
                m = re.match(r"^\s*(\S+)\s+总评\s+(\S+)\s+等级\s+(\S+)", line)
                if m:
                    seen[m.group(1)] = (m.group(2), m.group(3))
            msg = parent_message(st)
            said = dict(re.findall(r"(语文|数学|英语)等级\s*([A-E]|缺考)", msg))
            for sub in st.scores:
                t, lt = want[(st.sid, sub)]
                shown = "—" if t is None else f"{t:.1f}"
                if seen.get(sub) != (shown, lt):
                    bad(f"card {st.sid} {sub}: {seen.get(sub)} want {(shown, lt)}")
                if said.get(sub) != lt:
                    bad(f"notice {st.sid} {sub}: {said.get(sub)!r} want {lt}")
        for cls, members in by_class(students).items():
            for sub in ("语文", "数学", "英语"):
                for name, score, lt in rank_class(members, sub):
                    sid = next(s.sid for s in members if s.name == name)
                    t, wl = want[(sid, sub)]
                    if not same(score, t) or lt != wl:
                        bad(f"rank {sid} {sub}: {(score, lt)} want {(t, wl)}")
        fd, path = tempfile.mkstemp(suffix=".csv")
        os.close(fd)
        export_csv(students, path)
        with open(path, encoding="utf-8-sig", newline="") as fh:
            for row in csv.DictReader(fh):
                t, wl = want[(row["学号"], row["科目"])]
                if row["总评"] != ("" if t is None else f"{t:.1f}") or row["等级"] != wl:
                    bad(f"export {row['学号']} {row['科目']}: {(row['总评'], row['等级'])} want {(t, wl)}")
        summ = class_summary(students)
        for cls, members in by_class(students).items():
            for sub in ("语文", "数学", "英语"):
                ts = [want[(s.sid, sub)] for s in members]
                letters = {}
                for _t, lt in ts:
                    letters[lt] = letters.get(lt, 0) + 1
                scored = [t for t, _ in ts if t is not None]
                rate = round(sum(1 for t in scored if t >= 60) / len(scored), 3) if scored else None
                got = summ[cls][sub]
                if {k: v for k, v in got["letters"].items() if v} != letters:
                    bad(f"summary {cls} {sub} letters {got['letters']} want {letters}")
                if not same(got["pass_rate"], rate):
                    bad(f"summary {cls} {sub} pass_rate {got['pass_rate']} want {rate}")
    elif group == "rename":
        from gradebook.models import Student
        from gradebook.loader import load_csv
        if dataclasses.is_dataclass(Student):
            names = [f.name for f in dataclasses.fields(Student)]
            if "class_name" not in names or "cls" in names:
                bad(f"Student fields {names}")
        s = Student(sid="1", name="x", class_name="c")
        if "cls" in vars(s) or vars(s).get("class_name") != "c":
            bad(f"Student stores {sorted(vars(s))}")
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            v = s.cls
            s.cls = "d"
        if v != "c" or s.class_name != "d":
            bad(f"cls alias read {v!r} / write -> {s.class_name!r}")
        if sum(issubclass(w.category, DeprecationWarning) for w in caught) < 2:
            bad("cls alias does not warn DeprecationWarning on read and write")
        if load_csv(csv_path)[0].class_name != "一班":
            bad("load_csv does not fill class_name")
except Exception as exc:
    bad(f"{type(exc).__name__}: {exc}")
print(json.dumps(out, ensure_ascii=False))
'''


def project_root():
    for dirpath, _dirs, files in os.walk(OUT):
        if "models.py" in files and os.path.basename(dirpath) == "gradebook":
            return os.path.dirname(dirpath)
    return None


def originals():
    with zipfile.ZipFile("/w/in/gradebook.zip") as zf:
        return {
            n.split("/", 1)[1]: zf.read(n)
            for n in zf.namelist()
            if n.split("/", 1)[-1].startswith("tests/") and not n.endswith("/")
        }


def probe(work, group, extra_env=None):
    env_bits = [f"{k}={v}" for k, v in (extra_env or {}).items()]
    proc = run(["env", f"PYTHONPATH={work}", *env_bits, sys.executable, "probe.py", group, "hidden.csv"], cwd=work)
    try:
        got = json.loads(proc.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError):
        return False, f"{group}: crashed {tail(proc.stderr)}"
    return got["ok"], f"{group}: " + " | ".join(got["why"][:3])


def main():
    sc = Score()
    root = project_root()
    if not root:
        sc.fail("no project (gradebook/models.py) in delivered files")
        sc.emit()
    work = workdir(root)
    changed = [
        rel for rel, raw in originals().items()
        if not os.path.exists(os.path.join(work, rel)) or Path(work, rel).read_bytes() != raw
    ]
    given = run([sys.executable, "-m", "unittest", "discover", "-s", "tests", "-t", "."], cwd=work)
    sc.check(
        not changed and given.returncode == 0,
        f"given tests: changed={changed[:3]} rc={given.returncode} {tail(given.stderr)}",
    )
    Path(work, "probe.py").write_text(PROBE, encoding="utf-8")
    Path(work, "hidden.csv").write_text(HIDDEN_CSV, encoding="utf-8")
    custom = os.path.abspath("custom-grading.json")
    th = {"A": 95, "B": 85, "C": 75, "D": 65}
    Path(custom).write_text(json.dumps(th), encoding="utf-8")
    ok, note = probe(work, "math")
    sc.check(ok, note)
    ok1, n1 = probe(work, "thresholds")
    ok2, n2 = probe(work, "thresholds", {"GRADEBOOK_GRADING": custom})
    sc.check(ok1 and ok2, n1 if not ok1 else n2)
    ok1, n1 = probe(work, "sites")
    ok2, n2 = probe(work, "sites", {"GRADEBOOK_GRADING": custom, "PROBE_TH": json.dumps(th).replace(" ", "")})
    sc.check(ok1 and ok2, n1 if not ok1 else "custom thresholds " + n2)
    ok, note = probe(work, "rename")
    left = []
    for path in sorted(Path(work, "gradebook").glob("*.py")):
        if path.name == "models.py":
            continue
        for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if re.search(r"(?<!args)\.cls\b|\bcls\s*=", line):
                left.append(f"{path.name}:{i}")
    sc.check(ok and not left, note if not ok else "student .cls left at " + ",".join(left[:5]))
    sc.emit()


main()
