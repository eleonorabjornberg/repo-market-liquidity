"""H7m, the calendar-clean variants of candidate C, and D's (not run), `docs/stages/h7-calendar-clean.md` and its section 9
(directive #147, the rulings on Q1-Q6).

What is covered:

* `TurnDayTests`, `RealTurnLabelTests` -- Q1: the third clause of the exclusion set, `turn_label(T) is not None`, read from the
  parent for the scored day only. The label function is injected (it exists only at the parent's later pin, #149); the real one
  runs in `RealTurnLabelTests`, which is skipped at a pin that lacks `repo_model.turn_days` and nowhere else.
* `ObjectiveVariantTests`, `CorridorEffrTests` -- Q4 and Q2: CV3 (clean days, least squares) is the baseline's fit on the days
  nothing drops, CV4 (every day, absolute deviation) reads no flags, and CV2's left side is the corridor-normalised EFFR.
* `PoliticsWhiteTests` -- the block length reported beside goalpost 2 (reporting only).

* `SolverTests` -- the exact absolute-deviation line against brute force over every two-point vertex and the `b = 0` boundary;
  a planted line recovered exactly; a falling trend gives the boundary; the kink search drops only kinks that cannot win, and
  tied kinks go to the smaller one.
* `TieRuleTests` -- section 2(b): starts tied within a grid step resolve by objective then by the smaller vector; starts tied
  further apart than a grid step are **not identified** and serve nothing. A constructed case in which two share vectors fit
  alike (a group with no reserves) is "not identified" under all four variants (CV1, CV2, DV1, DV2).
* `FlagTests` -- the exclusion flags are the parent's, read through its rule at the day's own decision instant: each of the four
  classes of section 2(a) and a day that is none. The leakage tests carry a recorded mutation each.
* `TrainingDayTests` -- a flagged day is not a training day and does not count toward an episode; a dropped day is still served.
* `FitTests` -- the planted shares and parameters are recovered by absolute deviation on corridor-position and EFFR left sides.
* `PathTests` and `SummaryTests` -- the real-time path, its gaps and the goalposts' figures, development evidence only.

**Recorded mutations** (CLAUDE.md), 20 October 2026, in a disposable copy of the tree, CPython 3.11, the parent at the pin
(8fd2cf8), `PYTHONDONTWRITEBYTECODE=1`, applied by a one-line replacement and confirmed by `grep`, the suite run against the
copy, the copy discarded:

1. `check_flag_reads`: replace `read.row != info.scored_index` by `False`. A flag read for any row but the scored one is no
   longer refused; `FlagTests.test_a_flag_read_for_another_day_than_the_scored_one_is_refused` fails with
   `AssertionError: LookAheadError not raised`.
2. `clean_days`: replace `flag.day != x.day` by `False`. The flags of another day (the cutoff day's, say) are taken for a
   day's own; `FlagTests.test_the_flags_of_another_day_are_refused` fails with `AssertionError: LookAheadError not raised`.
3. `training_days`: replace `x.day <= cutoff` by `x.day <= next_business_day(cutoff, 60)` (a refit fits on days up to sixty
   business days after its cutoff). `refit_c`'s own guard then raises `repo_model.splits.LookAheadError: the shares for the
   refit at 2019-01-14 would be fitted on 2019-01-15, after its cutoff` from `PathTests`' class setup and two more tests, and
   `TrainingDayTests.test_a_refit_never_fits_on_a_day_after_its_cutoff` and
   `test_the_counted_episode_rule_is_taken_over_the_clean_days` fail with `AssertionError`. With that guard also replaced
   by `if False:`, four tests fail with `AssertionError` and none passes a refit that read a later day.

4. `check_no_future`: replace `if _signature(*now, left_side, series) != _signature(*then, left_side, cut_series):` by
   `if False:`. A training sample that read a later row is no longer refused;
   `NoFutureTests.test_a_sample_that_read_a_later_row_is_refused` fails with `AssertionError: LookAheadError not raised`
   (the only failure).

5. `read_turn`: replace `if read != scored:` by `if False:`. A turn-day label read for another day is no longer refused;
   `TurnDayTests.test_a_label_read_for_another_day_is_refused` fails with `AssertionError: LookAheadError not raised` (the only
   failure).
6. `read_flags`: replace `read_turn(labeller, scored.date, scored.date)` by `read_turn(labeller, scored.date, rows[i].date)`
   (the label of the cutoff row, one day early). `read_turn` refuses it: `repo_model.splits.LookAheadError: the turn-day label of
   2019-03-19 was read for 2019-03-18; it is read for the scored day only`, from the class setup of `TurnDayTests` and
   `FlagTests`.
7. `Flags.dropped`: remove `or self.turn is not None`. A turn day is no longer dropped;
   `TurnDayTests.test_a_turn_day_is_dropped_by_the_third_clause_alone` fails with `AssertionError: False is not true`, and
   `test_a_turn_day_is_not_a_training_day_and_does_not_count_toward_an_episode` with `AssertionError: 100 != 98`.

Mutations 5 to 7 were applied on 21 October 2026 the same way (CPython 3.11, the parent at the pin 8fd2cf8, the tests run
against a disposable copy of the tree). The tests of this turn (Q1 to Q4, the Politis-White figure) were written before the code
and watched failing: against the earlier module they failed with `AttributeError: module 'repo_liquidity.h7_clean' has no
attribute 'parent_turn_label'` at import.

Order of work, said plainly (for mutations 1 to 4, the first draft): the first draft of `repo_liquidity.h7_clean` was written before these tests, so they were not
watched failing against an absent module as the first step. With the module moved away the suite fails at once with
`ImportError` (`cannot import name 'h7_clean' from 'repo_liquidity'`), and each mutation above was applied to the finished
module and killed by a test that passes without it.
"""

from __future__ import annotations

import itertools
import unittest
from datetime import date, timedelta
from unittest import mock

import numpy as np
from repo_model import asof, data
from repo_model.data import DailyObservation, next_business_day
from repo_model.splits import LookAheadError

import test_h7_candidate_c as tc
import test_h7_candidate_d as td
from repo_liquidity import demand_curve
from repo_liquidity import h7_candidate_c as c
from repo_liquidity import h7_candidate_d as d
from repo_liquidity import h7_clean as h

#: A coarse kink grid keeps the fits in the tests quick; it holds the planted kink, 0.03.
COARSE = tuple(round(0.0025 * i, 4) for i in range(1, 33))
EPISODES = tc.EPISODES
MIN_SCARCE = 15
CORRIDOR, EFFR = "corridor", "effr_corridor"


def _brute(z, y):
    """The least objective over the boundary b = 0 and every line through two points with distinct z and b >= 0."""
    best = float(np.abs(y - np.median(y)).sum())
    for i, j in itertools.combinations(range(len(y)), 2):
        if z[i] == z[j]:
            continue
        slope = (y[i] - y[j]) / (z[i] - z[j])
        if slope >= 0:
            best = min(best, float(np.abs(y - (y[i] - slope * z[i]) - slope * z).sum()))
    return best


