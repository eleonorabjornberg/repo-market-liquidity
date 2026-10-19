"""H7m, groundwork G6, third record (`docs/stages/h7-g6.md` §11): the calendar flags, the calendar-tied event process and
the calendar-stratified statistic's strata.

Synthetic data only. The flags are read from the parent's panel columns (`treasury_settlement_coupons`, `quarter_end`); no
calendar is re-implemented. A missing value in either column is a data error, never a zero.

**Recorded mutations** (CLAUDE.md), 19 October 2026, in a disposable copy of the tree, CPython 3.11, the parent at the pin
(8fd2cf8), `PYTHONDONTWRITEBYTECODE=1`, applied by `sed` and confirmed by `grep`, the suite run against the copy, the copy
discarded:

* the missing-column guard, `if coupons is None or quarter_end is None: raise ValueError(...)` in `calendar_flags`,
  replaced by `if False:` (the guard removed): `test_a_hole_in_a_calendar_column_is_a_data_error` errored with
  `TypeError: float() argument must be a string or a real number, not 'NoneType'` instead of raising `ValueError`.
* the lag in the fit, `previous, today = event[:-1], event[1:]` in `fit_calendar_process`, replaced by
  `previous, today = event[1:], event[1:]` (the design then reads the day it predicts, the look-ahead the declaration
  forbids): `test_the_fit_reads_the_previous_day_never_the_day_itself` failed with
  `AssertionError: 8.182100780480217 not less than -2.0`.

Written first, and watched failing: before `calendar_flags` existed this module did not import:
`AttributeError: module 'repo_liquidity.goalposts' has no attribute 'calendar_flags'`.
"""

from __future__ import annotations

import math
import random
import unittest
from datetime import date

from repo_liquidity import goalposts as gp


def _values(coupons=0.0, quarter_end=0.0):
    return {"treasury_settlement_coupons": coupons, "quarter_end": quarter_end}


class FlagTests(unittest.TestCase):
    def test_a_coupon_settlement_on_or_before_the_20th_is_mid_month(self):
        self.assertEqual(gp.calendar_flags(date(2025, 4, 15), _values(coupons=31.0)), gp.Calendar(1, 0, 0, 0))
        self.assertEqual(gp.calendar_flags(date(2025, 4, 20), _values(coupons=1.0)), gp.Calendar(1, 0, 0, 0))

    def test_a_coupon_settlement_after_the_20th_is_month_end(self):
        self.assertEqual(gp.calendar_flags(date(2025, 4, 30), _values(coupons=5.0)), gp.Calendar(0, 1, 0, 0))
        self.assertEqual(gp.calendar_flags(date(2025, 4, 21), _values(coupons=5.0)), gp.Calendar(0, 1, 0, 0))

    def test_no_coupon_is_no_coupon_flag(self):
        self.assertEqual(gp.calendar_flags(date(2025, 4, 15), _values(coupons=0.0)), gp.Calendar(0, 0, 0, 0))

    def test_a_quarter_end_is_flagged_and_a_december_one_is_also_a_year_end(self):
        self.assertEqual(gp.calendar_flags(date(2025, 9, 30), _values(coupons=4.0, quarter_end=1.0)),
                         gp.Calendar(0, 1, 1, 0))
        self.assertEqual(gp.calendar_flags(date(2025, 12, 31), _values(coupons=4.0, quarter_end=1.0)),
                         gp.Calendar(0, 1, 1, 1))

    def test_a_december_day_that_is_not_a_quarter_end_is_no_year_end(self):
        self.assertEqual(gp.calendar_flags(date(2025, 12, 15), _values(quarter_end=0.0)).year_end, 0)

    def test_a_hole_in_a_calendar_column_is_a_data_error(self):
        for values in ({"treasury_settlement_coupons": None, "quarter_end": 0.0},
                       {"treasury_settlement_coupons": 0.0, "quarter_end": None},
                       {"quarter_end": 0.0}):
            with self.assertRaises(ValueError):
                gp.calendar_flags(date(2025, 4, 15), values)

    def test_the_class_ranks_quarter_end_over_month_end_over_mid_month_over_none(self):
        self.assertEqual(gp.calendar_class(gp.Calendar(0, 0, 0, 0)), 0)
        self.assertEqual(gp.calendar_class(gp.Calendar(1, 0, 0, 0)), 1)
        self.assertEqual(gp.calendar_class(gp.Calendar(0, 1, 0, 0)), 2)
        self.assertEqual(gp.calendar_class(gp.Calendar(0, 1, 1, 0)), 3)
        self.assertEqual(gp.calendar_class(gp.Calendar(0, 1, 1, 1)), 3)

    def test_the_strata_cross_the_state_with_the_class_and_keep_each_pair_apart(self):
        flags = [gp.Calendar(0, 0, 0, 0), gp.Calendar(1, 0, 0, 0), gp.Calendar(0, 1, 1, 0), gp.Calendar(0, 0, 0, 0)]
        strata = gp.calendar_strata([0.0, 0.0, 3.0, 3.0], flags)
        self.assertEqual(len(set(strata)), 4)
        self.assertEqual(strata[0], gp.calendar_strata([0.0], [flags[0]])[0])
        self.assertNotEqual(gp.calendar_strata([1.0], [flags[0]])[0], gp.calendar_strata([0.0], [flags[3]])[0] + 0.0)

    def test_the_strata_need_one_flag_per_day(self):
        with self.assertRaises(ValueError):
            gp.calendar_strata([0.0, 1.0], [gp.Calendar(0, 0, 0, 0)])


