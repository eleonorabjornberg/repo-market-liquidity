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


class AgencyRowTests(unittest.TestCase):
    """Table 1's "Federal agency debt securities" row (#30; answer 15, Nicholas Beroud: include agency debt).

    Its footnote mark is printed "(2)" in 2018 and a bare "2" in 2025; neither may be read as a number.
    """

    def test_old_format_2018(self):
        row = h41.parse_release(page("20180405.htm.gz"), release_date=date(2018, 4, 5), row=h41.AGENCY_ROW)
        self.assertEqual((row.week_ended, row.week_average, row.change_from_prior_week, row.wednesday_level),
                         (date(2018, 4, 4), 4391, 0, 4391))

    def test_new_format_2025(self):
        row = h41.parse_release(page("20250102.htm.gz"), release_date=date(2025, 1, 2), row=h41.AGENCY_ROW)
        self.assertEqual((row.week_ended, row.week_average, row.change_from_prior_week, row.wednesday_level),
                         (date(2025, 1, 1), 2347, 0, 2347))

    def test_the_prose_mention_of_the_row_name_is_not_read_as_the_row(self):
        text = "Averages of daily figures Wednesday Jan 1, 2025 Federal agency debt securities, and mortgage-backed"
        with self.assertRaises(ValueError):
            h41.parse_release(text, release_date=date(2025, 1, 2), row=h41.AGENCY_ROW)


class AgencySecuritiesTests(unittest.TestCase):
    """The derived measure Nicholas asked for in answer 15: agency debt plus MBS, week by week, from the same release."""

    def _release(self, name, release_date, row):
        return h41.parse_release(page(name), release_date=release_date, row=row)

    def test_the_change_is_agency_debt_plus_mbs_from_the_same_release(self):
        agency = self._release("20180405.htm.gz", date(2018, 4, 5), h41.AGENCY_ROW)
        mbs = self._release("20180405.htm.gz", date(2018, 4, 5), h41.MBS_ROW)
        total = h41.agency_securities([agency], [mbs])
        self.assertEqual(len(total), 1)
        self.assertEqual((total[0].week_ended, total[0].release_date), (date(2018, 4, 4), date(2018, 4, 5)))
        self.assertEqual(total[0].change_from_prior_week, 0 + -5030)
        self.assertEqual(total[0].week_average, 4391 + 1754368)
        self.assertEqual(total[0].wednesday_level, 4391 + 1754368)

    def test_releases_of_different_weeks_are_not_added(self):
        agency = self._release("20180405.htm.gz", date(2018, 4, 5), h41.AGENCY_ROW)
        mbs = self._release("20250102.htm.gz", date(2025, 1, 2), h41.MBS_ROW)
        with self.assertRaises(ValueError):
            h41.agency_securities([agency], [mbs])

    def test_extracts_of_different_lengths_are_not_added(self):
        agency = self._release("20180405.htm.gz", date(2018, 4, 5), h41.AGENCY_ROW)
        with self.assertRaises(ValueError):
            h41.agency_securities([agency], [])


if __name__ == "__main__":
    unittest.main()
