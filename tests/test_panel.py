"""The Phase 3 measurement panel rebuilds to its manifest from tracked fixtures alone.

Since L0 (#21, option (a)) the manifests are records made at `records.RECORD_PIN`. The checks that rebuild each
version to its manifest, stamp included, and versions 2 and 3 entire, run at the record commit
(`scripts/verify_records.py`). Here version 1 is rebuilt at the new pin, and versions 2 and 3 are refused.
"""

import hashlib
import pathlib
import tempfile
import unittest

from repo_liquidity import PARENT_COMMIT, declaration, panel, records, scheduled


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

    def test_the_panel_rebuilds_to_the_recorded_bytes_at_the_new_pin(self):
        self.assertEqual(hashlib.sha256(self.path.read_bytes()).hexdigest(), self.tracked["sha256"])
        self.assertEqual(self.built["sha256"], self.tracked["sha256"])
        self.assertEqual(self.built["parent_commit"], PARENT_COMMIT)
        self.assertEqual(self.tracked["parent_commit"], records.RECORD_PIN)

    def test_versions_2_and_3_are_records_only(self):
        """Recorded mutation (12 October 2026): in `panel.build`, `if version in RECORD_VERSIONS:` changed to
        `if False and version in RECORD_VERSIONS:`. This test failed with AssertionError (ValueError not raised)."""
        for version in panel.RECORD_VERSIONS:
            with self.assertRaises(ValueError) as caught:
                panel.build(pathlib.Path(self.tmp.name) / f"v{version}.csv", version=version)
            self.assertIn("verify_records.py", str(caught.exception))
        self.assertEqual(panel.RECORD_VERSIONS, (2, 3))

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


if __name__ == "__main__":
    unittest.main()
