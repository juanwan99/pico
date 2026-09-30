import io
import os
import unittest
from contextlib import redirect_stdout

from gradebook.cli import main

DATA = os.path.join(os.path.dirname(__file__), "data", "sample.csv")


class CliTest(unittest.TestCase):
    def run_cli(self, *args):
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = main(list(args))
        return rc, buf.getvalue()

    def test_summary_lists_classes(self):
        rc, out = self.run_cli("summary", DATA)
        self.assertEqual(rc, 0)
        for cls in ("七年级1班", "七年级2班", "七年级3班"):
            self.assertIn(cls, out)

    def test_card_unknown(self):
        self.assertEqual(self.run_cli("card", DATA, "nope")[0], 1)

    def test_rank_header(self):
        rc, out = self.run_cli("rank", DATA, "七年级1班", "数学")
        self.assertEqual(rc, 0)
        self.assertTrue(out.splitlines()[0].startswith("名次"))
