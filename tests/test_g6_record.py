"""H7m, groundwork G6: the power study's record (`results/g6/power_study.json`, `docs/research/h7m-power-study.md`).

The record is output of `scripts/g6_power_study.py`, never hand-edited. These tests check what can be checked without a
rerun: it was made at this tree's pins; it holds what `docs/stages/h7-g6.md` declared; it reads no day after the
development end; no candidate appears in it; and the published tables are the record's own, printed by the script.
"""

import importlib.util
import json
import unittest
from datetime import date
from pathlib import Path

from repo_liquidity import PANEL_SHA256, PARENT_COMMIT, goalposts

ROOT = Path(__file__).resolve().parents[1]
RECORD = ROOT / "results" / "g6" / "power_study.json"
DOC = ROOT / "docs" / "research" / "h7m-power-study.md"
DECLARATION = ROOT / "docs" / "stages" / "h7-g6.md"


def _script():
    spec = importlib.util.spec_from_file_location("g6_power_study", ROOT / "scripts" / "g6_power_study.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class RecordTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.record = json.loads(RECORD.read_text(encoding="utf-8"))

    def test_it_was_made_at_this_trees_pins(self):
        self.assertEqual(self.record["pins"], {"parent": PARENT_COMMIT, "panel_digest": PANEL_SHA256})

    def test_it_holds_what_was_declared(self):
        script = _script()
        declared = self.record["declaration"]
        self.assertEqual((declared["seed"], declared["step"], tuple(declared["grid"])),
                         (script.SEED, script.STEP, script.GRID))
        self.assertEqual(declared["lengths"], list(goalposts.LOOKS))
        self.assertEqual(declared["draws"], {"60": 100000, "125": 100000, "250": 10000})
        text = DECLARATION.read_text(encoding="utf-8")
        for needle in ("20261014", "0.035", "0.125", "100,000", "every 20th scored day"):
            self.assertIn(needle, text)

    def test_it_reads_no_day_after_the_development_end(self):
        last = date.fromisoformat(self.record["days"]["last"])
        self.assertLessEqual(last, goalposts.DEVELOPMENT_END)
        self.assertLessEqual(date.fromisoformat(self.record["provenance"]["panel_last_day"]), goalposts.DEVELOPMENT_END)
        self.assertGreaterEqual(date.fromisoformat(self.record["days"]["first"]), goalposts.EVENTS_FROM)

    def test_it_scores_no_candidate(self):
        self.assertIn("No candidate is scored", self.record["what"])
        for name in ("stage6", "deployable", "h7_estimator", "candidate"):
            self.assertNotIn(name, json.dumps(self.record["declaration"]))

    def test_it_is_not_a_smoke_run(self):
        self.assertFalse(self.record["smoke"])

    def test_the_published_tables_are_the_records_own(self):
        tables = _script().tables(self.record)
        self.assertIn(tables, DOC.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
