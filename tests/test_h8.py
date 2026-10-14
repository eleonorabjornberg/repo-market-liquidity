"""The H.8 bank-group first prints (#26; `docs/decisions/data-meaning.md` answers 6 and 17).

Cash assets and total assets of large domestic, small domestic and foreign-related banks, each week as first printed.
`tests/fixtures/h8_pages/` holds two archived release pages, one in the page-per-heading layout of 2018 (a table runs
over two pages, the lines on either) and one in the table-per-heading layout of the 2020s; the extract and the breaks
record are the tracked ones.
"""

import copy
import csv
import gzip
import json
import pathlib
import tempfile
import unittest
from datetime import date, time

from repo_model.asof import StaleReadError
from repo_model.splits import LookAheadError

from repo_liquidity import declaration, h8

ROOT = pathlib.Path(__file__).resolve().parents[1]
PAGES = ROOT / "tests" / "fixtures" / "h8_pages"
EXTRACT_DIR = ROOT / "tests" / "fixtures" / "snapshots" / "h8_groups"
EXTRACT = EXTRACT_DIR / h8.EXTRACT_NAME


def page(name):
    return gzip.decompress((PAGES / name).read_bytes())


def values(release, week):
    return {field: line.weeks[week] for field, line in release.lines.items()}


class ParseTests(unittest.TestCase):
    def test_the_2018_layout_reads_the_lines_from_both_pages_of_each_table(self):
        release = h8.parse_group_lines(page("20180105.htm.gz"), date(2018, 1, 5))
        self.assertEqual(sorted(release.lines[h8.FIELDS[0]].weeks),
                         [date(2017, 12, 6), date(2017, 12, 13), date(2017, 12, 20), date(2017, 12, 27)])
        self.assertEqual(values(release, date(2017, 12, 27)), {
            "h8_large_domestic_cash_assets": 1145.2, "h8_large_domestic_total_assets": 9507.5,
            "h8_small_domestic_cash_assets": 339.9, "h8_small_domestic_total_assets": 4936.1,
            "h8_foreign_related_cash_assets": 867.5, "h8_foreign_related_total_assets": 2307.2})
        self.assertIsNone(release.stated_time)

    def test_the_2020s_layout_reads_the_four_weeks_and_not_the_monthly_columns(self):
        release = h8.parse_group_lines(page("20250103.htm.gz"), date(2025, 1, 3))
        self.assertEqual(sorted(release.lines[h8.FIELDS[0]].weeks),
                         [date(2024, 12, 4), date(2024, 12, 11), date(2024, 12, 18), date(2024, 12, 25)])
        self.assertEqual(values(release, date(2024, 12, 25)), {
            "h8_large_domestic_cash_assets": 1578.2, "h8_large_domestic_total_assets": 13906.3,
            "h8_small_domestic_cash_assets": 526.1, "h8_small_domestic_total_assets": 6797.4,
            "h8_foreign_related_cash_assets": 1105.5, "h8_foreign_related_total_assets": 3047.7})
        self.assertIsNone(release.stated_time)
        self.assertEqual(release.stated_date, date(2025, 1, 3))

    def test_a_stated_release_time_is_read(self):
        stated = b"<p>For release at 4:15 p.m. Eastern Time</p>" + page("20250103.htm.gz")
        self.assertEqual(h8.parse_group_lines(stated, date(2025, 1, 3)).stated_time, time(16, 15))

    def test_the_seasonally_adjusted_twin_is_not_read(self):
        # Table 6 (large, seasonally adjusted) prints 1,519.0 for the same week as table 7's 1,578.2.
        release = h8.parse_group_lines(page("20250103.htm.gz"), date(2025, 1, 3))
        self.assertNotEqual(release.lines["h8_large_domestic_cash_assets"].weeks[date(2024, 12, 25)], 1519.0)

    def test_a_page_without_a_group_table_is_refused(self):
        text = page("20250103.htm.gz").replace(b"Assets and Liabilities of Foreign-Related Institutions in the United States",
                                                b"Assets and Liabilities of Somewhere Else")
        with self.assertRaises(ValueError):
            h8.parse_group_lines(text, date(2025, 1, 3))

    def test_a_page_with_a_line_twice_is_refused(self):
        text = page("20250103.htm.gz")
        marker = b"Not seasonally adjusted, billions of dollars"
        # Make table 5 (all domestically chartered, NSA) look like a second large-bank table.
        text = text.replace(b"Assets and Liabilities of Domestically Chartered Commercial Banks in the United States",
                            b"Assets and Liabilities of Large Domestically Chartered Commercial Banks in the United States")
        self.assertIn(marker, text)
        with self.assertRaises(ValueError):
            h8.parse_group_lines(text, date(2025, 1, 3))

    def test_a_line_without_a_number_is_refused(self):
        text = page("20250103.htm.gz").replace(b"1,578.2", b"n.a.")
        with self.assertRaises(ValueError):
            h8.parse_group_lines(text, date(2025, 1, 3))

    def test_a_page_that_is_not_a_release_is_refused(self):
        with self.assertRaises(ValueError):
            h8.parse_group_lines(b"<html>no tables</html>", date(2025, 1, 3))


