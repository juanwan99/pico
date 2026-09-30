import csv
import os
import tempfile
import unittest

from gradebook.export import export_csv
from gradebook.loader import by_class, find, load_csv
from gradebook.notify import parent_message
from gradebook.ranking import rank_class
from gradebook.report_card import render_card
from gradebook.summary import class_summary

DATA = os.path.join(os.path.dirname(__file__), "data", "sample.csv")


class ReportsTest(unittest.TestCase):
    def setUp(self):
        self.students = load_csv(DATA)

    def test_card_shape(self):
        text = render_card(find(self.students, "2026001"))
        lines = text.splitlines()
        self.assertEqual(lines[0], "张伟（七年级1班）成绩单")
        self.assertEqual(len(lines), 4)
        for line in lines[1:]:
            self.assertIn("总评", line)
            self.assertIn("等级", line)

    def test_rank_everyone_listed_missing_last(self):
        members = by_class(self.students)["七年级2班"]
        rows = rank_class(members, "英语")
        self.assertEqual(len(rows), 6)
        self.assertEqual(rows[-1][0], "徐明")
        self.assertIsNone(rows[-1][1])
        scores = [r[1] for r in rows[:-1]]
        self.assertEqual(scores, sorted(scores, reverse=True))

    def test_export_rows(self):
        fd, path = tempfile.mkstemp(suffix=".csv")
        os.close(fd)
        try:
            n = export_csv(self.students, path)
            with open(path, encoding="utf-8-sig", newline="") as fh:
                rows = list(csv.reader(fh))
        finally:
            os.remove(path)
        self.assertEqual(n, 54)
        self.assertEqual(rows[0], ["学号", "姓名", "班级", "科目", "总评", "等级"])
        self.assertEqual(len(rows), 55)

    def test_summary_keys(self):
        got = class_summary(self.students)
        self.assertEqual(sorted(got), ["七年级1班", "七年级2班", "七年级3班"])
        for info in got.values():
            self.assertEqual(sorted(info), ["数学", "英语", "语文"])
            for s in info.values():
                self.assertEqual(set(s), {"mean", "pass_rate", "letters"})

    def test_notice_mentions_every_subject(self):
        msg = parent_message(find(self.students, "2026001"))
        self.assertTrue(msg.startswith("张伟家长您好"))
        for sub in ("语文", "数学", "英语"):
            self.assertIn(sub + "等级", msg)
