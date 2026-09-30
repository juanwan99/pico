import os
import unittest

from roster.io import load_students
from roster.seating import make_seating
from roster.stats import group_means, mean, median

DATA = os.path.join(os.path.dirname(__file__), "data", "class.csv")


class LoadTest(unittest.TestCase):
    def test_reads_excel_csv(self):
        rows = load_students(DATA)
        self.assertEqual(len(rows), 5)
        self.assertEqual(rows[0]["name"], "张三")
        self.assertEqual(rows[1]["name"], "李四")
        self.assertIsNone(rows[2]["score"])


class StatsTest(unittest.TestCase):
    def test_mean_skips_absent(self):
        self.assertEqual(mean([90, None, 70]), 80)

    def test_mean_nobody(self):
        self.assertIsNone(mean([None, None]))

    def test_median_odd(self):
        self.assertEqual(median([3, 1, 2]), 2)

    def test_median_even(self):
        self.assertEqual(median([4, 1, 3, 2]), 2.5)

    def test_group_means(self):
        self.assertEqual(group_means(load_students(DATA)), {"A": 85.0, "B": 71.0, "C": 65.0})


class SeatingTest(unittest.TestCase):
    def test_full_rows(self):
        self.assertEqual(make_seating(list("abcdef"), 3), [list("abc"), list("def")])

    def test_short_last_row(self):
        self.assertEqual(make_seating(list("abcdefg"), 3), [list("abc"), list("def"), ["g"]])


if __name__ == "__main__":
    unittest.main()
