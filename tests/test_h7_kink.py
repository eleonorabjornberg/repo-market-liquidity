"""H7m, A's re-specified kink: the six declared variants (`docs/stages/h7-kink.md`, with its section 7; directive #151).

What is covered:

* `SolverTests` -- the exact absolute-deviation line, with one intercept or one per group, against brute force (every
  two-point vertex for one intercept; every within-group break point for several); a planted line recovered exactly.
* `FitTests` -- section 2: the variants differ by exactly the axes of the table; a planted kink at 0.12 is recovered exactly
  by all six; a regime with fewer than 50 pairs leaves the refit **not fitted**, never merged into a neighbour.
* `TieRuleTests` -- section 2, "the tie rule": the finding-#54 construction (linear data with no kink, ratios 0.10 to 0.15)
  is **not identified** under every variant, and is never replaced by a picked point or by the fixed 0.12.
* `FlagTests` -- the exclusion set is the parent's two flags plus the turn-day clause (section 7(ii)), each read through the
  parent's rule or label at the scored day alone; the clause cannot be read at the pin.
* `RegimeTests` -- the width regime table (section 2(c) and 7(i)), read at **announcement**, and the stop when it differs
  from the list expected. The leakage tests carry a recorded mutation each.
* `PairTests`, `PathTests`, `ReportTests` -- the training start, the cutoff, the same served days, clean days per regime,
  the Politis-White block length, and the leakage check on a refit.

**Recorded mutations** (CLAUDE.md), 20 October 2026, in a disposable copy of the tree, CPython 3.11, the parent at the pin
(8fd2cf8), `PYTHONDONTWRITEBYTECODE=1`, applied by a one-line replacement and confirmed by `grep`, the suite run against the
copy, the copy discarded:

1. `_publication_at`: replace `if p.announced_at <= instant and p.effective <= day` by `if p.effective <= day` (a width read
   at its effective date instead of its announcement). The guard `check_public` then raises
   `repo_model.splits.LookAheadError: the rate effective 2020-03-16 was read for 2020-03-16, but it was announced at 2020-03-15
   17:00:00, after the decision instant 2020-03-13 16:00:00` from three tests (`RegimeTests`:
   `test_a_cut_announced_after_the_decision_is_not_the_regime_of_the_next_day`, `test_a_day_with_no_on_rrp_rate_has_no_regime`
   and `test_the_expected_list_is_checked_and_a_difference_stops_the_run`), which are the only failures.
2. `check_public`: replace `if publication.announced_at > instant:` by `if False:`. A publication announced after the decision
   instant is no longer refused; `RegimeTests.test_the_guard_refuses_a_publication_made_after_the_decision_instant` fails with
   `AssertionError: LookAheadError not raised`.
3. `read_turn_labels`: replace `label_fn(x.day)` by `label_fn(next_business_day(x.day, 1))` (the label of the next business day
   read for a scored day). `FlagTests.test_the_turn_label_is_read_for_the_scored_day_alone` fails with
   `AssertionError: Lists differ` (the labels read are not the scored days).
4. `training_days`: replace `x.day <= cutoff and x.day > TRAIN_AFTER` by `x.day <= next_business_day(cutoff, 60) and x.day >
   TRAIN_AFTER`. `refit`'s own guard raises `repo_model.splits.LookAheadError: the kink for the refit at 2020-04-14 would be fitted
   on 2020-04-15, after its cutoff` from four `PathTests` tests, and
   `PairTests.test_a_refit_never_fits_on_a_day_after_its_cutoff` fails with `AssertionError: False is not true`.
5. `training_days`: replace `x.day > TRAIN_AFTER and x.ratio` by `True and x.ratio`. The 25 bp regime and every earlier day enter;
   `PairTests.test_no_pair_is_scored_on_or_before_the_training_start` fails with `AssertionError`.
6. `check_no_future`: replace `if _signature(mine) != _signature(then):` by `if False:`. A day built from a later row is no
   longer refused; `LeakageTests.test_a_sample_that_read_a_later_row_is_refused` fails with
   `AssertionError: LookAheadError not raised`.

Order of work, said plainly: the tests were written first and the module did not exist; the first run was
`ImportError: cannot import name 'h7_kink' from 'repo_liquidity'`. Each mutation above was applied to the finished module.
"""

from __future__ import annotations

import itertools
import unittest
from datetime import date, datetime, time, timedelta

import numpy as np
from repo_model import asof, data
from repo_model.announced_iorb import IorbAnnouncement
from repo_model.data import DailyObservation, next_business_day
from repo_model.splits import LookAheadError

