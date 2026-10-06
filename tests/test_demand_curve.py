"""Stage 2: the reserve demand curve and the location of its bend (`docs/decisions/stage-2-bend.md`)."""

import random
import unittest
from datetime import date

from repo_model.splits import LookAheadError

from repo_liquidity import demand_curve as dc


def synthetic(kink, n=800, seed=1):
    rng = random.Random(seed)
    xs = [0.08 + 0.10 * rng.random() for _ in range(n)]
    ys = [1.0 + 400.0 * max(kink - x, 0.0) + rng.gauss(0, 1.0) for x in xs]
    return xs, ys


class FitTests(unittest.TestCase):
    def test_the_broken_stick_recovers_a_known_bend(self):
        xs, ys = synthetic(0.12)
        fit = dc.fit_broken_stick(xs, ys)
        self.assertAlmostEqual(fit.kink, 0.12, delta=0.002)
        self.assertGreater(fit.slope, 0)

    def test_the_fit_is_invariant_to_row_order(self):
        xs, ys = synthetic(0.11)
        order = list(range(len(xs)))
        random.Random(2).shuffle(order)
        self.assertEqual(dc.fit_broken_stick(xs, ys).kink,
                         dc.fit_broken_stick([xs[i] for i in order], [ys[i] for i in order]).kink)

    def test_the_interval_covers_the_bend_and_is_reproducible(self):
        xs, ys = synthetic(0.12, n=400)
        first = dc.kink_interval(xs, ys, seed=7, replications=100)
        self.assertEqual(first, dc.kink_interval(xs, ys, seed=7, replications=100))
        self.assertLessEqual(first[0], 0.12)
        self.assertGreaterEqual(first[1], 0.12)


class RuleTests(unittest.TestCase):
    def test_the_rule_passes_when_regimes_overlap_and_the_pooled_interval_is_sharp(self):
        verdict = dc.stability_verdict(pooled=(0.115, 0.125), regimes={"a": (0.11, 0.12), "b": (0.12, 0.13)})
        self.assertTrue(verdict["shown"])

    def test_the_rule_fails_on_a_regime_that_does_not_overlap(self):
        verdict = dc.stability_verdict(pooled=(0.115, 0.125), regimes={"a": (0.13, 0.15)})
        self.assertFalse(verdict["shown"])
        self.assertEqual(verdict["non_overlapping"], ["a"])

    def test_the_rule_fails_on_a_wide_pooled_interval(self):
        verdict = dc.stability_verdict(pooled=(0.10, 0.135), regimes={"a": (0.11, 0.12)})
        self.assertFalse(verdict["shown"])
        self.assertFalse(verdict["pooled_sharp"])

    def test_the_rule_fails_with_no_eligible_regime(self):
        self.assertFalse(dc.stability_verdict(pooled=(0.115, 0.125), regimes={})["shown"])

    def test_eligibility_counts_scarce_days(self):
        self.assertEqual(dc.scarce_days([0.12, 0.129, 0.13, 0.14]), 2)


class WindowTests(unittest.TestCase):
    def test_a_day_in_2026_is_refused(self):
        """Leakage guard: Stage 2 reads nothing the parent's lockbox holds.

        Recorded mutation (6 October 2026): in `demand_curve.require_window`, the lines
        `require_unlocked(days, where="Stage 2 demand curve")` and `late = [day for day in days if day > LAST_DAY]`
        replaced by `late = []`. This test then fails with AssertionError: LookAheadError not raised.
        """
        with self.assertRaises(LookAheadError):
            dc.require_window([date(2025, 12, 31), date(2026, 1, 2)])


if __name__ == "__main__":
    unittest.main()
