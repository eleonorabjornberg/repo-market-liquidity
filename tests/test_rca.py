"""The quarterly anchor of the group reserves: RC-A "balances due from Federal Reserve Banks" (#43, H7m groundwork G4).

The parser is tested on small synthetic bulk zips; the tracked extract, its declaration and the guards are tested on the
real extract cut by `scripts/extract_rca.py` from the 34 stored quarters. No test scores anything.
"""

import csv
import hashlib
import io
import json
import pathlib
import shutil
import tempfile
import unittest
import zipfile
from datetime import date, datetime, timedelta

from repo_model.asof import StaleReadError
from repo_model.splits import LookAheadError

from repo_liquidity import declaration, development, rca

ROOT = pathlib.Path(__file__).resolve().parents[1]
DIRECTORY = ROOT / "tests" / "fixtures" / "snapshots" / "rca_anchor"
EXTRACT = DIRECTORY / rca.EXTRACT_NAME
NEW_YORK = rca.NEW_YORK
QUARTER = date(2021, 3, 31)


def bulk_zip(filers, as_of="2026-01-15T04:30:03"):
    """A bulk zip with the three files the parser reads. `filers`: IDRSSD -> (update or None, assets, frb balance).

    `assets` and `frb balance` are strings in thousands of dollars; an empty string is a blank item. A filer is in
    Schedule RC and RC-A whatever it carries, and in the POR file when it has an update time.
    """
    por = ["IDRSSD\tName\tLast Date/Time Submission Updated On", "ID\tname\tlast"]
    rc = ["IDRSSD\tRCON2170\tRCFD2170", "ID\ta\ta"]
    rca_lines = ["IDRSSD\tRCON0090\tRCFD0090", "ID\tb\tb"]
    for idrssd, (update, assets, frb) in filers.items():
        if update is not None:
            por.append(f"{idrssd}\tbank\t{update}")
        rc.append(f"{idrssd}\t{assets}\t")
        rca_lines.append(f"{idrssd}\t{frb}\t")
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("Readme.txt", f"data from Call Reports as of {as_of}\n")
        archive.writestr("FFIEC CDR Call Bulk POR 03312021.txt", "\n".join(por) + "\n")
        archive.writestr("FFIEC CDR Call Schedule RC 03312021.txt", "\n".join(rc) + "\n")
        archive.writestr("FFIEC CDR Call Schedule RCA 03312021.txt", "\n".join(rca_lines) + "\n")
    return buffer.getvalue()


def filers(updates, top=3):
    """Five filers; the `top` largest by assets are the large group."""
    sizes = {1: 500, 2: 400, 3: 300, 4: 200, 5: 100}
    balances = {1: 50, 2: 40, 3: 30, 4: 20, 5: 10}
    return {i: (updates.get(i, "2021-05-05T12:00:00"), str(sizes[i]), str(balances[i])) for i in sizes}


class ParseTests(unittest.TestCase):
    def parse(self, banks, top_n=3):
        return rca.parse_quarter(bulk_zip(banks), QUARTER, top_n=top_n)

    def test_the_largest_filers_by_total_assets_are_the_large_group_and_the_rest_the_small(self):
        rows, holes, as_of, _ = self.parse(filers({}))
        self.assertEqual(as_of, "2026-01-15T04:30:03")
        self.assertEqual([(r.group, r.filers, r.balances_kusd) for r in rows],
                         [("large_domestic", 3, 120), ("small_domestic", 2, 30)])
        self.assertEqual(holes, [])

    def test_a_group_is_available_only_after_its_slowest_member_was_last_updated(self):
        rows, _, _, _ = self.parse(filers({2: "2021-09-01T08:00:00", 5: "2021-04-20T08:00:00"}))
        by_group = {r.group: r for r in rows}
        self.assertEqual(by_group["large_domestic"].latest_update, datetime(2021, 9, 1, 8))
        self.assertEqual(by_group["small_domestic"].latest_update, datetime(2021, 5, 5, 12))
        self.assertEqual(by_group["large_domestic"].available_from, datetime(2021, 9, 2, tzinfo=NEW_YORK))

    def test_a_blank_item_among_the_largest_is_a_hole_and_not_a_zero(self):
        banks = filers({})
        banks[3] = ("2021-05-05T12:00:00", "300", "")
        rows, holes, _, _ = self.parse(banks)
        self.assertEqual([(r.group, r.filers, r.balances_kusd) for r in rows],
                         [("large_domestic", 2, 90), ("small_domestic", 2, 30)])
        self.assertEqual([(h["reason"], h["idrssd"]) for h in holes], [("large_member_item_blank", 3)])
        self.assertTrue(all(h["row_kept"] for h in holes))

    def test_a_filer_that_is_blank_outside_the_largest_is_not_in_the_small_group_and_is_not_listed_as_a_hole(self):
        banks = filers({})
        banks[5] = ("2021-05-05T12:00:00", "100", "")
        rows, holes, _, _ = self.parse(banks)
        self.assertEqual([(r.group, r.filers, r.balances_kusd) for r in rows],
                         [("large_domestic", 3, 120), ("small_domestic", 1, 20)])
        self.assertEqual(holes, [])

    def test_a_carrying_filer_with_no_update_time_is_refused(self):
        banks = filers({})
        banks[4] = (None, "200", "20")
        with self.assertRaises(ValueError):
            self.parse(banks)

    def test_a_file_that_is_not_a_zip_is_refused(self):
        with self.assertRaises(ValueError):
            rca.parse_quarter(b"<html>technical difficulties</html>", QUARTER)

    def test_the_lag_profile_is_the_share_of_the_balance_public_by_each_lag(self):
        _, _, _, profile = self.parse(filers({1: "2021-12-01T08:00:00"}))
        small = profile["small_domestic"]
        large = profile["large_domestic"]
        self.assertEqual(small["45"], 1.0)
        self.assertEqual(large["45"], 0.5833)  # filers 2 and 3 (40 + 30 of 120) were public by 45 days; filer 1 was not
        self.assertEqual(large["180"], 0.5833)
        self.assertEqual(large["365"], 1.0)

    def test_a_lag_beyond_the_development_end_is_not_profiled(self):
        quarter = development.development_end() - timedelta(days=100)
        payload = bulk_zip(filers({}))
        _, _, _, profile = rca.parse_quarter(payload, quarter, top_n=3)
        self.assertIsNotNone(profile["large_domestic"]["45"])
        self.assertIsNone(profile["large_domestic"]["180"])


