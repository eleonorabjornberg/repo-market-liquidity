"""The H.4.1 parser: first prints of the Fed's U.S. Treasury securities held outright.

Each archived release is its own first print. The parser reads table 1's row "U.S. Treasury securities": the week
average, its change from the previous week as printed, and the Wednesday level, in millions of dollars.
"""

import gzip
import pathlib
import unittest
from datetime import date

from repo_liquidity import h41

PAGES = pathlib.Path(__file__).resolve().parent / "fixtures" / "h41_pages"


def page(name):
    return gzip.decompress((PAGES / name).read_bytes()).decode("utf-8", errors="replace")


class ParseTests(unittest.TestCase):
    def test_old_format_2018(self):
        row = h41.parse_release(page("20180405.htm.gz"), release_date=date(2018, 4, 5))
        self.assertEqual(row.week_ended, date(2018, 4, 4))
        self.assertEqual(row.week_average, 2419828)
        self.assertEqual(row.change_from_prior_week, -4996)
        self.assertEqual(row.wednesday_level, 2413031)

    def test_new_format_2025(self):
        row = h41.parse_release(page("20250102.htm.gz"), release_date=date(2025, 1, 2))
        self.assertEqual(row.week_ended, date(2025, 1, 1))
        self.assertEqual(row.week_average, 4303855)
        self.assertEqual(row.change_from_prior_week, -4961)
        self.assertEqual(row.wednesday_level, 4291106)

    def test_a_release_dated_its_own_wednesday_is_refused(self):
        with self.assertRaises(ValueError):
            h41.parse_release(page("20250102.htm.gz"), release_date=date(2025, 1, 1))

    def test_a_page_without_the_row_is_refused(self):
        with self.assertRaises(ValueError):
            h41.parse_release("<html>no table here</html>", release_date=date(2025, 1, 2))


if __name__ == "__main__":
    unittest.main()
