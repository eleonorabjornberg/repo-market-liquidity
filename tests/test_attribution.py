"""H10 step 1: the attribution method on synthetic episodes with planted shares (`docs/decisions/h10-method.md`).

No real episode is attributed here. The synthetic series are generated from a seed; the panel is read only for the
episode list (which days are onsets, cross-checked between the parent's two sources) and for the as-of guard.
"""

import pathlib
import random
import tempfile
import unittest
from datetime import date, time

from repo_model.asof import InformationRule
from repo_model.splits import LookAheadError

from repo_liquidity import attribution, declaration, panel
from repo_liquidity.attribution import BASELINE_DAYS, DRIVERS, SPREAD, WINDOW_DAYS

BETA = {"treasury_settlement": 0.04, "tga": 0.02, "reserve_balances": -0.01, "quarter_end": 8.0}


def synthetic(episodes, *, n=360, noise=0.0, extra=None, seed=7):
    """Drivers as persistent random walks, a spread that is exactly BETA times them plus noise, and a planted jump of
    each driver at each episode start. `extra` maps an episode start to a residual added to the spread over its
    window. Returns the series and the planted shares of each episode."""
    rng = random.Random(seed)
    level = {"treasury_settlement": 100.0, "tga": 400.0, "reserve_balances": 3000.0}
    series = {name: [] for name in DRIVERS}
    jumps = {}
    for start in episodes:
        jumps[start] = {
            "treasury_settlement": rng.uniform(150, 300),
            "tga": rng.uniform(100, 250),
            "reserve_balances": -rng.uniform(150, 400),
        }
    for t in range(n):
        for name in level:
            level[name] += rng.gauss(0, {"treasury_settlement": 15, "tga": 10, "reserve_balances": 20}[name])
            series[name].append(level[name])
        series["quarter_end"].append(0.0)
    # apply the jumps as temporary displacements of the window days only
    for start in episodes:
        for t in range(start, start + WINDOW_DAYS):
            for name, jump in jumps[start].items():
                series[name][t] += jump
    for q in range(40, n, 60):
        series["quarter_end"][q] = 1.0
    spread = []
    for t in range(n):
        value = sum(BETA[name] * series[name][t] for name in DRIVERS) + rng.gauss(0, noise)
        spread.append(value)
    for start, add in (extra or {}).items():
        for t in range(start, start + WINDOW_DAYS):
            spread[t] += add
    series[SPREAD] = spread
    return series


def planted(series, start):
    """The true shares of the observed rise, from the planted coefficients."""
    rise = attribution.change(series[SPREAD], start)
    parts = {name: BETA[name] * attribution.change(series[name], start) for name in DRIVERS}
    return rise, {name: v / rise for name, v in parts.items()}, 1 - sum(parts.values()) / rise