from repo_liquidity import h7_estimator as h7
from repo_liquidity import h7_kink as k
from repo_liquidity import scheduled

DECISION = time(16, 0)


# -- constructed data -------------------------------------------------------------------------------------------------------


def _business_days(first, count):
    out = [first]
    while len(out) < count:
        out.append(next_business_day(out[-1], 1))
    return out


def _pairs(count=420, *, kink=0.12, slope=60.0, intercepts=(1.0,), regime_lengths=None, seed=3, noise=0.3, clean=True):
    """Constructed days: ratios cycling 0.08 to 0.20, a planted hinge, one intercept per regime run."""
    rng = np.random.default_rng(seed)
    days = _business_days(date(2019, 1, 2), count)
    lengths = regime_lengths or (count,)
    out, regime, left = [], 0, lengths[0]
    for index, day in enumerate(days):
        while index >= left and regime + 1 < len(lengths):
            regime += 1
            left += lengths[regime]
        ratio = 0.08 + 0.12 * ((index * 37) % 101) / 100.0
        y = intercepts[regime % len(intercepts)] + slope * max(0.0, kink - ratio) + float(rng.normal(0.0, noise))
        out.append(k.KDay(day, ratio, y, y, regime, clean))
    return out


def _variants():
    return [k.BASELINE] + list(k.VARIANTS)


# -- the solver -------------------------------------------------------------------------------------------------------------


def _brute_one(z, y):
    best = float(np.abs(y - np.median(y)).sum())
    for i, j in itertools.combinations(range(len(y)), 2):
        if z[i] == z[j]:
            continue
        slope = (y[i] - y[j]) / (z[i] - z[j])
        if slope >= 0:
            best = min(best, float(np.abs(y - (y[i] - slope * z[i]) - slope * z).sum()))
    return best


def _brute_groups(z, y, groups):
    """The least objective over b = 0 and every within-group break point b = (y_i - y_j) / (z_i - z_j) >= 0."""
    candidates = {0.0}
    for g in np.unique(groups):
        idx = np.flatnonzero(groups == g)
        for i, j in itertools.combinations(idx, 2):
            if z[i] != z[j]:
                slope = (y[i] - y[j]) / (z[i] - z[j])
                if slope >= 0:
                    candidates.add(float(slope))
    best = np.inf
    for b in candidates:
        total = 0.0
        for g in np.unique(groups):
            r = y[groups == g] - b * z[groups == g]
            total += float(np.abs(r - np.median(r)).sum())
        best = min(best, total)
    return best


class SolverTests(unittest.TestCase):
    def test_one_intercept_equals_brute_force_over_every_vertex(self):
        rng = np.random.default_rng(20261020)
        for case in range(80):
            n = int(rng.integers(4, 12))
            z = np.maximum(rng.uniform(-0.5, 1.0, n), 0.0)
            y = rng.normal(0.0, 3.0, n) + z * rng.uniform(-3.0, 8.0)
            if case % 3 == 0:
                y = np.round(y)  # whole basis points: many exact ties
            a, b, f = k.lad_lines(z[None, :], y, np.zeros(n, dtype=int))
            want = _brute_one(z, y)
            self.assertAlmostEqual(float(f[0]), want, delta=1e-9 * max(1.0, want), msg=f"case {case}")
            self.assertGreaterEqual(float(b[0]), 0.0)

    def test_several_intercepts_equal_brute_force_over_every_break_point(self):
        rng = np.random.default_rng(11)
        for case in range(60):
            n = int(rng.integers(6, 13))
            groups = np.sort(rng.integers(0, 3, n))
            z = np.maximum(rng.uniform(-0.5, 1.0, n), 0.0)
            y = rng.normal(0.0, 2.0, n) + 2.0 * groups + z * rng.uniform(-2.0, 6.0)
            a, b, f = k.lad_lines(z[None, :], y, groups)
            want = _brute_groups(z, y, groups)
            self.assertAlmostEqual(float(f[0]), want, delta=1e-9 * max(1.0, want), msg=f"case {case}")

    def test_a_planted_line_with_two_intercepts_is_recovered_exactly(self):
        z = np.maximum(0.05 - np.linspace(0.0, 0.1, 40), 0.0)
        groups = np.repeat([0, 1], 20)
        y = np.where(groups == 0, 0.2, 3.0) + 8.0 * z
        a, b, f = k.lad_lines(z[None, :], y, groups)
        self.assertAlmostEqual(float(f[0]), 0.0, places=8)
        self.assertAlmostEqual(float(b[0]), 8.0, places=6)
        self.assertAlmostEqual(float(a[0, 0]), 0.2, places=6)
        self.assertAlmostEqual(float(a[0, 1]), 3.0, places=6)

    def test_a_falling_trend_gives_the_boundary(self):
        z = np.linspace(0.0, 1.0, 21)
        a, b, f = k.lad_lines(z[None, :], 5.0 - 3.0 * z, np.zeros(21, dtype=int))
        self.assertEqual(float(b[0]), 0.0)

    def test_squares_with_group_intercepts_is_the_group_demeaned_slope(self):
        z = np.array([0.0, 1.0, 2.0, 3.0, 0.0, 1.0, 2.0, 3.0])
        groups = np.repeat([0, 1], 4)
        y = np.where(groups == 0, 1.0, 9.0) + 2.0 * z
        a, b, f = k.squares_lines(z[None, :], y, groups)
        self.assertAlmostEqual(float(b[0]), 2.0, places=9)
        self.assertAlmostEqual(float(f[0]), 0.0, places=9)
        self.assertAlmostEqual(float(a[0, 1]), 9.0, places=9)


