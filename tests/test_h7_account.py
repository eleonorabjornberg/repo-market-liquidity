"""H7m, development step 4: the account of the bank distribution for A and C (`docs/stages/h7-step4.md`, directive #144).

Aggregate deployable liquidity under the three declared alternatives of protocol section 8 (as observed, all reserves held by the
large domestic banks, in proportion to group assets), per served day, with the 90% interval where the estimator has one and the
group-by-group terms for the estimators that model groups. It decides nothing and scores nothing. All inputs here are synthetic.
What is covered:

* `ScheduleTests` -- a refit serves from the second business day after its cutoff to the day before the next refit serves from.
* `AccountCTests` -- C's account is step 2's own machinery (`h7_candidate_c.distribution`): the as-observed figure is C's
  estimate, the alternatives hold the same total reserves, the groups sum to the aggregate, the interval is the bootstrap's, a
  refit that did not fit or a day with no group week is counted missing, a break week is flagged.
* `AOwnTests` -- A as defined (`R - k`) has no per-group term, so the three alternatives give the same figure (the reason, shown
  on a constructed composition change); its interval is the kink's, flipped.
* `AGroupedTests` -- A's kink read as every group's share, through step 2's machinery: the alternatives differ where the clip
  bites, the aggregate does not increase with the share (so the interval's endpoints are the aggregate at the kink's ends).
* `GuardTests` -- a day served before its refit's lag, or by a week not public at its instant, is `LookAheadError`.
* `SummaryTests` -- medians, ranges, zero days, years and differences from the as-observed figure, and the empty account.
* `RecordTests` -- a refit that does not match the tracked record is `ValueError`; the record dumps and loads back unchanged.

**Recorded mutation** (CLAUDE.md), 23 October 2026, in a disposable copy of the tree, CPython 3.11.17, the parent at the pin
(08ff67e), applied by a one-line replacement and confirmed by `grep`, the suite run against the copy, the copy discarded:

1. `serving_starts`: replace `next_business_day(cut, SERVING_LAG)` by `next_business_day(cut, 0)` (a refit serves the day of its
   cutoff, whose own scored day it was fitted on). The guard `check_served_after_cutoff` raises
   `repo_model.splits.LookAheadError: 2019-01-31 is served by the refit at 2019-01-31, before its serving day 2019-02-04` from every
   `account_*` call that builds a served day (28 errors; 29 of 42 tests fail), and `ScheduleTests` fails with `AssertionError`.

Written first, and watched failing: before `repo_liquidity.h7_account` existed the module did not import:
`ImportError: cannot import name 'h7_account' from 'repo_liquidity'`.
"""

from __future__ import annotations

import json
import unittest
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from repo_model.data import next_business_day
from repo_model.splits import LookAheadError

from repo_liquidity import h7_account as a
from repo_liquidity import h7_candidate_c as c

NEW_YORK = ZoneInfo("America/New_York")
ASSETS = (9500.0, 5000.0, 2300.0)
SHARES = (0.06, 0.14, 0.03)
FIRST_CUTOFF = date(2019, 1, 31)


def _days(start, count):
    out = [start]
    while len(out) < count:
        out.append(next_business_day(out[-1], 1))
    return out


def _release(wednesday):
    return datetime.combine(wednesday + timedelta(days=9), time(16, 15), tzinfo=NEW_YORK)


def _week(wednesday, reserves, brk=False):
    return c.GroupWeek(wednesday, _release(wednesday), tuple(reserves), ASSETS, brk)


def _day(day, week, ratio=0.12):
    instant = datetime.combine(day, time(16, 0), tzinfo=NEW_YORK)
    return c.DayC(day, instant, ratio, 0.5, 0.0, week)


def _refit(cutoff, shares=SHARES, fitted=True, draws=()):
    return c.RefitC(cutoff, shares if fitted else None, fitted, 0.03 if fitted else None, 0.5, 20.0, 1.0, 100, ("e",), True,
                    (), tuple(draws), {"fitted": fitted})


def _a_refit(cutoff, kink=0.10, lower=0.09, upper=0.12, fitted=True):
    return a.ARefit(cutoff, fitted, kink if fitted else None, lower if fitted else None, upper if fitted else None)


WEEK = _week(date(2018, 12, 26), (900.0, 300.0, 400.0))
DAYS = [_day(day, WEEK) for day in _days(date(2019, 1, 31), 40)]
CUTOFFS = [DAYS[0].day, DAYS[20].day]


