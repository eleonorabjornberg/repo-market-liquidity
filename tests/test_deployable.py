"""Stage 6: the deployable-liquidity candidates A and B (`docs/stages/stage-6.md`)."""

import math
import unittest
from datetime import date, timedelta

from repo_model.splits import LookAheadError

from repo_liquidity import anchored, deployable


def _days(start, n):
    out, day = [], start
    while len(out) < n:
        if day.weekday() < 5:
            out.append(day)
        day += timedelta(days=1)
    return out


class AucTests(unittest.TestCase):
    def test_perfect_and_reversed_separation(self):
        self.assertEqual(deployable.auc([1.0, 2.0, 3.0, 4.0], [1, 1, 0, 0]), 1.0)
        self.assertEqual(deployable.auc([1.0, 2.0, 3.0, 4.0], [0, 0, 1, 1]), 0.0)

    def test_ties_count_half(self):
        self.assertEqual(deployable.auc([1.0, 1.0], [1, 0]), 0.5)

    def test_one_class_has_no_score(self):
        self.assertIsNone(deployable.auc([1.0, 2.0], [0, 0]))


class StabilityTests(unittest.TestCase):
    def test_the_bar_is_strict(self):
        verdict = deployable.stability({"2025-01-02": 0.004, "2025-01-03": 0.005}, limit=0.005)
        self.assertFalse(verdict["shown"])
        self.assertEqual(verdict["worst"]["day"], "2025-01-03")
        self.assertTrue(deployable.stability({"2025-01-02": 0.0049}, limit=0.005)["shown"])


class CandidateATests(unittest.TestCase):
    """The curve's bend: the first episode's until the second counts, then the second's."""

    def _sample(self):
        first = _days(date(2018, 4, 3), 400)
        second = _days(date(2025, 1, 2), 200)
        rows = []
        for i, day in enumerate(first):
            x = 0.09 + 0.06 * (i % 50) / 50
            rows.append(deployable.Day(day, x, 0.2 + 8.0 * max(0.115 - x, 0.0) + 0.002 * ((i * 7) % 5)))
        for i, day in enumerate(second):
            x = 0.10 + 0.06 * (i % 40) / 40
            rows.append(deployable.Day(day, x, 0.2 + 8.0 * max(0.15 - x, 0.0) + 0.002 * ((i * 3) % 5)))
        return rows, second

    def test_the_first_episode_bend_holds_until_the_second_counts(self):
        rows, second = self._sample()
        early = deployable.bend_at(rows, cutoff=second[30], replications=50)
        self.assertEqual(early.episode, "2018 to March 2020")
        self.assertAlmostEqual(early.bend, 0.115, places=2)
        late = deployable.bend_at(rows, cutoff=second[-1], replications=50)
        self.assertEqual(late.episode, "2025")
        self.assertAlmostEqual(late.bend, 0.15, places=2)
        self.assertLess(late.lower, late.bend + 1e-12)
        self.assertGreater(late.upper, late.bend - 1e-12)

    def test_days_after_the_cutoff_do_not_move_the_bend(self):
        """The bend is fitted only on days at or before the refit's cutoff.

        Recorded mutation (8 October 2026): in `deployable.bend_at`, the filter
        `seen = [row for row in rows if row.day <= cutoff]` changed to `seen = list(rows)`. This test failed with
        LookAheadError, raised by the guard `require_on_or_before` that follows it.
        """
        rows, second = self._sample()
        cutoff = second[100]
        poisoned = [row if row.day <= cutoff else deployable.Day(row.day, 0.05, 9.9) for row in rows]
        clean = [row for row in rows if row.day <= cutoff]
        self.assertEqual(deployable.bend_at(poisoned, cutoff=cutoff, replications=50),
                         deployable.bend_at(clean, cutoff=cutoff, replications=50))


class CandidateBTests(unittest.TestCase):
    """The latent buffer with a third head: with that head empty, the filter is Stage 3b's."""

    def test_with_no_gap_observations_it_is_stage_3b(self):
        anchor = anchored.Anchor(intercept=0.9, slope=8.0, last_day=date(2019, 1, 1))
        days = _days(date(2019, 1, 2), 60)
        obs3 = [anchored.Observation(d, 0.12 + 0.001 * (i % 7), (0.9 + 0.01 * (i % 3), 3.0 + 0.1 * (i % 4)), "ordinary")
                for i, d in enumerate(days)]
        obs_b = [deployable.ObservationB(o.day, o.x, (o.y[0], o.y[1], None), o.kind) for o in obs3]
        params3 = anchored.start_params(obs3, anchor)
        params_b = deployable.params_b_from_3b(params3)
        path3 = anchored.filter_path(obs3, params3, anchor=anchor, jump_days=[])
        path_b = deployable.filter_path_b(obs_b, params_b, anchor=anchor, jump_days=[])
        for s3, sb in zip(path3, path_b):
            self.assertAlmostEqual(s3.mean, sb.mean, places=12)
            self.assertAlmostEqual(s3.variance, sb.variance, places=12)

    def test_drift_is_held_at_zero(self):
        self.assertLess(deployable.natural_b(deployable.start_params_b_example())[1], 1e-30)

    def test_the_break_grid_is_quarterly_and_before_the_cutoff(self):
        grid = deployable.break_grid(date(2021, 1, 15))
        self.assertEqual(grid[0], date(2020, 4, 1))
        self.assertTrue(all(day <= date(2021, 1, 15) for day in grid))
        self.assertEqual(deployable.break_grid(date(2026, 1, 1))[-1], date(2024, 10, 1))
        self.assertEqual(len(deployable.break_grid(date(2026, 1, 1))), 19)


if __name__ == "__main__":
    unittest.main()
