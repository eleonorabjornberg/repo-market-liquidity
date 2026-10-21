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

from lockbox_helper import moved_lockbox
from repo_liquidity import attribution, declaration, development, panel
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
            result = attribution.attribute_synthetic(series, start, draws=20)
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

    def test_fixed_coefficient_shares_equal_coefficient_times_change_over_rise(self):
        """H10 method v1, section 2: beta_j * dx_j / rise from the full model's coefficients, reported beside the
        Shapley shares. Known coefficients 2, -1, 3 on an orthogonal design."""
        xtx = [[2.0 if i == j else 0.0 for j in range(3)] for i in range(3)]
        xty = [4.0, -2.0, 6.0]
        fixed = attribution._fixed_shares(xtx, xty, [1.0, 2.0, 0.5], rise=4.0)
        self.assertEqual(len(fixed), 3)
        for got, want in zip(fixed, (2.0 / 4.0, -2.0 / 4.0, 1.5 / 4.0)):
            self.assertAlmostEqual(got, want)

    def test_an_attributed_episode_carries_fixed_shares_that_match_the_planted_ones(self):
        series = synthetic([100, 200])
        result = attribution.attribute_synthetic(series, 100, draws=20)
        _, true_shares, _ = planted(series, 100)
        self.assertEqual(set(result.fixed_shares), set(DRIVERS))
        for name in DRIVERS:
            self.assertAlmostEqual(result.fixed_shares[name], true_shares[name], places=6)

    def test_shares_and_residual_sum_to_one(self):
        series = synthetic([100, 200], noise=0.3)
        result = attribution.attribute_synthetic(series, 100, draws=20)
        self.assertAlmostEqual(sum(result.shares.values()) + result.residual_share, 1.0, places=9)

    def test_a_planted_residual_is_recovered_and_the_episode_does_not_fit_itself(self):
        """Leave-episode-out: the residual added to the episode's own window must stay a residual. Were the episode in
        its own fitting sample, the regression would absorb part of it into the drivers."""
        series = synthetic([100, 200], extra={100: 3.0})
        rise, _, _ = planted(series, 100)
        result = attribution.attribute_synthetic(series, 100, draws=20)
        self.assertAlmostEqual(result.residual_share, 3.0 / rise, places=6)
        self.assertGreater(result.residual_share, 0.05)

    def test_a_dominant_residual_is_reported_as_one(self):
        series = synthetic([100], extra={100: 60.0})
        result = attribution.attribute_synthetic(series, 100, draws=20)
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
                result = attribution.attribute_synthetic(series, 100, draws=150, seed=seed)
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
        a = attribution.attribute_synthetic(series, 100, draws=40, seed=5)
        b = attribution.attribute_synthetic(series, 100, draws=40, seed=5)
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
        results = [attribution.attribute_synthetic(series, s, draws=20) for s in (100, 200)]
        self.assertEqual([r.status for r in results], ["attributed", "not attributable"])
        self.assertIn("missing", results[1].reason)
        summary = attribution.outcome(results)
        self.assertEqual(summary["episodes"], 2)
        self.assertEqual(summary["not_attributable"], 1)

    def test_an_incomplete_window_at_the_end_is_not_attributable(self):
        series = synthetic([100], n=300)
        self.assertEqual(attribution.attribute_synthetic(series, 297, draws=5).status, "not attributable")

    def test_a_window_with_no_rise_is_not_attributable(self):
        series = synthetic([100])
        series[SPREAD] = [1.0] * len(series[SPREAD])
        result = attribution.attribute_synthetic(series, 100, draws=5)
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
    def test_the_decided_count_is_twenty_windows_per_episode(self):
        """H10 method v1, section 4 (Eleonora's ruling on #37): 20 placebo windows per episode, fixed seed."""
        self.assertEqual(attribution.PLACEBO_WINDOWS, 20)
        series = synthetic([130, 250])
        series["treasury_settlement"] = [v + 5000.0 for v in series["treasury_settlement"]]  # all one day type
        picks = attribution.placebo_starts(series, [130, 250])
        gap = BASELINE_DAYS + WINDOW_DAYS
        for onset, starts in picks.items():
            self.assertEqual(len(starts), 20)
            self.assertEqual(len(set(starts)), 20)
            self.assertTrue(all(abs(t - o) >= gap for t in starts for o in (130, 250)))
        self.assertEqual(picks, attribution.placebo_starts(series, [130, 250]))

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
        """Leakage guard: the development tier ends where the model repo's lockbox says (one lockbox, plan Q5).

        `check_development` calls the parent's `lockbox.require_unlocked`; this module holds no copy of the end date.
        Recorded mutation (14 October 2026): in `attribution.check_development`, the call
        `lockbox.require_unlocked(dates, where="attribution")` replaced by `pass`.
        `test_a_date_after_the_development_tier_is_refused` then fails with AssertionError: LookAheadError not raised.
        """
        attribution.check_development([date(2026, 9, 3)])
        with self.assertRaises(LookAheadError):
            attribution.check_development([date(2026, 9, 3), date(2026, 9, 4)])

    def test_the_end_follows_the_parents_lockbox_not_a_copy(self):
        """Leakage guard: moving the parent's locked tier moves the end here (no second lockbox to drift).

        Recorded mutation (14 October 2026): in `attribution.check_development`, the parent's call replaced by
        `late = [d for d in dates if d > date(2026, 9, 3)]` raising `LookAheadError` for any such date. This test then
        errors with LookAheadError: late, raised for 2026-09-10, whose tier the patched lockbox leaves open.
        """
        with moved_lockbox(date(2026, 12, 1)):
            attribution.check_development([date(2026, 9, 10)])
            with self.assertRaises(LookAheadError):
                attribution.check_development([date(2026, 12, 1)])

    def test_there_is_no_copy_of_the_end_date(self):
        self.assertFalse(hasattr(attribution, "DEVELOPMENT_END"))


