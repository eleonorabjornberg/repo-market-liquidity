"""HX step 3 (M2, #214): the candidate set, the benchmarks and the variant count, declared before any is run.

`docs/research/dispersion-candidates.md` is the draft for Eleonora. Nothing is run, fitted or scored here: the tests pin
what the page declares, so a later change to the set or the count is a visible edit.
"""

import pathlib
import re
import unittest

from repo_liquidity import dispersion_candidates as cand
from repo_liquidity import dispersion_estimator as w1

ROOT = pathlib.Path(__file__).resolve().parents[1]
PAGE = (ROOT / "docs/research/dispersion-candidates.md").read_text(encoding="utf-8")
HYPOTHESIS = (ROOT / "docs/research/dispersion-volume-hypothesis.md").read_text(encoding="utf-8")


class CandidateSetTests(unittest.TestCase):
    def test_the_default_set_is_w1_alone(self):
        self.assertEqual(cand.CANDIDATES, ("W1",))

    def test_the_only_candidate_is_the_estimator_step_2_declared(self):
        self.assertEqual(cand.PRIMARY, "W1")
        self.assertEqual(cand.INPUTS_OF["W1"], (w1.LEFT_COLUMN,))

    def test_every_candidate_reads_inputs_from_the_declared_five(self):
        from repo_liquidity import dispersion_volume

        declared = {i.name for i in dispersion_volume.INPUTS}
        self.assertEqual(len(declared), 5)
        for name in cand.CANDIDATES:
            self.assertLessEqual(set(cand.INPUTS_OF[name]), declared)

    def test_the_benchmarks_are_r_s_and_r_plus_s_unchanged(self):
        self.assertEqual(cand.BENCHMARKS, ("R", "S", "R+S"))


class VariantCountTests(unittest.TestCase):
    def test_the_count_in_play_is_13_with_11_variants(self):
        self.assertEqual(cand.ESTIMATORS_IN_PLAY, 13)
        self.assertEqual(cand.VARIANTS_IN_PLAY, 11)

    def test_declaring_w1_as_the_candidate_adds_nothing_to_what_step_2_counted(self):
        self.assertEqual(cand.ADDED_AT_M2, 0)
        self.assertEqual(cand.ESTIMATORS_IN_PLAY, w1.VARIANTS_IN_PLAY)

    def test_each_further_candidate_would_add_one(self):
        self.assertEqual(cand.count_with(("W1",)), 13)
        self.assertEqual(cand.count_with(("W1", "W2")), 14)

    def test_the_hypothesis_page_carries_the_same_count(self):
        self.assertRegex(HYPOTHESIS, r"count in play is 13, 11 of them variants")

    def test_the_candidates_page_states_the_count_and_the_set(self):
        self.assertIn("13 estimators in play, 11 of them variants", PAGE)
        self.assertIn("W1 alone", PAGE)
        self.assertNotRegex(PAGE, r"count in play is 1[4-9]")


class PageTests(unittest.TestCase):
    def test_the_page_restates_the_three_benchmarks(self):
        for name in ("**R:**", "**S:**", "**R+S:**"):
            self.assertIn(name, PAGE)

    def test_the_page_says_nothing_is_run_fitted_or_scored(self):
        self.assertRegex(PAGE, r"Nothing is run, fitted or scored")

    def test_the_page_has_a_marked_question_with_numbered_options_and_a_default(self):
        self.assertRegex(PAGE, r"(?m)^1\. \*\*W1 alone")
        self.assertRegex(PAGE, r"(?m)^2\. ")
        self.assertIn("Default", PAGE)

    def test_the_hypothesis_page_points_to_the_declaration(self):
        self.assertIn("dispersion-candidates.md", HYPOTHESIS)


if __name__ == "__main__":
    unittest.main()
