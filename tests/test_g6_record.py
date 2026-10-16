"""H7m, groundwork G6: the power study's second record (`docs/research/h7m-power-study-2.json`, `.md`) and the archived first.

The record is output of `scripts/g6_power_study.py`, never hand-edited. These tests check what can be checked without a
rerun: it was made at this tree's pins; it holds what `docs/stages/h7-g6.md` declared (§4-§10); it reads no day after the
development end; no candidate appears in it; the events it counts for the floor are the window's own, and its tables'
window counts match the shares beneath them (finding #95); the calibration met the declared tolerance; and the
published tables are the record's own, printed by the script. The first record is archived byte for byte
(`archive/h7m-power-study-1/`), never edited.
"""

import hashlib
import importlib.util
import json
import unittest
from datetime import date
from pathlib import Path

from repo_liquidity import PANEL_SHA256, PARENT_COMMIT, goalposts

ROOT = Path(__file__).resolve().parents[1]
RECORD = ROOT / "docs" / "research" / "h7m-power-study-2.json"
DOC = ROOT / "docs" / "research" / "h7m-power-study-2.md"
DECLARATION = ROOT / "docs" / "stages" / "h7-g6.md"
ARCHIVE = ROOT / "archive" / "h7m-power-study-1"

#: The parent pin the first record was made at (L27, #105 moved the tree to a later pin). A published record is never
#: edited in place, so it keeps naming the pin it was made at.
FIRST_RECORD_PARENT_COMMIT = "53e61af9b4175e854c196908d3c76b228c039667"
FIRST_RECORD_SHA256 = {
    "h7m-power-study.json": "5a44c9a00955ea8c90b5ee5f2ce772bd143cc9aa9b5abf3f256bc143dfe3a0b9",
    "h7m-power-study.md": "0e0c1cc68e6f0423ba497fd0be5ed7da9a42b3aa09af282a909ff20ad06f2597",
}


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
        self.assertEqual(declared["seed"], 20261014)
        self.assertEqual(declared["lengths"], list(goalposts.LOOKS))
        self.assertEqual(declared["draws"], {"60": 100000, "125": 100000, "250": 10000})
        self.assertEqual(declared["event_floor_counts"], "events in the window")
        self.assertEqual(declared["calibration_tolerance"], 1e-4)
        text = DECLARATION.read_text(encoding="utf-8")
        for needle in ("20261014", "0.035", "0.125", "100,000", "every 20th scored day", "## 9.", "## 10.", "Q7"):
            self.assertIn(needle, text)

    def test_the_window_seed_is_the_declared_one(self):
        """Finding #95: the first record's `SEED + start*10 + look` is retired."""
        source = (ROOT / "scripts" / "g6_power_study.py").read_text(encoding="utf-8")
        self.assertNotIn("start*10", source.replace(" ", ""))
        self.assertIn("gp.window_seed(start)", source)

    def test_it_reads_no_day_after_the_development_end_and_labels_to_it(self):
        last = date.fromisoformat(self.record["days"]["last"])
        self.assertEqual(last, goalposts.DEVELOPMENT_END)
        self.assertEqual(date.fromisoformat(self.record["provenance"]["repo_operation_coverage_end"]),
                         goalposts.DEVELOPMENT_END)
        self.assertLessEqual(date.fromisoformat(self.record["provenance"]["panel_last_day"]), goalposts.DEVELOPMENT_END)
        self.assertGreaterEqual(date.fromisoformat(self.record["days"]["first"]), goalposts.EVENTS_FROM)

    def test_it_scores_no_candidate(self):
        self.assertIn("No candidate is scored", self.record["what"])
        for name in ("stage6", "deployable", "h7_estimator", "candidate"):
            self.assertNotIn(name, json.dumps(self.record["declaration"]))

    def test_it_is_not_a_smoke_run(self):
        self.assertFalse(self.record["smoke"])
        self.assertEqual(self.record["part_b"]["power_at_250_days"]["replicates"], 400)
        self.assertEqual(self.record["part_b"]["days_to_the_event_floor"]["series"], 2000)

    def test_the_published_tables_are_the_records_own(self):
        script = _script()
        text = DOC.read_text(encoding="utf-8")
        self.assertIn(script.tables(self.record), text)
        self.assertIn(script.tables_part_b(self.record), text)

    def test_the_floor_counts_the_events_in_the_window(self):
        """Finding #95: every window's event count is the window's own, and a window's usable count never exceeds it."""
        for window in self.record["windows"]:
            for result in window["results"].values():
                self.assertEqual(result["window_events"], window["events"])
                self.assertLessEqual(result["usable_events"], result["window_events"])
                self.assertEqual(result["supported"], bool(result["lower"] > 0.0 and result["point"] >= goalposts.MME
                                                           and window["events"] >= goalposts.EVENT_FLOOR))

    def test_each_tables_window_counts_match_the_shares_beneath_them(self):
        """Finding #95: "12 of 76" stood above shares over 7 windows. Now every share's denominator is a counted window."""
        windows = self.record["windows"]
        era = goalposts.era
        first_days = {(w["length"], w["start"]): date.fromisoformat(w["first_day"]) for w in windows}
        for row in self.record["power"]:
            if not row["windows"]:
                continue
            mine = [w for w in windows if w["length"] == row["length"]
                    and (row["era"] == "pooled" or era(first_days[(w["length"], w["start"])]) == row["era"])]
            floor = [w for w in mine if w["events"] >= goalposts.EVENT_FLOOR]
            self.assertEqual((row["windows"], row["windows_at_the_event_floor"]), (len(mine), len(floor)))
            for gain, cells in row["gains"].items():
                self.assertEqual(cells["all_windows"]["windows"], len(mine))
                self.assertEqual(cells["windows_at_the_floor"]["windows"], len(floor))
                self.assertEqual(cells["all_windows"]["supported"], sum(w["results"][gain]["supported"] for w in mine))
                self.assertEqual(cells["windows_at_the_floor"]["supported"],
                                 sum(w["results"][gain]["supported"] for w in floor))

    def test_every_reading_has_its_interval_at_the_effective_windows(self):
        for row in self.record["power"]:
            if not row["windows"]:
                continue
            for cells in row["gains"].values():
                for key, count in (("all_windows", row["windows"]), ("windows_at_the_floor",
                                                                      row["windows_at_the_event_floor"])):
                    reading = cells[key]
                    if not count:
                        self.assertIsNone(reading["interval"])
                        continue
                    expected = goalposts.power(reading["supported"], count, row["length"], self.record["declaration"]["step"])
                    self.assertAlmostEqual(reading["interval"][0], expected.low)
                    self.assertAlmostEqual(reading["interval"][1], expected.high)
                    self.assertAlmostEqual(reading["effective_windows"], expected.effective)

    def test_the_planting_met_the_declared_tolerance(self):
        tolerance = self.record["declaration"]["calibration_tolerance"]
        realised = self.record["planting"]["realised_gain_on_the_whole_span"]
        checked = 0
        for target, result in realised.items():
            if float(target) == 0.0 or result is None:
                continue
            self.assertLessEqual(abs(result["miss"]), tolerance, target)
            checked += 1
        self.assertGreater(checked, 0)
        for target, result in self.record["part_b"]["planting"]["mean_gain_on_the_reference_series"].items():
            if float(target) != 0.0 and result is not None:
                self.assertLessEqual(abs(result["miss"]), tolerance, target)

    def test_the_event_process_is_the_fitted_two_state_chain(self):
        process = self.record["part_b"]["process"]
        self.assertEqual(process["calibration_window"][1], goalposts.DEVELOPMENT_END.isoformat())
        self.assertGreaterEqual(process["calibration_window"][0], "2025-01-01")
        fitted = goalposts.EventProcess(process["start"], process["stay"], process["transitions_from_quiet"],
                                        process["transitions_from_event"])
        self.assertAlmostEqual(fitted.stationary, process["stationary"])
        self.assertEqual(process["transitions_from_quiet"] + process["transitions_from_event"], process["days"] - 1)

    def test_part_b_counts_replicates_beside_its_shares(self):
        power = self.record["part_b"]["power_at_250_days"]
        for gain, row in power["gains"].items():
            self.assertEqual(row["all_replicates"]["replicates"], power["replicates"], gain)
            self.assertEqual(row["replicates_at_the_floor"]["replicates"], power["replicates_at_the_event_floor"], gain)
            self.assertLessEqual(row["all_replicates"]["supported"], power["replicates"])


class ArchivedFirstRecordTests(unittest.TestCase):
    def test_the_first_record_is_archived_byte_for_byte(self):
        for name, digest in FIRST_RECORD_SHA256.items():
            self.assertEqual(hashlib.sha256((ARCHIVE / name).read_bytes()).hexdigest(), digest, name)
            self.assertIn(digest, (ARCHIVE / "README.md").read_text(encoding="utf-8"))

    def test_it_is_no_longer_where_the_second_is_published(self):
        for name in FIRST_RECORD_SHA256:
            self.assertFalse((ROOT / "docs" / "research" / name).exists(), name)

    def test_it_keeps_naming_the_pin_it_was_made_at(self):
        record = json.loads((ARCHIVE / "h7m-power-study.json").read_text(encoding="utf-8"))
        self.assertEqual(record["pins"], {"parent": FIRST_RECORD_PARENT_COMMIT, "panel_digest": PANEL_SHA256})

    def test_the_archive_says_why(self):
        text = (ARCHIVE / "README.md").read_text(encoding="utf-8")
        for needle in ("#95", "usable strata", "seed", "1e-4", "2025-12-31"):
            self.assertIn(needle, text)


if __name__ == "__main__":
    unittest.main()