# -- the fit, the variants and the tie rule ---------------------------------------------------------------------------------


class FitTests(unittest.TestCase):
    def test_the_variants_are_the_six_of_the_table_in_order(self):
        self.assertEqual([v.id for v in k.VARIANTS], ["V1", "V2", "V3", "V4", "V5", "V6"])
        self.assertEqual(
            [(v.clean, v.left, v.objective, v.intercepts) for v in k.VARIANTS],
            [(True, "spread", "squares", "one"), (False, "spread", "lad", "one"), (False, "spread", "squares", "regime"),
             (True, "spread", "lad", "one"), (True, "spread", "lad", "regime"), (True, "effr", "lad", "regime")],
        )
        self.assertEqual((k.BASELINE.clean, k.BASELINE.left, k.BASELINE.objective, k.BASELINE.intercepts),
                         (False, "spread", "squares", "one"))

    def test_a_planted_kink_at_0_12_is_recovered_exactly_by_every_variant(self):
        shifted = _pairs(420, intercepts=(1.0, 4.0, 2.0), regime_lengths=(140, 140, 140), noise=0.0)
        level = _pairs(420, noise=0.0)
        for variant in _variants():
            days = shifted if variant.intercepts == "regime" else level
            pairs = k.training_days(days, days[-1].day, variant)
            fit = k.fit_kink(pairs, variant)
            self.assertTrue(fit.fitted, (variant.id, fit.reason))
            self.assertEqual(fit.kink, 0.12, variant.id)
            self.assertGreater(fit.slope, 0.0)

    def test_the_baseline_equals_the_parents_fit_on_the_same_pairs(self):
        from repo_model import satiation

        days = _pairs(420)
        pairs = k.training_days(days, days[-1].day, k.BASELINE)
        level, record = satiation.fit_level([p.ratio for p in pairs], [p.spread for p in pairs])
        fit = k.fit_kink(pairs, k.BASELINE)
        self.assertEqual((fit.fitted, fit.kink), (bool(record["fitted"]), level))

    def test_fewer_than_the_minimum_pairs_is_not_fitted(self):
        days = _pairs(200)
        fit = k.fit_kink(k.training_days(days, days[-1].day, k.BASELINE), k.BASELINE)
        self.assertFalse(fit.fitted)
        self.assertEqual(fit.reason, "too few pairs")

    def test_a_regime_with_fewer_than_fifty_pairs_is_not_fitted_and_not_merged(self):
        days = _pairs(420, intercepts=(1.0, 4.0), regime_lengths=(371, 49))
        for variant in (k.VARIANTS[2], k.VARIANTS[4], k.VARIANTS[5]):
            fit = k.fit_kink(k.training_days(days, days[-1].day, variant), variant)
            self.assertFalse(fit.fitted, variant.id)
            self.assertIn("regime", fit.reason)
            self.assertEqual(fit.regime_counts, {0: 371, 1: 49})
        one = k.fit_kink(k.training_days(days, days[-1].day, k.VARIANTS[3]), k.VARIANTS[3])
        self.assertTrue(one.fitted)  # a single intercept has no regime to be short of

    def test_the_effr_variant_fits_on_the_effr_side(self):
        days = _pairs(420)
        days = [d._replace(effr=d.spread + 5.0) for d in days]
        pairs = k.training_days(days, days[-1].day, k.VARIANTS[5])
        self.assertTrue(all(abs(p.effr - p.spread - 5.0) < 1e-12 for p in pairs))
        self.assertEqual(k.left_side(pairs[0], k.VARIANTS[5]), pairs[0].effr)
        self.assertEqual(k.left_side(pairs[0], k.VARIANTS[4]), pairs[0].spread)


