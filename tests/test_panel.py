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
        for column in ("runoff_cap_treasury_bn", "runoff_cap_mbs_bn"):
            # The first row has no decision instant before it, as in the parent's scheduled inputs.
            self.assertEqual(self.built["coverage"][column]["missing_rows"], 1, column)

    def test_the_manifest_lists_every_phase3_column(self):
        self.assertEqual(self.built["phase3_columns"],
                         list(declaration.BUILT_COLUMNS) + list(declaration.SCHEDULED_COLUMNS))


if __name__ == "__main__":
    unittest.main()
