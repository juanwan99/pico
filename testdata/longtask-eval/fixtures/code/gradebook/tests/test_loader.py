import os
import unittest

from gradebook.loader import by_class, find, load_csv

DATA = os.path.join(os.path.dirname(__file__), "data", "sample.csv")


class LoaderTest(unittest.TestCase):
    def setUp(self):
        self.students = load_csv(DATA)

    def test_counts(self):
        self.assertEqual(len(self.students), 18)
        self.assertEqual(sorted(by_class(self.students)), ["七年级1班", "七年级2班", "七年级3班"])

    def test_student_fields(self):
        s = find(self.students, "2026001")
        self.assertEqual(s.name, "张伟")
        self.assertEqual(s.cls, "七年级1班")
        self.assertEqual(s.subjects(), ["数学", "英语", "语文"])

    def test_missing_marks(self):
        s = find(self.students, "2026004")
        self.assertIsNone(s.part("数学", "期中"))
        e = find(self.students, "2026011")
        self.assertEqual(e.scores["英语"], {"平时": None, "期中": None, "期末": None})

    def test_group_by_class_keeps_order(self):
        groups = by_class(self.students)
        self.assertEqual([s.sid for s in groups["七年级2班"]][:2], ["2026007", "2026008"])
        self.assertTrue(all(s.cls == "七年级2班" for s in groups["七年级2班"]))
