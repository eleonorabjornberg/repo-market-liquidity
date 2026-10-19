"""The announced balance-sheet pace: the runoff caps less the announced purchases, as a declared H7 input (#125, avenue #56).

`runoff_caps` reads (0, 0) from 1 August 2019 and again from 1 December 2025, so H7 sees a flat balance sheet there. The
Fed added reserves by buying Treasury bills after both dates and, in 2020-22, by asset purchases. `announced_pace` is
one row per announcement: the caps in force, the purchases announced, and the signed pace (caps minus purchases, in $bn
a month, positive meaning drain). Each row's purchases are read from a saved federalreserve.gov or newyorkfed.org page.
Nothing here is wired into an estimator or a score.
"""

import gzip
import html
import json
import pathlib
import re
import tempfile
import unittest
from datetime import date, datetime, time, timedelta

from repo_liquidity import announced_pace, declaration, scheduled, snapshots

ROOT = pathlib.Path(__file__).resolve().parents[1]
NOTES = ROOT / "tests" / "fixtures" / "snapshots" / "fomc_notes"
DECISION = time(16, 0)


def page_text(name):
    raw = gzip.decompress((NOTES / "pages" / name).read_bytes()).decode("utf-8", errors="replace")
    text = re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", re.sub(r"(?s)<(script|style).*?</\1>", "", raw))))
    return text.replace("‑", "-")


def weekdays(first, last):
    days, day = [], first
    while day <= last:
        if day.weekday() < 5:
            days.append(day)
        day += timedelta(days=1)
    return days


def at(text):
    return datetime.fromisoformat(text)


class TableTests(unittest.TestCase):
    def test_the_tables_match_their_manifests(self):
        announced_pace.load_announced_pace()
        announced_pace.load_purchases()

    def test_an_edited_table_is_refused(self):
        for path, old, new in ((NOTES / "announced_pace.csv", b",-60,", b",-61,"),
                               (NOTES / "announced_purchases.csv", b",60,0,", b",61,0,")):
            original = path.read_bytes()
            self.assertIn(old, original, path.name)
            try:
                path.write_bytes(original.replace(old, new))
                with self.assertRaises(ValueError):
                    announced_pace.load_announced_pace() if "pace" in path.name else announced_pace.load_purchases()
            finally:
                path.write_bytes(original)

    def test_the_table_is_what_the_builder_makes_from_the_two_inputs(self):
        """The caps are never entered by hand: the table is rebuilt from `runoff_caps.csv` and `announced_purchases.csv`."""
        self.assertEqual(announced_pace.build_table_bytes(), (NOTES / "announced_pace.csv").read_bytes())

    def test_every_row_carries_the_caps_in_force_on_its_effective_day(self):
        caps = scheduled.load_runoff_caps()
        for row in announced_pace.load_announced_pace():
            in_force = max((c for c in caps if c.effective <= row.effective), key=lambda c: c.effective)
            self.assertEqual(row.caps, in_force.values, row.effective)

    def test_the_signed_pace_is_caps_less_purchases(self):
        for row in announced_pace.load_announced_pace():
            if row.purchases is None:
                self.assertIsNone(row.signed)
            else:
                self.assertAlmostEqual(row.signed, sum(row.caps) - sum(row.purchases), places=9, msg=row.effective)

    def test_a_row_is_announced_before_the_day_it_takes_effect(self):
        for row in announced_pace.load_announced_pace():
            self.assertLess(row.announced_at.date(), row.effective)

    def test_a_row_never_carries_a_value_announced_after_it(self):
        """The builder refuses a row whose carried caps or purchases were announced later than the row itself."""
        caps = scheduled.load_runoff_caps()
        purchases = announced_pace.load_purchases()
        late = purchases[0]._replace(announced_at=at("2030-01-01T12:00"), effective=date(2030, 1, 2))
        early = caps[-1]._replace(announced_at=at("2029-01-01T12:00"), effective=date(2031, 1, 1))
        with self.assertRaises(ValueError):
            announced_pace.build_rows(caps + [early], purchases + [late])

    def test_a_purchase_before_any_cap_is_refused(self):
        caps = scheduled.load_runoff_caps()
        first = announced_pace.load_purchases()[0]._replace(announced_at=at("2017-01-01T12:00"), effective=date(2017, 1, 2))
        with self.assertRaises(ValueError):
            announced_pace.build_rows(caps, [first])


