"""Phase 3 panel version 6 (#209, H10's second declaration, step 2): version 5's columns, then the second declaration's inputs.

Version 6 is built at the same pin as version 5. It adds `sofr_p1`, `sofr_p99` and `sofr_p99_p1_bp`, the derived
`fed_repo_material_use` and `facility_material_use` (the facility event, `docs/decisions/h10-method-2.md` section 1) and
`pd_fails_deliver_ust` with its tracked extract. Version 5, its manifest and the registered method's inputs are not touched.
"""

import csv
import hashlib
import json
import pathlib
import tempfile
import unittest
from datetime import date, timedelta
from unittest import mock

from repo_liquidity import PARENT_COMMIT, declaration, development, h10_apply, h10_drivers_2 as d2, indicators, panel, panel_v6, pd_fails

ROOT = pathlib.Path(__file__).resolve().parents[1]
PANEL_V5_SHA256 = "63fe5f7fd5ccae40e30aad729fab8f8f417a1323b717635a95aae727fb8143c1"
ADDED = ("sofr_p1", "sofr_p99", "pd_fails_deliver_ust", "sofr_p99_p1_bp", "fed_repo_material_use", "facility_material_use")


class FedRepoMaterialUseTests(unittest.TestCase):
    """`fed_repo_material_use` on each panel day, from the parent's repo operation results (`accepted`, USD bn per
    operation date, overnight and term alike): data-meaning row 14."""

    def test_before_the_first_operation_no_repo_was_offered_so_there_is_no_event(self):
        self.assertEqual(panel_v6.fed_repo_material_use(date(2019, 9, 16), {}), 0.0)
        self.assertEqual(panel_v6.fed_repo_material_use(date(2018, 4, 3), {date(2018, 4, 3): 5.0}), 0.0)

    def test_an_operation_date_of_one_billion_or_more_is_an_event_and_the_edge_counts(self):
        day = date(2020, 3, 12)
        self.assertEqual(panel_v6.fed_repo_material_use(day, {day: 1.0}), 1.0)
        self.assertEqual(panel_v6.fed_repo_material_use(day, {day: 0.99}), 0.0)
        self.assertEqual(panel_v6.fed_repo_material_use(day, {day: 150.0}), 1.0)

    def test_in_the_years_the_desk_operated_every_day_a_date_without_a_row_is_missing_not_zero(self):
        self.assertIsNone(panel_v6.fed_repo_material_use(date(2020, 3, 12), {}))

    def test_from_the_standing_facility_a_date_without_an_operation_is_zero(self):
        self.assertEqual(panel_v6.fed_repo_material_use(date(2021, 7, 29), {}), 0.0)
        self.assertEqual(panel_v6.fed_repo_material_use(date(2024, 1, 2), {}), 0.0)
        self.assertEqual(panel_v6.fed_repo_material_use(date(2025, 12, 31), {date(2025, 12, 31): 74.6}), 1.0)


class FacilityRowTests(unittest.TestCase):
    def test_before_the_standing_facility_its_take_up_is_a_structural_zero_in_the_event(self):
        """The panel carries no `srf_take_up` before 2021-07-29 (the facility did not exist); the event reads that as no
        standing-facility use, so that the term repo operations alone decide a day of 2019-21."""
        row = {"srf_take_up": None, "fed_repo_material_use": 0.0}
        self.assertEqual(panel_v6.facility_for_row(date(2020, 3, 12), row), 0.0)
        self.assertEqual(panel_v6.facility_for_row(date(2020, 3, 12), {**row, "fed_repo_material_use": 1.0}), 1.0)

    def test_after_inception_a_missing_standing_facility_reading_is_not_read_as_zero(self):
        self.assertIsNone(panel_v6.facility_for_row(date(2022, 1, 5), {"srf_take_up": None, "fed_repo_material_use": 0.0}))
        self.assertEqual(panel_v6.facility_for_row(date(2022, 1, 5), {"srf_take_up": 1.2, "fed_repo_material_use": 0.0}), 1.0)
        self.assertEqual(panel_v6.facility_for_row(date(2022, 1, 5), {"srf_take_up": 0.9, "fed_repo_material_use": 0.0}), 0.0)

    def test_the_event_is_the_second_declarations(self):
        for srf, fed in ((0.0, 0.0), (1.0, 0.0), (0.0, 1.0), (1.0, 1.0), (0.5, None), (None, 1.0)):
            self.assertEqual(panel_v6.facility_for_row(date(2023, 6, 1), {"srf_take_up": srf, "fed_repo_material_use": fed}),
                             d2.facility_event(srf, fed))


