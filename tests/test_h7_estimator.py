"""H7m, development step 1: the estimand and the as-of estimator (`docs/stages/h7-step1.md`, directive #22).

Deployable liquidity on day T is the parent's reserves ratio at T's decision instant minus the kink of the reserve demand
curve in force at that refit (the parent's `satiation.fit_level`), with a 90% interval and the parent's scarcity state
beside it. Nothing is scored here. What is covered:

* `AsofDaysTests` -- the days are read through the parent's `InformationRule`; R and S are the parent's own functions'
  values; a later row moves no earlier day; a locked day is refused.
* `RefitTests` -- a planted kink is recovered; too few pairs is reported as not fitted, without an interval; the interval
  brackets the fitted kink; a pair after the cutoff is refused.
* `NotRPlusAConstantTests` (must-show 3) -- on a constructed input in which the kink moves, the estimate is not R plus a
  constant and ranks a pair of days the opposite way to R.
* `PathTests` (must-show 4) -- each refit's real-time path, its served days, and the gap to the previous refit.
* `LeakageTests` (must-show 2) -- a refit that read a row after its cutoff is refused with `LookAheadError`.

**Recorded mutations** (CLAUDE.md), 13 October 2026, in a disposable copy of the tree, CPython 3.11, the parent at the pin
(09640f5), `PYTHONDONTWRITEBYTECODE=1`, applied by `sed` or a one-line replacement and confirmed by `grep`, the suite run
against the copy, the copy discarded:

1. `training_pairs`: replace `d.day <= cutoff` by `d.day <= next_business_day(cutoff, 60)`. A refit then fits on days up to
   sixty business days after its cutoff. `RefitTests.test_training_pairs_stop_at_the_cutoff` fails with
   `AssertionError: 361 != 301`, and fifteen tests (every `PathTests` and `LeakageTests` test that builds a path or a
   refit, among them `LeakageTests.test_a_refit_that_read_a_later_pair_is_refused` and
   `LeakageTests.test_the_refit_in_force_is_unmoved_by_rows_after_its_cutoff`) raise
   `repo_model.splits.LookAheadError: the kink for the refit at 2024-03-18 would be fitted on 2024-03-19, after its cutoff`
   from `_require_on_or_before`.
2. `check_no_future`: replace `if again.fitted != p.refit.fitted or abs(again.level - p.refit.level) > 1e-12:` by `if False:`.
   A refit that differs from the cut panel's is no longer refused;
   `LeakageTests.test_a_refit_that_read_a_later_pair_is_refused` fails with `AssertionError: LookAheadError not raised`
   (it is the only failure).

Written first, and watched failing: before `repo_liquidity.h7_estimator` existed the module did not import:
`ImportError: cannot import name 'h7_estimator' from 'repo_liquidity'`.
"""

from __future__ import annotations

import unittest
from datetime import date, time, timedelta

from repo_model import measurement_fields, scarcity
from repo_model.asof import InformationRule
from repo_model.data import DailyObservation, next_business_day
from repo_model.splits import LookAheadError

from repo_liquidity import h7_estimator as h7

REPLICATIONS = 40


def _days(start, count):
    out = [start]
    while len(out) < count:
        out.append(next_business_day(out[-1], 1))
    return out


def _panel(start=date(2023, 1, 3), count=760, assets=26000.0):
    """Business days; the reserves step weekly through ratios 0.09 to 0.16 against constant assets; the spread is flat."""

    out = []
    for index, day in enumerate(_days(start, count)):
        wednesday = day - timedelta(days=(day.weekday() - 2) % 7)
        week = (wednesday - date(2023, 1, 4)).days // 7
        ratio = 0.09 + 0.007 * ((week * 7) % 11)
        out.append(DailyObservation(day, {
            "sofr": 4.0, "iorb": 4.0, "reserve_balances": assets * ratio, "bank_total_assets": assets,
            "on_rrp": 20.0 + index % 3,
        }))
    return out