class RecoveryTests(unittest.TestCase):
    def test_with_no_noise_and_no_planted_residual_the_residual_is_zero(self):
        series = synthetic([100, 200])
        for start in (100, 200):
            result = attribution.attribute(series, start, draws=20)
            self.assertEqual(result.status, "attributed")
            self.assertAlmostEqual(result.residual_share, planted(series, start)[2], places=6)
            self.assertLess(abs(result.residual_share), 1e-6)

    def test_with_orthogonal_drivers_the_shares_are_exactly_coefficient_times_change(self):
        xtx = [[2.0 if i == j else 0.0 for j in range(3)] for i in range(3)]
        xty = [4.0, -2.0, 6.0]  # coefficients 2, -1, 3
        d = [1.0, 2.0, 0.5]
        shares, residual, explained = attribution._shares(xtx, xty, d, rise=4.0)
        self.assertAlmostEqual(shares[0], 2.0 / 4.0)
        self.assertAlmostEqual(shares[1], -2.0 / 4.0)
        self.assertAlmostEqual(shares[2], 1.5 / 4.0)
        self.assertAlmostEqual(residual, (4.0 - 1.5) / 4.0)
        self.assertAlmostEqual(explained, 1.5 / 4.0)

    def test_shares_and_residual_sum_to_one(self):
        series = synthetic([100, 200], noise=0.3)
        result = attribution.attribute(series, 100, draws=20)
        self.assertAlmostEqual(sum(result.shares.values()) + result.residual_share, 1.0, places=9)

    def test_a_planted_residual_is_recovered_and_the_episode_does_not_fit_itself(self):
        """Leave-episode-out: the residual added to the episode's own window must stay a residual. Were the episode in
        its own fitting sample, the regression would absorb part of it into the drivers."""
        series = synthetic([100, 200], extra={100: 3.0})
        rise, _, _ = planted(series, 100)
        result = attribution.attribute(series, 100, draws=20)
        self.assertAlmostEqual(result.residual_share, 3.0 / rise, places=6)
        self.assertGreater(result.residual_share, 0.05)

    def test_a_dominant_residual_is_reported_as_one(self):
        series = synthetic([100], extra={100: 60.0})
        result = attribution.attribute(series, 100, draws=20)
        self.assertGreater(result.residual_share, 0.5)
        self.assertFalse(result.residual_under_bar)

    def test_the_interval_covers_the_planted_share_at_about_the_nominal_rate(self):
        """The shares are Shapley values over refitted sub-models, so chance correlation between drivers moves a point
        share away from its planted value (the record, section 2); the interval is what must cover it, at about 90%
        (30 seeded replications, each of the four shares and the residual; the floor is 0.80)."""
        for noise in (0.0, 0.35):
            covered = total = 0
            for seed in range(30):
                series = synthetic([100], noise=noise, seed=seed)
                result = attribution.attribute(series, 100, draws=150, seed=seed)
                _, shares, residual = planted(series, 100)
                for name in DRIVERS:
                    lo, hi = result.intervals[name]
                    covered += lo <= shares[name] <= hi
                    total += 1
                lo, hi = result.residual_interval
                covered += lo <= residual <= hi
                total += 1
            self.assertGreaterEqual(covered / total, 0.80, f"noise {noise}: coverage {covered}/{total}")

    def test_the_same_seed_gives_the_same_interval(self):
        series = synthetic([100], noise=0.3)
        a = attribution.attribute(series, 100, draws=40, seed=5)
        b = attribution.attribute(series, 100, draws=40, seed=5)
        self.assertEqual(a.intervals, b.intervals)


class ShapleyTests(unittest.TestCase):
    def test_the_shares_add_up_to_the_full_model(self):
        values = {(): 0.0, (0,): 1.0, (1,): 2.0, (0, 1): 4.0}
        phi = attribution.shapley(values, 2)
        self.assertAlmostEqual(sum(phi), 4.0)
        self.assertAlmostEqual(phi[0], 1.5)
        self.assertAlmostEqual(phi[1], 2.5)

    def test_a_driver_that_adds_nothing_gets_nothing(self):
        values = {(): 0.0, (0,): 3.0, (1,): 0.0, (0, 1): 3.0}
        self.assertAlmostEqual(attribution.shapley(values, 2)[1], 0.0)


class MissingDataTests(unittest.TestCase):
    def test_an_episode_with_a_missing_input_is_not_attributable_and_is_counted(self):
        series = synthetic([100, 200])
        series["tga"][198] = None
        series = {k: list(v) for k, v in series.items()}
        results = [attribution.attribute(series, s, draws=20) for s in (100, 200)]
        self.assertEqual([r.status for r in results], ["attributed", "not attributable"])
        self.assertIn("missing", results[1].reason)
        summary = attribution.outcome(results)
        self.assertEqual(summary["episodes"], 2)
        self.assertEqual(summary["not_attributable"], 1)

    def test_an_incomplete_window_at_the_end_is_not_attributable(self):
        series = synthetic([100], n=300)
        self.assertEqual(attribution.attribute(series, 297, draws=5).status, "not attributable")

    def test_a_window_with_no_rise_is_not_attributable(self):
        series = synthetic([100])
        series[SPREAD] = [1.0] * len(series[SPREAD])
        result = attribution.attribute(series, 100, draws=5)
        self.assertEqual(result.status, "not attributable")


