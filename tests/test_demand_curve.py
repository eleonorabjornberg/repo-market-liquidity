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


class RevisedTests(unittest.TestCase):
    """The post-hoc revised test (`docs/decisions/stage-2-bend.md`, amendment of 6 October 2026)."""

    def test_the_episodes_are_as_written(self):
        self.assertEqual(dc.EPISODES[0][2], date(2020, 3, 13))
        self.assertEqual(dc.EPISODES[1][1:], (date(2025, 1, 1), date(2025, 12, 31)))
        self.assertEqual(dc.MIN_SCARCE_DAYS_REVISED, 60)

    def test_corridor_position(self):
        self.assertEqual(dc.corridor_position(sofr=5.30, iorb=5.40, on_rrp_rate=5.30), 0.0)
        self.assertEqual(dc.corridor_position(sofr=5.40, iorb=5.40, on_rrp_rate=5.30), 1.0)
        self.assertAlmostEqual(dc.corridor_position(sofr=5.45, iorb=5.40, on_rrp_rate=5.30), 1.5)

    def test_the_revised_rule_needs_both_episodes_sharp(self):
        both = {"e1": {"eligible": True, "interval": (0.11, 0.12)}, "e2": {"eligible": True, "interval": (0.13, 0.14)}}
        self.assertTrue(dc.revised_verdict(both)["shown"])
        wide = dict(both, e2={"eligible": True, "interval": (0.10, 0.14)})
        self.assertFalse(dc.revised_verdict(wide)["shown"])
        short = dict(both, e2={"eligible": False, "interval": (0.13, 0.14)})
        self.assertFalse(dc.revised_verdict(short)["shown"])

    def test_the_shift_interval_covers_a_known_shift(self):
        x1, y1 = synthetic(0.11, n=300, seed=3)
        x2, y2 = synthetic(0.13, n=300, seed=4)
        low, high = dc.shift_interval((x1, y1), (x2, y2), seed=5, replications=100)
        self.assertLessEqual(low, 0.02)
        self.assertGreaterEqual(high, 0.02)
        self.assertEqual((low, high), dc.shift_interval((x1, y1), (x2, y2), seed=5, replications=100))


class OverlapTests(unittest.TestCase):
    def test_the_comparison_uses_only_the_shared_band(self):
        mk = lambda day, ratio, pos: dc.Day(date(2020, 1, day), ratio, 0.0, None, None, pos)
        first = [mk(1, 0.10, 1.0), mk(2, 0.12, 1.0), mk(3, 0.125, 1.0)]
        second = [mk(4, 0.12, 2.0), mk(5, 0.13, 2.0), mk(6, 0.14, 9.0)]
        result = dc.overlap_comparison(first, second, seed=1, replications=50)
        self.assertEqual(result["ratio_band"], [0.12, 0.125])
        self.assertEqual(result["days"], [2, 1])
        self.assertEqual(result["difference"], 1.0)