class _Measured(unittest.TestCase):
    def setUp(self):
        context = scarcity.measurement_declaration()
        context.__enter__()
        self.addCleanup(context.__exit__, None, None, None)
        self.registry = measurement_fields.load_registry()

    def rule(self):
        return InformationRule(self.registry, scarcity.LEGS, decision_time=time(16, 0), horizon=1)

    def days(self, rows):
        return h7.asof_days(rows, self.rule())

    def planted(self, count=760, kink=lambda index: 0.12):
        """The panel with the spread planted on the ratio the rule reads for each scored day: -1 bp at or above the kink
        in force that day and 60 bp per point of ratio below it (plus a small deterministic wiggle)."""

        rows = _panel(count=count)
        ratios = {d.day: d.ratio for d in self.days(rows)}
        out = [rows[0]]
        for index, row in enumerate(rows[1:], start=1):
            ratio = ratios[row.date]
            values = dict(row.values)
            if ratio is not None:
                values["sofr"] = 4.0 + (-1.0 + 60.0 * max(0.0, kink(index) - ratio) + 0.05 * (index % 3)) / 100.0
            out.append(DailyObservation(row.date, values))
        return out


def _pairs(count=500, kink=0.12):
    """Days carrying a planted kink directly, without the as-of read: the ratio cycles through 0.09 to 0.16."""

    days = _days(date(2023, 1, 4), count)
    out = []
    for index, day in enumerate(days):
        ratio = 0.09 + 0.001 * (index % 71)
        spread = -1.0 + 60.0 * max(0.0, kink - ratio) + 0.05 * (index % 3)
        out.append(h7.Day(day, ratio, spread, 1.0))
    return out


class AsofDaysTests(_Measured):
    def test_the_ratio_and_the_state_are_the_parents_functions_of_the_legs_the_rule_reads(self):
        rows = _panel(count=300)
        days = self.days(rows)
        index = next(i for i, d in enumerate(days) if d.day == date(2023, 9, 20))
        info = self.rule().information_set(h7._extended([r.date for r in rows], index), index + 1)
        read = {r.feature: r.row for r in info.reads}
        reserves = rows[read["reserve_balances"]].values["reserve_balances"]
        assets = rows[read["bank_total_assets"]].values["bank_total_assets"]
        on_rrp = rows[read["on_rrp"]].values["on_rrp"]
        self.assertAlmostEqual(days[index].ratio, scarcity.reserves_ratio(reserves, assets))
        self.assertEqual(days[index].state, float(scarcity.reserve_scarcity_state(reserves, assets, on_rrp)))
        self.assertAlmostEqual(days[index].spread, (rows[index + 1].values["sofr"] - 4.0) * 100.0)

    def test_the_scored_day_is_the_row_after_the_decision_row(self):
        rows = _panel(count=300)
        days = self.days(rows)
        self.assertEqual([d.day for d in days], [r.date for r in rows[1:]])

    def test_a_later_rows_values_do_not_move_an_earlier_day(self):
        rows = _panel(count=300)
        full = self.days(rows)
        changed = [DailyObservation(r.date, dict(r.values)) for r in rows]
        for later in changed[200:]:
            later.values["reserve_balances"] = 9999.0
            later.values["on_rrp"] = 9999.0
        again = self.days(changed)
        first = [d for d in full if d.day <= rows[199].date]
        self.assertEqual(first, [d for d in again if d.day <= rows[199].date])

    def test_a_locked_day_is_refused(self):
        rows = _panel(start=date(2026, 8, 3), count=45)
        with self.assertRaises(LookAheadError):
            self.days(rows)


