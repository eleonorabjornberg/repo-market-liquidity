"""H7m stage verdict (directive #187): the record `results/h7/verdict.json` and the page `docs/stages/h7m-verdict.md`.

Written before the module `repo_liquidity.h7_verdict`; the first run failed with ImportError. The verdict is Eleonora's ruling of
26 October 2026 on #181 (option (a)) applied to step 5's development scores: no candidate is eligible after steps 2 to 5, so H7m is
not testable as stated (`docs/research/plan.md:185`, `:193`; eligibility `docs/decisions/measurement-protocol.md:51`, section 7).

What is checked: the statuses are what the step 5 and kink records yield through the rule, not typed; every figure is a record's
figure read through a reader that refuses one no record carries; a typed figure fails; the rule's quotes are the files' lines; the
page is what the record renders to; the plan keeps its earlier text and gains a dated note; nothing is claimed beyond the ruling.

Recorded mutation (26 October 2026): in `h7_verdict.read_figure`, the line `raise ValueError(...)` for a path that no record
carries replaced by `return None`. `FigureReaderTests.test_a_path_no_record_carries_is_refused` failed with
`AssertionError: ValueError not raised`.
"""

from __future__ import annotations

import copy
import hashlib
import json
import unittest
from pathlib import Path

from repo_liquidity import h7_verdict as v

ROOT = Path(__file__).resolve().parents[1]
RECORD = ROOT / "results" / "h7" / "verdict.json"
PAGE = ROOT / "docs" / "stages" / "h7m-verdict.md"
PLAN = ROOT / "docs" / "research" / "plan.md"
FORBIDDEN = ("decides nothing", "post hoc", "held out", "lockbox", "blind tier", "live record")
EXPECTED = {
    **{n: "ineligible: goalpost 1 does not hold" for n in ("B", "V1", "V2", "V3", "V4", "V5", "V6")},
    "C": "ineligible: goalpost 2 does not hold",
    "CV3": "ineligible: goalpost 1 is unreadable on development data",
    "CV1": "not scorable",
    "CV2": "not scorable",
    "CV4": "not scorable",
}


def _step5(name_to_g1, name_to_g2, scorable=True):
    """A synthetic step 5 record with the fields `derive` reads."""
    estimators = {}
    for name, g1 in name_to_g1.items():
        e = {"status": "scored" if scorable else "not scorable", "family": "A" if g1 != "unreadable" else "C"}
        if g1 == "unreadable":
            e["goalpost_1"] = {"reading": v.GOALPOST_ONE_C}
        else:
            e["goalpost_1"] = {"reading": v.GOALPOST_ONE_A,
                               "recorded": {"holds": g1 == "holds", "limit": 0.5,
                                            "worst": {"day": "2021-01-04", "gap": 0.1 if g1 == "holds" else 2.0}}}
        e["goalpost_2"] = {"all: all": {"median_points": name_to_g2[name], "limit_points": 3.0,
                                        "position": "under the bar" if name_to_g2[name] < 3.0 else "not under the bar"}}
        if not scorable:
            e["reason"] = "serves no day"
            e["goalpost_2"] = None
        estimators[name] = e
    return {"estimators": estimators, "settings": {"width_limit_points": 3.0}}


class FigureReaderTests(unittest.TestCase):
    RECORDS = {"step5": {"a": {"b": 3.25, "c": "text", "d": [1, 2]}}}

    def test_it_reads_a_figure_a_record_carries(self):
        self.assertEqual(v.read_figure(self.RECORDS, "step5", ["a", "b"]), 3.25)
        self.assertEqual(v.figure(self.RECORDS, "step5", ["a", "b"]),
                         {"value": 3.25, "source": "step5", "path": ["a", "b"]})

    def test_a_path_no_record_carries_is_refused(self):
        with self.assertRaises(ValueError):
            v.read_figure(self.RECORDS, "step5", ["a", "missing"])
        with self.assertRaises(ValueError):
            v.read_figure(self.RECORDS, "nowhere", ["a", "b"])

    def test_a_branch_is_not_a_figure(self):
        with self.assertRaises(ValueError):
            v.read_figure(self.RECORDS, "step5", ["a"])
        with self.assertRaises(ValueError):
            v.read_figure(self.RECORDS, "step5", ["a", "d"])

    def test_the_check_names_a_typed_figure_a_changed_figure_and_a_bare_number(self):
        good = {"x": v.figure(self.RECORDS, "step5", ["a", "b"])}
        self.assertEqual(v.check_figures(good, self.RECORDS), [])
        typed = {"x": {"value": 3.25}}
        self.assertTrue(v.check_figures(typed, self.RECORDS))
        changed = {"x": {"value": 3.3, "source": "step5", "path": ["a", "b"]}}
        self.assertTrue(v.check_figures(changed, self.RECORDS))
        self.assertEqual(v.untyped_numbers({"x": 3.25, "y": {"z": [1.5]}, "ok": True}), ["x", "y.z[0]"])
        self.assertEqual(v.untyped_numbers(good), [])


