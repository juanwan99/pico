"""LC2: repaired roster project — given tests green, tests untouched, hidden edge tests green."""

import os
import sys
import zipfile
from pathlib import Path

sys.path.insert(0, "/w/check")
from _common import OUT, Score, run, tail, workdir

HIDDEN = """
import os
import tempfile
import unittest

from roster.io import load_students
from roster.seating import make_seating
from roster.stats import group_means, mean, median


class Hidden(unittest.TestCase):
    def test_group_everyone_absent(self):
        rows = [{"name": "x", "group": "Z", "score": None}, {"name": "y", "group": "A", "score": 70.0}]
        self.assertEqual(group_means(rows), {"A": 70.0, "Z": None})

    def test_median_edges(self):
        self.assertEqual(median([5]), 5)
        self.assertIsNone(median([]))
        self.assertIsNone(median([None]))
        self.assertEqual(median([1, None, 2]), 1.5)

    def test_mean_empty(self):
        self.assertIsNone(mean([]))

    def test_seating_edges(self):
        self.assertEqual(make_seating(list("ab"), 5), [["a", "b"]])
        self.assertEqual(make_seating([], 3), [])
        self.assertEqual(make_seating(list("abc"), 1), [["a"], ["b"], ["c"]])
        with self.assertRaises(ValueError):
            make_seating(list("ab"), 0)

    def test_load_bom_spaces(self):
        fd, path = tempfile.mkstemp(suffix=".csv")
        os.close(fd)
        with open(path, "w", encoding="utf-8-sig", newline="") as fh:
            fh.write("姓名,组别,分数\\n 甲 , B ,\\n乙,A,59.5\\n")
        rows = load_students(path)
        self.assertEqual([r["name"] for r in rows], ["甲", "乙"])
        self.assertEqual(rows[0]["group"], "B")
        self.assertIsNone(rows[0]["score"])
        self.assertEqual(rows[1]["score"], 59.5)


if __name__ == "__main__":
    unittest.main()
"""

PROTECTED = ("tests/test_roster.py", "tests/data/class.csv")


def project_root():
    for dirpath, _dirs, files in os.walk(OUT):
        if "stats.py" in files and os.path.basename(dirpath) == "roster":
            return os.path.dirname(dirpath)
    return None


def original(name):
    with zipfile.ZipFile("/w/in/roster.zip") as zf:
        for n in zf.namelist():
            if n.endswith(name):
                return zf.read(n)
    return None


def main():
    sc = Score()
    root = project_root()
    if not root:
        sc.fail("no repaired project (roster/stats.py) in delivered files")
        sc.emit()
    work = workdir(root)
    changed = []
    for rel in PROTECTED:
        path = os.path.join(work, rel)
        if not os.path.exists(path) or Path(path).read_bytes() != original(rel):
            changed.append(rel)
    sc.check(not changed, "tests changed or missing: " + ",".join(changed))
    given = run([sys.executable, "-m", "unittest", "discover", "-s", "tests", "-t", "."], cwd=work)
    sc.check(given.returncode == 0, f"given tests fail: {tail(given.stderr)}")
    os.makedirs(os.path.join(work, "hidden_tests"), exist_ok=True)
    open(os.path.join(work, "hidden_tests", "__init__.py"), "w").close()
    with open(os.path.join(work, "hidden_tests", "test_hidden.py"), "w", encoding="utf-8") as fh:
        fh.write(HIDDEN)
    hidden = run(
        [sys.executable, "-m", "unittest", "discover", "-s", "hidden_tests", "-t", "."], cwd=work
    )
    sc.check(hidden.returncode == 0, f"hidden tests fail: {tail(hidden.stderr, 240)}")
    sc.emit()


main()
