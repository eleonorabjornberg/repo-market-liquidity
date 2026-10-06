"""Stage 2's record regenerates exactly from tracked fixtures, and states the decided rule's verdict."""

import importlib.util
import json
import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]


def _script():
    spec = importlib.util.spec_from_file_location("stage2", ROOT / "scripts" / "stage2_demand_curve.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class Stage2RecordTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.script = _script()
        cls.computed = cls.script.compute()
        cls.tracked = json.loads(cls.script.RECORD.read_text(encoding="utf-8"))

    def test_the_record_regenerates_exactly(self):
        self.assertEqual(json.dumps(self.computed, sort_keys=True), json.dumps(self.tracked, sort_keys=True))

    def test_the_window_ends_before_2026(self):
        self.assertLessEqual(self.tracked["settings"]["window"][1], "2025-12-31")

    def test_the_verdict_follows_the_decided_rule(self):
        from repo_liquidity import demand_curve as dc

        eligible = {label: tuple(entry["kink_interval_90"]) for label, entry in self.tracked["regimes"].items()
                    if entry["scarce_days"] >= dc.MIN_SCARCE_DAYS and entry.get("fit")}
        verdict = dc.stability_verdict(pooled=tuple(self.tracked["pooled"]["kink_interval_90"]), regimes=eligible)
        self.assertEqual(verdict, self.tracked["verdict"])


if __name__ == "__main__":
    unittest.main()
