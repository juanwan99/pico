import unittest

from classfund.money import fmt_yuan, parse_yuan


class MoneyTest(unittest.TestCase):
    def test_fmt(self):
        self.assertEqual(fmt_yuan(1230), "¥12.30")
        self.assertEqual(fmt_yuan(5), "¥0.05")
        self.assertEqual(fmt_yuan(-50), "-¥0.50")

    def test_fmt_rejects_float(self):
        with self.assertRaises(TypeError):
            fmt_yuan(12.3)

    def test_parse(self):
        self.assertEqual(parse_yuan("12.3"), 1230)
        self.assertEqual(parse_yuan("12.30元"), 1230)
        self.assertEqual(parse_yuan("¥12"), 1200)
        self.assertEqual(parse_yuan("-0.5"), -50)


if __name__ == "__main__":
    unittest.main()