class OutcomeRuleTests(unittest.TestCase):
    def _a(self, residual):
        return attribution.Attribution(0, "attributed", residual_share=residual)

    def test_drivers_named_needs_more_than_half_under_the_bar(self):
        named = [self._a(0.1), self._a(0.2), self._a(0.9)]
        self.assertEqual(attribution.outcome(named)["outcome"], "drivers named")
        split = [self._a(0.1), self._a(0.9)]
        self.assertEqual(attribution.outcome(split)["outcome"], "residual dominates")

    def test_a_not_attributable_episode_is_a_miss_in_the_denominator(self):
        results = [self._a(0.1), attribution.Attribution(1, "not attributable", "x")]
        summary = attribution.outcome(results)
        self.assertEqual((summary["under_bar"], summary["episodes"]), (1, 2))
        self.assertEqual(summary["outcome"], "residual dominates")

    def test_the_bar_is_the_plans(self):
        self.assertEqual(attribution.RESIDUAL_BAR, 0.5)
        self.assertEqual(attribution.MAJORITY, 0.5)


class PlaceboTests(unittest.TestCase):
    def test_placebo_windows_touch_no_episode_and_share_the_day_type(self):
        series = synthetic([100, 200])
        series["quarter_end"][200] = 1.0
        picks = attribution.placebo_starts(series, [100, 200], per_episode=4)
        gap = BASELINE_DAYS + WINDOW_DAYS
        for onset, starts in picks.items():
            self.assertTrue(starts)
            for t in starts:
                self.assertTrue(all(abs(t - o) >= gap for o in (100, 200)))
                self.assertEqual(attribution._day_type(series, t), attribution._day_type(series, onset))
        self.assertEqual(picks, attribution.placebo_starts(series, [100, 200], per_episode=4))


class DevelopmentGuardTests(unittest.TestCase):
    def test_a_date_after_the_development_tier_is_refused(self):
        """Leakage guard: the development tier ends 2026-09-03 (plan, Q5); the model repo's lockbox holds the rest.

        Recorded mutation (13 October 2026): in `attribution.check_development`, `d > DEVELOPMENT_END` changed to
        `d > date(2100, 1, 1)`. `test_a_date_after_the_development_tier_is_refused` then fails with AssertionError:
        LookAheadError not raised.
        """
        attribution.check_development([date(2026, 9, 3)])
        with self.assertRaises(LookAheadError):
            attribution.check_development([date(2026, 9, 3), date(2026, 9, 4)])


class PanelTests(unittest.TestCase):
    """The episode source and the as-of guard, on the tracked panel (version 1, the published columns)."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        path = pathlib.Path(cls.tmp.name) / "phase3_panel.csv"
        panel.build(path, version=1)
        from repo_model.data import load_daily_panel

        cls.rows = [r for r in load_daily_panel(path) if r.date <= attribution.DEVELOPMENT_END]
        cls.dates = [r.date for r in cls.rows]

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_both_onset_sources_agree_on_the_panel(self):
        found = attribution.cross_check_onsets(self.rows)
        self.assertTrue(found)

    def test_the_sources_disagreeing_is_refused(self):
        from unittest import mock

        with mock.patch("repo_model.pressure.onsets", return_value=()):
            with self.assertRaises(ValueError):
                attribution.cross_check_onsets(self.rows)

    def test_the_series_carry_every_driver_for_every_row(self):
        series = attribution.series_from_rows(self.rows)
        self.assertEqual(set(series), {SPREAD, *DRIVERS})
        self.assertTrue(all(len(v) == len(self.rows) for v in series.values()))

    def _rule(self):
        return InformationRule(declaration.registry(), list(DRIVERS), decision_time=time(16, 0))

    def test_a_window_is_public_a_few_weeks_after_its_onset(self):
        onset = attribution.episode_onsets(self.rows)[3]
        rule = self._rule()
        attribution.check_window_public(rule, self.dates, onset, onset + WINDOW_DAYS + 10)

    def test_a_window_read_at_its_own_onset_is_leakage(self):
        """Leakage guard: the window's inputs are not public at the instant the onset is decided.

        Recorded mutation (13 October 2026): in `attribution.check_window_public`, `available > deadline` changed to
        `available > datetime.max`. `test_a_window_read_at_its_own_onset_is_leakage` then fails with AssertionError:
        LookAheadError not raised.
        """
        onset = attribution.episode_onsets(self.rows)[3]
        rule = self._rule()
        with self.assertRaises(LookAheadError):
            attribution.check_window_public(rule, self.dates, onset, onset + 1)


if __name__ == "__main__":
    unittest.main()