class ReleaseTimeTests(unittest.TestCase):
    def test_the_declared_time_and_an_unstated_one_pass(self):
        h8.check_stated_release_time(date(2025, 1, 3), time(16, 15))
        h8.check_stated_release_time(date(2018, 1, 5), None)

    def test_a_page_that_states_another_time_is_refused(self):
        """Availability guard: a later stated time would make the declaration early, which is the direction that leaks.

        Recorded mutation (13 October 2026): in `src/repo_liquidity/h8.py`, `check_stated_release_time`'s condition
        `stated_time != RELEASE_TIME` changed to `stated_time < RELEASE_TIME` (only an earlier time refused). This test
        then fails with AssertionError: ValueError not raised.
        """
        with self.assertRaises(ValueError):
            h8.check_stated_release_time(date(2025, 1, 3), time(17, 0))


class ExtractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.prints = h8.load_extract(EXTRACT)
        cls.releases = json.loads((EXTRACT_DIR / h8.RELEASES_NAME).read_text(encoding="utf-8"))

    def test_the_extract_is_consecutive_weeks_from_the_first_release_to_the_last_before_the_blind_tier(self):
        self.assertEqual(self.prints[0].week_ending, date(2017, 12, 27))
        self.assertEqual(self.prints[0].release_date, date(2018, 1, 5))
        self.assertLessEqual(self.prints[-1].release_date, h8.LAST_RELEASE)
        self.assertEqual(self.prints[-1].week_ending, date(2026, 8, 19))
        self.assertEqual(self.prints[-1].release_date, date(2026, 8, 28))

    def test_the_tracked_page_digests_name_the_releases_the_record_lists(self):
        listed = {record["release_date"]: record["sha256"] for record in self.releases["releases"]}
        for item in self.prints:
            self.assertEqual(listed[item.release_date.isoformat()], item.release_sha256, item.week_ending)

    def test_every_week_is_read_from_the_earliest_release_that_carries_it(self):
        """Data guard: a week read from a later release is a revised value, not the first print.

        Recorded mutation (13 October 2026): in `tests/fixtures/snapshots/h8_groups/h8_group_first_print.csv`, the
        release date of the week ending 2018-01-03 changed from 2018-01-12 to 2018-01-19 (with the manifest digest
        refreshed). This test then fails with ValueError: the week ending 2018-01-03 is read from the release of
        2018-01-19, but the earliest release that carries it is 2018-01-12.
        """
        h8.check_first_prints(self.prints, self.releases)

    def test_a_week_read_from_a_later_release_is_refused(self):
        moved = list(self.prints)
        item = self.prints[1]
        moved[1] = h8.FirstPrint(item.week_ending, date(2018, 1, 19), item.values, item.release_sha256)
        with self.assertRaises(ValueError):
            h8.check_first_prints(moved, self.releases)

    def test_the_three_groups_sum_to_the_parents_all_banks_first_print(self):
        """Cross-check: each week's three total-assets lines sum to the parent's `frb_h8` first print, to rounding.

        The parent's extract (`tests/fixtures/snapshots/h8_inputs/frb_h8/h8_total_assets_first_print.csv` at the pin)
        is cut from the same pages by a different parser, so agreement on every week, from the same release, says that
        no table, line or column was misread. Over the 452 weeks the largest difference is 0.1 (the groups' rounding).

        Recorded mutation (13 October 2026): in `tests/fixtures/snapshots/h8_groups/h8_group_first_print.csv`, the small
        domestic total assets of the week ending 2025-12-24 changed from 6886.8 to 6887.8 (manifest digest refreshed).
        This test then fails with AssertionError: 1.0 not less than or equal to 0.100000001 : the week ending 2025-12-24
        differs from the parent's by 1.0.
        """
        from repo_liquidity import parent_root

        path = parent_root() / "tests/fixtures/snapshots/h8_inputs/frb_h8/h8_total_assets_first_print.csv"
        with path.open(encoding="utf-8", newline="") as handle:
            parent = {row["week_ending"]: row for row in csv.DictReader(handle)}
        for item in self.prints:
            row = parent[item.week_ending.isoformat()]
            total = sum(item.values[field] for field in h8.FIELDS if field.endswith("total_assets"))
            self.assertLessEqual(abs(total - float(row["total_assets"])), 0.1 + 1e-9,
                                 f"the week ending {item.week_ending} differs from the parent's by "
                                 f"{total - float(row['total_assets']):.1f}")
            self.assertEqual(row["release_date"], item.release_date.isoformat(), item.week_ending)

    def test_an_edited_extract_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = pathlib.Path(tmp) / EXTRACT.name
            out.write_bytes(EXTRACT.read_bytes().replace(b"1145.2", b"1145.3"))
            out.with_name(out.name + ".manifest.json").write_bytes(
                (EXTRACT_DIR / (EXTRACT.name + ".manifest.json")).read_bytes())
            with self.assertRaises(ValueError):
                h8.load_extract(out)

    def test_an_extract_that_skips_a_week_is_refused(self):
        import hashlib

        lines = EXTRACT.read_bytes().decode("utf-8").splitlines(keepends=True)
        del lines[5]
        data = "".join(lines).encode("utf-8")
        with tempfile.TemporaryDirectory() as tmp:
            out = pathlib.Path(tmp) / EXTRACT.name
            out.write_bytes(data)
            out.with_name(out.name + ".manifest.json").write_text(json.dumps({"sha256": hashlib.sha256(data).hexdigest()}))
            with self.assertRaises(ValueError):
                h8.load_extract(out)

    def test_the_writer_and_the_loader_round_trip(self):
        again = h8.write_extract(self.prints)
        self.assertEqual(again, EXTRACT.read_bytes())

    def test_the_observations_are_public_at_the_release_not_before(self):
        rows = h8.observations(self.prints, "h8_small_domestic_cash_assets", source_sha="x")
        self.assertEqual(len(rows), len(self.prints))
        self.assertEqual(rows[0].ref_date, date(2017, 12, 27))
        self.assertEqual((rows[0].available_at.date(), rows[0].available_at.time().isoformat()), (date(2018, 1, 5), "16:15:00"))
        self.assertEqual(rows[0].value, 339.9)
        with self.assertRaises(ValueError):
            h8.observations(self.prints, "h8_large_domestic_reserves", source_sha="x")


class DeclarationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.prints = h8.load_extract(EXTRACT)
        cls.entry = declaration.registry()[h8.SOURCE_ID]

    def test_the_overlay_passes_the_parents_validators(self):
        self.assertEqual(declaration.validate(), [])

    def test_the_declared_fields_are_the_six_group_lines(self):
        self.assertEqual(tuple(self.entry["fields"]), h8.FIELDS)
        self.assertEqual(set(self.entry["field_frequencies"].values()), {"weekly"})
        for field in h8.FIELDS:
            self.assertEqual(declaration.FIELDS[field], ((h8.SOURCE_ID, field),))

    def test_no_release_is_published_after_its_declared_availability(self):
        """Leakage guard: the declared lag covers every release in the extract.

        Recorded mutation (13 October 2026): in `declarations/h8_groups.json`, `frb_h8_groups.release_lag.days`
        changed from 12 to 8. This test then fails with LookAheadError: the week ending 2017-12-27 was released
        2018-01-05 16:15:00, after its declared availability 2018-01-04 16:15:00.
        """
        h8.check_declared_lag(self.entry, self.prints)

    def test_a_release_later_than_declared_is_refused(self):
        entry = copy.deepcopy(self.entry)
        entry["release_lag"]["days"] = 8
        with self.assertRaises(LookAheadError):
            h8.check_declared_lag(entry, self.prints)

    def test_a_lag_longer_than_the_slowest_release_is_stale(self):
        """Staleness guard: the declared lag is the measured maximum and not above it.

        Recorded mutation (13 October 2026): in `declarations/h8_groups.json`, `frb_h8_groups.release_lag.days`
        changed from 12 to 20. `test_no_release_is_published_after_its_declared_availability` then fails with
        StaleReadError: the declared lag of 20 days is longer than the 12 days the slowest release in the extract took.
        """
        entry = copy.deepcopy(self.entry)
        entry["release_lag"]["days"] = 20
        with self.assertRaises(StaleReadError):
            h8.check_declared_lag(entry, self.prints)

    def test_the_declaration_is_record_date_calendar_days(self):
        entry = copy.deepcopy(self.entry)
        entry["release_lag"]["unit"] = "business_days"
        with self.assertRaises(ValueError):
            h8.check_declared_lag(entry, self.prints)

    def test_the_worst_case_lag_is_the_declared_one(self):
        self.assertEqual(h8.worst_case_lag_days(self.prints), self.entry["release_lag"]["days"])


class BreaksTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.record = json.loads(h8.BREAKS_PATH.read_text(encoding="utf-8"))
        cls.page = gzip.decompress(h8.NOTES_PAGE.read_bytes())

    def test_the_record_is_the_saved_pages_notes(self):
        import hashlib

        self.assertEqual(hashlib.sha256(self.page).hexdigest(), self.record["source"]["sha256"])
        self.assertEqual(h8.parse_notes(self.page), self.record["events"])

    def test_the_events_are_dated_wednesdays_inside_the_extract(self):
        dates = [date.fromisoformat(event["as_of"]) for event in self.record["events"]]
        self.assertEqual(dates, sorted(dates))
        self.assertEqual(len(dates), len(set(dates)))
        self.assertTrue(all(day.weekday() == 2 and h8.FIRST_WEEK <= day <= h8.LAST_RELEASE for day in dates))
        self.assertEqual(dates[0], date(2018, 2, 7))

    def test_the_march_2023_divestitures_are_declared_as_stated(self):
        by_date = {event["as_of"]: event for event in self.record["events"]}
        for day in ("2023-03-22", "2023-03-29"):
            self.assertEqual(by_date[day]["kinds"], ["nonbank_divestiture"])
            self.assertEqual(by_date[day]["first_amount_billion"], 87.0)
            self.assertEqual(by_date[day]["scope"], "domestic")

    def test_what_the_notes_do_not_carry_is_listed(self):
        text = " ".join(self.record["not_in_the_notes"])
        self.assertIn("large-bank panel", text)
        self.assertIn("First Republic", text)

    def test_a_note_of_an_unknown_kind_is_refused(self):
        text = self.page.replace(b"Because of the conversion of a thrift institution to a commercial bank, the assets",
                                 b"Because of something else, the assets", 1)
        with self.assertRaises(ValueError):
            h8.parse_notes(text)

    def test_a_notes_page_whose_index_and_blocks_disagree_is_refused(self):
        text = self.page.replace(b'<a name="notes_20180207">', b'<a name="notes_20180208">', 1)
        with self.assertRaises(ValueError):
            h8.parse_notes(text)

    def test_the_notes_after_the_blind_tier_starts_are_not_read(self):
        """Availability guard: a note as of a day after the panel's last (3 September 2026) is not recorded.

        The saved page carries a note as of 2026-09-30, published after the lockbox's blind tier began. Recorded
        mutation (13 October 2026): in `src/repo_liquidity/h8.py`, `LAST_RELEASE` changed from `date(2026, 9, 3)` to
        `date(2026, 12, 31)`. This test then fails with AssertionError: '2026-09-30' unexpectedly found in the parsed
        events' dates.
        """
        self.assertIn(b"September 30, 2026", self.page)
        self.assertNotIn("2026-09-30", [event["as_of"] for event in h8.parse_notes(self.page)])
        self.assertNotIn("2026-09-30", [event["as_of"] for event in self.record["events"]])


if __name__ == "__main__":
    unittest.main()