class IndependentProcessTests(unittest.TestCase):
    def test_it_is_the_observed_share_with_no_memory(self):
        process = gp.independent_process([0, 1, 0, 0, 1, 0, 0, 0])
        self.assertEqual((process.start, process.stay), (0.25, 0.25))
        self.assertAlmostEqual(process.stationary, 0.25)

    def test_a_series_with_no_event_or_only_events_is_not_fitted(self):
        for series in ([0, 0, 0], [1, 1], []):
            with self.assertRaises(ValueError):
                gp.independent_process(series)


def _flag_cycle(n, every=5):
    return [gp.Calendar(0, 0, 1 if i % every == 0 else 0, 0) for i in range(n)]


class CalendarFitTests(unittest.TestCase):
    def test_without_a_penalty_the_fit_solves_the_score_equations(self):
        # The model is additive in the previous day and the flag, so the cells' shares are not reproduced; the
        # maximum-likelihood fit satisfies sum((p - y) * x) = 0 for the intercept, the previous day and the flag.
        rng = random.Random(11)
        flags = [gp.Calendar(0, 0, int(rng.random() < 0.3), 0) for _ in range(400)]
        event = [int(rng.random() < 0.4) for _ in range(400)]
        fit = gp.fit_calendar_process(event, flags, ridge=0.0)
        residuals = [(fit.probability(prev, flag) - today, prev, flag.quarter_end)
                     for prev, today, flag in zip(event, event[1:], flags[1:])]
        self.assertAlmostEqual(sum(r for r, _, _ in residuals), 0.0, places=6)
        self.assertAlmostEqual(sum(r * prev for r, prev, _ in residuals), 0.0, places=6)
        self.assertAlmostEqual(sum(r * flagged for r, _, flagged in residuals), 0.0, places=6)

    def test_the_penalty_shrinks_the_slopes_toward_zero_and_leaves_the_intercept_alone(self):
        rng = random.Random(3)
        flags = [gp.Calendar(0, 0, int(rng.random() < 0.1), 0) for _ in range(300)]
        event = [int(rng.random() < (0.6 if f.quarter_end else 0.05)) for f in flags]
        free = gp.fit_calendar_process(event, flags, ridge=0.0)
        shrunk = gp.fit_calendar_process(event, flags)
        self.assertEqual(shrunk.ridge, gp.RIDGE)
        self.assertLess(abs(shrunk.coefficients[4]), abs(free.coefficients[4]))
        self.assertGreater(abs(free.coefficients[4]), 0.5)

    def test_a_flag_that_never_occurs_has_a_zero_slope_under_the_penalty(self):
        rng = random.Random(4)
        event = [int(rng.random() < 0.2) for _ in range(200)]
        fit = gp.fit_calendar_process(event, [gp.Calendar(0, 0, 0, 0)] * 200)
        for slope in fit.coefficients[2:]:
            self.assertAlmostEqual(slope, 0.0, places=9)

    def test_the_fit_reads_the_previous_day_never_the_day_itself(self):
        """An alternating series: an event follows a quiet day and a quiet day follows an event, so the slope on the
        previous day is strongly negative. Reading the day itself as the predictor would make it strongly positive."""
        event = [i % 2 for i in range(200)]
        fit = gp.fit_calendar_process(event, [gp.Calendar(0, 0, 0, 0)] * 200, ridge=0.1)
        self.assertLess(fit.coefficients[1], -2.0)

    def test_the_pairs_and_events_are_counted(self):
        event = [0, 1, 1, 0, 0]
        fit = gp.fit_calendar_process(event, [gp.Calendar(0, 0, 0, 0)] * 5)
        self.assertEqual((fit.days, fit.events, fit.pairs), (5, 2, 4))
        self.assertAlmostEqual(fit.share, 2 / 5)

    def test_columns_of_different_lengths_are_a_data_error(self):
        with self.assertRaises(ValueError):
            gp.fit_calendar_process([0, 1, 0], [gp.Calendar(0, 0, 0, 0)] * 2)

    def test_a_series_with_no_event_or_no_quiet_day_is_not_fitted(self):
        for series in ([0] * 10, [1] * 10, [1]):
            with self.assertRaises(ValueError):
                gp.fit_calendar_process(series, [gp.Calendar(0, 0, 0, 0)] * len(series))

    def test_a_negative_penalty_is_a_data_error(self):
        with self.assertRaises(ValueError):
            gp.fit_calendar_process([0, 1, 0, 1], [gp.Calendar(0, 0, 0, 0)] * 4, ridge=-1.0)

    def test_the_probability_is_the_logistic_of_the_declared_form(self):
        fit = gp.CalendarProcess((-2.0, 1.0, 0.5, 0.25, 1.5, 0.75), 0.1, 10, 1, 1.0, 9)
        flags = gp.Calendar(1, 0, 1, 1)
        expected = 1.0 / (1.0 + math.exp(-(-2.0 + 1.0 + 0.5 + 1.5 + 0.75)))
        self.assertAlmostEqual(fit.probability(1, flags), expected)
        self.assertAlmostEqual(fit.probability(0, gp.Calendar(0, 0, 0, 0)), 1.0 / (1.0 + math.exp(2.0)))