class RefitTests(unittest.TestCase):
    def test_a_planted_kink_is_recovered(self):
        fit = h7.refit(_pairs(), date(2025, 12, 31), replications=REPLICATIONS)
        self.assertTrue(fit.fitted)
        self.assertAlmostEqual(fit.level, 0.12, delta=0.0026)

    def test_the_interval_brackets_the_kink_and_is_ordered(self):
        fit = h7.refit(_pairs(), date(2025, 12, 31), replications=REPLICATIONS)
        self.assertLessEqual(fit.lower, fit.level)
        self.assertGreaterEqual(fit.upper, fit.level)
        self.assertLessEqual(fit.lower, fit.upper)

    def test_too_few_pairs_is_not_fitted_and_has_no_interval(self):
        fit = h7.refit(_pairs(count=100), date(2025, 12, 31), replications=REPLICATIONS)
        self.assertFalse(fit.fitted)
        self.assertIsNone(fit.lower)
        self.assertIsNone(fit.upper)

    def test_the_bootstrap_is_reproducible(self):
        a = h7.refit(_pairs(), date(2025, 12, 31), replications=REPLICATIONS)
        b = h7.refit(_pairs(), date(2025, 12, 31), replications=REPLICATIONS)
        self.assertEqual((a.lower, a.upper), (b.lower, b.upper))

    def test_training_pairs_stop_at_the_cutoff(self):
        days = _pairs()
        cutoff = days[300].day
        pairs = h7.training_pairs(days, cutoff)
        self.assertEqual(len(pairs), 301)
        self.assertEqual(max(p.day for p in pairs), cutoff)

    def test_a_pair_after_the_cutoff_is_refused(self):
        days = _pairs()
        with self.assertRaises(LookAheadError):
            h7.refit(days, days[300].day, replications=REPLICATIONS)

    def test_a_day_without_a_ratio_or_a_spread_is_not_a_pair(self):
        days = _pairs()
        days[10] = days[10]._replace(ratio=None)
        days[11] = days[11]._replace(spread=None)
        pairs = h7.training_pairs(days, days[-1].day)
        self.assertEqual(len(pairs), len(days) - 2)


class NotRPlusAConstantTests(unittest.TestCase):
    """Must-show 3: the estimate is not a monotone transform of R plus a constant when the kink moves."""

    def moving_days(self):
        # the planted kink is 0.11 for the first 520 days and 0.14 after: the refits at 520 and later learn it
        days = _days(date(2023, 1, 4), 900)
        out = []
        for index, day in enumerate(days):
            ratio = 0.09 + 0.001 * (index % 71)
            kink = 0.11 if index < 520 else 0.14
            out.append(h7.Day(day, ratio, -1.0 + 60.0 * max(0.0, kink - ratio) + 0.05 * (index % 3), 1.0))
        return out

    def test_the_estimate_is_not_the_ratio_plus_a_constant(self):
        days = self.moving_days()
        path = h7.real_time_path(days, [days[500].day, days[899 - 5].day], replications=REPLICATIONS)
        first, last = path[0].refit.level, path[1].refit.level
        self.assertGreater(last - first, 0.02)
        offsets = {round(e.ratio - e.deployable, 9) for p in path for e in p.estimates}
        self.assertGreater(len(offsets), 1)

    def test_a_pair_of_days_is_ranked_opposite_ways_by_the_ratio_and_the_estimate(self):
        days = self.moving_days()
        path = h7.real_time_path(days, [days[500].day, days[899 - 5].day], replications=REPLICATIONS)
        flipped = [(a, b) for a in path[0].estimates for b in path[1].estimates
                   if a.ratio < b.ratio and a.deployable > b.deployable]
        self.assertTrue(flipped)

    def test_with_a_fixed_kink_the_estimate_is_the_ratio_plus_a_constant(self):
        days = _pairs(count=700)
        path = h7.real_time_path(days, [days[400].day, days[500].day], replications=REPLICATIONS)
        offsets = {round(e.ratio - e.deployable, 9) for p in path for e in p.estimates}
        self.assertEqual(len(offsets), 1)


