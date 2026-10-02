import os
import unittest
from datetime import date

from classfund import api_v1
from classfund.ledger import Entry, Ledger, load_csv

DATA = os.path.join(os.path.dirname(__file__), "..", "data")


class LedgerTest(unittest.TestCase):
    def test_balance(self):
        led = Ledger([Entry(date(2026, 9, 1), 30000, "班费", "20250301"), Entry(date(2026, 9, 8), -3260, "卫生用品")])
        self.assertEqual(led.balance(), 26740)
        self.assertEqual(led.paid_by("20250301"), 30000)

    def test_rejects_float(self):
        with self.assertRaises(TypeError):
            Ledger([Entry(date(2026, 9, 1), 300.0, "班费", "20250301")])

    def test_load_sample(self):
        led = load_csv(os.path.join(DATA, "entries.csv"))
        self.assertEqual(len(led.entries), 48)
        self.assertEqual(led.paid_by("20250326"), 30000)

    def test_api_v1_shape(self):
        led = Ledger([Entry(date(2026, 9, 1), 30000, "班费", "20250301")])
        self.assertEqual(api_v1.get_balance(led), {"balance_fen": 30000, "balance": "¥300.00"})
        self.assertEqual(api_v1.list_entries(led, "20250301")[0]["date"], "2026/9/1")


if __name__ == "__main__":
    unittest.main()