class PanelV6Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        base = pathlib.Path(cls.tmp.name)
        cls.v5_path, cls.v6_path = base / "v5.csv", base / "v6.csv"
        cls.v5 = panel.build(cls.v5_path, version=5)
        cls.v6 = panel.build(cls.v6_path, version=6)
        cls.tracked = panel.load_manifest(6)
        with cls.v5_path.open(encoding="utf-8") as handle:
            cls.rows5 = list(csv.DictReader(handle))
        with cls.v6_path.open(encoding="utf-8") as handle:
            cls.rows6 = list(csv.DictReader(handle))

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_version_6_rebuilds_to_its_manifest_at_the_pin(self):
        self.assertEqual(hashlib.sha256(self.v6_path.read_bytes()).hexdigest(), self.tracked["sha256"])
        self.assertEqual(self.v6, self.tracked)
        self.assertEqual((self.tracked["version"], self.tracked["parent_commit"]), (6, PARENT_COMMIT))
        self.assertEqual(self.tracked["decision_time"], "18:00:00")
        self.assertEqual(self.tracked["refusals"], {})

    def test_version_5_is_not_touched(self):
        self.assertEqual(self.v5["sha256"], PANEL_V5_SHA256)
        self.assertEqual(panel.load_manifest(5)["sha256"], PANEL_V5_SHA256)
        self.assertEqual(self.v5, panel.load_manifest(5))
        self.assertEqual(self.tracked["v5_sha256"], PANEL_V5_SHA256)
        self.assertEqual(panel.CURRENT_VERSION, 5)
        self.assertEqual(h10_apply.PANEL_VERSION, 5)
        self.assertNotIn(6, panel.RECORD_VERSIONS)

    def test_the_columns_are_version_5s_then_the_six_added(self):
        v5_columns = panel.load_manifest(5)["columns"]
        self.assertEqual(self.tracked["columns"], v5_columns + list(ADDED))
        self.assertEqual(list(self.rows6[0]), ["date"] + self.tracked["columns"])
        self.assertEqual(self.tracked["added_columns"], list(ADDED))
        self.assertEqual(self.tracked["phase3_columns"], panel.load_manifest(5)["phase3_columns"] + list(ADDED))

    def test_every_version_5_cell_is_unchanged_and_no_date_is_added(self):
        self.assertEqual([r["date"] for r in self.rows6], [r["date"] for r in self.rows5])
        for old, new in zip(self.rows5, self.rows6):
            for column, value in old.items():
                self.assertEqual(new[column], value, (old["date"], column))

    def test_no_locked_day_is_in_the_panel(self):
        self.assertEqual(self.tracked["end_date"], development.development_end().isoformat())
        self.assertFalse(any(development.is_locked(date.fromisoformat(r["date"])) for r in self.rows6))

    def test_sofr_p99_p1_is_computed_on_the_row(self):
        seen = 0
        for row in self.rows6:
            p1, p99 = row["sofr_p1"], row["sofr_p99"]
            if p1 == "" or p99 == "":
                self.assertEqual(row["sofr_p99_p1_bp"], "", row["date"])
                continue
            self.assertEqual(float(row["sofr_p99_p1_bp"]), indicators._bp(float(p99), float(p1)), row["date"])
            seen += 1
        self.assertGreater(seen, 2000)

    def test_the_sofr_percentiles_are_missing_on_exactly_two_days_of_the_source(self):
        """The parent's SOFR snapshots print no 1st and 99th percentile on 2019-05-31 and 2021-08-05. A window with either day
        has no change in the second declaration's fit (a missing day is never filled)."""
        for column in ("sofr_p1", "sofr_p99", "sofr_p99_p1_bp"):
            self.assertEqual(self.tracked["coverage"][column]["missing_rows"], 2, column)
        self.assertEqual([r["date"] for r in self.rows6 if r["sofr_p1"] == ""], ["2019-05-31", "2021-08-05"])

    def test_the_facility_event_has_the_row_14_counts(self):
        """Data-meaning row 14's note: 190 term repo events from 2019-09-17 to 2021-07-28 and 31 from 2021-07-29."""
        temp = [r for r in self.rows6 if "2019-09-17" <= r["date"] <= "2021-07-28"]
        later = [r for r in self.rows6 if "2021-07-29" <= r["date"] <= "2025-12-31"]
        self.assertEqual(sum(1 for r in temp if r["fed_repo_material_use"] == "1"), 190)
        self.assertEqual(sum(1 for r in later if r["fed_repo_material_use"] == "1"), 31)

    def test_the_facility_event_is_the_declared_union_on_every_row(self):
        events = 0
        for row in self.rows6:
            day = date.fromisoformat(row["date"])
            srf = None if row["srf_take_up"] == "" else float(row["srf_take_up"])
            fed = None if row["fed_repo_material_use"] == "" else float(row["fed_repo_material_use"])
            expected = d2.facility_event(0.0 if srf is None and day < panel_v6.SRF_INCEPTION else srf, fed)
            got = None if row["facility_material_use"] == "" else float(row["facility_material_use"])
            self.assertEqual(got, expected, row["date"])
            events += got == 1.0
        self.assertGreater(events, 190)
        self.assertEqual(self.tracked["coverage"]["facility_material_use"]["missing_rows"], 0)

    def test_the_fails_column_carries_each_week_to_the_following_rows_and_no_further(self):
        """The column at a row is the latest Wednesday's figure, at most 13 days old (the parent's weekly carry). Recorded
        mutation (11 November 2026): in `panel.build`, `_weekly_carry(("pd_fails_deliver_ust",) if v6 else ())` changed to
        `_weekly_carry()` (the fails no longer carried). This test failed with AssertionError (a non-Wednesday row had
        no figure), and so did `test_version_6_rebuilds_to_its_manifest_at_the_pin` (the digest moved)."""
        weeks = {w.as_of: w.value_musd for w in pd_fails.load_extract() if w.field == pd_fails.DRIVER_FIELD}
        seen = 0
        for row in self.rows6:
            day = date.fromisoformat(row["date"])
            wednesday = day - timedelta(days=(day.weekday() - 2) % 7)
            candidates = [d for d in weeks if d <= day and (day - d).days <= 13]
            if not candidates:
                self.assertEqual(row["pd_fails_deliver_ust"], "", row["date"])
                continue
            latest = max(candidates)
            self.assertNotEqual(row["pd_fails_deliver_ust"], "", row["date"])
            self.assertEqual(float(row["pd_fails_deliver_ust"]), weeks[latest] / 1000.0, row["date"])
            seen += 1
        self.assertGreater(seen, 2000)
        self.assertEqual(self.tracked["coverage"]["pd_fails_deliver_ust"]["missing_rows"], 0)

    def test_the_manifest_names_the_fails_extract_and_the_repo_operation_snapshots(self):
        self.assertEqual(self.tracked["pd_fails_extract_sha256"], hashlib.sha256(pd_fails.EXTRACT.read_bytes()).hexdigest())
        self.assertIn("fed_repo_ops_snapshots_sha256", self.tracked)
        self.assertEqual(self.tracked["measurement_breaks"], {k: list(v) for k, v in indicators.MEASUREMENT_BREAKS.items()})
        self.assertIn("fed_repo_material_use", self.tracked["derived_columns_note"])

    def test_the_build_asks_that_no_fails_week_is_read_before_it_is_public(self):
        """Recorded mutation (11 November 2026): in `panel._version_6`, the call `pd_fails.check_declared_lag(...)` replaced by
        `pass`. This test failed with AssertionError (`0 != 1`: the guard was never called)."""
        with mock.patch.object(pd_fails, "check_declared_lag", wraps=pd_fails.check_declared_lag) as guard:
            panel.build(pathlib.Path(self.tmp.name) / "again.csv", version=6)
        self.assertEqual(guard.call_count, 1)


class VersionTests(unittest.TestCase):
    def test_version_6_is_registered_and_the_default_stays_5(self):
        self.assertIn(6, panel.MANIFESTS)
        self.assertEqual(panel.MANIFESTS[6].name, "phase3_panel_v6_manifest.json")
        self.assertEqual(panel.CURRENT_VERSION, 5)

    def test_the_declaration_names_the_added_built_columns(self):
        self.assertEqual(declaration.BUILT_COLUMNS_V6_ADDED, ("sofr_p1", "sofr_p99", "pd_fails_deliver_ust"))


if __name__ == "__main__":
    unittest.main()
