"""Stage 5a: the daily log's guards (`docs/stages/stage-5a.md`)."""

import gzip
import html
import re
import unittest
from datetime import date, datetime

from repo_liquidity import live, scheduled


class FomcCalendarTests(unittest.TestCase):
    def test_every_statement_is_on_the_saved_page(self):
        calendar = live.load_fomc_calendar()
        raw = gzip.decompress(live.CALENDAR_PAGE.read_bytes()).decode("utf-8", errors="replace")
        text = re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", raw)))
        for statement in calendar:
            meeting = statement.meeting.rsplit(",", 1)[0]
            year = statement.meeting.rsplit(" ", 1)[1]
            section = text[text.index(f"{year} FOMC Meetings"):]
            self.assertIn(meeting, section[:3000], statement.meeting)
            self.assertEqual(statement.instant.time(), live.STATEMENT_TIME)

    def test_the_page_matches_its_manifest(self):
        live.load_fomc_calendar()  # raises ValueError on a mismatch

    def test_the_calendar_is_in_order(self):
        instants = [statement.instant for statement in live.load_fomc_calendar()]
        self.assertEqual(instants, sorted(instants))


class FomcGuardTests(unittest.TestCase):
    STATEMENTS = (live.Statement("September 15-16, 2026", datetime(2026, 9, 16, 14, 0)),
                  live.Statement("October 27-28, 2026", datetime(2026, 10, 28, 14, 0)))

    def test_a_decision_after_an_uncovered_statement_is_refused(self):
        """A day whose decision instant follows a scheduled statement the rate tables do not yet cover is refused.

        Recorded mutation (7 October 2026): in `live.require_tables_cover`, the filter `if last < statement.instant`
        changed to `if False`. This test failed with AssertionError (ValueError not raised).
        """
        tables = {"iorb_rate.csv": datetime(2026, 9, 16, 14, 0), "on_rrp_rate.csv": datetime(2026, 9, 16, 14, 0)}
        with self.assertRaises(ValueError) as caught:
            live.require_tables_cover(datetime(2026, 10, 28, 16, 0), tables, statements=self.STATEMENTS)
        self.assertIn("October 27-28, 2026", str(caught.exception))
        self.assertIn("iorb_rate.csv", str(caught.exception))

    def test_a_decision_before_the_statement_passes(self):
        tables = {"iorb_rate.csv": datetime(2026, 9, 16, 14, 0), "on_rrp_rate.csv": datetime(2026, 9, 16, 14, 0)}
        live.require_tables_cover(datetime(2026, 10, 27, 16, 0), tables, statements=self.STATEMENTS)

    def test_one_table_behind_is_enough_to_refuse(self):
        tables = {"iorb_rate.csv": datetime(2026, 10, 28, 14, 0), "on_rrp_rate.csv": datetime(2026, 9, 16, 14, 0)}
        with self.assertRaises(ValueError) as caught:
            live.require_tables_cover(datetime(2026, 10, 29, 16, 0), tables, statements=self.STATEMENTS)
        self.assertIn("on_rrp_rate.csv", str(caught.exception))
        tables["on_rrp_rate.csv"] = datetime(2026, 10, 28, 14, 0)
        live.require_tables_cover(datetime(2026, 10, 29, 16, 0), tables, statements=self.STATEMENTS)

    def test_the_tracked_tables_cover_today(self):
        live.require_tables_cover(datetime(2026, 10, 7, 16, 0), live.table_coverage())

    def test_table_coverage_reads_both_tables(self):
        coverage = live.table_coverage()
        self.assertEqual(set(coverage), {"iorb_rate.csv", "on_rrp_rate.csv"})
        self.assertEqual(coverage["iorb_rate.csv"], scheduled.load_iorb_rates()[-1].announced_at)


class LoggableTests(unittest.TestCase):
    def test_a_development_day_is_never_logged(self):
        """No day on or before the development window's end is logged (`docs/stages/stage-5a.md`, must-show 3).

        Recorded mutation (7 October 2026): in `live.require_loggable`, `if day <= LAST_DEVELOPMENT_DAY:` changed to
        `if False:`. This test failed with AssertionError (ValueError not raised).
        """
        with self.assertRaises(ValueError):
            live.require_loggable(date(2025, 12, 31))
        live.require_loggable(date(2026, 10, 8))


if __name__ == "__main__":
    unittest.main()
