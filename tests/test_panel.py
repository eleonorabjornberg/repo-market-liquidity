"""The Phase 3 measurement panel rebuilds to its manifest from tracked fixtures alone."""

import hashlib
import pathlib
import tempfile
import unittest

from repo_liquidity import declaration, panel, scheduled


class PanelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.path = pathlib.Path(cls.tmp.name) / "phase3_panel.csv"
        cls.built = panel.build(cls.path)
        cls.tracked = panel.load_manifest()

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_the_panel_rebuilds_to_its_tracked_manifest(self):
        self.assertEqual(self.built, self.tracked)
        self.assertEqual(hashlib.sha256(self.path.read_bytes()).hexdigest(), self.tracked["sha256"])

    def test_the_published_columns_are_the_parent_panel(self):
        from repo_liquidity import PANEL_SHA256

        self.assertEqual(self.built["parent_panel_sha256"], PANEL_SHA256)

    def test_no_phase3_column_is_refused(self):
        self.assertEqual(self.built["refusals"], {})

    def test_the_panel_starts_with_the_parent_panel(self):
        self.assertEqual(self.built["start_date"], "2018-04-03")

    def test_facility_columns_are_missing_exactly_before_the_facility(self):
        for column in ("srf_take_up", "srf_rate"):
            self.assertEqual(self.built["coverage"][column]["first"], scheduled.SRF_INCEPTION.isoformat())
        rows = self.path.read_text().splitlines()
        header = rows[0].split(",")
        take_up, rate = header.index("srf_take_up"), header.index("srf_rate")
        for line in rows[1:]:
            cells = line.split(",")
            before = cells[0] < scheduled.SRF_INCEPTION.isoformat()
            self.assertEqual(cells[take_up] == "", before, cells[0])
            self.assertEqual(cells[rate] == "", before, cells[0])

    def test_every_other_phase3_column_covers_the_panel(self):
        for column in ("on_rrp", "bank_total_assets", "soma_treasury_weekly_change"):
            self.assertEqual(self.built["coverage"][column]["missing_rows"], 0, column)
        for column in ("runoff_cap_treasury_bn", "runoff_cap_mbs_bn", "on_rrp_rate"):
            # The first row has no decision instant before it, as in the parent's scheduled inputs.
            self.assertEqual(self.built["coverage"][column]["missing_rows"], 1, column)

    def test_the_manifest_lists_every_phase3_column(self):
        self.assertEqual(self.built["phase3_columns"],
                         list(declaration.BUILT_COLUMNS) + list(declaration.SCHEDULED_COLUMNS))



class PanelV2Tests(unittest.TestCase):
    """The Stage 1a correction's panel (`docs/stages/stage-1a-correction.md`)."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.path = pathlib.Path(cls.tmp.name) / "phase3_panel_v2.csv"
        cls.built = panel.build(cls.path, version=2)
        cls.tracked = panel.load_manifest(2)
        lines = cls.path.read_text().splitlines()
        header = lines[0].split(",")
        cls.rows = [dict(zip(header, line.split(","))) for line in lines[1:]]

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_the_panel_rebuilds_to_its_tracked_manifest(self):
        self.assertEqual(self.built, self.tracked)
        self.assertEqual(hashlib.sha256(self.path.read_bytes()).hexdigest(), self.tracked["sha256"])

    def test_version_1_is_unchanged_inside_version_2(self):
        v1 = panel.load_manifest(1)
        self.assertEqual(self.built["v1_sha256"], v1["sha256"])
        self.assertEqual(self.built["parent_panel_sha256"], v1["parent_panel_sha256"])
        v1_path = pathlib.Path(self.tmp.name) / "phase3_panel_v1.csv"
        panel.build(v1_path, version=1)
        lines = v1_path.read_text().splitlines()
        header = lines[0].split(",")
        v1_rows = [dict(zip(header, line.split(","))) for line in lines[1:]]
        self.assertEqual([{column: row[column] for column in header} for row in self.rows], v1_rows)

    def test_no_column_is_refused(self):
        self.assertEqual(self.built["refusals"], {})

    def test_the_mbs_change_covers_the_panel(self):
        self.assertEqual(self.built["coverage"]["soma_mbs_weekly_change"]["missing_rows"], 0)

    def test_repo_take_up_is_zero_then_temporary_then_standing(self):
        for row in self.rows:
            day = row["date"]
            if day < "2019-09-17":
                self.assertEqual((row["fed_repo_take_up"], row["fed_repo_facility"]), ("0", "0"), day)
            elif day < scheduled.SRF_INCEPTION.isoformat():
                self.assertIn(row["fed_repo_facility"], ("1", ""), day)
                if row["temp_repo_take_up"] == "":
                    self.assertEqual(row["fed_repo_take_up"], "", day)
                else:
                    # Question 14: overnight plus the term repos outstanding that day.
                    expected = float(row["temp_repo_take_up"]) + float(row["temp_repo_term_outstanding"] or 0)
                    self.assertAlmostEqual(float(row["fed_repo_take_up"]), expected, places=6, msg=day)
            else:
                self.assertEqual(row["fed_repo_facility"], "2", day)
                self.assertEqual(row["fed_repo_take_up"], row["srf_take_up"], day)

    def test_the_temporary_operations_stay_inside_their_window(self):
        for row in self.rows:
            if row["temp_repo_take_up"] != "":
                self.assertTrue("2019-09-17" <= row["date"] <= "2021-07-28", row["date"])

    def test_term_repos_outstanding_cover_every_weekday_of_the_window_and_no_other(self):
        for row in self.rows:
            inside = "2019-09-17" <= row["date"] <= "2021-07-28"
            self.assertEqual(row["temp_repo_term_outstanding"] != "", inside, row["date"])

    def test_the_repo_material_use_event_counts_each_days_operations(self):
        for row in self.rows:
            day = row["date"]
            if day < "2019-09-17":
                self.assertEqual(row["fed_repo_material_use"], "0", day)
            elif row["srf_take_up"] != "":
                self.assertEqual(row["fed_repo_material_use"], row["srf_material_use"], day)
            elif row["temp_repo_take_up"] != "" or row["temp_repo_term_take_up"] != "":
                accepted = float(row["temp_repo_take_up"] or 0) + float(row["temp_repo_term_take_up"] or 0)
                self.assertEqual(row["fed_repo_material_use"], "1" if accepted >= 1.0 else "0", day)

    def test_material_use_is_take_up_of_at_least_one_billion(self):
        for row in self.rows:
            if row["srf_take_up"] == "":
                self.assertEqual(row["srf_material_use"], "", row["date"])
            else:
                self.assertEqual(row["srf_material_use"], "1" if float(row["srf_take_up"]) >= 1.0 else "0", row["date"])

    def test_the_manifest_lists_every_phase3_column(self):
        self.assertEqual(self.built["phase3_columns"],
                         list(declaration.BUILT_COLUMNS_V2) + list(declaration.SCHEDULED_COLUMNS)
                         + list(declaration.DERIVED_COLUMNS_V2))


if __name__ == "__main__":
    unittest.main()