class TieRuleTests(unittest.TestCase):
    def _linear(self):
        """Finding #54: linear data with no kink, ratios 0.10 to 0.15. Every grid point at or above 0.15 fits alike."""
        days = _business_days(date(2019, 1, 2), 420)
        out = []
        for i, day in enumerate(days):
            ratio = 0.10 + 0.05 * ((i * 53) % 101) / 100.0
            y = 5.0 - 40.0 * ratio + 0.001 * (i % 2)  # falling in ratio, a hinge with k >= 0.15 fits it exactly
            out.append(k.KDay(day, ratio, y, y, 0, True))
        return out

    def test_the_finding_54_construction_is_not_identified_under_every_variant(self):
        days = self._linear()
        for variant in _variants():
            fit = k.fit_kink(k.training_days(days, days[-1].day, variant), variant)
            self.assertFalse(fit.fitted, variant.id)
            self.assertIn("not identified", fit.reason, variant.id)
            self.assertIsNotNone(fit.tied, variant.id)
            self.assertGreater(fit.tied[1] - fit.tied[0], 0.0025, variant.id)
            self.assertIsNone(fit.kink, "a tied point is never picked, nor replaced by the fixed 0.12")

    def test_a_tie_over_one_grid_step_goes_to_the_lower_objective_then_the_lower_index(self):
        days = _pairs(420, noise=0.0)
        pairs = k.training_days(days, days[-1].day, k.VARIANTS[3])
        fit = k.fit_kink(pairs, k.VARIANTS[3])
        self.assertTrue(fit.fitted)
        self.assertEqual(fit.kink, 0.12)


# -- the exclusion set ------------------------------------------------------------------------------------------------------


def _flag_rows(first=date(2019, 3, 18), last=date(2019, 5, 3), coupons=()):
    out, day = [], first
    while day <= last:
        if day.weekday() < 5 and day not in data.market_holidays().closed:
            values = {n: rule(day) for n, rule in data.CALENDAR_COLUMN_RULES.items() if n != "quarter_end_window"}
            values.update(sofr=2.4, iorb=2.4, treasury_settlement_coupons=5.0 if day in coupons else 0.0)
            out.append(DailyObservation(day, values))
        day += timedelta(days=1)
    return k.with_quarter_end_window(out)


class FlagTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.coupon_day = date(2019, 4, 10)
        cls.rows = _flag_rows(coupons=(cls.coupon_day,))
        cls.flags = k.read_flags(cls.rows, k.flag_rule())

    def test_a_quarter_end_a_tax_date_and_a_coupon_day_are_dropped(self):
        for day in (date(2019, 3, 29), date(2019, 4, 15), self.coupon_day):
            self.assertTrue(self.flags[day].dropped(), day)

    def test_the_quarter_end_window_is_dropped_though_not_a_settlement_day(self):
        self.assertEqual(self.flags[date(2019, 3, 27)].settlement_day, 0.0)
        self.assertTrue(self.flags[date(2019, 3, 27)].dropped())

    def test_an_ordinary_day_is_clean(self):
        flag = self.flags[date(2019, 4, 9)]
        self.assertEqual((flag.settlement_day, flag.quarter_end_window, flag.dropped()), (0.0, 0.0, False))

    def test_the_flags_are_the_parents_own_composition(self):
        for day, flag in self.flags.items():
            if flag.unread:
                continue
            row = next(r for r in self.rows if r.date == day)
            self.assertEqual(flag.settlement_day, asof._settlement_day(row.values), day)

    def test_a_row_the_rule_cannot_score_is_unread_and_dropped(self):
        first = self.flags[self.rows[1].date]
        self.assertTrue(first.unread and first.dropped())

    def test_a_hole_in_a_flag_is_a_data_error(self):
        with self.assertRaises(ValueError):
            k.Flags(date(2019, 4, 9), None, 0.0).dropped()

    def test_a_flag_read_for_another_day_than_the_scored_one_is_refused(self):
        rule = k.flag_rule()
        info = rule.information_set([r.date for r in self.rows], 10)
        k.check_flag_reads(info)
        moved = tuple(r._replace(row=r.row - 1) if r.kind in (asof.KIND_CALENDAR, asof.KIND_SCHEDULED) else r for r in info.reads)
        with self.assertRaises(LookAheadError):
            k.check_flag_reads(info._replace(reads=moved))

    def test_the_turn_clause_drops_a_labelled_day(self):
        labels = {date(2019, 4, 30): "last", date(2019, 5, 1): "first"}
        days = [k.KDay(d, 0.1, 1.0, 1.0, 0, True) for d in (date(2019, 4, 29), date(2019, 4, 30), date(2019, 5, 1), date(2019, 5, 2))]
        got = k.mark_clean(days, self.flags, labels)
        self.assertEqual([x.clean for x in got], [False, False, False, True])  # 04-29 is a month-end settlement day

    def test_the_first_business_day_after_a_month_end_is_clean_without_the_clause_and_dropped_with_it(self):
        day = date(2019, 5, 1)
        self.assertFalse(self.flags[day].dropped())
        [without] = k.mark_clean([k.KDay(day, 0.1, 1.0, 1.0, 0, True)], self.flags, {})
        [with_clause] = k.mark_clean([k.KDay(day, 0.1, 1.0, 1.0, 0, True)], self.flags, {day: "first"})
        self.assertEqual((without.clean, with_clause.clean), (True, False))

    def test_the_turn_label_is_read_for_the_scored_day_alone(self):
        asked = []
        days = [k.KDay(d, 0.1, 1.0, 1.0, 0, True) for d in _business_days(date(2019, 4, 1), 8)]

        def label(day):
            asked.append(day)
            return None

        k.read_turn_labels(days, label)
        self.assertEqual(asked, [x.day for x in days])

    def test_the_flags_of_another_day_are_refused(self):
        days = [k.KDay(d, 0.1, 1.0, 1.0, 0, True) for d in _business_days(date(2019, 4, 1), 6)]
        flags = {d.day: k.Flags(d.day, 0.0, 0.0) for d in days}
        flags[days[3].day] = k.Flags(days[1].day, 1.0, 0.0)
        with self.assertRaises(LookAheadError):
            k.mark_clean(days, flags, {})

    def test_a_day_without_flags_is_a_data_error(self):
        with self.assertRaises(ValueError):
            k.mark_clean([k.KDay(date(2019, 4, 1), 0.1, 1.0, 1.0, 0, True)], {}, {})

    def test_the_turn_label_cannot_be_read_at_the_pin(self):
        try:
            import repo_model.turn_days  # noqa: F401
        except ImportError:
            with self.assertRaises(k.TurnDaysUnavailable) as caught:
                k.parent_turn_label()
            self.assertIn("#149", str(caught.exception))
        else:
            self.assertTrue(callable(k.parent_turn_label()))


# -- the width regimes ------------------------------------------------------------------------------------------------------


def _pub(announce, effective, rate):
    return scheduled.Publication(announce, effective, (rate,), (str(rate),), "x")


def _note(announce, effective, rate_bps, change):
    return IorbAnnouncement(announce, effective, rate_bps, change, "change")


