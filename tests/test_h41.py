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



class MbsRowTests(unittest.TestCase):
    """Table 1's "Mortgage-backed securities" row (`docs/stages/stage-1a-correction.md`, item 1).

    Its footnote mark is printed as "(4)" in 2018 and as a bare "4" in 2025; neither may be read as a number.
    """

    def test_old_format_2018(self):
        row = h41.parse_release(page("20180405.htm.gz"), release_date=date(2018, 4, 5), row=h41.MBS_ROW)
        self.assertEqual((row.week_ended, row.week_average, row.change_from_prior_week, row.wednesday_level),
                         (date(2018, 4, 4), 1754368, -5030, 1754368))

    def test_new_format_2025(self):
        row = h41.parse_release(page("20250102.htm.gz"), release_date=date(2025, 1, 2), row=h41.MBS_ROW)
        self.assertEqual((row.week_ended, row.week_average, row.change_from_prior_week, row.wednesday_level),
                         (date(2025, 1, 1), 2233262, -12690, 2233262))

    def test_the_treasury_row_is_still_the_default(self):
        default = h41.parse_release(page("20250102.htm.gz"), release_date=date(2025, 1, 2))
        named = h41.parse_release(page("20250102.htm.gz"), release_date=date(2025, 1, 2), row=h41.TREASURY_ROW)
        self.assertEqual(default, named)

    def test_an_unknown_row_is_refused(self):
        with self.assertRaises(ValueError):
            h41.parse_release(page("20250102.htm.gz"), release_date=date(2025, 1, 2), row="Gold certificate account")


if __name__ == "__main__":
    unittest.main()