class SolverTests(unittest.TestCase):
    def test_the_objective_equals_brute_force_over_every_vertex(self):
        rng = np.random.default_rng(20261020)
        for case in range(120):
            n = int(rng.integers(4, 13))
            z = np.maximum(rng.uniform(-0.5, 1.0, n), 0.0)
            y = rng.normal(0.0, 3.0, n) + z * rng.uniform(-3.0, 8.0)
            if case % 3 == 0:
                y = np.round(y)  # whole numbers, as EFFR - IORB is: many exact ties
            a, b, f = h.lad_lines(z[None, :], y)
            want = _brute(z, y)
            self.assertAlmostEqual(f[0], want, delta=1e-9 * max(1.0, want), msg=f"case {case}")
            self.assertGreaterEqual(b[0], 0.0)
            self.assertAlmostEqual(float(np.abs(y - a[0] - b[0] * z).sum()), f[0], places=9)

    def test_a_planted_line_is_recovered_exactly(self):
        z = np.maximum(0.05 - np.linspace(0.0, 0.1, 41), 0.0)
        a, b, f = h.lad_lines(z[None, :], 0.2 + 8.0 * z)
        self.assertAlmostEqual(f[0], 0.0, places=9)
        self.assertAlmostEqual(b[0], 8.0, places=6)
        self.assertAlmostEqual(a[0], 0.2, places=6)

    def test_a_falling_trend_gives_the_boundary_b_equal_zero(self):
        z = np.linspace(0.0, 1.0, 21)
        a, b, f = h.lad_lines(z[None, :], 5.0 - 3.0 * z)
        self.assertEqual(b[0], 0.0)
        self.assertAlmostEqual(a[0], float(np.median(5.0 - 3.0 * z)), places=9)

    def test_a_row_with_no_spread_in_z_is_flat(self):
        a, b, f = h.lad_lines(np.zeros((1, 7)), np.arange(7.0))
        self.assertEqual((float(a[0]), float(b[0]), float(f[0])), (3.0, 0.0, 12.0))

    def test_dropping_clearly_worse_kinks_does_not_change_the_answer(self):
        rng = np.random.default_rng(7)
        for case in range(12):
            n = int(rng.integers(30, 120))
            x = rng.uniform(0.0, 0.1, n)
            y = np.maximum(0.05 - x, 0.0) * 8.0 + rng.normal(0.0, 0.05, n)
            if case % 2:
                y = np.round(y * 20.0) / 20.0
            got = h.lad_curve(x, y)
            kinks = np.asarray(h.KINK_GRID)
            below = np.searchsorted(np.sort(x), kinks)
            kinks = kinks[(below > 0) & (below < n)]
            a, b, f = h.lad_lines(np.maximum(kinks[:, None] - x[None, :], 0.0), y)
            first = int(np.argmax(f <= f.min() * (1.0 + h.KINK_TIE_RTOL)))
            self.assertEqual(got.kink, float(kinks[first]))
            self.assertAlmostEqual(got.objective, float(f[first]), delta=1e-9 * float(f[first]))

    def test_tied_kinks_go_to_the_smaller_kink(self):
        x = np.linspace(0.01, 0.09, 30)
        got = h.lad_curve(x, np.full(30, 0.5))  # a flat left side: every kink fits alike with b = 0
        valid = [k for k in h.KINK_GRID if 0 < np.searchsorted(np.sort(x), k) < 30]
        self.assertEqual(got.kink, valid[0])
        self.assertEqual(got.slope, 0.0)

    def test_no_kink_with_points_on_both_sides_is_no_curve(self):
        self.assertIsNone(h.lad_curve([0.5, 0.6, 0.7], [1.0, 2.0, 3.0]))


def _searched(params, objective):
    return h.Searched(tuple(params), h.Curve(0.03, 0.1, 8.0, objective))


class TieRuleTests(unittest.TestCase):
    def test_tied_starts_further_than_a_grid_step_apart_are_not_identified(self):
        got = h.combine_starts([_searched((0.05, 0.14, 0.03), 1.0), _searched((0.10, 0.14, 0.03), 1.0 + 1e-12)], h.STEPS_C)
        self.assertEqual(got.status, h.NOT_IDENTIFIED)
        self.assertIsNone(got.chosen)
        self.assertAlmostEqual(got.span[0], 0.05)

    def test_tied_starts_within_a_grid_step_resolve_by_objective_then_the_smaller_vector(self):
        got = h.combine_starts([_searched((0.07, 0.14, 0.03), 1.0), _searched((0.06, 0.14, 0.03), 1.0)], h.STEPS_C)
        self.assertEqual((got.status, got.chosen.params), (h.FITTED, (0.06, 0.14, 0.03)))
        lower = h.combine_starts([_searched((0.07, 0.14, 0.03), 1.0 - 1e-10), _searched((0.06, 0.14, 0.03), 1.0)], h.STEPS_C)
        self.assertEqual(lower.chosen.params, (0.07, 0.14, 0.03))

    def test_a_start_that_is_clearly_worse_is_not_tied(self):
        got = h.combine_starts([_searched((0.05, 0.14, 0.03), 2.0), _searched((0.20, 0.14, 0.03), 1.0)], h.STEPS_C)
        self.assertEqual((got.status, got.chosen.params, got.starts_agree), (h.FITTED, (0.20, 0.14, 0.03), False))

    def test_d_compares_the_slope_in_its_own_step(self):
        steps = h.STEPS_D
        near = h.combine_starts([_searched((0.1, -0.5, 0.14, 0.03), 1.0), _searched((0.1, -0.4, 0.14, 0.03), 1.0)], steps)
        far = h.combine_starts([_searched((0.1, -0.5, 0.14, 0.03), 1.0), _searched((0.1, -0.3, 0.14, 0.03), 1.0)], steps)
        self.assertEqual((near.status, far.status), (h.FITTED, h.NOT_IDENTIFIED))

    def test_no_start_is_no_fit(self):
        self.assertEqual(h.combine_starts([], h.STEPS_C).status, h.NO_FIT)


def _quiet_flags(days):
    return {x.day: h.Flags(x.day, 0.0, 0.0) for x in days}


def _effr_series(days):
    """A corridor-normalised EFFR position that follows the same planted D as the SOFR corridor position, on its own scale (a
    different left side). It is not rounded: the published EFFR is in whole basis points, and a left side that coarse ties more
    often, as the declaration says."""
    return {EFFR: {x.day: 0.8 * x.corridor + 0.1 for x in days}}


def _no_turns(day):
    """A stand-in for the parent's `turn_days.turn_label` where a test is not about the turn days: no day is a turn day. The
    parent's own function is used in `RealTurnLabelTests` and by the run (`h.parent_turn_label`)."""
    return None


def _turn_label_or_stand_in():
    try:
        return h.parent_turn_label()
    except ValueError:  # the pin of this tree predates repo_model.turn_days (it comes with the pin move, #149)
        return _no_turns


class _FitCase(unittest.TestCase):
    """Fits are slow, so a class fits once."""

    @classmethod
    def setUpClass(cls):
        cls.patch = mock.patch.object(h, "KINK_GRID", COARSE)
        cls.patch.start()
        cls.addClassCleanup(cls.patch.stop)


