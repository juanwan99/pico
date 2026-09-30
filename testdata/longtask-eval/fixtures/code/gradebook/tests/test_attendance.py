import os
import unittest

from gradebook.attendance import class_attendance, load_attendance
from gradebook.loader import load_csv

HERE = os.path.join(os.path.dirname(__file__), "data")


class AttendanceTest(unittest.TestCase):
    def test_roll_up(self):
        students = load_csv(os.path.join(HERE, "sample.csv"))
        rec = load_attendance(os.path.join(HERE, "attendance.csv"))
        got = class_attendance(students, rec)
        self.assertEqual(got["七年级1班"], {"到": 1, "迟到": 1, "请假": 1, "旷课": 0})
        self.assertEqual(got["七年级2班"]["旷课"], 1)
        self.assertEqual(got["七年级3班"]["到"], 1)