class SourceTests(unittest.TestCase):
    """Each purchase row's amount and date are read from its saved page."""

    def test_every_amount_and_date_phrase_is_in_a_saved_page(self):
        for row in announced_pace.load_purchases():
            pages = [page_text(row.page)] + ([page_text(row.also_page)] if row.also_page else [])
            for phrase in row.amount_phrases:
                self.assertTrue(any(phrase in text for text in pages), (row.effective, phrase))
            if row.date_phrase:
                self.assertTrue(any(row.date_phrase in text for text in pages), (row.effective, row.date_phrase))

    def test_a_quantified_row_names_the_amounts_its_phrases_state(self):
        for row in announced_pace.load_purchases():
            if row.purchases is None:
                continue
            text = " ".join(row.amount_phrases)
            for amount in row.purchases:
                if amount:
                    self.assertIn(f"${amount:g} billion", text, (row.effective, amount))

    def test_the_announcement_time_is_the_pages_release_time_or_the_end_of_the_day(self):
        """A Board statement states the minute it was released; a Desk statement states none and is read from 23:59."""
        for row in announced_pace.load_purchases():
            text = page_text(row.page)
            if "federalreserve.gov" in row.source_url:
                stated = re.search(r"For release at (\d{1,2}):?(\d{2})? ([ap])\.m\.", text)
                if stated is None:
                    self.assertEqual(row.announced_at.time(), time(17, 0), row.effective)  # the Sunday action, 15 March 2020
                    continue
                hour = int(stated.group(1)) % 12 + (12 if stated.group(3) == "p" else 0)
                self.assertEqual(row.announced_at.time(), time(hour, int(stated.group(2) or 0)), row.effective)
            else:
                self.assertEqual(row.announced_at.time(), time(23, 59), row.effective)

    def test_the_saved_pages_are_in_the_snapshot_manifest_by_hash(self):
        manifest = snapshots.load_manifest("announced_pace")
        for name, digest in manifest["source_pages"].items():
            self.assertEqual(snapshots.hashlib.sha256((NOTES / "pages" / name).read_bytes()).hexdigest(), digest)


class MustShowTests(unittest.TestCase):
    """The rows the caps alone read as a flat balance sheet."""

    def pace(self, day):
        return announced_pace.pace_values([day - timedelta(days=1), day], decision_time=DECISION)[1]

    def test_october_2019_adds_reserves_where_the_caps_read_zero(self):
        self.assertEqual(scheduled.runoff_cap_values([date(2019, 10, 14), date(2019, 10, 15)], decision_time=DECISION)[1],
                         (0.0, 0.0))
        self.assertEqual(self.pace(date(2019, 10, 16)).signed, -60.0)
        self.assertEqual(self.pace(date(2019, 10, 14)).signed, 0.0)  # announced the 11th at 23:59, effective the 15th

    def test_june_2020_to_march_2022_is_net_purchases(self):
        self.assertEqual(self.pace(date(2020, 6, 12)).signed, -120.0)
        self.assertEqual(self.pace(date(2021, 11, 16)).signed, -105.0)
        self.assertEqual(self.pace(date(2021, 12, 16)).signed, -90.0)
        self.assertEqual(self.pace(date(2022, 1, 18)).signed, -60.0)
        self.assertEqual(self.pace(date(2022, 2, 15)).signed, -30.0)
        self.assertEqual(self.pace(date(2022, 3, 15)).signed, 0.0)

    def test_the_spring_2020_surge_has_no_monthly_amount(self):
        for day in (date(2020, 3, 17), date(2020, 3, 25), date(2020, 6, 10)):
            self.assertIsNone(self.pace(day).signed, day)
            self.assertEqual(self.pace(day).status, "unquantified")

    def test_runoff_resumes_from_the_caps_with_nothing_announced(self):
        self.assertEqual(self.pace(date(2022, 6, 2)).signed, 47.5)
        self.assertEqual(self.pace(date(2022, 9, 2)).signed, 95.0)

    def test_december_2025_adds_reserves_where_the_caps_read_zero(self):
        self.assertEqual(scheduled.runoff_cap_values([date(2025, 12, 11), date(2025, 12, 12)], decision_time=DECISION)[1],
                         (0.0, 0.0))
        self.assertEqual(self.pace(date(2025, 12, 15)).signed, -40.0)

    def test_the_pace_is_unquantified_after_the_first_schedule_of_december_2025(self):
        self.assertIsNone(self.pace(date(2026, 1, 13)).signed)
        self.assertIsNone(self.pace(date(2026, 9, 3)).signed)

    def test_nothing_is_read_before_the_first_cap(self):
        self.assertIsNone(announced_pace.pace_values([date(2017, 9, 20), date(2017, 9, 21)], decision_time=DECISION)[1])


