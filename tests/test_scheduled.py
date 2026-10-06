"""Scheduled inputs: the standing repo facility's rate and the FOMC runoff caps.

Each row of `tests/fixtures/snapshots/fomc_notes/*.csv` is read from a saved federalreserve.gov page. The value for
row T is read at T's decision instant (16:00 on the panel day before T): only publications at or before that instant,
effective on or before T (`metadata/sources_phase3.json`, `scheduled_availability`).
"""

import gzip
import html
import json
import pathlib
import re
import unittest
from datetime import date, datetime, time, timedelta

from repo_liquidity import scheduled

ROOT = pathlib.Path(__file__).resolve().parents[1]
NOTES = ROOT / "tests" / "fixtures" / "snapshots" / "fomc_notes"
DECISION = time(16, 0)


def page_text(name):
    raw = gzip.decompress((NOTES / "pages" / name).read_bytes()).decode("utf-8", errors="replace")
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", raw)))


def weekdays(first, last):
    days, day = [], first
    while day <= last:
        if day.weekday() < 5:
            days.append(day)
        day += timedelta(days=1)
    return days


class TableTests(unittest.TestCase):
    def test_tables_match_their_manifests(self):
        scheduled.load_srf_rates()
        scheduled.load_runoff_caps()

    def test_an_edited_table_is_refused(self):
        path = NOTES / "srf_rate.csv"
        original = path.read_bytes()
        try:
            path.write_bytes(original.replace(b",0.25,", b",0.30,"))
            with self.assertRaises(ValueError):
                scheduled.load_srf_rates()
        finally:
            path.write_bytes(original)

    def test_every_row_is_announced_before_the_business_day_before_it_takes_effect(self):
        for row in scheduled.load_srf_rates() + scheduled.load_runoff_caps():
            previous = row.effective - timedelta(days=1)
            while previous.weekday() >= 5:
                previous -= timedelta(days=1)
            self.assertLessEqual(row.announced_at, datetime.combine(previous, DECISION), row)

    def test_every_srf_rate_is_in_its_page(self):
        for row in scheduled.load_srf_rates():
            text = page_text(row.page)
            self.assertRegex(text, rf"repurchase agreement operations (with|at) (a minimum bid rate of|a rate of) "
                                   rf"{re.escape(row.raw_values[0])} percent", row.page)
            self.assertIn(f"Effective {row.effective:%B} {row.effective.day}, {row.effective.year}", text)

    def test_every_cap_is_in_its_page(self):
        for row in scheduled.load_runoff_caps():
            text = page_text(row.page)
            for amount in row.raw_values:
                if amount == "0":
                    self.assertIn("all principal payments", text, row.page)
                else:
                    self.assertIn(f"${amount} billion", text, (row.page, amount))

    def test_srf_rates_match_the_parent_operation_snapshots(self):
        checked = scheduled.cross_check_srf_operations()
        self.assertGreater(checked, 0)


class ReadTests(unittest.TestCase):
    def test_srf_rate_is_missing_before_the_facility(self):
        dates = weekdays(date(2021, 7, 26), date(2021, 7, 30))
        values = scheduled.srf_rate_values(dates, decision_time=DECISION)
        self.assertEqual([v for d, v in zip(dates, values) if d < date(2021, 7, 29)], [None, None, None])
        self.assertEqual(values[dates.index(date(2021, 7, 29))], 0.25)

    def test_a_rate_announced_the_afternoon_before_is_read_on_its_effective_day(self):
        dates = weekdays(date(2026, 9, 14), date(2026, 9, 18))
        values = scheduled.srf_rate_values(dates, decision_time=DECISION)
        self.assertEqual(values[dates.index(date(2026, 9, 16))], 3.75)
        self.assertEqual(values[dates.index(date(2026, 9, 17))], 4.0)

    def test_caps_follow_their_effective_dates(self):
        dates = weekdays(date(2025, 3, 28), date(2025, 4, 2))
        values = scheduled.runoff_cap_values(dates, decision_time=DECISION)
        self.assertEqual(values[dates.index(date(2025, 3, 31))], (25.0, 35.0))
        self.assertEqual(values[dates.index(date(2025, 4, 1))], (5.0, 35.0))

    def test_a_publication_after_the_decision_instant_is_never_read(self):
        """Leakage guard for both scheduled inputs.

        Every row announced after a day's decision instant is moved to take effect that day; the values read at
        that instant must not move.

        Recorded mutation (6 October 2026): in `scheduled._in_force`, `known = [row for row in rows if
        row.announced_at <= instant and row.effective <= day]` changed to `known = [row for row in rows if
        row.effective <= day]`. This test then fails with AssertionError: 4.0 != 0.25 at 2021-07-29
        (load_srf_rates): the shifted September 2026 note was read before it was published.
        """
        dates = weekdays(date(2017, 12, 1), date(2026, 9, 30))
        for loader, reader in ((scheduled.load_srf_rates, scheduled.srf_rate_values),
                               (scheduled.load_runoff_caps, scheduled.runoff_cap_values)):
            rows = loader()
            baseline = reader(dates, decision_time=DECISION, rows=rows)
            for index in range(1, len(dates)):
                instant = datetime.combine(dates[index - 1], DECISION)
                late = [row for row in rows if row.announced_at > instant]
                if not late:
                    continue
                early = [row for row in rows if row.announced_at <= instant]
                shifted = early + [row._replace(effective=dates[index]) for row in late]
                self.assertEqual(reader(dates[index - 1 : index + 1], decision_time=DECISION, rows=shifted)[1],
                                 baseline[index], (dates[index], loader.__name__))

    def test_columns_already_on_a_row_are_refused(self):
        from repo_model.data import DailyObservation

        rows = [DailyObservation(date(2022, 1, 3), {"srf_rate": 1.0}), DailyObservation(date(2022, 1, 4), {})]
        with self.assertRaises(ValueError):
            scheduled.with_scheduled(rows, decision_time=DECISION)


if __name__ == "__main__":
    unittest.main()