class WithholdTests(unittest.TestCase):
    def row(self, update):
        return rca.Row(date(2025, 12, 31), "large_domestic", 25, 1000, update, "0" * 64)

    def test_a_group_with_a_member_last_updated_on_a_locked_day_is_withheld_and_listed(self):
        """Leakage guard: nothing past the parent's development end is read.

        Recorded mutation (14 October 2026): in `repo_liquidity.rca.withhold_locked`, the test
        `development.is_locked(row.latest_update.date())` replaced by `False`. This test then fails: the group updated
        on the first locked day is kept and `holes` is empty (`AssertionError: Lists differ`).
        """
        end = development.development_end()
        inside = self.row(datetime.combine(end, datetime.min.time()) + timedelta(hours=9))
        outside = self.row(datetime.combine(end + timedelta(days=1), datetime.min.time()) + timedelta(hours=9))
        kept, holes = rca.withhold_locked([inside, outside])
        self.assertEqual(kept, [inside])
        self.assertEqual([h["reason"] for h in holes], ["updated_after_development_end"])


class ExtractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows = rca.load_extract(EXTRACT)
        cls.coverage = json.loads((DIRECTORY / rca.COVERAGE_NAME).read_text(encoding="utf-8"))
        cls.sources = json.loads((DIRECTORY / rca.SOURCES_NAME).read_text(encoding="utf-8"))

    def test_every_group_quarter_is_a_row_or_a_listed_withholding(self):
        quarters = len(self.coverage["quarters"])
        withheld = {(h["quarter_end"], h["group"]) for h in self.coverage["holes"] if not h["row_kept"]}
        kept = {(r.quarter_end.isoformat(), r.group) for r in self.rows}
        self.assertEqual(quarters, 34)
        self.assertEqual(len(kept) + len(withheld), quarters * len(rca.GROUPS))
        self.assertFalse(kept & withheld)

    def test_the_quarters_run_from_2018_03_31_to_2026_06_30(self):
        self.assertEqual(self.coverage["quarters"][0], "2018-03-31")
        self.assertEqual(self.coverage["quarters"][-1], "2026-06-30")

    def test_every_row_is_labelled_latest_filed_and_available_only_after_its_slowest_member_updated(self):
        with EXTRACT.open(encoding="utf-8") as handle:
            stored = list(csv.DictReader(handle))
        self.assertEqual({row["vintage"] for row in stored}, {"latest_filed"})
        for row in self.rows:
            self.assertGreater(row.available_from, row.latest_update.replace(tzinfo=NEW_YORK))

    def test_the_large_group_is_the_twenty_five_largest_and_each_carries_the_item(self):
        large = [r for r in self.rows if r.group == "large_domestic"]
        self.assertTrue(large)
        self.assertTrue(all(r.filers <= rca.TOP_N for r in large))
        self.assertEqual(max(r.filers for r in large), rca.TOP_N)

    def test_no_row_is_read_from_a_day_the_lockbox_holds(self):
        self.assertTrue(all(not development.is_locked(r.latest_update.date()) for r in self.rows))

    def test_the_sources_are_the_34_stored_zips_by_digest(self):
        self.assertEqual(len(self.sources["zips"]), 34)
        listed = {item["sha256"] for item in self.sources["zips"]}
        self.assertEqual({r.source_zip_sha256 for r in self.rows} - listed, set())

    def test_the_lag_profile_is_recorded_for_every_quarter_and_group(self):
        profile = self.coverage["lag_profile"]
        self.assertEqual(sorted(profile), self.coverage["quarters"])
        for quarter in profile.values():
            self.assertEqual(sorted(quarter), sorted(rca.GROUPS))

    def test_no_aggregate_across_the_two_groups_is_published(self):
        with EXTRACT.open(encoding="utf-8") as handle:
            self.assertEqual(tuple(csv.DictReader(handle).fieldnames), rca.EXTRACT_COLUMNS)
        self.assertNotIn("total", " ".join(rca.EXTRACT_COLUMNS))