class GuardTests(unittest.TestCase):
    def test_a_decision_instant_before_the_announcement_never_sees_the_pace(self):
        """Leakage guard (#125): a value announced after the decision instant is not read, and reading one raises.

        For every row, at an instant a minute before its announcement, `read` must not return that row, and `check_read`
        must refuse it as the row used.

        Recorded mutation (19 October 2026): in `announced_pace._in_force`, `known = [row for row in rows if
        row.announced_at <= instant and row.effective <= day]` changed to `known = [row for row in rows if
        row.effective <= day]`. `read` then selects the unannounced row and its `check_read` raises LookAheadError, so
        `test_every_unannounced_row_is_refused` fails with LookAheadError: the pace announced 2017-09-20 14:00:00 is read at
        2017-09-20 13:59:00, before it was public (also `test_the_newest_announced_row_is_read` and
        `test_a_later_announcement_never_moves_an_earlier_reading`).
        """
        rows = announced_pace.load_announced_pace()
        from repo_model.splits import LookAheadError

        for row in rows:
            instant = row.announced_at - timedelta(minutes=1)
            with self.assertRaises(LookAheadError, msg=str(row.effective)):
                announced_pace.check_read(rows, instant, row.effective, used=row)

    def test_every_unannounced_row_is_refused(self):
        rows = announced_pace.load_announced_pace()
        for row in rows:
            instant = row.announced_at - timedelta(minutes=1)
            got = announced_pace.read(rows, instant, row.effective)
            self.assertTrue(got is None or got.announced_at <= instant, row.effective)
            self.assertNotEqual(got, row)

    def test_a_pace_older_than_the_latest_announced_is_refused(self):
        """Staleness guard (#125): the value read is the newest announced and in force, never an older one.

        For every pair of rows, with the instant after both announcements and the day after both take effect, using
        the older row raises StaleReadError (a ValueError).

        Recorded mutation (19 October 2026): in `announced_pace._in_force`, `return max(known, key=lambda row:
        (row.effective, row.announced_at))` changed to `return known[0]`. `read` then returns the oldest admissible row
        and its `check_read` raises StaleReadError, so `test_the_newest_announced_row_is_read` fails with StaleReadError:
        the pace effective 2017-10-01 is read on 2018-01-01, after the pace effective 2018-01-01 was announced (also
        `test_every_unannounced_row_is_refused`).
        """
        from repo_model.asof import StaleReadError

        rows = announced_pace.load_announced_pace()
        checked = 0
        for newer in rows[1:]:
            instant = max(newer.announced_at, rows[0].announced_at) + timedelta(minutes=1)
            day = newer.effective + timedelta(days=1)
            for older in rows:
                if older.effective < newer.effective and older.announced_at <= instant:
                    with self.assertRaises(StaleReadError, msg=f"{older.effective} read on {day}"):
                        announced_pace.check_read(rows, instant, day, used=older)
                    checked += 1
        self.assertGreater(checked, 50)
        self.assertTrue(issubclass(StaleReadError, ValueError))

    def test_the_newest_announced_row_is_read(self):
        rows = announced_pace.load_announced_pace()
        for day in weekdays(date(2017, 9, 21), date(2026, 9, 30)):
            instant = datetime.combine(day - timedelta(days=1), DECISION)
            admissible = [r for r in rows if r.announced_at <= instant and r.effective <= day]
            expected = max(admissible, key=lambda r: (r.effective, r.announced_at)) if admissible else None
            self.assertEqual(announced_pace.read(rows, instant, day), expected, day)

    def test_a_later_announcement_never_moves_an_earlier_reading(self):
        """What is read at an instant does not change when rows announced after it are shifted to take effect that day."""
        rows = announced_pace.load_announced_pace()
        dates = weekdays(date(2017, 9, 21), date(2026, 9, 30))
        baseline = announced_pace.pace_values(dates, decision_time=DECISION, rows=rows)
        for index in range(1, len(dates)):
            instant = datetime.combine(dates[index - 1], DECISION)
            late = [r for r in rows if r.announced_at > instant]
            if not late:
                continue
            shifted = [r for r in rows if r.announced_at <= instant] + [r._replace(effective=dates[index]) for r in late]
            self.assertEqual(announced_pace.pace_values(dates[index - 1:index + 1], decision_time=DECISION, rows=shifted)[1],
                             baseline[index], dates[index])

    def test_the_values_are_not_wired_into_the_panel(self):
        from repo_model.data import DailyObservation

        out = scheduled.with_scheduled([DailyObservation(date(2022, 1, 3), {}), DailyObservation(date(2022, 1, 4), {})],
                                       decision_time=DECISION)
        for column in out[1].values:
            self.assertNotIn("pace", column)


class PublishedTests(unittest.TestCase):
    def test_the_series_is_published_and_rebuilds(self):
        with tempfile.TemporaryDirectory() as tmp:
            tracked = snapshots.load_manifest("announced_pace")
            rebuilt = snapshots.build("announced_pace", pathlib.Path(tmp), repo_commit=tracked["repo_commit"])
            self.assertEqual(rebuilt, tracked)
        rows = snapshots.read("announced_pace", sha256=tracked["sha256"])
        self.assertEqual(len(rows), tracked["rows"])
        self.assertEqual(set(tracked["source_inputs"]), {"announced_purchases.csv", "runoff_caps.csv"})

    def test_the_input_is_declared_and_passes_the_parents_validators(self):
        registry = declaration.registry()
        block = registry["fomc_announced_pace"]
        self.assertEqual(declaration.validate(), [])
        self.assertEqual(block["scheduled_availability"]["available_time"], "16:00")
        for feature in ("announced_pace_signed_bn", "announced_pace_treasury_purchases_bn",
                        "announced_pace_mbs_purchases_bn"):
            self.assertIn(feature, declaration.FIELDS)
            self.assertIn(feature, block["fields"])
        self.assertTrue(json.loads((ROOT / "declarations" / "fomc_announced_pace.json").read_text()))


if __name__ == "__main__":
    unittest.main()