class RegimeTests(unittest.TestCase):
    """IORB 2.00 and ON RRP 1.80 (width 20) until a cut announced on Sunday 2020-03-15 at 17:00, effective Monday 03-16."""

    def setUp(self):
        self.days = _business_days(date(2020, 3, 9), 10)
        self.rows = [DailyObservation(d, {"iorb": 2.00 if d < date(2020, 3, 16) else 1.60}) for d in self.days]
        self.pubs = [_pub(datetime(2020, 1, 1, 14, 0), date(2020, 1, 2), 1.80), _pub(datetime(2020, 3, 15, 17, 0), date(2020, 3, 16), 1.50)]
        self.notes = [_note(datetime(2020, 1, 1, 14, 0), date(2020, 1, 2), 200, 0),
                      _note(datetime(2020, 3, 15, 17, 0), date(2020, 3, 16), 160, -40)]

    def table(self):
        return k.width_regimes(self.rows, self.pubs, self.notes, decision_time=DECISION)

    def test_a_cut_announced_after_the_decision_is_not_the_regime_of_the_next_day(self):
        widths = self.table()
        monday, tuesday = date(2020, 3, 16), date(2020, 3, 17)
        self.assertEqual(widths[date(2020, 3, 13)].width, 20)
        self.assertEqual(widths[monday].width, 20)  # the cut was not public at Friday 16:00
        self.assertEqual(widths[tuesday].width, 10)  # public from Sunday 17:00, so by Monday's decision
        self.assertEqual(widths[self.days[0]].width, None)  # the first row has no decision instant

    def test_the_guard_refuses_a_publication_made_after_the_decision_instant(self):
        with self.assertRaises(LookAheadError):
            k.check_public(self.pubs[1], datetime(2020, 3, 13, 16, 0), date(2020, 3, 16))
        k.check_public(self.pubs[0], datetime(2020, 3, 13, 16, 0), date(2020, 3, 16))

    def test_the_regimes_are_the_runs_of_a_width_and_a_repeated_width_is_a_new_regime(self):
        pubs = [_pub(datetime(2020, 1, 1, 14, 0), date(2020, 1, 2), 1.80), _pub(datetime(2020, 3, 11, 14, 0), date(2020, 3, 12), 1.90),
                _pub(datetime(2020, 3, 18, 14, 0), date(2020, 3, 19), 1.80)]
        notes = [_note(datetime(2020, 1, 1, 14, 0), date(2020, 1, 2), 200, 0)]
        widths = k.width_regimes(self.rows[:1] + [DailyObservation(r.date, {"iorb": 2.00}) for r in self.rows[1:]], pubs, notes, decision_time=DECISION)
        runs = k.regime_table(widths)
        self.assertEqual([r.width for r in runs], [20, 10, 20])
        self.assertEqual([r.regime for r in runs], [0, 1, 2])

    def test_a_day_with_no_on_rrp_rate_has_no_regime(self):
        widths = k.width_regimes(self.rows, [self.pubs[1]], self.notes, decision_time=DECISION)
        self.assertIsNone(widths[date(2020, 3, 10)].regime)

    def test_the_expected_list_is_checked_and_a_difference_stops_the_run(self):
        table = k.regime_table(self.table())
        k.check_expected(table, (20, 10))
        with self.assertRaises(ValueError) as caught:
            k.check_expected(table, (20, 15, 10, 15))
        self.assertIn("finding", str(caught.exception))
        with self.assertRaises(ValueError):
            k.check_expected(table, (20, 15))

    def test_the_declared_list_after_the_training_start_is_20_15_10_15(self):
        self.assertEqual(k.EXPECTED_WIDTHS, (20, 15, 10, 15))


# -- the pairs and the walk-forward -----------------------------------------------------------------------------------------


class PairTests(unittest.TestCase):
    def test_no_pair_is_scored_on_or_before_the_training_start(self):
        days = [k.KDay(d, 0.1, 1.0, 1.0, 0, True) for d in (date(2018, 6, 12), date(2018, 6, 13), date(2018, 6, 14), date(2018, 6, 15))]
        pairs = k.training_days(days, date(2018, 12, 31), k.BASELINE)
        self.assertEqual([p.day for p in pairs], [date(2018, 6, 14), date(2018, 6, 15)])

    def test_a_dropped_day_is_not_a_pair_for_a_clean_variant_only(self):
        days = _pairs(60)
        days[5] = days[5]._replace(clean=False)
        cutoff = days[-1].day
        self.assertEqual(len(k.training_days(days, cutoff, k.VARIANTS[0])), 59)
        self.assertEqual(len(k.training_days(days, cutoff, k.VARIANTS[1])), 60)

    def test_a_day_without_a_regime_leaves_the_regime_variants_only(self):
        days = _pairs(60)
        days[5] = days[5]._replace(regime=None)
        cutoff = days[-1].day
        self.assertEqual(len(k.training_days(days, cutoff, k.VARIANTS[4])), 59)
        self.assertEqual(len(k.training_days(days, cutoff, k.VARIANTS[3])), 60)
        self.assertEqual(k.unregimed_days(days, cutoff), [days[5].day])

    def test_a_refit_never_fits_on_a_day_after_its_cutoff(self):
        days = _pairs(420)
        cutoff = days[300].day
        pairs = k.training_days(days, cutoff, k.BASELINE)
        self.assertTrue(all(p.day <= cutoff for p in pairs))
        with self.assertRaises(LookAheadError):
            k.refit(days, cutoff, k.BASELINE, replications=0)

    def test_the_regime_counts_per_refit_are_the_clean_training_days(self):
        days = _pairs(420, intercepts=(1.0, 3.0), regime_lengths=(300, 120))
        days[10] = days[10]._replace(clean=False)
        counts = k.regime_counts(k.training_days(days, days[-1].day, k.VARIANTS[4]))
        self.assertEqual(counts, {0: 299, 1: 120})


class PathTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.days = _pairs(520, intercepts=(1.0, 3.0), regime_lengths=(260, 260))
        cls.cutoffs = [cls.days[i].day for i in (320, 360, 400, 440)]

    def test_the_refit_serves_from_the_second_business_day_and_has_gaps_to_the_one_before(self):
        paths = k.real_time_path(self.days, self.cutoffs, k.VARIANTS[3], replications=0)
        self.assertEqual(len(paths), 4)
        first_served = min(e.day for e in paths[1].estimates)
        self.assertEqual(first_served, next_business_day(self.cutoffs[1], h7.SERVING_LAG))
        self.assertTrue(all(g >= 0 for g in paths[1].gaps.values()))
        self.assertEqual(paths[0].gaps, {})

    def test_the_interval_brackets_the_kink_when_replications_are_asked_for(self):
        fit = k.refit_on(self.days, self.cutoffs[0], k.VARIANTS[3], replications=20)
        self.assertTrue(fit.fitted)
        self.assertLessEqual(fit.lower, fit.level)
        self.assertGreaterEqual(fit.upper, fit.level)

    def test_workers_do_not_change_the_path(self):
        one = k.real_time_path(self.days, self.cutoffs, k.VARIANTS[4], replications=6)
        two = k.real_time_path(self.days, self.cutoffs, k.VARIANTS[4], replications=6, workers=2)
        self.assertEqual([(p.refit.level, p.refit.lower, p.refit.upper, p.gaps) for p in one],
                         [(p.refit.level, p.refit.lower, p.refit.upper, p.gaps) for p in two])

    def test_cutoffs_must_increase(self):
        with self.assertRaises(ValueError):
            k.real_time_path(self.days, [self.cutoffs[1], self.cutoffs[0]], k.BASELINE, replications=0)

    def test_the_variants_are_compared_on_the_same_served_days(self):
        paths = {v.id: k.real_time_path(self.days, self.cutoffs, v, replications=0) for v in (k.BASELINE, k.VARIANTS[2])}
        same = k.common_served_days(paths)
        for path in paths.values():
            served = {e.day for p in path for e in p.estimates}
            self.assertTrue(same <= served)
        summary = k.summarise(paths["B"], same)
        self.assertEqual(summary["served_days"], len(same))

    def test_a_refit_that_does_not_fit_serves_nothing_and_is_counted(self):
        thin = _pairs(520, intercepts=(1.0, 3.0), regime_lengths=(490, 30))
        paths = k.real_time_path(thin, [thin[i].day for i in (480, 500)], k.VARIANTS[4], replications=0)
        self.assertFalse(paths[1].refit.fitted)
        self.assertEqual(paths[1].estimates, [])
        self.assertEqual(k.summarise(paths, None)["not_fitted"], 1)


class ReportTests(unittest.TestCase):
    def test_the_politis_white_block_length_of_white_noise_is_short_and_of_a_slow_series_long(self):
        rng = np.random.default_rng(5)
        white = rng.normal(size=600)
        slow = np.cumsum(rng.normal(size=600) * 0.1) + rng.normal(size=600) * 0.05
        slow = slow - np.convolve(slow, np.ones(60) / 60, mode="same") * 0  # a random walk: strongly dependent
        self.assertLess(k.politis_white_block(white), 6.0)
        self.assertGreater(k.politis_white_block(slow), 30.0)

    def test_a_constant_series_has_no_block_length(self):
        self.assertIsNone(k.politis_white_block([1.0] * 100))
        self.assertIsNone(k.politis_white_block([1.0, 2.0]))

    def test_the_residuals_of_a_fit_are_the_left_side_less_its_curve(self):
        days = _pairs(420, noise=0.0)
        variant = k.VARIANTS[3]
        pairs = k.training_days(days, days[-1].day, variant)
        fit = k.fit_kink(pairs, variant)
        residuals = k.residuals(pairs, variant, fit)
        self.assertLess(max(abs(r) for r in residuals), 1e-6)