class CalendarSimulationTests(unittest.TestCase):
    def setUp(self):
        self.process = gp.CalendarProcess((-3.0, 1.0, 0.0, 0.0, 4.0, 0.0), 0.1, 400, 40, 1.0, 399)

    def test_a_series_is_seeded_and_one_event_indicator_per_flag(self):
        flags = _flag_cycle(500)
        a = gp.simulate_calendar_events(self.process, flags, random.Random(1))
        self.assertEqual(len(a), 500)
        self.assertEqual(a, gp.simulate_calendar_events(self.process, flags, random.Random(1)))
        self.assertNotEqual(a, gp.simulate_calendar_events(self.process, flags, random.Random(2)))
        self.assertTrue(set(a) <= {0, 1})

    def test_events_are_far_likelier_on_flagged_days(self):
        flags = _flag_cycle(20000)
        a = gp.simulate_calendar_events(self.process, flags, random.Random(5))
        flagged = [e for e, f in zip(a, flags) if f.quarter_end]
        plain = [e for e, f in zip(a, flags) if not f.quarter_end]
        self.assertGreater(sum(flagged) / len(flagged), 0.5)
        self.assertLess(sum(plain) / len(plain), 0.2)

    def test_no_flags_is_no_series(self):
        self.assertEqual(gp.simulate_calendar_events(self.process, [], random.Random(1)), [])


if __name__ == "__main__":
    unittest.main()