class FitTests(_FitCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.weeks = tc._weeks()
        cls.days = tc._planted_days(cls.weeks, count=100)
        cls.flags = _quiet_flags(cls.days)
        cls.series = _effr_series(cls.days)

    def refit(self, left):
        return h.refit_c(self.days, self.days[-1].day, self.flags, left, self.series, replications=0, episodes=EPISODES,
                         min_scarce=MIN_SCARCE)

    def test_cv1_recovers_the_planted_shares_on_the_corridor_position(self):
        fit = self.refit(CORRIDOR)
        self.assertTrue(fit.fitted, fit.record)
        self.assertEqual(fit.shares, tc.PLANTED)
        self.assertEqual(fit.record["status"], h.FITTED)
        self.assertGreater(fit.slope, 0.0)

    def test_cv2_recovers_the_planted_shares_on_effr_minus_iorb(self):
        fit = self.refit(EFFR)
        self.assertTrue(fit.fitted, fit.record)
        self.assertEqual(fit.shares, tc.PLANTED)

    def test_the_fit_is_deterministic(self):
        self.assertEqual(self.refit(CORRIDOR), self.refit(CORRIDOR))

    def test_no_counted_episode_is_not_fitted_and_has_no_interval(self):
        fit = h.refit_c(self.days, self.days[5].day, self.flags, CORRIDOR, self.series, replications=3, episodes=EPISODES,
                        min_scarce=MIN_SCARCE)
        self.assertFalse(fit.fitted)
        self.assertEqual((fit.shares, fit.draws, fit.record["status"]), (None, (), h.NO_EPISODE))

    def test_the_bootstrap_refits_each_draw_under_the_same_objective(self):
        fit = h.refit_c(self.days, self.days[-1].day, self.flags, CORRIDOR, self.series, replications=3, episodes=EPISODES,
                        min_scarce=MIN_SCARCE)
        self.assertEqual(len(fit.draws), 3)
        self.assertTrue(all(len(draw) == 3 for draw in fit.draws))

    def test_the_effr_left_side_needs_an_effr_column(self):
        with self.assertRaises(ValueError):
            h.left_sides([DailyObservation(date(2019, 1, 2), {"sofr": 2.4, "iorb": 2.4})], lambda day: 2.25)
        rows = [DailyObservation(date(2019, 1, 2), {"sofr": 2.4, "iorb": 2.40, "effr": 2.33})]
        self.assertEqual(h.left_sides(rows, lambda day: 2.25)[EFFR][date(2019, 1, 2)], round(0.08 / 0.15, 9))


class NotIdentifiedTests(_FitCase):
    """A group with no reserves has a share that moves nothing: two share vectors fit alike, and the fit must not pick one."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.weeks = [w._replace(reserves_bn=w.reserves_bn[:2] + (0.0,)) for w in tc._weeks()]
        cls.days = tc._planted_days(cls.weeks, count=100, shares=(0.06, 0.14, 0.03))
        cls.flags = _quiet_flags(cls.days)
        cls.series = _effr_series(cls.days)

    def test_cv1_and_cv2_are_not_identified(self):
        for left in (CORRIDOR, EFFR):
            fit = h.refit_c(self.days, self.days[-1].day, self.flags, left, self.series, replications=3, episodes=EPISODES,
                            min_scarce=MIN_SCARCE)
            self.assertFalse(fit.fitted, left)
            self.assertEqual((fit.shares, fit.draws, fit.record["status"]), (None, (), h.NOT_IDENTIFIED), left)
            self.assertGreater(fit.record["tied_span"][2], c.SHARE_GRID[1], left)

    def test_cv3_and_cv4_are_not_identified(self):
        """The same constructed case under least squares on clean days (CV3) and absolute deviation on every day (CV4)."""
        for kw in ({"objective": "ls"}, {"clean": False}):
            fit = h.refit_c(self.days, self.days[-1].day, self.flags, CORRIDOR, self.series, replications=3, episodes=EPISODES,
                            min_scarce=MIN_SCARCE, **kw)
            self.assertFalse(fit.fitted, kw)
            self.assertEqual((fit.shares, fit.draws, fit.record["status"]), (None, (), h.NOT_IDENTIFIED), kw)

    def test_dv1_and_dv2_are_not_identified(self):
        slr_rows = td.SLR_ROWS
        weeks = [w._replace(reserves_bn=w.reserves_bn[:2] + (0.0,)) for w in td._weeks()]
        days = td._planted_days(weeks, count=100)
        flags = _quiet_flags(days)
        series = _effr_series(days)
        self.assertTrue(slr_rows)
        for left in (CORRIDOR, EFFR):
            fit = h.refit_d(days, days[-1].day, flags, left, series, replications=2, episodes=EPISODES, min_scarce=MIN_SCARCE)
            self.assertFalse(fit.fitted, left)
            self.assertEqual((fit.params, fit.draws, fit.record["status"]), (None, (), h.NOT_IDENTIFIED), left)


def _flag_rows(first=date(2019, 3, 18), last=date(2019, 5, 3), coupons=()):
    """A panel of the columns the two flags read, from the parent's own calendar functions, with coupon settlements on `coupons`."""
    out, day = [], first
    while day <= last:
        if day.weekday() < 5 and day not in data.market_holidays().closed:
            values = {name: rule(day) for name, rule in data.CALENDAR_COLUMN_RULES.items() if name != "quarter_end_window"}
            values.update(sofr=2.4, iorb=2.4, treasury_settlement_coupons=5.0 if day in coupons else 0.0)
            out.append(DailyObservation(day, values))
        day += timedelta(days=1)
    return h.with_quarter_end_window(out)


class FlagTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.coupon_day = date(2019, 4, 10)
        cls.rows = _flag_rows(coupons=(cls.coupon_day,))
        cls.flags = h.read_flags(cls.rows, h.flag_rule(), _no_turns)

    def test_the_quarter_end_is_a_settlement_day(self):
        self.assertEqual(self.flags[date(2019, 3, 29)].settlement_day, 1.0)

    def test_the_two_business_days_either_side_of_the_quarter_end_are_the_window(self):
        window = {day for day, f in self.flags.items() if f.quarter_end_window == 1.0}
        self.assertEqual(window, {date(2019, 3, 27), date(2019, 3, 28), date(2019, 3, 29), date(2019, 4, 1), date(2019, 4, 2)})
        self.assertEqual(self.flags[date(2019, 3, 27)].settlement_day, 0.0)  # in the window only
        self.assertTrue(self.flags[date(2019, 3, 27)].dropped())

    def test_a_tax_date_is_a_settlement_day(self):
        self.assertEqual(self.flags[date(2019, 4, 15)].settlement_day, 1.0)

    def test_the_last_calendar_days_of_a_month_are_settlement_days(self):
        self.assertEqual(self.flags[date(2019, 4, 29)].settlement_day, 1.0)
        self.assertEqual(self.flags[date(2019, 4, 26)].settlement_day, 0.0)

    def test_a_coupon_settlement_is_a_settlement_day(self):
        self.assertEqual(self.flags[self.coupon_day].settlement_day, 1.0)
        self.assertTrue(self.flags[self.coupon_day].dropped())

    def test_a_day_that_is_none_of_the_four_is_clean(self):
        flag = self.flags[date(2019, 4, 9)]
        self.assertEqual((flag.settlement_day, flag.quarter_end_window, flag.dropped()), (0.0, 0.0, False))

    def test_the_flags_are_the_parents_own_composition(self):
        for day, flag in self.flags.items():
            if flag.unread:
                continue
            row = next(r for r in self.rows if r.date == day)
            self.assertEqual(flag.settlement_day, asof._settlement_day(row.values), day)
            self.assertEqual(flag.quarter_end_window, data.quarter_end_window(day), day)

    def test_a_row_the_rule_cannot_score_is_unread_and_leaves_the_training_days(self):
        first = self.flags[self.rows[1].date]  # too little history for the target's lag
        self.assertEqual((first.settlement_day, first.quarter_end_window, first.unread), (None, None, True))
        self.assertTrue(first.dropped())
        self.assertFalse(any(f.unread for day, f in self.flags.items() if day != self.rows[1].date))

    def test_a_hole_in_a_flag_is_a_data_error_not_a_clean_day(self):
        with self.assertRaises(ValueError):
            h.Flags(date(2019, 4, 9), None, 0.0).dropped()

    def test_a_flag_read_for_another_day_than_the_scored_one_is_refused(self):
        rule = h.flag_rule()
        dates = [r.date for r in self.rows]
        info = rule.information_set(dates, 10)
        h.check_flag_reads(info)  # its own reads pass
        moved = tuple(r._replace(row=r.row - 1) if r.kind in (asof.KIND_CALENDAR, asof.KIND_SCHEDULED) else r for r in info.reads)
        with self.assertRaises(LookAheadError):
            h.check_flag_reads(info._replace(reads=moved))

    def test_the_flags_of_another_day_are_refused(self):
        days = tc._planted_days(tc._weeks(), count=20)
        flags = _quiet_flags(days)
        flags[days[7].day] = h.Flags(days[3].day, 1.0, 0.0)  # the flags of another day (the cutoff day's, say)
        with self.assertRaises(LookAheadError):
            h.clean_days(days, flags)

    def test_a_day_without_flags_is_a_data_error(self):
        days = tc._planted_days(tc._weeks(), count=5)
        with self.assertRaises(ValueError):
            h.clean_days(days, {})


class TrainingDayTests(_FitCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.weeks = tc._weeks()
        cls.days = tc._planted_days(cls.weeks, count=100)
        cls.series = _effr_series(cls.days)

    def flags_dropping(self, indices):
        flags = _quiet_flags(self.days)
        for i in indices:
            flags[self.days[i].day] = h.Flags(self.days[i].day, 1.0, 0.0)
        return flags

    def sample(self, flags, cutoff, left=CORRIDOR):
        return h.training_days(self.days, cutoff, flags, left, self.series, lambda x: x.week is not None, episodes=EPISODES,
                               min_scarce=MIN_SCARCE)

    def test_the_refit_records_how_many_counted_days_were_dropped(self):
        fit = h.refit_c(self.days, self.days[-1].day, self.flags_dropping([20, 21, 22]), CORRIDOR, self.series, replications=0,
                        episodes=EPISODES, min_scarce=MIN_SCARCE)
        self.assertEqual(fit.record["dropped"], 3)
        self.assertEqual(fit.pairs, len(self.days) - 3)

    def test_a_flagged_day_is_not_a_training_day(self):
        sample, labels = self.sample(self.flags_dropping([20, 21, 22]), self.days[-1].day)
        self.assertEqual(len(sample), len(self.days) - 3)
        self.assertFalse({self.days[20].day, self.days[21].day, self.days[22].day} & {x.day for x in sample})
        self.assertEqual(labels, (EPISODES[0][0],))

    def test_the_quarter_end_window_alone_drops_a_day(self):
        flags = _quiet_flags(self.days)
        flags[self.days[30].day] = h.Flags(self.days[30].day, 0.0, 1.0)
        sample, _ = self.sample(flags, self.days[-1].day)
        self.assertEqual(len(sample), len(self.days) - 1)

    def test_the_counted_episode_rule_is_taken_over_the_clean_days(self):
        cutoff = self.days[MIN_SCARCE - 1].day  # exactly the minimum of days by the cutoff
        self.assertEqual(self.sample(_quiet_flags(self.days), cutoff)[1], (EPISODES[0][0],))
        self.assertEqual(self.sample(self.flags_dropping([4]), cutoff), ([], ()))

    def test_a_day_with_no_left_side_is_not_a_training_day(self):
        series = {EFFR: dict(self.series[EFFR])}
        series[EFFR][self.days[9].day] = None
        sample, _ = h.training_days(self.days, self.days[-1].day, _quiet_flags(self.days), EFFR, series,
                                    lambda x: x.week is not None, episodes=EPISODES, min_scarce=MIN_SCARCE)
        self.assertEqual(len(sample), len(self.days) - 1)

    def test_a_refit_never_fits_on_a_day_after_its_cutoff(self):
        cutoff = self.days[40].day
        sample, _ = self.sample(_quiet_flags(self.days), cutoff)
        self.assertTrue(all(x.day <= cutoff for x in sample))
        with mock.patch.object(h, "training_days", return_value=(self.days[:60], ("episode",))):
            with self.assertRaises(LookAheadError):
                h.refit_c(self.days, cutoff, _quiet_flags(self.days), CORRIDOR, self.series, replications=0)


class PathTests(_FitCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.weeks = tc._weeks()
        cls.days = tc._planted_days(cls.weeks, count=120)
        cls.series = _effr_series(cls.days)
        cls.flags = _quiet_flags(cls.days)
        for i in (62, 63):  # two dropped days inside what the first refit serves
            cls.flags[cls.days[i].day] = h.Flags(cls.days[i].day, 1.0, 0.0)
        cls.cutoffs = [cls.days[40].day, cls.days[80].day]
        with mock.patch.object(tc, "EPISODES", EPISODES):
            cls.path = h.path_c(cls.days, cls.cutoffs, cls.flags, CORRIDOR, cls.series, replications=3, episodes=EPISODES,
                                min_scarce=MIN_SCARCE)

    def test_a_dropped_day_is_still_served(self):
        served = {e.day for e in self.path[0].estimates}
        self.assertIn(self.days[62].day, served)
        self.assertIn(self.days[63].day, served)

    def test_a_refit_serves_from_the_second_business_day_after_its_cutoff(self):
        self.assertEqual(self.path[0].estimates[0].day, next_business_day(self.cutoffs[0], h.SERVING_LAG))
        self.assertEqual(self.path[1].estimates[0].day, next_business_day(self.cutoffs[1], h.SERVING_LAG))

    def test_the_first_refit_has_no_gaps_and_the_second_compares_with_it(self):
        self.assertEqual(self.path[0].gaps, {})
        self.assertEqual(set(self.path[1].gaps), {e.day for e in self.path[1].estimates})

    def test_a_refit_that_is_not_fitted_serves_nothing_and_its_days_are_missing(self):
        early = [self.days[5].day, self.days[80].day]
        path = h.path_c(self.days, early, self.flags, CORRIDOR, self.series, replications=0, episodes=EPISODES,
                        min_scarce=MIN_SCARCE)
        self.assertEqual(path[0].estimates, [])
        self.assertGreater(path[0].missing_days, 0)
        self.assertEqual(path[1].gaps, {})  # nothing to compare with

    def test_the_cutoffs_must_increase(self):
        with self.assertRaises(ValueError):
            h.path_c(self.days, [self.cutoffs[1], self.cutoffs[0]], self.flags, CORRIDOR, self.series, replications=0)


class SummaryTests(_FitCase):
    def test_the_summary_reads_goalposts_1_and_2_and_counts_the_refits(self):
        weeks = tc._weeks()
        days = tc._planted_days(weeks, count=120)
        series = _effr_series(days)
        path = h.path_c(days, [days[40].day, days[80].day], _quiet_flags(days), CORRIDOR, series, replications=3,
                        episodes=EPISODES, min_scarce=MIN_SCARCE)
        out = h.summarise(path)
        self.assertEqual((out["refits"], out["not_fitted_refits"]), (2, 0))
        self.assertEqual(out["refit_status"], {h.FITTED: 2})
        self.assertTrue(out["goalpost_1"]["holds"])  # the same planted shares at both refits: no gap
        self.assertEqual(out["goalpost_1"]["limit"], 0.005)
        self.assertEqual(out["goalpost_2"]["limit"], 0.03)
        self.assertEqual(out["served_days"], sum(len(p.estimates) for p in path))

    def test_the_baselines_paths_summarise_the_same_way(self):
        weeks = tc._weeks()
        days = tc._planted_days(weeks, count=120)
        path = c.real_time_path(days, [days[40].day, days[80].day], replications=2, episodes=EPISODES, min_scarce=MIN_SCARCE)
        out = h.summarise(path)
        self.assertEqual(out["refits"], 2)


class DrawsAndMemoTests(_FitCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.days = tc._planted_days(tc._weeks(), count=100)
        cls.series = _effr_series(cls.days)
        cls.flags = _quiet_flags(cls.days)

    def refit(self, **kw):
        return h.refit_c(self.days, self.days[-1].day, self.flags, CORRIDOR, self.series, replications=4, episodes=EPISODES,
                         min_scarce=MIN_SCARCE, **kw)

    def test_the_draws_do_not_depend_on_the_number_of_workers(self):
        self.assertEqual(self.refit(workers=1).draws, self.refit(workers=2).draws)

    def test_two_cutoffs_that_fit_on_the_same_days_share_one_refit(self):
        # after the episode's last day nothing is added to the sample: the 60th..100th days fit on the same days
        cutoffs = [self.days[-3].day, self.days[-2].day, self.days[-1].day]
        calls = []
        real = h.refit_c

        def counted(*args, **kw):
            calls.append(args[1])
            return real(*args, **kw)

        episode = (EPISODES[0][0], EPISODES[0][1], self.days[-4].day)  # the episode ends before the three cutoffs
        with mock.patch.object(h, "refit_c", counted):
            path = h.path_c(self.days, cutoffs, self.flags, CORRIDOR, self.series, replications=0, episodes=(episode,),
                            min_scarce=MIN_SCARCE)
        self.assertEqual(calls, [cutoffs[0]])
        self.assertEqual([p.refit.cutoff for p in path], cutoffs)
        self.assertEqual(len({p.refit.shares for p in path}), 1)
        self.assertTrue(all(p.refit.fitted for p in path))


class BaselinePathTests(unittest.TestCase):
    """The memoised baselines are the baselines: `baseline_path_c` and `_d` equal `real_time_path` of their modules."""

    def same(self, mine, theirs):
        self.assertEqual(len(mine), len(theirs))
        for a, b in zip(mine, theirs):
            self.assertEqual(a.refit, b.refit)
            self.assertEqual(a.estimates, b.estimates)
            self.assertEqual(a.gaps, b.gaps)
            self.assertEqual(a.missing_days, b.missing_days)
            self.assertEqual(a.break_days, b.break_days)

    def test_candidate_c(self):
        days = tc._planted_days(tc._weeks(), count=120)
        cutoffs = [days[20].day, days[40].day, days[41].day, days[80].day]
        kw = dict(replications=3, episodes=EPISODES, min_scarce=MIN_SCARCE)
        self.same(h.baseline_path_c(days, cutoffs, **kw), c.real_time_path(days, cutoffs, **kw))

    def test_candidate_d(self):
        days = td._planted_days(td._weeks(), count=120)
        cutoffs = [days[20].day, days[40].day, days[41].day, days[80].day]
        kw = dict(replications=2, episodes=EPISODES, min_scarce=MIN_SCARCE)
        self.same(h.baseline_path_d(days, cutoffs, **kw), d.real_time_path(days, cutoffs, **kw))


class NoFutureTests(unittest.TestCase):
    """A refit depends on the panel only through its training sample, which must be what the cut panel gives."""

    @classmethod
    def setUpClass(cls):
        cls.all_days = tc._planted_days(tc._weeks(), count=100)
        cls.rows = [DailyObservation(x.day, {}) for x in cls.all_days]
        cls.cutoffs = [cls.all_days[40].day, cls.all_days[70].day]

    def builder(self, leak=False):
        def build(rows):
            last = rows[-1].date
            days = [x for x in self.all_days if x.day <= last]
            series = {EFFR: {x.day: 0.8 * x.corridor + 0.1 + (0.001 * len(rows) if leak else 0.0) for x in days}}
            return days, _quiet_flags(days), series
        return build

    def check(self, build):
        h.check_no_future(self.rows, self.cutoffs, build, EFFR, lambda x: x.week is not None, episodes=EPISODES,
                          min_scarce=MIN_SCARCE)

    def test_a_sample_built_only_from_rows_up_to_the_cutoff_passes(self):
        self.check(self.builder())

    def test_a_sample_that_read_a_later_row_is_refused(self):
        with self.assertRaises(LookAheadError):
            self.check(self.builder(leak=True))


class TrackedPanelTests(unittest.TestCase):
    """The tracked fixtures: the panel's inputs for the run, checked and nothing fitted."""

    @classmethod
    def setUpClass(cls):
        from repo_liquidity import panel

        cls.rows, cls.pins = h.build_rows()
        cls.manifest = panel.load_manifest(4)
        cls.flags = h.read_flags(h.with_quarter_end_window(cls.rows), h.flag_rule(), _turn_label_or_stand_in())

    def test_the_version_4_columns_are_the_manifests_bytes_with_effr_added(self):
        self.assertEqual(self.pins["panel_sha256"], self.manifest["sha256"])
        self.assertEqual((self.pins["first_day"], self.pins["last_day"]), (self.manifest["start_date"], self.manifest["end_date"]))
        self.assertTrue(all("effr" in row.values for row in self.rows))

    def test_the_corridor_normalised_effr_is_known_on_every_day(self):
        from repo_liquidity import demand_curve, scheduled

        left = h.left_sides(self.rows)[EFFR]
        self.assertFalse([day for day, value in left.items() if value is None])
        publications = scheduled.load_on_rrp_rates()
        row = self.rows[500]
        floor = scheduled.rate_in_force(publications, row.date)
        self.assertEqual(left[row.date], demand_curve.corridor_position(
            sofr=float(row.values["effr"]), iorb=float(row.values["iorb"]), on_rrp_rate=floor))

    def test_only_the_second_row_has_flags_the_rule_cannot_read(self):
        self.assertEqual([day for day, f in self.flags.items() if f.unread], [self.rows[1].date])
        self.assertFalse([day for day, f in self.flags.items() if not f.unread and f.dropped() is None])

    def test_the_flags_drop_a_share_of_days_and_leave_the_rest(self):
        dropped = sum(1 for f in self.flags.values() if f.dropped())
        self.assertTrue(0 < dropped < len(self.flags))


class ScriptTests(_FitCase):
    """`scripts/h7_calendar_clean.py` prints its Markdown from the record and compares each variant with its baseline."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        import importlib.util
        from pathlib import Path

        path = Path(__file__).resolve().parents[1] / "scripts" / "h7_calendar_clean.py"
        spec = importlib.util.spec_from_file_location("h7_calendar_clean", path)
        cls.script = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.script)
        cls.days = tc._planted_days(tc._weeks(), count=120)
        cls.series = _effr_series(cls.days)
        cls.flags = _quiet_flags(cls.days)
        cls.cutoffs = [cls.days[40].day, cls.days[80].day]
        kw = dict(replications=2, episodes=EPISODES, min_scarce=MIN_SCARCE)
        cls.entries = {
            "C": cls.script._entry(h.baseline_path_c(cls.days, cls.cutoffs, **kw), 1.0,
                                   lambda refit: h.politis_white_block(h.baseline_residuals_c(cls.days, refit, episodes=EPISODES,
                                                                                              min_scarce=MIN_SCARCE))),
            "CV1": cls.script._entry(h.path_c(cls.days, cls.cutoffs, cls.flags, CORRIDOR, cls.series, **kw), 2.0),
        }

    def record(self):
        pins = {"panel_version": 1, "panel_sha256": "a" * 64, "parent_commit": "b" * 40, "effr_series_sha256": "c" * 64,
                "first_day": "2018-04-03", "last_day": "2025-12-31"}
        counts = self.script._episode_counts(self.days, self.flags, lambda x: x.week is not None)
        return {"tier": "development", "declaration": "docs/stages/h7-calendar-clean.md", "variant_count_added": 4,
                "not_run": {"D": h.D_NOT_RUN, **{v.id: h.D_NOT_RUN for v in h.D_VARIANTS}},
                "pins": pins, "window_end": "2025-12-31", "settings": {"replications": 2, "refit_every": 21, "block_length": 10},
                "cutoffs": [day.isoformat() for day in self.cutoffs], "unread_flag_days": ["2018-04-04"],
                "episode_counts": {"C": counts}, "estimators": self.entries, "comparison": self.script._compare(self.entries)}

    def test_each_variant_is_compared_with_its_own_baseline(self):
        comparison = self.script._compare(self.entries)
        self.assertEqual(set(comparison), {"CV1"})
        self.assertEqual(comparison["CV1"]["against"], "C")
        self.assertIn("baseline_worst_gap_points", comparison["CV1"])

    def test_the_markdown_is_printed_from_the_record(self):
        text = self.script.markdown(self.record())
        for needle in ("never edited by hand", "development", "| CV1 |", "| C |", "Goalposts 1 and 2", "2018-04-04",
                       "Politis", "not run (D dropped under #142)", "DV1"):
            self.assertIn(needle, text)

    def test_each_refit_reports_its_politis_white_block_beside_goalpost_2(self):
        for name, entry in self.entries.items():
            blocks = [r["politis_white_block"] for r in entry["refits"]]
            self.assertEqual(len(blocks), len(self.cutoffs), name)
            self.assertTrue(all(b is None or b > 0 for b in blocks), name)
            self.assertEqual(set(entry["summary"]["politis_white_block"]), {"refits", "median", "max"}, name)
            self.assertEqual(entry["summary"]["politis_white_block"]["refits"], sum(b is not None for b in blocks), name)

    def test_the_episode_counts_say_whether_an_episode_counts_clean(self):
        counts = self.script._episode_counts(self.days, self.flags, lambda x: x.week is not None)
        e = counts[EPISODES[0][0]] if EPISODES[0][0] in counts else next(iter(counts.values()))
        self.assertEqual(e["training_days"], e["clean_days"])  # nothing is flagged here
        self.assertEqual(e["scarce"], e["clean_scarce"])


class VariantTableTests(unittest.TestCase):
    def test_the_run_has_the_four_variants_of_c_and_d_is_not_run(self):
        self.assertEqual([v.id for v in h.VARIANTS], ["CV1", "CV2", "CV3", "CV4"])
        self.assertEqual({v.candidate for v in h.VARIANTS}, {"C"})
        # CV1: clean days, absolute deviation, SOFR corridor. CV2: the same on the corridor-normalised EFFR (replaces raw bp).
        # CV3: (a) only, clean days with least squares. CV4: (b) only, all days with absolute deviation.
        self.assertEqual([(v.days, v.objective, v.left) for v in h.VARIANTS],
                         [("clean", "lad", CORRIDOR), ("clean", "lad", EFFR), ("clean", "ls", CORRIDOR), ("all", "lad", CORRIDOR)])
        self.assertEqual([v.id for v in h.D_VARIANTS], ["DV1", "DV2", "DV3", "DV4"])
        self.assertEqual([(v.days, v.objective, v.left) for v in h.D_VARIANTS],
                         [(v.days, v.objective, v.left) for v in h.VARIANTS])
        self.assertEqual(h.D_NOT_RUN, "not run (D dropped under #142)")
        self.assertEqual({v.id for v in h.VARIANTS} & {v.id for v in h.D_VARIANTS}, set())


class TurnDayTests(unittest.TestCase):
    """Q1: the third clause of the exclusion set is `turn_label(T) is not None`, read from the parent at the scored day only. The
    label function is injected here (it exists only at the parent's next pin); `RealTurnLabelTests` runs the parent's own."""

    FIRST_OF_MAY, MID_APRIL = date(2019, 5, 1), date(2019, 4, 9)

    @classmethod
    def setUpClass(cls):
        cls.rows = _flag_rows()
        cls.calls = []

        def labeller(day):
            cls.calls.append(day)
            return "turn" if day == cls.FIRST_OF_MAY else None

        cls.flags = h.read_flags(cls.rows, h.flag_rule(), labeller)

    def test_a_turn_day_is_dropped_by_the_third_clause_alone(self):
        flag = self.flags[self.FIRST_OF_MAY]
        self.assertEqual((flag.settlement_day, flag.quarter_end_window, flag.turn), (0.0, 0.0, "turn"))
        self.assertTrue(flag.dropped())

    def test_a_day_with_no_label_stays_clean(self):
        flag = self.flags[self.MID_APRIL]
        self.assertEqual((flag.turn, flag.dropped()), (None, False))

    def test_the_label_is_asked_for_each_scored_day_once_and_for_no_other(self):
        self.assertEqual(sorted(self.calls), [row.date for row in self.rows[1:]])

    def test_a_label_read_for_another_day_is_refused(self):
        self.assertEqual(h.read_turn(lambda day: "turn", self.FIRST_OF_MAY, self.FIRST_OF_MAY), "turn")
        with self.assertRaises(LookAheadError):
            h.read_turn(lambda day: "turn", self.FIRST_OF_MAY, date(2019, 4, 30))

    def test_a_turn_day_is_not_a_training_day_and_does_not_count_toward_an_episode(self):
        days = tc._planted_days(tc._weeks(), count=100)
        flags = _quiet_flags(days)
        for i in (3, 4):
            flags[days[i].day] = h.Flags(days[i].day, 0.0, 0.0, False, "quarter_end_turn")
        series = _effr_series(days)
        sample, labels = h.training_days(days, days[-1].day, flags, CORRIDOR, series, lambda x: x.week is not None,
                                         episodes=EPISODES, min_scarce=MIN_SCARCE)
        self.assertEqual(len(sample), len(days) - 2)
        cutoff = days[MIN_SCARCE - 1].day  # exactly the minimum of days by the cutoff, which two turn days take below it
        args = (days, cutoff, None, CORRIDOR, series, lambda x: x.week is not None)
        self.assertEqual(h.training_days(*args, clean=False, episodes=EPISODES, min_scarce=MIN_SCARCE)[1], (EPISODES[0][0],))
        self.assertEqual(h.training_days(days, cutoff, flags, CORRIDOR, series, lambda x: x.week is not None,
                                         episodes=EPISODES, min_scarce=MIN_SCARCE)[1], ())

    def test_without_the_parents_function_the_flags_cannot_be_read(self):
        import sys

        with mock.patch.dict(sys.modules, {"repo_model.turn_days": None}):
            with self.assertRaises(ValueError) as caught:
                h.read_flags(self.rows, h.flag_rule())
        self.assertIn("turn_days", str(caught.exception))
        self.assertIn("#149", str(caught.exception))


def _has_turn_days():
    try:
        h.parent_turn_label()
    except ValueError:
        return False
    return True


@unittest.skipUnless(_has_turn_days(), "the parent at this tree's pin has no repo_model.turn_days; it comes with the pin move (#149)")
class RealTurnLabelTests(unittest.TestCase):
    """The parent's own `turn_label` through the exclusion set, on the cases the ruling names."""

    @classmethod
    def setUpClass(cls):
        cls.rows = _flag_rows(first=date(2021, 5, 17), last=date(2021, 6, 11))
        cls.flags = h.read_flags(cls.rows, h.flag_rule(), h.parent_turn_label())

    def test_the_last_business_day_three_calendar_days_before_month_end_is_dropped(self):
        flag = self.flags[date(2021, 5, 28)]  # Memorial Day is the 31st
        self.assertEqual((flag.settlement_day, flag.quarter_end_window), (0.0, 0.0))
        self.assertEqual(flag.turn, "turn")
        self.assertTrue(flag.dropped())

    def test_the_first_business_day_of_the_next_month_is_dropped(self):
        flag = self.flags[date(2021, 6, 1)]
        self.assertEqual((flag.settlement_day, flag.quarter_end_window, flag.turn), (0.0, 0.0, "turn"))
        self.assertTrue(flag.dropped())

    def test_a_mid_month_day_stays_clean(self):
        flag = self.flags[date(2021, 5, 19)]
        self.assertEqual((flag.turn, flag.dropped()), (None, False))

    def test_every_label_is_the_parents_own(self):
        from repo_model import turn_days

        for day, flag in self.flags.items():
            if not flag.unread:
                self.assertEqual(flag.turn, turn_days.turn_label(day), day)


class ObjectiveVariantTests(_FitCase):
    """Q4: CV3 is the calendar-clean days with least squares, CV4 is every day with absolute deviation."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.days = tc._planted_days(tc._weeks(), count=100)
        cls.series = _effr_series(cls.days)
        cls.flags = _quiet_flags(cls.days)
        cls.dropping = _quiet_flags(cls.days)
        for i in (20, 21, 22):
            cls.dropping[cls.days[i].day] = h.Flags(cls.days[i].day, 1.0, 0.0)

    def refit(self, flags, **kw):
        kw.setdefault("replications", 0)
        return h.refit_c(self.days, self.days[-1].day, flags, CORRIDOR, self.series, episodes=EPISODES, min_scarce=MIN_SCARCE,
                         **kw)

    def test_the_least_squares_curve_is_the_baselines_and_rejects_a_negative_slope(self):
        xs = [0.0, 0.01, 0.02, 0.03, 0.04, 0.05, 0.06]
        rising = [0.9, 0.7, 0.5, 0.3, 0.1, 0.1, 0.1]
        got = h.ls_curve(xs, rising)
        want = demand_curve.fit_broken_stick(xs, rising, h.KINK_GRID)
        self.assertEqual((got.kink, got.intercept, got.slope, got.objective), (want.kink, want.intercept, want.slope, want.sse))
        self.assertIsNone(h.ls_curve(xs, list(reversed(rising))))
        self.assertIsNone(h.ls_curve([0.5, 0.6], [1.0, 2.0]))  # no kink has points on both sides

    def test_cv3_on_days_nothing_drops_is_the_baseline_fit(self):
        mine = self.refit(self.flags, objective="ls")
        with mock.patch.object(c, "KINK_GRID", COARSE):  # the baseline searches the same kinks
            base = c.refit_c(self.days, self.days[-1].day, replications=0, episodes=EPISODES, min_scarce=MIN_SCARCE)
        self.assertEqual((mine.shares, mine.kink, mine.pairs), (base.shares, base.kink, base.pairs))
        self.assertAlmostEqual(mine.slope, base.slope)
        self.assertAlmostEqual(mine.intercept, base.intercept)
        self.assertAlmostEqual(mine.sse, base.sse)
        self.assertEqual(mine.record["objective_kind"], "ls")

    def test_cv3_drops_the_flagged_days(self):
        fit = self.refit(self.dropping, objective="ls")
        self.assertEqual((fit.pairs, fit.record["dropped"], fit.record["objective_kind"]), (len(self.days) - 3, 3, "ls"))

    def test_cv4_fits_every_day_even_where_the_flags_would_drop_them(self):
        fit = self.refit(self.dropping, clean=False)
        self.assertEqual((fit.pairs, fit.record["dropped"], fit.record["objective_kind"]), (len(self.days), 0, "lad"))
        self.assertEqual(fit.shares, tc.PLANTED)
        self.assertEqual(self.refit(None, clean=False).pairs, len(self.days))  # it reads no flags

    def test_cv1_and_cv4_differ_in_the_days_alone(self):
        clean, every = self.refit(self.dropping), self.refit(self.dropping, clean=False)
        self.assertEqual(clean.record["objective_kind"], every.record["objective_kind"])
        self.assertEqual(every.pairs - clean.pairs, 3)

    def test_the_bootstrap_of_each_variant_refits_under_its_own_objective(self):
        boom = mock.Mock(side_effect=AssertionError("the other objective was used"))
        with mock.patch.object(h, "lad_curve", boom):
            self.assertEqual(len(self.refit(self.flags, objective="ls", replications=3).draws), 3)
        with mock.patch.object(h, "ls_curve", boom):
            self.assertEqual(len(self.refit(self.flags, replications=3).draws), 3)

    def test_an_unknown_objective_is_a_data_error(self):
        with self.assertRaises(ValueError):
            self.refit(self.flags, objective="huber")

    def test_the_path_of_cv4_fits_on_the_flagged_days_and_the_path_of_cv1_does_not(self):
        cutoffs = [self.days[60].day, self.days[90].day]
        kw = dict(replications=0, episodes=EPISODES, min_scarce=MIN_SCARCE)
        every = h.path_c(self.days, cutoffs, self.dropping, CORRIDOR, self.series, clean=False, **kw)
        clean = h.path_c(self.days, cutoffs, self.dropping, CORRIDOR, self.series, **kw)
        self.assertEqual(every[0].refit.pairs - clean[0].refit.pairs, 3)

    def test_the_no_future_check_covers_the_variant_that_reads_no_flags(self):
        rows = [DailyObservation(x.day, {}) for x in self.days]
        h.check_no_future(rows, [self.days[40].day], lambda cut: (self.days[:len(cut)], None, self.series), CORRIDOR,
                          lambda x: x.week is not None, clean=False, episodes=EPISODES, min_scarce=MIN_SCARCE)


class CorridorEffrTests(unittest.TestCase):
    """Q2: the left side of CV2 is `(EFFR - ON RRP rate) / (IORB - ON RRP rate)`, in place of raw basis points."""

    def test_the_position_is_the_corridor_position_with_effr_in_place_of_sofr(self):
        rows = [DailyObservation(date(2019, 1, 2), {"sofr": 2.9, "iorb": 2.40, "effr": 2.33}),
                DailyObservation(date(2019, 1, 3), {"sofr": 2.9, "iorb": 2.40, "effr": 2.40})]
        got = h.left_sides(rows, lambda day: 2.25)[EFFR]
        self.assertEqual(got, {date(2019, 1, 2): round(0.08 / 0.15, 9), date(2019, 1, 3): 1.0})

    def test_a_wider_corridor_does_not_move_the_position_of_a_rate_at_the_same_place(self):
        rows = [DailyObservation(date(2019, 1, 2), {"iorb": 2.40, "effr": 2.325}),
                DailyObservation(date(2019, 1, 3), {"iorb": 2.40, "effr": 2.30})]
        wide = {date(2019, 1, 2): 2.25, date(2019, 1, 3): 2.20}  # 0.15 wide and 0.20 wide
        got = h.left_sides(rows, lambda day: wide[day])[EFFR]
        self.assertEqual(got[date(2019, 1, 2)], 0.5)
        self.assertEqual(got[date(2019, 1, 3)], 0.5)

    def test_a_missing_leg_or_rate_is_no_left_side_not_a_zero(self):
        rows = [DailyObservation(date(2019, 1, 2), {"iorb": 2.40, "effr": None}),
                DailyObservation(date(2019, 1, 3), {"iorb": 2.40, "effr": 2.3})]
        got = h.left_sides(rows, lambda day: None if day.day == 3 else 2.25)[EFFR]
        self.assertEqual(got, {date(2019, 1, 2): None, date(2019, 1, 3): None})

    def test_a_corridor_that_is_not_positive_is_a_data_error(self):
        rows = [DailyObservation(date(2019, 1, 2), {"iorb": 2.20, "effr": 2.3})]
        with self.assertRaises(ValueError):
            h.left_sides(rows, lambda day: 2.25)

    def test_the_raw_basis_point_series_is_not_offered_beside_it(self):
        rows = [DailyObservation(date(2019, 1, 2), {"iorb": 2.40, "effr": 2.33})]
        self.assertEqual(set(h.left_sides(rows, lambda day: 2.25)), {EFFR})


class PoliticsWhiteTests(unittest.TestCase):
    """Reporting only: the Politis-White block length of a refit's training residuals, beside goalpost 2. It changes nothing."""

    @staticmethod
    def ar1(phi, n, seed):
        import random

        rng, x, out = random.Random(seed), 0.0, []
        for _ in range(n + 200):
            x = phi * x + rng.gauss(0.0, 1.0)
            out.append(x)
        return out[200:]

    def test_white_noise_wants_a_short_block(self):
        self.assertLessEqual(h.politis_white_block(self.ar1(0.0, 1000, 1)), 3.0)

    def test_the_block_matches_the_published_estimator_on_a_fixed_series(self):
        # arch.bootstrap.optimal_block_length (the Politis-White / Patton-Politis-White estimator) gives 49.229 for this series
        self.assertAlmostEqual(h.politis_white_block(self.ar1(0.9, 1000, 1)), 49.23, places=2)

    def test_a_persistent_series_wants_a_long_block(self):
        self.assertGreater(h.politis_white_block(self.ar1(0.9, 1000, 1)), 10.0)

    def test_a_more_persistent_series_wants_a_longer_block(self):
        self.assertLess(h.politis_white_block(self.ar1(0.5, 1000, 2)), h.politis_white_block(self.ar1(0.9, 1000, 2)))

    def test_the_block_is_the_same_for_the_same_series_and_for_a_shifted_or_scaled_one(self):
        x = self.ar1(0.8, 600, 3)
        self.assertEqual(h.politis_white_block(x), h.politis_white_block(list(x)))
        self.assertEqual(h.politis_white_block(x), h.politis_white_block([5.0 + 3.0 * v for v in x]))

    def test_it_never_exceeds_the_published_cap(self):
        x = self.ar1(0.99, 300, 4)
        self.assertLessEqual(h.politis_white_block(x), min(3.0 * len(x) ** 0.5, len(x) / 3.0) + 1.0)

    def test_a_series_with_no_variation_or_too_short_has_no_block(self):
        self.assertIsNone(h.politis_white_block([0.0] * 100))
        self.assertIsNone(h.politis_white_block([1.0, 2.0, 1.5]))

    def test_a_fitted_refit_records_the_block_of_its_training_residuals(self):
        days = tc._planted_days(tc._weeks(), count=100)
        noisy = {EFFR: {x.day: 0.8 * x.corridor + 0.1 + 0.004 * v for x, v in zip(days, self.ar1(0.9, len(days), 5))}}
        fit = h.refit_c(days, days[-1].day, _quiet_flags(days), EFFR, noisy, replications=0, episodes=EPISODES,
                        min_scarce=MIN_SCARCE)
        self.assertTrue(fit.fitted, fit.record)
        self.assertIsInstance(fit.record["pw_block"], float)
        self.assertGreater(fit.record["pw_block"], 1.0)

    def test_a_refit_that_is_not_fitted_has_no_block(self):
        days = tc._planted_days(tc._weeks(), count=100)
        fit = h.refit_c(days, days[5].day, _quiet_flags(days), CORRIDOR, _effr_series(days), replications=0,
                        episodes=EPISODES, min_scarce=MIN_SCARCE)
        self.assertNotIn("pw_block", fit.record)

    def test_the_baselines_residuals_are_their_own_fit_on_their_own_days(self):
        days = tc._planted_days(tc._weeks(), count=100)
        base = c.refit_c(days, days[-1].day, replications=0, episodes=EPISODES, min_scarce=MIN_SCARCE)
        residuals = h.baseline_residuals_c(days, base, episodes=EPISODES, min_scarce=MIN_SCARCE)
        self.assertEqual(len(residuals), base.pairs)
        self.assertAlmostEqual(sum(r * r for r in residuals), base.sse, places=9)


if __name__ == "__main__":
    unittest.main()