class PanelTests(unittest.TestCase):
    """The episode source and the as-of guard, on the tracked panel (version 1, the published columns)."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        path = pathlib.Path(cls.tmp.name) / "phase3_panel.csv"
        panel.build(path, version=4)
        from repo_model.data import load_daily_panel

        cls.rows = [r for r in load_daily_panel(path) if r.date <= development.development_end()]
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

    def test_the_spread_alone_must_be_public_at_the_report(self):
        """Leakage guard: the outcome's own publication time is checked, not only the drivers'.

        The rule's first group is the spread (SOFR - IORB). With only the calendar driver declared, the spread is the
        one input the check can fail on. Recorded mutation (14 October 2026): in `attribution.check_window_public`,
        `for group in rule.groups:` changed to `for group in rule.groups[1:]:`. This test then fails with
        AssertionError: LookAheadError not raised.
        """
        onset = attribution.episode_onsets(self.rows)[3]
        rule = InformationRule(declaration.registry(), ["quarter_end"], decision_time=time(16, 0))
        self.assertEqual([group.feature for group in rule.groups], [SPREAD, "quarter_end"])
        attribution.check_window_public(rule, self.dates, onset, onset + WINDOW_DAYS + 10)
        with self.assertRaises(LookAheadError):
            attribution.check_window_public(rule, self.dates, onset, onset + 1)

    def test_attribute_refuses_a_window_whose_spread_was_not_public(self):
        """Leakage guard: `attribute` runs `check_window_public` when it is given the rule, dates and report index.

        Recorded mutation (14 October 2026): in `attribution.attribute`, the call `check_window_public(rule, dates,
        start, report_index)` replaced by `pass`. This test then fails with AssertionError: LookAheadError not raised.
        """
        series = attribution.series_from_rows(self.rows)
        onset = attribution.episode_onsets(self.rows)[3]
        rule = self._rule()
        kwargs = dict(rule=rule, dates=self.dates, draws=10)
        with self.assertRaises(LookAheadError):
            attribution.attribute(series, onset, report_index=onset + 1, **kwargs)
        result = attribution.attribute(series, onset, report_index=onset + WINDOW_DAYS + 10, **kwargs)
        self.assertIn(result.status, ("attributed", "not attributable"))

    def test_a_real_data_call_needs_all_three_arguments(self):
        """Leakage guard: `attribute` (the real-data entry point) refuses a call without the rule, the dates and the
        report index, or with only some of them (Eleonora's ruling on PR #61, 14 October 2026: required from H10 step 2).

        Recorded mutation (14 October 2026): in `attribution.attribute`, `if len(missing) > 0:` changed to
        `if len(missing) > 3:` (no call is ever refused for a missing argument). The first case then fails with
        AttributeError: 'NoneType' object has no attribute 'decision_instant' (the unchecked call reaches the guard).
        """
        series = attribution.series_from_rows(self.rows)
        onset = attribution.episode_onsets(self.rows)[3]
        for partial in ({}, {"rule": self._rule()}, {"dates": self.dates}, {"report_index": onset + 20},
                        {"rule": self._rule(), "dates": self.dates}):
            with self.assertRaises(ValueError):
                attribution.attribute(series, onset, draws=10, **partial)

    def test_the_synthetic_entry_point_takes_no_dates_and_the_real_one_is_not_it(self):
        series = synthetic([100], noise=0.3)
        self.assertEqual(attribution.attribute_synthetic(series, 100, draws=5).status, "attributed")
        with self.assertRaises(ValueError):
            attribution.attribute(series, 100, draws=5)


# ---------------------------------------------------------------------------------------------------------------
# Amendment (Eleonora, 14 October 2026; finding #52): a selection-aware null, and ON RRP as a driver. Synthetic only.

SLOPE = {"treasury_settlement": 0.04, "tga": 0.02, "reserve_balances": -0.01, "quarter_end": 3.0, "on_rrp": -0.015}
SPREAD_NOISE_BP = 1.6


def episodic(episodes, *, n=1500, seed=3, planted=True, drivers=DRIVERS, noise=SPREAD_NOISE_BP):
    """Stationary drivers and a spread (bp) of `noise` plus, when `planted`, the drivers' effect through SLOPE.
    At each episode start every driver jumps for the five window days, so the planted spread rises by about 16 bp (20 with ON RRP).
    With `planted=False` the spread is pure noise and carries no driver effect at all."""
    rng = random.Random(seed)
    spread_sd = {"treasury_settlement": 30.0, "tga": 20.0, "reserve_balances": 40.0, "on_rrp": 40.0}
    jump = {"treasury_settlement": 250.0, "tga": 150.0, "reserve_balances": -300.0, "on_rrp": -250.0}
    series = {name: [rng.gauss(0, spread_sd[name]) for _ in range(n)] for name in drivers if name != "quarter_end"}
    series["quarter_end"] = [1.0 if t % 70 == 40 else 0.0 for t in range(n)]
    for start in episodes:
        for t in range(start, start + WINDOW_DAYS):
            for name in series:
                if name in jump:
                    series[name][t] += jump[name]
    series = {name: series[name] for name in drivers}
    spread = [rng.gauss(0, noise) for _ in range(n)]
    if planted:
        for t in range(n):
            spread[t] += sum(SLOPE[name] * series[name][t] for name in drivers)
    series[SPREAD] = spread
    return series


class SelectionNullTests(unittest.TestCase):
    """H10 method, amendment (a): the placebo windows are picked by the same onset rule from a spread that carries no
    driver effect; an episode counts as attributed only if its explained share beats that null."""

    EPISODES = [150, 400, 650, 900, 1150, 1400]

    def test_the_null_rejects_an_episode_planted_with_a_real_driver_effect(self):
        series = episodic(self.EPISODES)
        null = attribution.selection_null(series, draws=40)
        self.assertGreater(null.episodes, 20)
        for start in self.EPISODES:
            self.assertIn(start, attribution.rule_onsets(series[SPREAD]))
            result = attribution.attribute_synthetic(series, start, draws=10)
            self.assertTrue(attribution.beats_null(result, null), (start, result.explained_share, null.bar))

    def test_the_null_does_not_reject_episodes_the_rule_picked_from_pure_noise(self):
        """The finding's selection effect: onsets chosen on the spread itself. Of the onsets the rule picks from a spread
        with no driver effect, only about the null's tail (5%) may beat it."""
        series = episodic([], planted=False, n=2400, noise=2.5)
        starts = attribution.rule_onsets(series[SPREAD])
        self.assertGreater(len(starts), 20)
        null = attribution.selection_null(series, draws=60)
        results = [attribution.point_attribution(series, s) for s in starts]
        beats = sum(attribution.beats_null(r, null) for r in results if r.status == "attributed")
        attributed = sum(r.status == "attributed" for r in results)
        self.assertLessEqual(beats / attributed, 0.20)

    def test_the_bar_is_the_decided_quantile_of_the_null_and_is_reproducible(self):
        series = episodic(self.EPISODES)
        a = attribution.selection_null(series, draws=20, seed=11)
        b = attribution.selection_null(series, draws=20, seed=11)
        self.assertEqual(a, b)
        self.assertEqual(attribution.NULL_QUANTILE, 0.95)
        ranked = sorted(a.explained)
        self.assertAlmostEqual(a.bar, attribution._percentile(ranked, attribution.NULL_QUANTILE))

    def test_a_null_that_selects_no_episode_is_refused(self):
        """A spread fully carried by the drivers has nothing for the rule to pick once their effect is removed."""
        series = episodic(self.EPISODES, noise=0.05)
        with self.assertRaises(ValueError):
            attribution.selection_null(series, draws=5)

    def test_an_episode_that_is_not_attributable_never_beats_the_null(self):
        null = attribution.SelectionNull(bar=0.1, quantile=0.95, draws=1, episodes=1, explained=(0.1,))
        self.assertFalse(attribution.beats_null(attribution.Attribution(0, "not attributable", "x"), null))

    def test_the_outcome_counts_an_episode_only_if_it_is_under_the_bar_and_beats_the_null(self):
        null = attribution.SelectionNull(bar=0.5, quantile=0.95, draws=1, episodes=1, explained=(0.5,))
        under = attribution.Attribution(0, "attributed", residual_share=0.3, explained_share=0.7)
        weak = attribution.Attribution(1, "attributed", residual_share=0.45, explained_share=0.4)
        summary = attribution.outcome_with_null([under, weak], null)
        self.assertEqual((summary["under_bar"], summary["beats_null"], summary["counted"]), (2, 1, 1))
        self.assertEqual(summary["outcome"], "residual dominates")

    def test_the_surrogate_spread_carries_no_driver_effect(self):
        series = episodic(self.EPISODES)
        removed = attribution.driver_free_spread(series, DRIVERS)
        beta = attribution.coefficients({**series, SPREAD: removed}, DRIVERS)
        for name, value in beta.items():
            self.assertAlmostEqual(value, 0.0, places=6, msg=name)


class OnRrpDriverTests(unittest.TestCase):
    """H10 method, amendment (b): ON RRP as a driver, entering as the window change like every other driver."""

    def test_the_proposed_driver_set_adds_on_rrp_last_and_leaves_the_decided_set_alone(self):
        self.assertEqual(attribution.DRIVERS, ("treasury_settlement", "tga", "reserve_balances", "quarter_end"))
        self.assertEqual(attribution.DRIVERS_WITH_ON_RRP, attribution.DRIVERS + ("on_rrp",))

    def test_the_on_rrp_driver_recovers_a_planted_coefficient(self):
        drivers = attribution.DRIVERS_WITH_ON_RRP
        series = episodic([150, 400, 650, 900, 1150], noise=0.3, drivers=drivers)
        beta = attribution.coefficients(series, drivers)
        self.assertAlmostEqual(beta["on_rrp"], SLOPE["on_rrp"], delta=0.002)
        result = attribution.attribute_synthetic(series, 400, drivers=drivers, draws=30)
        self.assertEqual(result.status, "attributed")
        self.assertIn("on_rrp", result.shares)
        planted_share = SLOPE["on_rrp"] * attribution.change(series["on_rrp"], 400) / result.rise_bp
        self.assertAlmostEqual(result.fixed_shares["on_rrp"], planted_share, delta=0.05)
        self.assertGreater(result.fixed_shares["on_rrp"], 0.1)

    def test_a_driver_with_no_effect_gets_a_coefficient_near_zero(self):
        drivers = attribution.DRIVERS_WITH_ON_RRP
        series = episodic([150, 400, 650, 900, 1150], noise=0.3, drivers=drivers)
        rng = random.Random(9)
        series["on_rrp"] = [rng.gauss(0, 40) for _ in series[SPREAD]]
        self.assertLess(abs(attribution.coefficients(series, drivers)["on_rrp"]), 0.01)

    def test_series_from_rows_reads_the_driver_it_is_given(self):
        from types import SimpleNamespace

        rows = [SimpleNamespace(spread_bps=1.0, values={"on_rrp": 2.5, "treasury_settlement": 1.0, "tga": 1.0,
                                                        "reserve_balances": 1.0, "quarter_end": 0.0})]
        series = attribution.series_from_rows(rows, attribution.DRIVERS_WITH_ON_RRP)
        self.assertEqual(series["on_rrp"], [2.5])
        self.assertNotIn("on_rrp", attribution.series_from_rows(rows))

    def test_an_on_rrp_input_not_public_at_the_report_is_leakage(self):
        """Leakage guard: ON RRP is checked on its own declaration, not only the spread's. The stub rule publishes the
        spread early and ON RRP after the report instant (on the registry's real declarations the spread is the later
        input, so only a stub can make ON RRP the binding one).

        Recorded mutation (14 October 2026): in `attribution.check_window_public`, `for group in rule.groups:` changed
        to `for group in rule.groups[:1]:`. This test then fails with AssertionError: LookAheadError not raised.
        """
        from datetime import datetime
        from types import SimpleNamespace

        dates = [date(2026, 1, 1 + i) for i in range(30)]
        deadline = datetime(2026, 1, 25, 16, 0)
        late = datetime(2026, 1, 26, 9, 0)
        groups = [SimpleNamespace(feature=SPREAD, kind="data", fields=("s",)),
                  SimpleNamespace(feature="on_rrp", kind="data", fields=("r",))]
        rule = SimpleNamespace(
            groups=groups,
            decision_instant=lambda d, i: deadline,
            availability=lambda d, fields, i: late if fields == ("r",) else datetime(2026, 1, 1),
        )
        with self.assertRaises(LookAheadError):
            attribution.check_window_public(rule, dates, 12, 20)
        rule.availability = lambda d, fields, i: datetime(2026, 1, 1)
        attribution.check_window_public(rule, dates, 12, 20)


if __name__ == "__main__":
    unittest.main()
