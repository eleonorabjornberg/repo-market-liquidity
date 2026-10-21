"""The Phase 3 measurement panel rebuilds to its manifest from tracked fixtures alone.

Since L0 (#21, option (a)) the manifests of versions 1 to 3 are records made at `records.RECORD_PIN`. The checks
that rebuild each of them to its manifest run at the record commit (`scripts/verify_records.py`). Version 4 (#149,
Eleonora's ruling of 21 October 2026) is version 1's build at the pin of 08ff67e, a new record with its own manifest:
it is rebuilt here, and versions 1 to 3 are refused.
"""

import json

import hashlib
import pathlib
import tempfile
import unittest

from repo_liquidity import PARENT_COMMIT, declaration, panel, records, scheduled

PANEL_V1_SHA256 = "acb77874e0ca2c9eeee1c33a229f5e12745e65bb1224088d52c391dbf54be2ab"


class PanelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.path = pathlib.Path(cls.tmp.name) / "phase3_panel.csv"
        cls.built = panel.build(cls.path, version=4)
        cls.tracked = panel.load_manifest(4)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_the_panel_rebuilds_to_the_recorded_bytes_at_the_new_pin(self):
        self.assertEqual(hashlib.sha256(self.path.read_bytes()).hexdigest(), self.tracked["sha256"])
        self.assertEqual(self.built["sha256"], self.tracked["sha256"])
        self.assertEqual(self.built["parent_commit"], PARENT_COMMIT)
        self.assertEqual(self.tracked["parent_commit"], PARENT_COMMIT)
        self.assertEqual(self.tracked["version"], 4)

    def test_versions_1_to_3_are_records_only(self):
        """Recorded mutation (12 October 2026): in `panel.build`, `if version in RECORD_VERSIONS:` changed to
        `if False and version in RECORD_VERSIONS:`. This test failed with AssertionError (ValueError not raised).
        Re-run for version 4 (21 October 2026): the same mutation; this test failed with AssertionError (ValueError not
        raised)."""
        for version in panel.RECORD_VERSIONS:
            with self.assertRaises(ValueError) as caught:
                panel.build(pathlib.Path(self.tmp.name) / f"v{version}.csv", version=version)
            self.assertIn("verify_records.py", str(caught.exception))
        self.assertEqual(panel.RECORD_VERSIONS, (1, 2, 3))

    def test_version_1_stays_as_published(self):
        """Never edited in place (ruling of 21 October 2026): version 1's manifest is the recorded one, and version 4's
        names it."""
        v1 = panel.load_manifest(1)
        self.assertEqual(v1["sha256"], PANEL_V1_SHA256)
        self.assertEqual(self.tracked["v1_sha256"], v1["sha256"])
        self.assertNotEqual(self.tracked["sha256"], v1["sha256"])
        self.assertEqual(self.tracked["parent_commit"], PARENT_COMMIT)

    def test_version_4_differs_from_version_1_only_in_srf_take_up(self):
        """The ruling's report: the 391 changed `srf_take_up` rows by date (`results/panel/v4_changes.json`, made from
        version 1 at its own pin and version 4 at this one). Version 4 carries those values, and its manifest differs from
        version 1's in nothing else the manifest records (columns, dates, coverage)."""
        v1 = panel.load_manifest(1)
        for key in ("columns", "phase3_columns", "start_date", "end_date", "coverage", "parent_panel_sha256"):
            self.assertEqual(self.tracked[key], v1[key], key)
        record = json.loads((panel.ROOT / "results" / "panel" / "v4_changes.json").read_text(encoding="utf-8"))
        self.assertEqual(record["column"], "srf_take_up")
        self.assertEqual(len(record["changes"]), record["count"])
        rows = self.path.read_text().splitlines()
        header = rows[0].split(",")
        column = header.index("srf_take_up")
        built = {line.split(",")[0]: line.split(",")[column] for line in rows[1:]}
        for change in record["changes"]:
            self.assertEqual(built[change["date"]], change["v4"], change["date"])
            self.assertLess(float(change["v4"]), float(change["v1"]), change["date"])

    def test_h10s_drivers_do_not_read_srf_take_up(self):
        """H10's development table is unchanged by version 4 because no driver it reads changed (#152 confirms this
        before the re-registration)."""
        from repo_liquidity import attribution

        self.assertNotIn("srf_take_up", attribution.DRIVERS_WITH_ON_RRP)
        self.assertNotIn("srf_take_up", attribution.SPREAD)

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