class BuildDaysTests(unittest.TestCase):
    """`build_days` on a constructed panel, through the parent's rules: ratios, flags, regimes and the left sides together."""

    @classmethod
    def setUpClass(cls):
        from repo_model import measurement_fields, scarcity

        import test_h7_estimator as t7

        cls.context = scarcity.measurement_declaration()
        cls.context.__enter__()
        rows = []
        for row in t7._panel(start=date(2023, 1, 3), count=90):
            values = {n: rule(row.date) for n, rule in data.CALENDAR_COLUMN_RULES.items() if n != "quarter_end_window"}
            values.update(row.values, treasury_settlement_coupons=0.0, effr=3.9, iorb=4.0, sofr=4.02)
            rows.append(DailyObservation(row.date, values))
        cls.rows = rows
        cls.rule = asof.InformationRule(measurement_fields.load_registry(), scarcity.LEGS, decision_time=DECISION, horizon=1)
        pubs = [_pub(datetime(2022, 12, 1, 14, 0), date(2022, 12, 2), 3.90)]
        notes = [_note(datetime(2022, 12, 1, 14, 0), date(2022, 12, 2), 400, 0)]
        cls.days = k.build_days(rows, cls.rule, publications=pubs, notes=notes, label_fn=lambda day: "turn" if day == date(2023, 2, 1) else None)

    @classmethod
    def tearDownClass(cls):
        cls.context.__exit__(None, None, None)

    def test_every_scored_day_but_the_first_row_is_built_with_its_own_values(self):
        self.assertEqual([x.day for x in self.days], [r.date for r in self.rows[1:]])
        first = self.days[0]
        self.assertAlmostEqual(first.spread, 2.0, places=9)
        self.assertEqual((first.effr, first.regime), (-10.0, 0))

    def test_the_regime_is_the_one_width_of_the_panel(self):
        self.assertEqual({x.regime for x in self.days}, {0})
        self.assertEqual(k.regime_table(k.width_regimes(self.rows, [_pub(datetime(2022, 12, 1, 14, 0), date(2022, 12, 2), 3.90)],
                                                          [_note(datetime(2022, 12, 1, 14, 0), date(2022, 12, 2), 400, 0)],
                                                          decision_time=DECISION))[0].width, 10)

    def test_a_turn_day_and_a_month_end_are_not_clean_and_an_ordinary_day_is(self):
        by = {x.day: x for x in self.days}
        self.assertFalse(by[date(2023, 2, 1)].clean)  # the turn label
        self.assertFalse(by[date(2023, 1, 31)].clean)  # the parent's month-end clause
        self.assertTrue(by[date(2023, 1, 18)].clean)

    def test_rows_without_effr_are_refused(self):
        bare = [DailyObservation(r.date, {n: v for n, v in r.values.items() if n != "effr"}) for r in self.rows]
        with self.assertRaises(ValueError):
            k.build_days(bare, self.rule, publications=[], notes=[], label_fn=lambda day: None)


class ScriptTests(unittest.TestCase):
    def test_the_run_exits_2_and_reads_nothing_while_the_parent_has_no_turn_label(self):
        import subprocess
        import sys
        from pathlib import Path

        try:
            import repo_model.turn_days  # noqa: F401
        except ImportError:
            pass
        else:
            self.skipTest("the parent has turn_days: the run is possible")
        script = Path(__file__).resolve().parents[1] / "scripts" / "h7_kink_run.py"
        done = subprocess.run([sys.executable, "-B", str(script)], capture_output=True, text=True,
                              env={**__import__("os").environ, "PYTHONDONTWRITEBYTECODE": "1"})
        self.assertEqual(done.returncode, 2)
        self.assertIn("#149", done.stderr)


class LeakageTests(unittest.TestCase):
    def _signature_days(self):
        return _pairs(420)

    def test_a_sample_built_from_the_cut_panel_equals_the_full_ones_up_to_the_cutoff(self):
        full = self._signature_days()
        cutoff = full[300].day
        k.check_no_future(full, cutoff, lambda until: [d for d in full if d.day <= until])

    def test_a_sample_that_read_a_later_row_is_refused(self):
        full = self._signature_days()
        cutoff = full[300].day

        def build(until):
            out = [d for d in full if d.day <= until]
            out[-1] = out[-1]._replace(regime=out[-1].regime + 1)  # a day built from a later row differs
            return out

        with self.assertRaises(LookAheadError):
            k.check_no_future(full, cutoff, build)


class BuildRowsTests(unittest.TestCase):
    def test_the_rows_rebuild_at_the_pin_and_match_the_current_panel_manifest(self):
        """`build_rows` rebuilds the panel columns at the parent pin and checks them against the current manifest (#151).

        Before the fix it checked version 1, which no longer rebuilds at 08ff67e (the panel is version 4), so the run's first
        step raised `ValueError`: the version-1 columns ... not the manifest's ... (reproduced at dc46dfb).
        """
        import importlib.util
        from pathlib import Path

        from repo_liquidity import h10_apply, panel

        script = Path(__file__).resolve().parents[1] / "scripts" / "h7_kink_run.py"
        spec = importlib.util.spec_from_file_location("h7_kink_run", script)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        rows, pins = module.build_rows()
        self.assertEqual(pins["panel_version"], h10_apply.PANEL_VERSION)
        self.assertEqual(pins["panel_sha256"], panel.load_manifest(h10_apply.PANEL_VERSION)["sha256"])
        self.assertTrue(rows)


if __name__ == "__main__":
    unittest.main()
