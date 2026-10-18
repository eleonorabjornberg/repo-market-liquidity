"""H10 step 3 amendment: the 2 bp placebo rise floor (#85, `docs/decisions/h10-method.md` section 10).

A placebo window counts only if its spread rise is at least `PLACEBO_RISE_FLOOR_BP` (2 bp). Below that it is excluded, not
refused, and the count excluded is reported. The placebo summary reports the unfloored reading (the published one) and
the floored one side by side. `results/h10/placebo_floor_2bp.json` is that comparison as a new development record; the
published step 2 record (`results/h10/development.json`) is not touched, and its bytes are pinned in
`tests/test_h10_step3.py`.

No new availability or leakage guard is added: the placebo reads the same columns through `attribution.point_attribution`
as the published record did, so the mutations recorded in `tests/test_h10_step2.py` cover it.

Recorded mutations of the floor (15 October 2026), each run on `FlooredPlaceboSummaryTests`, then restored:

* `rise >= floor` replaced with `rise > floor` in `h10_apply.floored_placebo_summary`:
  `test_a_two_bp_rise_is_kept_and_a_one_bp_rise_is_excluded` failed with AssertionError.
* the floor not applied (every attributed window kept): the same test and
  `test_the_excluded_count_is_reported_and_excluded_windows_are_not_refused` failed with AssertionError.
"""

import hashlib
import json
import pathlib
import statistics
import unittest

from repo_liquidity import PANEL_SHA256, attribution, h10_apply, h10_publish, panel
# The pin step 3's records were made at; this record was made at it too and, published, keeps naming it (#107).
from test_h10_step3 import RECORD_PARENT_COMMIT

ROOT = pathlib.Path(__file__).resolve().parents[1]
DEVELOPMENT = ROOT / "results" / "h10" / "development.json"
FLOOR = ROOT / "results" / "h10" / "placebo_floor_2bp.json"
PAGE = ROOT / "docs" / "research" / "h10-development-table.md"
METHOD = ROOT / "docs" / "decisions" / "h10-method.md"


def window(rise, explained=0.5):
    return attribution.Attribution(0, "attributed", rise_bp=rise, explained_share=explained)


class FlooredPlaceboSummaryTests(unittest.TestCase):
    def test_the_floor_is_two_bp(self):
        self.assertEqual(attribution.PLACEBO_RISE_FLOOR_BP, 2.0)

    def test_a_two_bp_rise_is_kept_and_a_one_bp_rise_is_excluded(self):
        summary = h10_apply.floored_placebo_summary([window(1.0, 0.1), window(2.0, 0.9)], episode_explained=0.5)
        self.assertEqual(summary["attributed"], 1)
        self.assertEqual(summary["median_explained"], 0.9)
        self.assertEqual(summary["excluded"], 1)

    def test_the_excluded_count_is_reported_and_excluded_windows_are_not_refused(self):
        results = [
            window(1.0), window(1.99),
            attribution.Attribution(1, "not attributable", "the window shows no rise in the spread", rise_bp=-3.0),
            attribution.Attribution(2, "not attributable", "an input of the window is missing or the window is incomplete"),
            window(4.0, 0.7),
        ]
        summary = h10_apply.floored_placebo_summary(results, episode_explained=0.5)
        self.assertEqual(summary["windows"], 5)
        # below the floor: 1.0, 1.99 and the -3.0 window; a window with a missing input has no rise to compare
        self.assertEqual(summary["excluded"], 3)
        self.assertEqual(summary["attributed"], 1)
        self.assertEqual(summary["share_at_or_above"], 1.0)

    def test_the_unfloored_reading_is_the_published_summary(self):
        results = [window(1.0, 0.1), window(2.0, 0.9)]
        self.assertEqual(h10_apply.placebo_summary(results, 0.5),
                         {"windows": 2, "attributed": 2, "median_explained": 0.5, "share_at_or_above": 0.5})

    def test_no_window_at_the_floor_gives_no_figures(self):
        summary = h10_apply.floored_placebo_summary([window(1.0)], episode_explained=0.5)
        self.assertEqual((summary["attributed"], summary["median_explained"], summary["share_at_or_above"]), (0, None, None))


class RecordTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.development = json.loads(DEVELOPMENT.read_text(encoding="utf-8"))
        cls.record = json.loads(FLOOR.read_text(encoding="utf-8"))

    def test_it_is_a_development_record_that_names_its_source_and_pin(self):
        r = self.record
        self.assertEqual(r["tier"], "development")
        self.assertIn("not_a_verdict", r)
        self.assertEqual(r["parent_commit"], RECORD_PARENT_COMMIT)
        self.assertEqual(r["parent_panel_sha256"], PANEL_SHA256)
        self.assertEqual(r["panel"], self.development["panel"])
        self.assertEqual(r["panel"]["sha256"], panel.load_manifest(1)["sha256"])
        self.assertEqual(r["source_record"]["sha256"], hashlib.sha256(DEVELOPMENT.read_bytes()).hexdigest())
        self.assertEqual(r["settings"]["placebo_rise_floor_bp"], 2.0)
        for key in ("seed", "placebo_windows", "baseline_days", "window_days"):
            self.assertEqual(r["settings"][key], self.development["settings"][key], key)

    def test_the_episodes_are_the_published_records(self):
        self.assertEqual([e["onset"] for e in self.record["episodes"]], [e["onset"] for e in self.development["episodes"]])

    def test_the_unfloored_reading_is_the_published_placebo_comparison(self):
        for new, old in zip(self.record["episodes"], self.development["episodes"]):
            if old["status"] != "attributed":
                continue
            self.assertEqual(new["unfloored"], old["placebo"], old["onset"])
        self.assertEqual(self.record["readings"]["unfloored"]["median_placebo_gap"],
                         self.development["summary"]["markers"]["median_placebo_gap"])

    def test_both_readings_carry_an_interval(self):
        for name in ("unfloored", "floored"):
            gap = self.record["readings"][name]["median_placebo_gap"]
            self.assertLessEqual(gap["interval"][0], gap["median"])
            self.assertLessEqual(gap["median"], gap["interval"][1])

    def test_the_floored_reading_is_the_gap_over_the_episodes_with_a_kept_window(self):
        gaps = [e["explained_share"] - e["floored"]["median_explained"] for e in self.record["episodes"]
                if e["status"] == "attributed" and e["floored"]["median_explained"] is not None]
        reading = self.record["readings"]["floored"]["median_placebo_gap"]
        self.assertEqual(reading["n"], len(gaps))
        self.assertAlmostEqual(reading["median"], statistics.median(gaps), places=12)

    def test_the_excluded_counts_add_up(self):
        total = sum(e["floored"]["excluded"] for e in self.record["episodes"] if e["status"] == "attributed")
        self.assertEqual(self.record["readings"]["floored"]["windows_excluded"], total)
        self.assertEqual(self.record["readings"]["unfloored"]["windows"],
                         sum(e["unfloored"]["windows"] for e in self.record["episodes"] if e["status"] == "attributed"))

    def test_the_floored_windows_are_recomputed_from_the_panel(self):
        rows, _ = h10_apply.load_development()
        again = h10_apply.placebo_floor_record(rows, self.development, panel.load_manifest(1))
        # The recomputation names the live pin; the record names the pin it was made at. Everything else must agree.
        again["parent_commit"] = RECORD_PARENT_COMMIT
        self.assertEqual(again, self.record)

    def test_the_page_points_to_the_record_and_is_the_one_the_script_renders(self):
        text = PAGE.read_text(encoding="utf-8")
        self.assertIn("results/h10/placebo_floor_2bp.json", text)
        self.assertIn(hashlib.sha256(FLOOR.read_bytes()).hexdigest(), text)
        self.assertEqual(text, h10_publish.render_tracked())

    def test_the_method_record_carries_the_amendment_as_a_draft(self):
        text = METHOD.read_text(encoding="utf-8")
        self.assertIn("Amendment (Eleonora, 15 October 2026; finding #82)", text)
        self.assertIn("2 bp", text)


if __name__ == "__main__":
    unittest.main()