class LoadGuardTests(unittest.TestCase):
    def copy(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        for path in DIRECTORY.glob(rca.EXTRACT_NAME + "*"):
            shutil.copy(path, tmp.name)
        return pathlib.Path(tmp.name) / rca.EXTRACT_NAME

    def rewrite(self, path, edit):
        with path.open(encoding="utf-8", newline="") as handle:
            rows = list(csv.reader(handle))
        edit(rows)
        with path.open("w", encoding="utf-8", newline="") as handle:
            csv.writer(handle, lineterminator="\n").writerows(rows)

    def test_an_edited_extract_is_refused(self):
        path = self.copy()
        self.rewrite(path, lambda rows: rows[1].__setitem__(rows[0].index("balances_kusd"), "1"))
        with self.assertRaises(ValueError):
            rca.load_extract(path)

    def test_a_row_not_labelled_latest_filed_is_refused(self):
        path = self.copy()
        self.rewrite(path, lambda rows: rows[1].__setitem__(rows[0].index("vintage"), "first_print"))
        manifest = path.with_name(path.name + ".manifest.json")
        record = json.loads(manifest.read_text())
        record["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
        manifest.write_text(json.dumps(record))
        with self.assertRaises(ValueError):
            rca.load_extract(path)

    def test_a_row_last_updated_in_the_blind_tier_is_refused(self):
        """Leakage guard: the loader refuses an extract that holds a figure updated on a locked day.

        Recorded mutation (14 October 2026): in `repo_liquidity.rca.load_extract`, the `if development.is_locked(...)`
        branch that raises replaced by `if False:`. This test then fails: `AssertionError: LookAheadError not raised`.
        """
        path = self.copy()
        rows = rca.load_extract(path)
        late = datetime.combine(development.development_end() + timedelta(days=3), datetime.min.time()) + timedelta(hours=9)
        rows[0] = rca.Row(rows[0].quarter_end, rows[0].group, rows[0].filers, rows[0].balances_kusd, late,
                          rows[0].source_zip_sha256)
        path.write_bytes(rca.write_extract(rows))
        manifest = path.with_name(path.name + ".manifest.json")
        record = json.loads(manifest.read_text())
        record["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
        manifest.write_text(json.dumps(record))
        with self.assertRaises(LookAheadError):
            rca.load_extract(path)


class DeclarationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.entry = declaration.overlay()[rca.SOURCE_ID]
        cls.rows = rca.load_extract(EXTRACT)

    def test_the_overlay_passes_the_parents_validators(self):
        self.assertEqual(declaration.validate(), [])

    def test_the_declared_fields_are_the_two_anchor_fields(self):
        self.assertEqual(tuple(self.entry["fields"]), rca.FIELDS)
        self.assertEqual(set(self.entry["field_frequencies"].values()), {"quarterly"})
        for field in rca.FIELDS:
            self.assertEqual(declaration.FIELDS[field], ((rca.SOURCE_ID, field),))

    def test_the_declaration_says_the_figures_are_latest_filed_and_the_groups_approximate(self):
        self.assertIn("LATEST-FILED", self.entry["limitation"])
        self.assertIn("approximation", self.entry["limitation"])
        self.assertIn("not first prints", self.entry["limitation"])

    def test_no_figure_is_available_after_its_declared_availability(self):
        rca.check_declared_lag(self.entry, self.rows)

    def test_a_figure_later_than_declared_is_refused(self):
        """Leakage guard: a figure read earlier than its last update is refused.

        Recorded mutation (14 October 2026): in `repo_liquidity.rca.check_declared_lag`, the comparison
        `row.available_from > declared` replaced by `False`. This test then fails: no `LookAheadError` is raised.
        """
        shorter = json.loads(json.dumps(self.entry))
        shorter["release_lag"]["days"] = int(self.entry["release_lag"]["days"]) - 1
        with self.assertRaises(LookAheadError):
            rca.check_declared_lag(shorter, self.rows)

    def test_a_lag_longer_than_the_slowest_figure_is_stale(self):
        """Staleness guard: a declared lag above the measured worst case is refused.

        Recorded mutation (14 October 2026): in `repo_liquidity.rca.check_declared_lag`, the test
        `int(lag["days"]) > worst` replaced by `False`. This test then fails: no `StaleReadError` is raised.
        """
        longer = json.loads(json.dumps(self.entry))
        longer["release_lag"]["days"] = int(self.entry["release_lag"]["days"]) + 1
        with self.assertRaises(StaleReadError):
            rca.check_declared_lag(longer, self.rows)

    def test_the_declaration_is_record_date_calendar_days(self):
        lag = self.entry["release_lag"]
        self.assertEqual((lag["basis"], lag["unit"]), ("record_date", "calendar_days"))
        with self.assertRaises(ValueError):
            rca.check_declared_lag({"release_lag": {**lag, "basis": "business_days"}}, self.rows)

    def test_the_worst_case_lag_is_the_declared_one(self):
        self.assertEqual(int(self.entry["release_lag"]["days"]), rca.worst_case_lag_days(self.rows))


class ReadGuardTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows = rca.load_extract(EXTRACT)
        cls.first = min((r for r in cls.rows if r.group == "large_domestic"), key=lambda r: r.available_from)

    def at(self, moment):
        return moment

    def test_a_figure_is_read_from_the_instant_it_is_available(self):
        row = rca.read(self.rows, self.first.group, self.first.quarter_end, self.first.available_from)
        self.assertEqual(row, self.first)

    def test_a_read_before_the_latest_update_is_look_ahead(self):
        """Leakage guard: a group-quarter is not read before its slowest member was last updated.

        Recorded mutation (14 October 2026): in `repo_liquidity.rca.read`, the test `row.available_from > at` replaced
        by `False`. This test then fails: no `LookAheadError` is raised.
        """
        with self.assertRaises(LookAheadError):
            rca.read(self.rows, self.first.group, self.first.quarter_end, self.first.available_from - timedelta(seconds=1))

    def test_a_read_of_an_older_quarter_than_the_latest_public_is_stale(self):
        """Staleness guard: a read of a quarter when a later one is already public is refused.

        Recorded mutation (14 October 2026): in `repo_liquidity.rca.read`, the test `latest.quarter_end > quarter_end`
        replaced by `False`. This test then fails: no `StaleReadError` is raised.
        """
        large = sorted((r for r in self.rows if r.group == "large_domestic"), key=lambda r: r.quarter_end)
        older, newer = next((a, b) for a, b in zip(large, large[1:]) if b.available_from > a.available_from)
        with self.assertRaises(StaleReadError):
            rca.read(self.rows, older.group, older.quarter_end, newer.available_from)

    def test_the_latest_public_quarter_is_the_one_whose_slowest_member_has_updated(self):
        at = self.first.available_from
        latest = rca.latest_public(self.rows, self.first.group, at)
        self.assertEqual(latest.quarter_end, max(r.quarter_end for r in self.rows
                                                if r.group == self.first.group and r.available_from <= at))
        self.assertIsNone(rca.latest_public(self.rows, self.first.group, self.first.available_from - timedelta(days=1)))

    def test_a_decision_instant_without_a_time_zone_is_refused(self):
        with self.assertRaises(ValueError):
            rca.latest_public(self.rows, "large_domestic", datetime(2026, 1, 1))

    def test_a_group_quarter_not_in_the_extract_is_refused(self):
        with self.assertRaises(ValueError):
            rca.read(self.rows, "large_domestic", date(2001, 3, 31), self.first.available_from)

    def test_the_observations_are_public_from_the_update_not_before(self):
        for obs in rca.observations(self.rows, "rca_large_domestic_frb_balances", source_sha="0" * 64):
            self.assertEqual(obs.series_id, "rca_large_domestic_frb_balances")
            row = next(r for r in self.rows if r.group == "large_domestic" and r.quarter_end == obs.ref_date)
            self.assertEqual(obs.available_at, row.available_from)
            self.assertEqual(obs.value, row.balances_bn)

    def test_an_unknown_field_is_refused(self):
        with self.assertRaises(ValueError):
            rca.observations(self.rows, "rca_total", source_sha="0" * 64)


if __name__ == "__main__":
    unittest.main()