class PathTests(unittest.TestCase):
    def setUp(self):
        self.days = _pairs(count=700)
        self.cutoffs = [self.days[k].day for k in (300, 350, 420)]
        self.path = h7.real_time_path(self.days, self.cutoffs, replications=REPLICATIONS)

    def test_one_path_per_refit_in_order(self):
        self.assertEqual([p.refit.cutoff for p in self.path], self.cutoffs)

    def test_a_refit_serves_from_the_second_business_day_after_its_cutoff_to_the_next_refits_serving_start(self):
        first = self.path[0]
        self.assertEqual(first.estimates[0].day, next_business_day(self.cutoffs[0], 2))
        second_start = next_business_day(self.cutoffs[1], 2)
        self.assertLess(first.estimates[-1].day, second_start)
        self.assertEqual(next_business_day(first.estimates[-1].day, 1), second_start)

    def test_the_last_refit_serves_to_the_last_day(self):
        self.assertEqual(self.path[-1].estimates[-1].day, self.days[-1].day)

    def test_each_estimate_is_the_ratio_minus_its_refits_kink(self):
        by_day = {d.day: d for d in self.days}
        for p in self.path:
            for e in p.estimates:
                self.assertAlmostEqual(e.deployable, by_day[e.day].ratio - p.refit.level)
                self.assertAlmostEqual(e.lower, e.ratio - p.refit.upper)
                self.assertAlmostEqual(e.upper, e.ratio - p.refit.lower)
                self.assertEqual(e.state, by_day[e.day].state)

    def test_the_first_refit_has_no_gaps_and_a_later_one_has_the_kink_difference_on_every_served_day(self):
        self.assertEqual(self.path[0].gaps, {})
        for k in (1, 2):
            p = self.path[k]
            expected = abs(p.refit.level - self.path[k - 1].refit.level)
            self.assertEqual(set(p.gaps), {e.day for e in p.estimates})
            for gap in p.gaps.values():
                self.assertAlmostEqual(gap, expected)

    def test_a_refit_that_did_not_fit_is_a_missing_estimate_never_a_fallback(self):
        short = h7.real_time_path(self.days, [self.days[100].day, self.days[400].day], replications=REPLICATIONS)
        self.assertFalse(short[0].refit.fitted)
        self.assertEqual(short[0].estimates, [])
        self.assertTrue(short[0].missing_days > 0)
        self.assertTrue(short[1].refit.fitted)
        self.assertEqual(short[1].gaps, {})

    def test_the_dollar_amount_is_the_estimate_times_bank_assets(self):
        self.assertAlmostEqual(h7.dollars(0.02, 26000.0), 520.0)

    def test_points_are_a_hundred_times_the_share(self):
        self.assertAlmostEqual(h7.points(0.0123), 1.23)

    def test_unordered_or_repeated_cutoffs_are_refused(self):
        with self.assertRaises(ValueError):
            h7.real_time_path(self.days, [self.cutoffs[1], self.cutoffs[0]], replications=REPLICATIONS)


class LeakageTests(_Measured):
    """Must-show 2: a refit reads nothing public after its cutoff.

    Recorded mutations 1 and 2: see the module docstring.
    """

    def moving(self):
        return self.planted(kink=lambda index: 0.11 if index < 480 else 0.14)

    def test_the_levels_pass_when_the_refits_use_nothing_later(self):
        rows = self.moving()
        days = self.days(rows)
        cutoffs = [days[k].day for k in (330, 560, 700)]
        path = h7.real_time_path(days, cutoffs, replications=0)
        h7.check_no_future(rows, self.rule(), path, replications=0)

    def test_a_refit_that_read_a_later_pair_is_refused(self):
        rows = self.moving()
        days = self.days(rows)
        cutoff = days[400].day
        honest = h7.refit_on(days, cutoff, replications=0)
        # a refit stamped with this cutoff that was fitted on 200 more days than were public at it
        leaked = h7.refit_on(days[:600], days[599].day, replications=0)._replace(cutoff=cutoff)
        self.assertNotEqual(leaked.level, honest.level)
        path = [h7.RefitPath(refit=leaked, estimates=[], gaps={}, missing_days=0)]
        with self.assertRaises(LookAheadError):
            h7.check_no_future(rows, self.rule(), path, replications=0)

    def test_the_refit_in_force_is_unmoved_by_rows_after_its_cutoff(self):
        rows = self.moving()
        days = self.days(rows)
        cutoff = days[400].day
        before = h7.refit_on(days, cutoff, replications=0)
        changed = [DailyObservation(r.date, dict(r.values)) for r in rows]
        for later in changed[420:]:
            later.values["sofr"] = 40.0
            later.values["reserve_balances"] = 1.0
        after = h7.refit_on(self.days(changed), cutoff, replications=0)
        self.assertEqual(before.level, after.level)


if __name__ == "__main__":
    unittest.main()
