"""Stage 5a: the daily log runner's refusals (`scripts/stage5a_log.py`, `docs/stages/stage-5a.md`).

Every refusal is raised before anything is fetched or fitted, so these tests run in seconds.
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

    def test_the_pinned_checksum_is_the_freeze_records(self):
        self.assertEqual(self.log.pinned_checksum(), self.log._freeze().checksum())

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

    def test_a_dry_run_passes_the_refusals(self):
        from repo_liquidity import curve_feature

        with curve_feature.stage4_declaration():
            decision = self.log.refuse(date(2026, 10, 8), Path(tempfile.mkdtemp()), dry_run=True, module=self.parent)
        self.assertEqual(decision.isoformat(), "2026-10-08T16:00:00")


if __name__ == "__main__":
    unittest.main()
