"""The primary dealers' Treasury fails, as a tracked extract with its own snapshot (#209, H10's second declaration, step 2).

The extract is the two fails series of the parent's New York Fed Primary Dealer Statistics export at the pin, copied byte
for byte, less the weeks published on a day the parent's lockbox holds. The declaration is `declarations/nyfed_pd_fails.json`
(Thursday of the following week, 16:30); the panel reads the weeks at that instant and carries each across the next rows.
"""

import dataclasses
import hashlib
import json
import pathlib
import unittest
from datetime import date, datetime, timedelta

from repo_model.asof import declared_availability
from repo_model.splits import LookAheadError

from repo_liquidity import declaration, development, h10_drivers_2 as d2, parent_root, pd_fails

ROOT = pathlib.Path(__file__).resolve().parents[1]


def weekdays(first: date, count: int):
    out, day = [], first
    while len(out) < count:
        if day.weekday() < 5:
            out.append(day)
        day += timedelta(days=1)
    return out


class ExtractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.weeks = pd_fails.load_extract()

    def test_the_extract_is_the_parents_export_less_the_locked_weeks(self):
        """Byte for byte: cutting the parent's tracked export again gives the tracked extract and its manifest."""
        export = (parent_root() / pd_fails.PARENT_EXPORT).read_bytes()
        cut, withheld = pd_fails.cut_extract(export)
        self.assertEqual(cut, pd_fails.EXTRACT.read_bytes())
        manifest = json.loads(pd_fails.MANIFEST.read_text(encoding="utf-8"))
        self.assertEqual(manifest["extract_sha256"], hashlib.sha256(cut).hexdigest())
        self.assertEqual(manifest["export_sha256"], hashlib.sha256(export).hexdigest())
        self.assertEqual(manifest["withheld_weeks"], [day.isoformat() for day in withheld])
        self.assertTrue(withheld, "the parent's export holds weeks published after the development end")

    def test_every_week_is_a_wednesday_of_one_of_the_two_series_and_none_is_withheld_by_the_desk(self):
        self.assertTrue(self.weeks)
        for week in self.weeks:
            self.assertEqual(week.as_of.weekday(), 2, week)
            self.assertIn(week.field, pd_fails.FIELD_COLUMNS)
            self.assertIsInstance(week.value_musd, int)
        self.assertEqual({week.field for week in self.weeks}, set(pd_fails.FIELD_COLUMNS))
        self.assertEqual(len({(w.field, w.as_of) for w in self.weeks}), len(self.weeks))

    def test_no_week_is_published_on_a_day_the_lockbox_holds(self):
        """The tracked extract keeps no week whose publication the parent's lockbox holds. Recorded mutation (11 November
        2026): in `pd_fails.cut_extract`, `if development.is_locked(published_instant(as_of).date()):` changed to
        `if False and ...`. `test_the_extract_is_the_parents_export_less_the_locked_weeks` failed with AssertionError (the
        cut kept the week of 2026-09-02, published 2026-09-10, so it no longer equalled the tracked extract)."""
        for week in self.weeks:
            self.assertFalse(development.is_locked(pd_fails.published_instant(week.as_of).date()), week)
        self.assertEqual(max(week.as_of for week in self.weeks), date(2026, 8, 26))

    def test_the_loader_refuses_an_extract_that_is_not_its_manifests(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            path = pathlib.Path(tmp) / pd_fails.EXTRACT_NAME
            path.write_bytes(pd_fails.EXTRACT.read_bytes() + b'"2026-08-26","PDFTD-UST","1"\n')
            path.with_name(path.name + ".manifest.json").write_bytes(pd_fails.MANIFEST.read_bytes())
            with self.assertRaises(ValueError):
                pd_fails.load_extract(path)

    def test_the_loader_refuses_a_week_published_on_a_locked_day(self):
        """Recorded mutation (11 November 2026): in `pd_fails.load_extract`, `if development.is_locked(published.date()):`
        changed to `if False and ...`. This test failed with AssertionError (LookAheadError not raised)."""
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            path = pathlib.Path(tmp) / pd_fails.EXTRACT_NAME
            data = pd_fails.EXTRACT.read_bytes() + b'"2026-09-02","PDFTD-UST","6578"\n'
            path.write_bytes(data)
            manifest = json.loads(pd_fails.MANIFEST.read_text(encoding="utf-8"))
            manifest["extract_sha256"] = hashlib.sha256(data).hexdigest()
            path.with_name(path.name + ".manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
            with self.assertRaises(LookAheadError):
                pd_fails.load_extract(path)


class ScheduleTests(unittest.TestCase):
    def test_the_publication_instant_is_the_declarations(self):
        """The module's schedule and the second declaration's step 1 constants are one schedule."""
        self.assertEqual(pd_fails.PUBLISH_DAYS_AFTER_WEDNESDAY, d2.FAILS_PUBLISH_DAYS_AFTER_WEDNESDAY)
        self.assertEqual(pd_fails.PUBLISH_TIME, d2.FAILS_PUBLISH_TIME)
        for as_of in (date(2026, 8, 26), date(2025, 12, 31), date(2013, 4, 3)):
            self.assertEqual(pd_fails.published_instant(as_of).replace(tzinfo=None), d2.published_fails_instant(as_of))

    def test_a_week_is_public_on_the_thursday_of_the_next_week_at_16_30_new_york(self):
        instant = pd_fails.published_instant(date(2026, 8, 26))
        self.assertEqual((instant.date(), instant.hour, instant.minute), (date(2026, 9, 3), 16, 30))
        self.assertEqual(str(instant.tzinfo), "America/New_York")

    def test_a_day_that_is_not_a_wednesday_has_no_publication(self):
        with self.assertRaises(ValueError):
            pd_fails.published_instant(date(2026, 8, 27))

    def test_observations_are_in_billions_and_carry_the_publication_instant(self):
        weeks = pd_fails.load_extract()
        rows = pd_fails.observations(weeks, source_sha="x", fields=("PDFTD-UST",))
        self.assertEqual(len(rows), sum(1 for w in weeks if w.field == "PDFTD-UST"))
        by_date = {w.as_of: w.value_musd for w in weeks if w.field == "PDFTD-UST"}
        for row in rows:
            self.assertEqual(row.series_id, "PDFTD-UST")
            self.assertAlmostEqual(row.value, by_date[row.ref_date] / 1000.0)
            self.assertEqual(row.available_at, pd_fails.published_instant(row.ref_date))


class DeclaredLagGuardTests(unittest.TestCase):
    """The panel build asks that no week is read before it is public: a week declared available earlier than the schedule
    publishes it would be a look-ahead."""

    @classmethod
    def setUpClass(cls):
        cls.weeks = pd_fails.load_extract()
        cls.dates = weekdays(date(2013, 4, 1), 3600)
        cls.rows = pd_fails.observations(cls.weeks, source_sha="x")

    def test_the_real_declaration_passes(self):
        with declaration.phase3_declaration():
            pd_fails.check_declared_lag(declaration.registry(), self.dates, self.rows)

    def test_a_week_published_after_its_declared_availability_is_a_lookahead(self):
        """Recorded mutation (11 November 2026): in `pd_fails.check_declared_lag`, `if declared is None or public > declared:`
        changed to `if declared is None:`. This test and `test_a_declaration_that_is_earlier_than_the_schedule_is_refused`
        failed with AssertionError (LookAheadError not raised)."""
        late = [dataclasses.replace(row, available_at=row.available_at + timedelta(days=1)) for row in self.rows]
        with declaration.phase3_declaration():
            with self.assertRaises(LookAheadError):
                pd_fails.check_declared_lag(declaration.registry(), self.dates, late)

    def test_a_declaration_that_is_earlier_than_the_schedule_is_refused(self):
        registry = json.loads(json.dumps(declaration.registry()))
        registry[pd_fails.SOURCE_ID]["release_lag"]["days"] = 5
        with declaration.phase3_declaration():
            with self.assertRaises(LookAheadError):
                pd_fails.check_declared_lag(registry, self.dates, self.rows)

    def test_the_declared_availability_is_not_earlier_than_the_publication_for_any_week(self):
        registry = declaration.registry()
        positions = {day: i for i, day in enumerate(self.dates)}
        checked = 0
        for row in self.rows:
            if row.ref_date not in positions:
                continue
            declared = declared_availability(registry, pd_fails.SOURCE_ID, row.series_id, self.dates, positions[row.ref_date])
            self.assertGreaterEqual(declared, row.available_at.replace(tzinfo=None), row.ref_date)
            checked += 1
        self.assertGreater(checked, 600)


if __name__ == "__main__":
    unittest.main()
