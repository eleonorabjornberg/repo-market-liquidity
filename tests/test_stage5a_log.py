"""Stage 5a: the daily log runner's refusals (`scripts/stage5a_log.py`, `docs/stages/stage-5a.md`).

Every refusal is raised before anything is fetched or fitted, so these tests run in seconds.

Stage 5a was retired on 12 October 2026 before it started (repo-market-model#643, S3). The Stage 4 freeze it forecasts
with is a record of the parent pin it was made at, and hashes this repository's IORB table, deleted that day. So at
head every run is refused at the checksum; the checks that the pinned checksum is the freeze's and that a dry run
passes run at the record commit (`scripts/verify_records.py`, L0 #21, option (a)).
"""

import argparse
import importlib.util
import tempfile
import unittest
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _log():
    spec = importlib.util.spec_from_file_location("stage5a_log", ROOT / "scripts" / "stage5a_log.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class RunnerRefusalTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from repo_liquidity import live

        cls.log = _log()
        cls.parent = live.parent_live()

    def _args(self, day, **extra):
        values = {"date": day, "out_dir": tempfile.mkdtemp(), "dry_run": False, "raw_root": None,
                  "workflow_run": None}
        values.update(extra)
        return argparse.Namespace(**values)

    def test_saved_snapshots_are_for_dry_runs_only(self):
        with self.assertRaises(ValueError):
            self.log.run(self._args(date(2026, 10, 8), raw_root=[Path("/nonexistent")]))

    def test_a_development_day_is_refused(self):
        from repo_liquidity import curve_feature

        with curve_feature.stage4_declaration(), self.assertRaises(ValueError):
            self.log.refuse(date(2025, 12, 30), Path(tempfile.mkdtemp()), dry_run=True, module=self.parent)

    def test_a_logged_day_is_refused(self):
        from repo_liquidity import curve_feature, live

        out = Path(tempfile.mkdtemp())
        live.write_record(out, date(2026, 10, 8), {"decision_day": "2026-10-08"})
        with curve_feature.stage4_declaration(), self.assertRaises(ValueError):
            self.log.refuse(date(2026, 10, 8), out, dry_run=False, module=self.parent)

    def test_a_day_past_an_uncovered_fomc_statement_is_refused(self):
        from repo_liquidity import curve_feature

        with curve_feature.stage4_declaration(), self.assertRaises(ValueError) as caught:
            self.log.refuse(date(2026, 10, 29), Path(tempfile.mkdtemp()), dry_run=True, module=self.parent)
        self.assertIn("October 27-28, 2026", str(caught.exception))

    def test_a_drifted_declaration_is_refused(self):
        from repo_liquidity import curve_feature

        saved = curve_feature.REFIT_EVERY
        curve_feature.REFIT_EVERY = saved + 1
        try:
            with curve_feature.stage4_declaration(), self.assertRaises(ValueError) as caught:
                self.log.refuse(date(2026, 10, 8), Path(tempfile.mkdtemp()), dry_run=True, module=self.parent)
            self.assertIn("checksum", str(caught.exception))
        finally:
            curve_feature.REFIT_EVERY = saved

    def test_a_live_run_is_made_on_its_day_after_the_decision(self):
        from repo_liquidity import curve_feature

        with curve_feature.stage4_declaration(), self.assertRaises(ValueError):
            self.log.refuse(date(2026, 10, 8) if date.today() != date(2026, 10, 8) else date(2026, 10, 9),
                            Path(tempfile.mkdtemp()), dry_run=False, module=self.parent)

    def test_since_the_retirement_a_dry_run_is_refused_at_the_checksum(self):
        from repo_liquidity import curve_feature
        from repo_liquidity.records import FREEZE_CHECKSUM

        self.assertEqual(self.log.pinned_checksum(), FREEZE_CHECKSUM)
        with curve_feature.stage4_declaration(), self.assertRaises(ValueError) as caught:
            self.log.refuse(date(2026, 10, 8), Path(tempfile.mkdtemp()), dry_run=True, module=self.parent)
        self.assertIn("verify_records.py", str(caught.exception))


if __name__ == "__main__":
    unittest.main()