class ScheduleTests(unittest.TestCase):
    def test_a_refit_serves_from_the_second_business_day_after_its_cutoff(self):
        index = a.serving_index([d.day for d in DAYS], CUTOFFS)
        start0 = next_business_day(CUTOFFS[0], 2)
        start1 = next_business_day(CUTOFFS[1], 2)
        self.assertNotIn(DAYS[0].day, index)
        self.assertNotIn(DAYS[1].day, index)
        self.assertEqual(index[start0], 0)
        self.assertEqual(index[start1], 1)
        before = [d.day for d in DAYS if d.day < start1][-1]
        self.assertEqual(index[before], 0)
        self.assertEqual(index[DAYS[-1].day], 1)

    def test_cutoffs_must_increase(self):
        with self.assertRaises(ValueError):
            a.serving_index([d.day for d in DAYS], [CUTOFFS[1], CUTOFFS[0]])


class AccountCTests(unittest.TestCase):
    def setUp(self):
        self.draws = [(0.05, 0.13, 0.02), (0.07, 0.15, 0.04), (0.06, 0.14, 0.03)] * 4
        self.refits = [_refit(CUTOFFS[0], draws=self.draws), _refit(CUTOFFS[1], shares=(0.08, 0.14, 0.03), draws=self.draws)]
        self.account = a.account_c("C", DAYS, CUTOFFS, self.refits)

    def test_a_refit_serves_from_the_second_business_day_after_its_cutoff(self):
        first = next_business_day(CUTOFFS[0], 2)
        self.assertEqual(self.account.served[0].day, first)
        self.assertEqual(self.account.served[0].cutoff, CUTOFFS[0])
        by_day = {s.day: s for s in self.account.served}
        self.assertEqual(by_day[next_business_day(CUTOFFS[1], 2)].cutoff, CUTOFFS[1])

    def test_the_as_observed_figure_is_the_estimate_of_the_current_machinery(self):
        for s in self.account.served:
            shares = self.refits[0 if s.cutoff == CUTOFFS[0] else 1].shares
            self.assertAlmostEqual(s.figures["as_observed"].aggregate, c.deployable(WEEK, shares), places=12)

    def test_every_alternative_is_step_twos_distribution(self):
        s = self.account.served[0]
        expected = c.distribution(WEEK, SHARES)
        for name in a.ALTERNATIVES:
            self.assertAlmostEqual(s.figures[name].aggregate, expected[name]["aggregate"], places=12)
            self.assertEqual(s.figures[name].groups, expected[name]["groups"])

    def test_the_groups_sum_to_the_aggregate_and_the_alternatives_differ(self):
        s = self.account.served[0]
        for name in a.ALTERNATIVES:
            self.assertAlmostEqual(sum(s.figures[name].groups), s.figures[name].aggregate, places=12)
        values = {round(s.figures[name].aggregate, 9) for name in a.ALTERNATIVES}
        self.assertGreater(len(values), 1)

    def test_the_interval_is_the_bootstrap_of_each_alternative_and_holds_the_point(self):
        s = self.account.served[0]
        for name in a.ALTERNATIVES:
            fig = s.figures[name]
            values = sorted(c.distribution(WEEK, draw)[name]["aggregate"] for draw in self.draws)
            self.assertLessEqual(fig.lower, fig.aggregate)
            self.assertGreaterEqual(fig.upper, fig.aggregate)
            self.assertLessEqual(fig.lower, values[len(values) // 2])
            self.assertGreaterEqual(fig.upper, values[len(values) // 2])
            self.assertGreater(fig.upper - fig.lower, 0.0)

    def test_a_refit_with_no_draws_has_no_interval(self):
        account = a.account_c("C", DAYS, CUTOFFS, [_refit(CUTOFFS[0]), _refit(CUTOFFS[1])])
        fig = account.served[0].figures["as_observed"]
        self.assertIsNone(fig.lower)
        self.assertIsNone(fig.upper)

    def test_a_refit_that_did_not_fit_serves_nothing_and_its_days_are_counted(self):
        account = a.account_c("CV", DAYS, CUTOFFS, [_refit(CUTOFFS[0], fitted=False), _refit(CUTOFFS[1])])
        start1 = next_business_day(CUTOFFS[1], 2)
        self.assertTrue(all(s.day >= start1 for s in account.served))
        reasons = set(account.missing.values())
        self.assertEqual(reasons, {a.NOT_FITTED})
        self.assertEqual(len(account.missing), len([d for d in DAYS if next_business_day(CUTOFFS[0], 2) <= d.day < start1]))

    def test_a_day_with_no_group_week_or_no_ratio_is_counted_missing(self):
        days = list(DAYS)
        days[5] = days[5]._replace(week=None)
        days[6] = days[6]._replace(ratio=None)
        account = a.account_c("C", days, CUTOFFS, self.refits)
        self.assertEqual(account.missing[days[5].day], a.NO_WEEK)
        self.assertEqual(account.missing[days[6].day], a.NO_RATIO)
        self.assertNotIn(days[5].day, {s.day for s in account.served})

    def test_a_break_week_is_flagged_and_still_served(self):
        brk = _week(date(2018, 12, 26), (900.0, 300.0, 400.0), brk=True)
        days = [_day(d.day, brk) for d in DAYS]
        account = a.account_c("C", days, CUTOFFS, self.refits)
        self.assertTrue(all(s.break_week for s in account.served))
        self.assertEqual(len(account.served), len(self.account.served))

    def test_there_is_one_refit_for_each_cutoff(self):
        with self.assertRaises(ValueError):
            a.account_c("C", DAYS, CUTOFFS, self.refits[:1])


class AOwnTests(unittest.TestCase):
    def test_the_aggregate_is_the_ratio_minus_the_kink_under_every_alternative(self):
        account = a.account_a_own("B", DAYS, CUTOFFS, [_a_refit(CUTOFFS[0]), _a_refit(CUTOFFS[1], kink=0.11, lower=0.10, upper=0.13)])
        s = account.served[0]
        for name in a.ALTERNATIVES:
            self.assertAlmostEqual(s.figures[name].aggregate, 0.12 - 0.10, places=12)
            self.assertIsNone(s.figures[name].groups)

    def test_moving_reserves_between_groups_does_not_move_it(self):
        """The reason, constructed: the same total reserves in two compositions, and the same ratio."""
        other = _week(date(2018, 12, 26), (1600.0, 0.0, 0.0))
        refits = [_a_refit(CUTOFFS[0]), _a_refit(CUTOFFS[1])]
        one = a.account_a_own("B", DAYS, CUTOFFS, refits)
        two = a.account_a_own("B", [_day(d.day, other) for d in DAYS], CUTOFFS, refits)
        self.assertEqual([s.figures for s in one.served], [s.figures for s in two.served])

    def test_the_interval_is_the_kinks_interval_flipped(self):
        account = a.account_a_own("B", DAYS, CUTOFFS, [_a_refit(CUTOFFS[0]), _a_refit(CUTOFFS[1])])
        fig = account.served[0].figures["as_observed"]
        self.assertAlmostEqual(fig.lower, 0.12 - 0.12, places=12)
        self.assertAlmostEqual(fig.upper, 0.12 - 0.09, places=12)

    def test_it_needs_no_group_week(self):
        days = [d._replace(week=None) for d in DAYS]
        account = a.account_a_own("B", days, CUTOFFS, [_a_refit(CUTOFFS[0]), _a_refit(CUTOFFS[1])])
        self.assertTrue(account.served)

    def test_a_refit_that_did_not_fit_serves_nothing(self):
        account = a.account_a_own("V", DAYS, CUTOFFS, [_a_refit(CUTOFFS[0], fitted=False), _a_refit(CUTOFFS[1])])
        self.assertEqual(set(account.missing.values()), {a.NOT_FITTED})


class AGroupedTests(unittest.TestCase):
    def test_the_kink_is_every_groups_share_through_step_twos_machinery(self):
        account = a.account_a_grouped("B", DAYS, CUTOFFS, [_a_refit(CUTOFFS[0]), _a_refit(CUTOFFS[1])])
        s = account.served[0]
        expected = c.distribution(WEEK, (0.10, 0.10, 0.10))
        for name in a.ALTERNATIVES:
            self.assertAlmostEqual(s.figures[name].aggregate, expected[name]["aggregate"], places=12)
            self.assertEqual(s.figures[name].groups, expected[name]["groups"])

    def test_the_alternatives_differ_where_the_clip_bites(self):
        account = a.account_a_grouped("B", DAYS, CUTOFFS, [_a_refit(CUTOFFS[0]), _a_refit(CUTOFFS[1])])
        s = account.served[0]
        values = {round(s.figures[name].aggregate, 9) for name in a.ALTERNATIVES}
        self.assertEqual(len(values), 3)

    def test_the_aggregate_does_not_increase_with_the_share(self):
        weeks = [WEEK, _week(date(2018, 12, 26), (1600.0, 0.0, 0.0)), _week(date(2018, 12, 26), (0.0, 800.0, 800.0))]
        for week in weeks:
            for name in a.ALTERNATIVES:
                last = None
                for k in (0.0, 0.02, 0.05, 0.08, 0.10, 0.12, 0.15, 0.2, 0.3):
                    value = c.distribution(week, (k, k, k))[name]["aggregate"]
                    if last is not None:
                        self.assertLessEqual(value, last + 1e-12)
                    last = value

    def test_the_interval_is_the_aggregate_at_the_kinks_upper_and_lower_ends(self):
        account = a.account_a_grouped("B", DAYS, CUTOFFS, [_a_refit(CUTOFFS[0]), _a_refit(CUTOFFS[1])])
        s = account.served[0]
        for name in a.ALTERNATIVES:
            low = c.distribution(WEEK, (0.12, 0.12, 0.12))[name]["aggregate"]
            high = c.distribution(WEEK, (0.09, 0.09, 0.09))[name]["aggregate"]
            self.assertAlmostEqual(s.figures[name].lower, low, places=12)
            self.assertAlmostEqual(s.figures[name].upper, high, places=12)

    def test_a_day_with_no_group_week_is_missing_not_estimated(self):
        days = list(DAYS)
        days[7] = days[7]._replace(week=None)
        account = a.account_a_grouped("B", days, CUTOFFS, [_a_refit(CUTOFFS[0]), _a_refit(CUTOFFS[1])])
        self.assertEqual(account.missing[days[7].day], a.NO_WEEK)


class GuardTests(unittest.TestCase):
    def test_a_day_served_before_the_lag_is_refused(self):
        early = a.ServedDay(CUTOFFS[0], CUTOFFS[0], False, {})
        with self.assertRaises(LookAheadError):
            a.check_served_after_cutoff([early])

    def test_the_day_after_the_cutoff_is_still_too_early(self):
        early = a.ServedDay(next_business_day(CUTOFFS[0], 1), CUTOFFS[0], False, {})
        with self.assertRaises(LookAheadError):
            a.check_served_after_cutoff([early])

    def test_the_second_business_day_is_allowed(self):
        a.check_served_after_cutoff([a.ServedDay(next_business_day(CUTOFFS[0], 2), CUTOFFS[0], False, {})])

    def test_a_group_week_public_after_the_decision_instant_is_refused(self):
        late = _week(date(2019, 1, 30), (900.0, 300.0, 400.0))
        days = [_day(d.day, late) for d in DAYS]
        with self.assertRaises(LookAheadError):
            a.account_c("C", days, CUTOFFS, [_refit(CUTOFFS[0]), _refit(CUTOFFS[1])])


class SummaryTests(unittest.TestCase):
    def setUp(self):
        self.refits = [_refit(CUTOFFS[0]), _refit(CUTOFFS[1])]
        self.account = a.account_c("C", DAYS, CUTOFFS, self.refits)
        self.summary = a.summarise(self.account)

    def test_it_counts_served_and_missing_days(self):
        self.assertEqual(self.summary["served_days"], len(self.account.served))
        self.assertEqual(self.summary["missing_days"], len(self.account.missing))

    def test_each_alternative_has_points_of_bank_assets(self):
        figures = sorted(s.figures["as_observed"].aggregate for s in self.account.served)
        row = self.summary["alternatives"]["as_observed"]
        self.assertAlmostEqual(row["median_points"], 100.0 * figures[len(figures) // 2], places=9)
        self.assertAlmostEqual(row["min_points"], 100.0 * figures[0], places=9)
        self.assertAlmostEqual(row["max_points"], 100.0 * figures[-1], places=9)
        self.assertEqual(row["days"], len(figures))

    def test_the_difference_from_as_observed_is_zero_for_as_observed(self):
        self.assertEqual(self.summary["alternatives"]["as_observed"]["median_difference_points"], 0.0)

    def test_zero_days_are_counted(self):
        week = _week(date(2018, 12, 26), (10.0, 10.0, 10.0))
        account = a.account_c("C", [_day(d.day, week) for d in DAYS], CUTOFFS, self.refits)
        row = a.summarise(account)["alternatives"]["as_observed"]
        self.assertEqual(row["days_at_zero"], row["days"])

    def test_groups_are_reported_where_the_estimator_has_them(self):
        groups = self.summary["alternatives"]["all_large_domestic"]["groups"]
        self.assertEqual(set(groups), set(c.GROUPS))
        own = a.summarise(a.account_a_own("B", DAYS, CUTOFFS, [_a_refit(CUTOFFS[0]), _a_refit(CUTOFFS[1])]))
        self.assertNotIn("groups", own["alternatives"]["as_observed"])

    def test_the_median_width_is_in_points_and_none_without_intervals(self):
        self.assertIsNone(self.summary["alternatives"]["as_observed"]["median_width_points"])
        own = a.summarise(a.account_a_own("B", DAYS, CUTOFFS, [_a_refit(CUTOFFS[0]), _a_refit(CUTOFFS[1])]))
        self.assertAlmostEqual(own["alternatives"]["as_observed"]["median_width_points"], 3.0, places=9)

    def test_the_years_split_the_served_days(self):
        years = self.summary["by_year"]
        self.assertEqual(sum(row["days"] for row in years.values()), self.summary["served_days"])
        self.assertTrue(set(years) <= {"2019"})

    def test_an_account_that_serves_nothing_is_said_so(self):
        empty = a.account_c("CV1", DAYS, CUTOFFS, [_refit(CUTOFFS[0], fitted=False), _refit(CUTOFFS[1], fitted=False)])
        summary = a.summarise(empty)
        self.assertEqual(summary["served_days"], 0)
        self.assertEqual(summary["alternatives"], {})
        self.assertGreater(summary["missing_days"], 0)

    def test_break_week_days_are_counted(self):
        brk = _week(date(2018, 12, 26), (900.0, 300.0, 400.0), brk=True)
        account = a.account_c("C", [_day(d.day, brk) for d in DAYS], CUTOFFS, self.refits)
        summary = a.summarise(account)
        self.assertEqual(summary["break_week_days"], summary["served_days"])


class RecordTests(unittest.TestCase):
    def test_a_refit_that_matches_the_record_passes(self):
        refits = [_refit(CUTOFFS[0]), _refit(CUTOFFS[1], fitted=False)]
        record = [{"cutoff": CUTOFFS[0].isoformat(), "fitted": True, "parameters": list(SHARES)},
                  {"cutoff": CUTOFFS[1].isoformat(), "fitted": False, "parameters": None}]
        a.check_against_record(refits, record)

    def test_shares_that_differ_from_the_record_are_refused(self):
        record = [{"cutoff": CUTOFFS[0].isoformat(), "fitted": True, "parameters": [0.07, 0.14, 0.03]},
                  {"cutoff": CUTOFFS[1].isoformat(), "fitted": True, "parameters": list(SHARES)}]
        with self.assertRaises(ValueError):
            a.check_against_record([_refit(CUTOFFS[0]), _refit(CUTOFFS[1])], record)

    def test_a_fitted_flag_that_differs_is_refused(self):
        record = [{"cutoff": CUTOFFS[0].isoformat(), "fitted": False, "parameters": None},
                  {"cutoff": CUTOFFS[1].isoformat(), "fitted": True, "parameters": list(SHARES)}]
        with self.assertRaises(ValueError):
            a.check_against_record([_refit(CUTOFFS[0]), _refit(CUTOFFS[1])], record)

    def test_cutoffs_that_differ_from_the_record_are_refused(self):
        record = [{"cutoff": "2019-01-30", "fitted": True, "parameters": list(SHARES)},
                  {"cutoff": CUTOFFS[1].isoformat(), "fitted": True, "parameters": list(SHARES)}]
        with self.assertRaises(ValueError):
            a.check_against_record([_refit(CUTOFFS[0]), _refit(CUTOFFS[1])], record)

    def test_a_refits_are_read_from_the_kink_record(self):
        rows = [{"cutoff": "2020-03-13", "fitted": True, "kink": 0.0925, "lower": 0.09, "upper": 0.12},
                {"cutoff": "2020-04-14", "fitted": False, "kink": None, "lower": None, "upper": None}]
        refits = a.a_refits_from_record(rows)
        self.assertEqual(refits[0], a.ARefit(date(2020, 3, 13), True, 0.0925, 0.09, 0.12))
        self.assertFalse(refits[1].fitted)

    def test_a_fitted_kink_record_without_an_interval_is_refused(self):
        with self.assertRaises(ValueError):
            a.a_refits_from_record([{"cutoff": "2020-03-13", "fitted": True, "kink": 0.0925, "lower": None, "upper": None}])

    def test_the_dump_loads_back_unchanged_and_keeps_number_lists_on_one_line(self):
        record = {"b": [0.1, 0.2, None, 3], "a": {"days": ["2020-01-02", "2020-01-03"], "n": 2}, "c": [{"x": [1, 2]}]}
        text = a.dump_record(record)
        self.assertEqual(json.loads(text), record)
        self.assertIn('[0.1, 0.2, null, 3]', text)
        self.assertTrue(text.endswith("\n"))
        self.assertLess(text.index('"a"'), text.index('"b"'))


if __name__ == "__main__":
    unittest.main()