class DeriveTests(unittest.TestCase):
    def test_goalpost_one_that_fails_makes_a_candidate_ineligible_whatever_its_width(self):
        got = v.derive(_step5({"X": "fails"}, {"X": 1.0}))
        self.assertFalse(got["X"]["eligible"])
        self.assertEqual(got["X"]["status"], "ineligible: goalpost 1 does not hold")

    def test_a_width_over_the_bar_makes_a_candidate_ineligible(self):
        got = v.derive(_step5({"X": "holds"}, {"X": 3.46}))
        self.assertEqual(got["X"]["status"], "ineligible: goalpost 2 does not hold")

    def test_goalpost_one_unreadable_is_not_a_pass(self):
        got = v.derive(_step5({"X": "unreadable"}, {"X": 2.5}))
        self.assertFalse(got["X"]["eligible"])
        self.assertEqual(got["X"]["status"], "ineligible: goalpost 1 is unreadable on development data")

    def test_both_goalposts_holding_is_eligible_and_the_verdict_then_refuses(self):
        got = v.derive(_step5({"X": "holds"}, {"X": 2.5}))
        self.assertTrue(got["X"]["eligible"])
        with self.assertRaises(ValueError):
            v.verdict(got)

    def test_no_eligible_candidate_gives_the_rules_result(self):
        got = v.derive(_step5({"X": "fails", "Y": "unreadable"}, {"X": 2.0, "Y": 3.5}))
        self.assertEqual(v.verdict(got), "not testable as stated")

    def test_an_estimator_that_serves_no_day_is_not_scorable_with_the_records_reason(self):
        got = v.derive(_step5({"X": "fails"}, {"X": 2.0}, scorable=False))
        self.assertEqual(got["X"]["status"], "not scorable")
        self.assertEqual(got["X"]["reason"], "serves no day")
        self.assertFalse(got["X"]["eligible"])

    def test_a_width_exactly_at_the_bar_does_not_hold(self):
        got = v.derive(_step5({"X": "holds"}, {"X": 3.0}))
        self.assertEqual(got["X"]["status"], "ineligible: goalpost 2 does not hold")


class TrackedRecordTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.record = json.loads(RECORD.read_text(encoding="utf-8"))
        cls.records = v.load_records(ROOT)

    def test_the_verdict_is_the_rules_result_for_no_eligible_candidate(self):
        self.assertEqual(self.record["verdict"], "not testable as stated")
        self.assertEqual(self.record["eligible"], [])
        self.assertEqual(self.record["tier"], "development")
        self.assertEqual(self.record["directive"], "repo-market-liquidity#187")

    def test_each_status_is_what_the_step_five_and_kink_records_yield(self):
        derived = v.derive(self.records["step5"], kink=self.records["kink"])
        self.assertEqual(set(self.record["estimators"]), set(EXPECTED))
        for name, e in self.record["estimators"].items():
            self.assertEqual(e["status"], derived[name]["status"], name)
            self.assertEqual(e["status"], EXPECTED[name], name)
            self.assertEqual(e["reason"], derived[name]["reason"], name)
            self.assertFalse(e["eligible"], name)
        self.assertEqual(self.record["verdict"], v.verdict(derived))

    def test_every_a_worst_gap_is_at_or_above_half_a_point_in_the_kink_record(self):
        for name in ("B", "V1", "V2", "V3", "V4", "V5", "V6"):
            gap = v.read_figure(self.records, "kink", ["summaries", name, "all_served_days", "goalpost_1", "worst", "gap"])
            self.assertGreaterEqual(gap, 0.5, name)
            self.assertEqual(self.record["estimators"][name]["goalpost_1"]["worst_gap_points"]["value"], gap, name)

    def test_c_is_over_the_bar_and_cv3_is_under_it_with_goalpost_one_unreadable(self):
        c = self.record["estimators"]["C"]["goalpost_2"]
        cv3 = self.record["estimators"]["CV3"]["goalpost_2"]
        self.assertGreater(c["median_points"]["value"], c["limit_points"]["value"])
        self.assertEqual(c["limit_points"]["value"], 3.0)
        self.assertLess(cv3["median_points"]["value"], cv3["limit_points"]["value"])
        self.assertEqual(self.record["estimators"]["CV3"]["goalpost_1"]["reading"], v.GOALPOST_ONE_C)

    def test_cv1_cv2_and_cv4_are_not_scorable_and_carry_the_records_reason(self):
        for name in ("CV1", "CV2", "CV4"):
            e = self.record["estimators"][name]
            self.assertEqual(e["status"], "not scorable")
            self.assertEqual(e["reason"], self.records["step5"]["estimators"][name]["reason"])
            self.assertIn("69 of 70 refits", e["reason"])

    def test_beside_the_rule_no_gain_against_r_plus_s_is_at_or_above_the_mme_and_every_gain_against_s_is_negative(self):
        beside = self.record["beside"]
        for name, row in beside.items():
            self.assertNotEqual(row["vs_rs_position"], "at or above the MME", name)
            self.assertLess(row["vs_s_point"]["value"], 0, name)
        self.assertEqual(set(beside), {"B", "V1", "V2", "V3", "V4", "V5", "V6", "C", "CV3"})
        self.assertEqual(self.record["beside_note"],
                         "reported as development evidence; not the reason for the verdict")

    def test_every_figure_rereads_from_its_record_and_no_number_is_typed(self):
        self.assertEqual(v.check_figures(self.record, self.records), [])
        self.assertEqual(v.untyped_numbers(self.record), [])

    def test_a_typed_figure_fails(self):
        typed = copy.deepcopy(self.record)
        typed["estimators"]["C"]["goalpost_2"]["median_points"]["value"] = 3.0
        self.assertTrue(v.check_figures(typed, self.records))
        bare = copy.deepcopy(self.record)
        bare["estimators"]["C"]["goalpost_2"]["median_points"] = 3.46
        self.assertEqual(v.untyped_numbers(bare), ["estimators.C.goalpost_2.median_points"])
        unsourced = copy.deepcopy(self.record)
        del unsourced["estimators"]["C"]["goalpost_2"]["median_points"]["source"]
        self.assertTrue(v.check_figures(unsourced, self.records))

    def test_the_record_is_what_the_tracked_records_build(self):
        self.assertEqual(v.build(ROOT), self.record)

    def test_the_sources_are_the_tracked_files_as_they_are(self):
        self.assertEqual(self.record["sources"], v.source_digests(ROOT))

    def test_the_account_digest_is_the_account_on_main_not_the_archived_one(self):
        """The step-4 account pinned in the verdict is the republished one (#190), not the superseded record (#174).

        Mutation recorded: restoring `sources.distribution_account.sha256` in `results/h7/verdict.json` to the archived
        digest `5b8ee596...20e8` made this test fail with AssertionError.
        """
        pinned = self.record["sources"]["distribution_account"]["sha256"]
        account = ROOT / "results" / "h7" / "distribution-account.json"
        archived = ROOT / "archive" / "h7-distribution-account-5b8ee596" / "distribution-account.json"
        self.assertEqual(pinned, hashlib.sha256(account.read_bytes()).hexdigest())
        self.assertNotEqual(pinned, hashlib.sha256(archived.read_bytes()).hexdigest())

    def test_the_quotes_are_the_files_lines(self):
        quotes = self.record["rule"]["quotes"]
        self.assertEqual([(q["file"], q["lines"]) for q in quotes],
                         [("docs/research/plan.md", [185, 186]), ("docs/research/plan.md", [193, 194]),
                          ("docs/decisions/measurement-protocol.md", [51, 51])])
        for q in quotes:
            lines = (ROOT / q["file"]).read_text(encoding="utf-8").splitlines()
            first, last = q["lines"]
            self.assertEqual(q["text"], "\n".join(lines[first - 1:last]), q["file"])

    def test_the_ruling_is_recorded_with_its_date_and_wording(self):
        r = self.record["ruling"]
        self.assertEqual((r["date"], r["on"], r["option"], r["wording"]), ("2026-10-26", "repo-market-liquidity#181", "(a)", "yep"))
        self.assertIn("Effort then goes to H7f with R+S alone", self.record["plan_consequence"]["quote"])

    def test_the_page_is_what_the_record_renders_to(self):
        self.assertEqual(PAGE.read_text(encoding="utf-8"), v.markdown(self.record))

    def test_nothing_is_claimed_beyond_the_ruling(self):
        text = (RECORD.read_text(encoding="utf-8") + PAGE.read_text(encoding="utf-8")).lower()
        for phrase in FORBIDDEN:
            self.assertNotIn(phrase, text.replace("-", " "))
        for phrase in ("cannot be measured", "can not be measured", "will fail", "h7f will", "h7f would"):
            self.assertNotIn(phrase, text)
        self.assertIn("not an action here", text)

    def test_the_plan_keeps_its_earlier_text_and_gains_a_dated_note(self):
        plan = PLAN.read_text(encoding="utf-8")
        self.assertIn("**Where H7m stands (12 October 2026)**", plan)
        self.assertIn("- **Open:** M2–M12.", plan)
        note = plan.split("**Note (26 October 2026).**", 1)[1].split("\n\n", 1)[0]
        for needle in ("Step 5 is done", "not testable as stated", "docs/stages/h7m-verdict.md", "M8 and later do not apply"):
            self.assertIn(needle, note)


if __name__ == "__main__":
    unittest.main()
