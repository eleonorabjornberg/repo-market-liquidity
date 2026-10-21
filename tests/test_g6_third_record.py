"""H7m, groundwork G6: the third record's published write-up (`docs/research/h7m-power-study-3.json`, `.md`, directive #126).

The record is output of `scripts/g6_power_study.py --third`, assembled from the Mac run's three parts and never
hand-edited. This checks what needs no rerun: the write-up carries the tables the script prints from the record, and the
record was made at this tree's pins and scores no candidate.
"""

import importlib.util
import json
import unittest
from pathlib import Path

from repo_liquidity import PARENT_COMMIT

ROOT = Path(__file__).resolve().parents[1]
RECORD = ROOT / "docs" / "research" / "h7m-power-study-3.json"
DOC = ROOT / "docs" / "research" / "h7m-power-study-3.md"


def _script():
    spec = importlib.util.spec_from_file_location("g6_power_study", ROOT / "scripts" / "g6_power_study.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ThirdRecordWriteUpTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.record = json.loads(RECORD.read_text(encoding="utf-8"))

    def test_the_published_tables_are_the_records_own(self):
        text = DOC.read_text(encoding="utf-8")
        self.assertIn(_script().tables_third(self.record).rstrip("\n"), text)

    def test_it_was_made_at_this_trees_parent_pin_and_is_not_a_smoke_run(self):
        self.assertEqual(self.record["pins"]["parent"], PARENT_COMMIT)
        self.assertFalse(self.record["smoke"])

    def test_the_write_up_is_labelled_development_and_scores_no_candidate(self):
        text = DOC.read_text(encoding="utf-8")
        self.assertIn("Development evidence, never a verdict. No candidate is scored", text)


if __name__ == "__main__":
    unittest.main()
