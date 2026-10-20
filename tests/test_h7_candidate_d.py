"""H7m, development step 3: candidate D, the SLR-bound group's buffer set by leverage headroom (`docs/stages/h7-step3.md`,
directive #138).

Aggregate deployable liquidity on day T is candidate C's, except that the large domestic group's buffer share is
`clip(level + slope * h, 0, 0.30)` with `h` the nine G-SIB depository subsidiaries' leverage headroom in dollars over the group's
assets. Nothing is scored here. What is covered:

* `HeadroomTests` -- the dollars of headroom per bank and for the nine, the transform, a quarter with no requirement.
* `DeployableTests` -- the buffer share, its clip, the slope-zero reduction to candidate C, the group-by-group terms.
* `NotCPlusAConstantTests` (must-show 3) -- with group reserves and assets flat, a change in headroom alone moves D.
* `DistributionTests` (must-show 5) -- the three declared alternatives of protocol section 8, group by group.
* `ReadHeadroomTests` -- a day reads the latest complete quarter of the nine banks public at its decision instant.
* `FitTests`, `IntervalTests`, `PathTests` (must-show 4) -- the four parameters are recovered; no counted episode is not fitted;
  a day without headroom is not a training day; the bootstrap interval; each refit's real-time path and its gaps.
* `LeakageTests` (must-show 2) -- a headroom read public after the decision instant is `LookAheadError`; a read that is not
  the latest complete quarter is `StaleReadError`; a refit that read a later row is refused.
* `OutOfSampleTests` (must-show 4) -- Stage 6's own test machinery, on constructed data only.
* `TrackedSeriesTests` -- the published `slr_headroom` snapshot loads through its own checks and D reads it.

**Recorded mutations** (CLAUDE.md), 20 October 2026, in a disposable copy of the tree, CPython 3.11, the parent at the pin
(8fd2cf8), `PYTHONDONTWRITEBYTECODE=1`, applied by a one-line replacement and confirmed by `grep`, the suite run against the
copy, the copy discarded:

1. `read_headroom`: replace `banks[b].available_from <= instant` by `banks[b].quarter_end <= instant.date()` (a quarter is read
   from its quarter-end, not from the day after its latest update). Ten tests that build days (`LeakageTests`, `SampleTests`,
   `ReadHeadroomTests`) raise `repo_model.splits.LookAheadError: 2019-01-03 read the quarter ended 2018-12-31, public at
   2019-01-31 00:00:00-05:00, after its decision instant 2019-01-02 16:00:00-05:00` from `check_reads`; four more fail with
   `AssertionError` (14 in all).
2. `check_reads`: replace `x.headroom is None or x.headroom.quarter_end < latest.quarter_end` by `False`. A quarter older than the
   latest complete one is no longer refused; `LeakageTests.test_a_headroom_read_that_is_not_the_latest_complete_quarter_is_stale`
   fails with `AssertionError: StaleReadError not raised` (the only failure).
3. `check_reads`: replace `if x.headroom is not None and x.headroom.public_at > x.instant:` by `if False:`. A quarter public after
   the decision instant is no longer refused; `LeakageTests.test_a_headroom_read_public_after_the_decision_instant_is_refused` fails
   with `AssertionError: LookAheadError not raised` (the only failure).
4. `training_days`: replace `x.day <= cutoff` by `x.day <= next_business_day(cutoff, 60)`. A refit then fits on days up to sixty
   business days after its cutoff; `FitTests.test_only_days_up_to_the_cutoff_count_toward_an_episode` and
   `test_days_without_headroom_do_not_count_toward_the_sixty_scarce_days` fail with `AssertionError`, and four tests that fit a refit
   (`PathTests`' class setup among them) raise `repo_model.splits.LookAheadError: the parameters for the refit at 2019-01-22 would be
   fitted on 2019-01-23, after its cutoff` from `fit_refit`.
5. `check_no_future`: replace `if again.fitted != p.refit.fitted or again.params != p.refit.params:` by `if False:`. A refit that
   differs from the cut panel's is no longer refused; `LeakageTests.test_a_refit_that_read_later_days_is_refused` fails with
   `AssertionError: LookAheadError not raised` (the only failure).

Written first, and watched failing: before `repo_liquidity.h7_candidate_d` existed the module did not import:
`ImportError: cannot import name 'h7_candidate_d' from 'repo_liquidity'`.
"""

from __future__ import annotations

import unittest
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from repo_model import measurement_fields, scarcity
from repo_model.asof import InformationRule, StaleReadError
from repo_model.data import DailyObservation, next_business_day
from repo_model.splits import LookAheadError

from repo_liquidity import h7_candidate_c as c
from repo_liquidity import h7_candidate_d as d
from repo_liquidity import h7_estimator as h7
from repo_liquidity import slr

NEW_YORK = ZoneInfo("America/New_York")
REPLICATIONS = 6
ASSETS = (9500.0, 5000.0, 2300.0)
#: The planted parameters: the large group's level and slope, and the small and foreign-related shares (all on the grids).
PLANTED = d.Params(0.10, -0.5, 0.14, 0.03)
PLANTED_KINK = 0.03
EPISODE = ("test episode", date(2019, 1, 1), date(2019, 12, 31))
EPISODES = (EPISODE,)
MIN_SCARCE = 30
#: Total headroom of the nine banks, USD billions, for the quarters ended 2018-06-30 .. 2019-09-30.
QUARTER_HEADROOM = {date(2018, 6, 30): 500.0, date(2018, 9, 30): 800.0, date(2018, 12, 31): 350.0,
                    date(2019, 3, 31): 900.0, date(2019, 6, 30): 600.0, date(2019, 9, 30): 700.0}
EXPOSURE_KUSD = 1_000_000_000  # one trillion dollars per bank


def _days(start, count):
    out = [start]
    while len(out) < count:
        out.append(next_business_day(out[-1], 1))
    return out


def _release(wednesday):
    return datetime.combine(wednesday + timedelta(days=9), time(16, 15), tzinfo=NEW_YORK)


def _week(wednesday, reserves, assets=ASSETS, brk=False):
    return c.GroupWeek(wednesday, _release(wednesday), tuple(reserves), tuple(assets), brk)


def _cycle(index, modulus, step):
    return ((index * step) % modulus) / (modulus - 1)


def _planted_reserves(index):
    """The large group sits between 6 points below and 5 above its planted buffer range; the others as in C's tests."""
    large = ASSETS[0] * (0.04 + 0.11 * _cycle(index, 13, 5))
    small = ASSETS[1] * (0.14 - 0.03 + 0.11 * _cycle(index, 11, 3))
    foreign = ASSETS[2] * (0.03 - 0.03 + 0.11 * _cycle(index, 7, 2))
    return large, small, foreign


def _weeks(first=date(2018, 12, 26), count=70, breaks=()):
    out = []
    for index in range(count):
        wednesday = first + timedelta(weeks=index)
        out.append(_week(wednesday, _planted_reserves(index), brk=wednesday in breaks))
    return out


def _noise(index):
    return 0.02 * (((index * 7919) % 13) - 6) / 6.0


def _quarter_rows(quarter_end, total_headroom_bn, *, lag_days=30, banks=None, requirement=6.0):
    """The nine banks' rows for a quarter, each with an equal share of the total headroom, last updated `lag_days` after it."""
    banks = list(slr.BANKS) if banks is None else banks
    per_bank_bn = total_headroom_bn / 9.0
    tier1 = int(round(requirement / 100.0 * (EXPOSURE_KUSD + per_bank_bn * 1_000_000)))
    update = datetime.combine(quarter_end + timedelta(days=lag_days), time(12, 0))
    return [slr.Row(quarter_end, idrssd, slr.BANKS[idrssd], update, "RCFA", tier1, EXPOSURE_KUSD, None, "0" * 64)
            for idrssd in banks]


def _slr_rows(quarters=QUARTER_HEADROOM):
    out = []
    for quarter_end, headroom in quarters.items():
        out.extend(_quarter_rows(quarter_end, headroom))
    return out


SLR_ROWS = _slr_rows()


def _instant(day):
    return datetime.combine(day - timedelta(days=1), time(16, 0), tzinfo=NEW_YORK)


def _planted_days(weeks, start=date(2019, 1, 7), count=230, kink=PLANTED_KINK, params=PLANTED, slr_rows=SLR_ROWS):
    """Days that read the latest public week and the latest complete quarter, with the corridor position planted on D_D."""
    out = []
    for index, day in enumerate(_days(start, count)):
        instant = _instant(day)
        week = c.read_week(weeks, instant)
        head = d.read_headroom(slr_rows, instant)
        if week is None or head is None:
            continue
        value = d.deployable(week, head.headroom_bn, params)
        ratio = 0.10 + 0.0001 * (index % 7)
        corridor = 0.10 + 8.0 * max(0.0, kink - value) + _noise(index)
        out.append(d.DayD(day, instant, ratio, corridor, 1.0, week, head))
    return out


class HeadroomTests(unittest.TestCase):
    def test_a_banks_headroom_is_tier_1_over_the_requirement_less_the_exposure(self):
        row = _quarter_rows(date(2018, 12, 31), 900.0)[0]
        want_bn = (row.tier1_capital_kusd / 0.06 - row.total_leverage_exposure_kusd) / 1_000_000.0
        self.assertAlmostEqual(d.bank_headroom_bn(row), want_bn, places=6)
        self.assertAlmostEqual(d.bank_headroom_bn(row), 100.0, places=3)

    def test_the_nine_banks_headroom_is_summed(self):
        head = d.read_headroom(_quarter_rows(date(2018, 12, 31), 900.0), _instant(date(2019, 3, 1)))
        self.assertAlmostEqual(head.headroom_bn, 900.0, places=3)
        self.assertEqual(head.quarter_end, date(2018, 12, 31))

    def test_the_transform_is_headroom_over_the_large_groups_assets(self):
        week = _week(date(2019, 1, 2), (900.0, 300.0, 100.0))
        self.assertAlmostEqual(d.transform(week, 950.0), 950.0 / ASSETS[0])

    def test_a_quarter_with_no_requirement_has_no_headroom(self):
        rows = _quarter_rows(date(2026, 6, 30), 900.0, requirement=6.0)
        head = d.read_headroom(rows, _instant(date(2026, 8, 20)))
        self.assertEqual(head.quarter_end, date(2026, 6, 30))
        self.assertIsNone(head.headroom_bn)

    def test_an_unknown_exclusion_quarter_is_flagged_not_refused(self):
        head = d.read_headroom(_quarter_rows(date(2020, 9, 30), 800.0), _instant(date(2020, 11, 20)))
        self.assertTrue(head.exclusion_unknown)
        self.assertIsNotNone(head.headroom_bn)
        other = d.read_headroom(_quarter_rows(date(2019, 3, 31), 800.0), _instant(date(2019, 5, 20)))
        self.assertFalse(other.exclusion_unknown)


class DeployableTests(unittest.TestCase):
    WEEK = _week(date(2023, 1, 4), (1000.0, 300.0, 400.0))

    def test_the_large_groups_buffer_is_a_level_plus_a_slope_times_the_transform(self):
        params = d.Params(0.10, -0.5, 0.04, 0.10)
        h = d.transform(self.WEEK, 950.0)
        shares = d.shares_at(params, self.WEEK, 950.0)
        self.assertAlmostEqual(shares[0], 0.10 - 0.5 * h)
        self.assertEqual(shares[1:], (0.04, 0.10))

    def test_the_buffer_is_kept_inside_zero_and_the_top_of_the_share_grid(self):
        low = d.shares_at(d.Params(0.05, -1.0, 0.0, 0.0), self.WEEK, 9500.0)
        high = d.shares_at(d.Params(0.30, 1.0, 0.0, 0.0), self.WEEK, 9500.0)
        self.assertEqual(low[0], 0.0)
        self.assertEqual(high[0], 0.30)

    def test_the_sum_of_each_groups_reserves_above_its_buffer_over_the_groups_assets(self):
        params = d.Params(0.10, -0.5, 0.04, 0.10)
        shares = d.shares_at(params, self.WEEK, 950.0)
        want = sum(max(r - s * a, 0.0) for r, s, a in zip(self.WEEK.reserves_bn, shares, ASSETS)) / sum(ASSETS)
        self.assertAlmostEqual(d.deployable(self.WEEK, 950.0, params), want)

    def test_with_the_slope_at_zero_d_is_c_with_the_level_as_the_large_share(self):
        params = d.Params(0.07, 0.0, 0.04, 0.10)
        for headroom in (100.0, 950.0, 2000.0):
            self.assertAlmostEqual(d.deployable(self.WEEK, headroom, params),
                                   c.deployable(self.WEEK, (0.07, 0.04, 0.10)))

    def test_a_group_below_its_buffer_contributes_zero(self):
        week = _week(date(2023, 1, 4), (1000.0, 100.0, 400.0))
        terms = d.group_contributions(week, 950.0, d.Params(0.05, 0.0, 0.04, 0.10))
        self.assertEqual(terms[1], 0.0)
        self.assertAlmostEqual(sum(terms), d.deployable(week, 950.0, d.Params(0.05, 0.0, 0.04, 0.10)))

    def test_no_headroom_is_refused_not_replaced(self):
        with self.assertRaises(ValueError):
            d.deployable(self.WEEK, None, PLANTED)

    def test_parameters_off_their_grids_or_out_of_range_are_refused(self):
        for bad in (d.Params(0.31, 0.0, 0.0, 0.0), d.Params(0.1, 1.5, 0.0, 0.0), d.Params(0.1, 0.0, -0.01, 0.0)):
            with self.assertRaises(ValueError):
                d.deployable(self.WEEK, 950.0, bad)

    def test_points_are_a_hundred_times_the_share(self):
        self.assertEqual(d.points(0.0125), 1.25)


class NotCPlusAConstantTests(unittest.TestCase):
    """Must-show 3: group reserves and assets flat, headroom moves, and D's estimate moves."""

    PARAMS = d.Params(0.10, -0.5, 0.05, 0.05)

    def test_headroom_moves_while_group_reserves_stay_flat_and_the_estimate_moves(self):
        a = _week(date(2023, 1, 4), (1000.0, 350.0, 150.0))
        b = _week(date(2023, 1, 11), (1000.0, 350.0, 150.0))
        self.assertEqual((a.reserves_bn, a.assets_bn), (b.reserves_bn, b.assets_bn))
        low, high = d.deployable(a, 300.0, self.PARAMS), d.deployable(b, 1200.0, self.PARAMS)
        self.assertNotAlmostEqual(low, high, places=4)
        self.assertGreater(high, low)  # more headroom, a lower buffer (the slope is negative), more deployable liquidity

    def test_c_does_not_move_on_the_same_pair(self):
        a = _week(date(2023, 1, 4), (1000.0, 350.0, 150.0))
        b = _week(date(2023, 1, 11), (1000.0, 350.0, 150.0))
        self.assertEqual(c.deployable(a, (0.1, 0.05, 0.05)), c.deployable(b, (0.1, 0.05, 0.05)))

    def test_the_difference_is_not_a_constant_offset_because_of_the_clip(self):
        # reserves of the large group are far above the buffer: the headroom moves D; far below it: the group contributes 0
        # on both days and the headroom moves nothing
        rich = _week(date(2023, 1, 4), (3000.0, 350.0, 150.0))
        poor = _week(date(2023, 1, 4), (100.0, 350.0, 150.0))
        gap_rich = d.deployable(rich, 1200.0, self.PARAMS) - d.deployable(rich, 300.0, self.PARAMS)
        gap_poor = d.deployable(poor, 1200.0, self.PARAMS) - d.deployable(poor, 300.0, self.PARAMS)
        self.assertGreater(gap_rich, 0.001)
        self.assertEqual(gap_poor, 0.0)


class DistributionTests(unittest.TestCase):
    """Must-show 5: the protocol's three alternatives (section 8), group by group, for D."""

    PARAMS = d.Params(0.08, -0.5, 0.04, 0.03)
    WEEK = _week(date(2023, 1, 4), (1000.0, 300.0, 400.0))

    def result(self):
        return d.distribution(self.WEEK, 950.0, self.PARAMS)

    def test_the_three_alternatives_are_named(self):
        self.assertEqual(tuple(self.result()), ("as_observed", "all_large_domestic", "proportional_to_assets"))

    def test_as_observed_is_the_aggregate(self):
        self.assertAlmostEqual(self.result()["as_observed"]["aggregate"], d.deployable(self.WEEK, 950.0, self.PARAMS))

    def test_every_alternative_holds_the_same_total_reserves_and_gives_the_groups_terms(self):
        for name, item in self.result().items():
            self.assertAlmostEqual(item["reserves_bn"], sum(self.WEEK.reserves_bn), msg=name)
            self.assertAlmostEqual(sum(item["groups"]), item["aggregate"], msg=name)
            self.assertEqual(len(item["groups"]), 3)

    def test_all_held_by_the_large_domestic_banks_uses_d_s_own_large_buffer(self):
        shares = d.shares_at(self.PARAMS, self.WEEK, 950.0)
        total = sum(self.WEEK.reserves_bn)
        want = max(total - shares[0] * ASSETS[0], 0.0) / sum(ASSETS)
        self.assertAlmostEqual(self.result()["all_large_domestic"]["aggregate"], want)

    def test_the_alternatives_move_with_headroom_through_the_large_buffer(self):
        low = d.distribution(self.WEEK, 100.0, self.PARAMS)["proportional_to_assets"]["aggregate"]
        high = d.distribution(self.WEEK, 2000.0, self.PARAMS)["proportional_to_assets"]["aggregate"]
        self.assertNotEqual(low, high)


class _Measured(unittest.TestCase):
    def setUp(self):
        context = scarcity.measurement_declaration()
        context.__enter__()
        self.addCleanup(context.__exit__, None, None, None)
        self.registry = measurement_fields.load_registry()

    def rule(self):
        return InformationRule(self.registry, scarcity.LEGS, decision_time=time(16, 0), horizon=1)


def _panel(start=date(2019, 1, 2), count=330, assets=26000.0):
    out = []
    for index, day in enumerate(_days(start, count)):
        ratio = 0.09 + 0.007 * (((index // 5) * 7) % 11)
        out.append(DailyObservation(day, {
            "sofr": 2.4 + 0.02 * (index % 4), "iorb": 2.4, "reserve_balances": assets * ratio, "bank_total_assets": assets,
            "on_rrp": 20.0,
        }))
    return out


def _rate(day):
    return 2.25


class ReadHeadroomTests(unittest.TestCase):
    def test_a_day_reads_the_latest_complete_quarter_public_at_its_instant(self):
        # the quarter ended 2018-12-31 is public from 2019-01-31 + 1 day (updated 30 days after the quarter-end)
        before = d.read_headroom(SLR_ROWS, _instant(date(2019, 1, 31)))
        after = d.read_headroom(SLR_ROWS, _instant(date(2019, 2, 5)))
        self.assertEqual(before.quarter_end, date(2018, 9, 30))
        self.assertEqual(after.quarter_end, date(2018, 12, 31))
        self.assertLessEqual(after.public_at, _instant(date(2019, 2, 5)))

    def test_nothing_is_read_before_the_first_complete_quarter_is_public(self):
        self.assertIsNone(d.read_headroom(SLR_ROWS, _instant(date(2018, 7, 15))))

    def test_a_quarter_is_complete_only_when_all_nine_banks_are_public(self):
        rows = _quarter_rows(date(2018, 9, 30), 800.0)
        late = [r for r in _quarter_rows(date(2018, 12, 31), 350.0)]
        slow = late[0].__class__(**{**late[0].__dict__, "latest_update": datetime(2019, 3, 20, 12, 0)})
        rows += late[1:] + [slow]
        mid = d.read_headroom(rows, _instant(date(2019, 2, 20)))
        self.assertEqual(mid.quarter_end, date(2018, 9, 30))  # the ninth bank is not public yet
        end = d.read_headroom(rows, _instant(date(2019, 3, 25)))
        self.assertEqual(end.quarter_end, date(2018, 12, 31))
        self.assertEqual(end.public_at, slow.available_from)

    def test_a_bank_missing_from_a_quarter_makes_it_incomplete_for_good(self):
        rows = _quarter_rows(date(2018, 9, 30), 800.0) + _quarter_rows(date(2018, 12, 31), 350.0, banks=list(slr.BANKS)[:8])
        self.assertEqual(d.read_headroom(rows, _instant(date(2019, 6, 1))).quarter_end, date(2018, 9, 30))

    def test_the_decision_instant_is_the_parents_16_00_on_the_panel_day_before(self):
        # an update at 23:59 on the day before the instant is not yet public: the figure is read from the next day
        rows = _quarter_rows(date(2018, 9, 30), 800.0, lag_days=0)
        rows = [r.__class__(**{**r.__dict__, "latest_update": datetime(2018, 12, 3, 23, 59)}) for r in rows]
        self.assertIsNone(d.read_headroom(rows, datetime(2018, 12, 3, 16, 0, tzinfo=NEW_YORK)))
        self.assertIsNone(d.read_headroom(rows, datetime(2018, 12, 3, 23, 59, tzinfo=NEW_YORK)))
        self.assertIsNotNone(d.read_headroom(rows, datetime(2018, 12, 4, 16, 0, tzinfo=NEW_YORK)))

    def test_a_naive_instant_is_refused(self):
        with self.assertRaises(ValueError):
            d.read_headroom(SLR_ROWS, datetime(2019, 3, 1, 16, 0))


class SampleTests(_Measured):
    def setUp(self):
        super().setUp()
        self.rows = _panel()
        self.weeks = _weeks(first=date(2018, 12, 26), count=60)

    def days(self, rows=None, slr_rows=None):
        return d.sample_d(self.rows if rows is None else rows, self.rule(), self.weeks,
                          SLR_ROWS if slr_rows is None else slr_rows, on_rrp_rate=_rate)

    def test_each_day_reads_the_week_and_the_quarter_public_at_its_decision_instant(self):
        for day in [x for x in self.days() if x.week is not None and x.headroom is not None]:
            self.assertLessEqual(day.week.public_at, day.instant)
            self.assertLessEqual(day.headroom.public_at, day.instant)

    def test_ratio_state_week_and_corridor_are_candidate_c_s(self):
        own = {x.day: x for x in c.sample_c(self.rows, self.rule(), self.weeks, on_rrp_rate=_rate)}
        for day in self.days():
            self.assertEqual((day.ratio, day.state, day.week, day.corridor),
                             (own[day.day].ratio, own[day.day].state, own[day.day].week, own[day.day].corridor))

    def test_a_locked_day_is_refused(self):
        rows = _panel(start=date(2026, 8, 3), count=45)
        with self.assertRaises(LookAheadError):
            self.days(rows=rows)


class FitTests(unittest.TestCase):
    def setUp(self):
        self.weeks = _weeks()
        self.days = _planted_days(self.weeks)

    def test_the_planted_parameters_are_recovered(self):
        fit = d.fit_parameters(self.days)
        self.assertEqual(fit.params, PLANTED)
        self.assertAlmostEqual(fit.kink, PLANTED_KINK, places=9)
        self.assertLess(fit.sse, 0.05)
        self.assertGreater(fit.slope, 0.0)

    def test_the_fit_is_deterministic(self):
        self.assertEqual(d.fit_parameters(self.days), d.fit_parameters(self.days))

    def test_the_fit_reports_whether_its_starts_agree(self):
        self.assertIn(d.fit_parameters(self.days).starts_agree, (True, False))

    def test_a_refit_is_fitted_on_a_counted_episode(self):
        fit = d.refit_d(self.days, self.days[-1].day, replications=0, episodes=EPISODES, min_scarce=MIN_SCARCE)
        self.assertTrue(fit.fitted)
        self.assertEqual(fit.params, PLANTED)
        self.assertEqual(fit.episodes, (EPISODE[0],))
        self.assertEqual(fit.draws, ())

    def test_no_counted_episode_is_not_fitted_and_has_no_interval(self):
        fit = d.refit_d(self.days, self.days[10].day, replications=REPLICATIONS, episodes=EPISODES, min_scarce=MIN_SCARCE)
        self.assertFalse(fit.fitted)
        self.assertIsNone(fit.params)
        self.assertEqual(fit.draws, ())

    def test_only_days_up_to_the_cutoff_count_toward_an_episode(self):
        sample, labels = d.training_days(self.days, self.days[28].day, episodes=EPISODES, min_scarce=MIN_SCARCE)
        self.assertEqual((sample, labels), ([], ()))
        sample, labels = d.training_days(self.days, self.days[29].day, episodes=EPISODES, min_scarce=MIN_SCARCE)
        self.assertEqual(labels, (EPISODE[0],))
        self.assertEqual(len(sample), 30)

    def test_a_day_without_a_week_a_corridor_or_a_headroom_is_not_a_training_day(self):
        broken = list(self.days)
        broken[5] = broken[5]._replace(week=None)
        broken[6] = broken[6]._replace(corridor=None)
        broken[7] = broken[7]._replace(headroom=None)
        broken[8] = broken[8]._replace(headroom=broken[8].headroom._replace(headroom_bn=None))
        sample, _ = d.training_days(broken, broken[-1].day, episodes=EPISODES, min_scarce=MIN_SCARCE)
        self.assertEqual(len(sample), len(broken) - 4)

    def test_days_without_headroom_do_not_count_toward_the_sixty_scarce_days(self):
        without = [x._replace(headroom=None) if i % 2 else x for i, x in enumerate(self.days)]
        sample, labels = d.training_days(without, self.days[59].day, episodes=EPISODES, min_scarce=MIN_SCARCE)
        self.assertEqual(labels, (EPISODE[0],))
        self.assertEqual(len(sample), 30)
        none = [x._replace(headroom=None) for x in self.days]
        self.assertEqual(d.training_days(none, self.days[-1].day, episodes=EPISODES, min_scarce=MIN_SCARCE), ([], ()))

    def test_a_day_after_the_cutoff_is_refused(self):
        with self.assertRaises(LookAheadError):
            d.fit_refit(self.days[:150], self.days[100].day, replications=0)

    def test_a_negative_slope_is_not_a_fit(self):
        flipped = [x._replace(corridor=-x.corridor) for x in self.days]
        fit = d.fit_parameters(flipped)
        self.assertTrue(fit is None or fit.slope >= 0.0)


class IntervalTests(unittest.TestCase):
    def setUp(self):
        self.weeks = _weeks()
        self.days = _planted_days(self.weeks)
        self.cutoff = self.days[-1].day

    def fit(self, **kw):
        return d.refit_d(self.days, self.cutoff, replications=REPLICATIONS, episodes=EPISODES, min_scarce=MIN_SCARCE, **kw)

    def test_the_draws_are_reproducible_and_depend_on_the_seed(self):
        self.assertEqual(self.fit().draws, self.fit().draws)
        self.assertNotEqual(self.fit().draws, self.fit(seed=7).draws)

    def test_each_draw_is_a_parameter_vector_on_the_grids(self):
        draws = self.fit().draws
        self.assertTrue(draws)
        for params in draws:
            self.assertIn(params.level, d.LEVEL_GRID)
            self.assertIn(params.slope, d.SLOPE_GRID)
            self.assertIn(params.small, c.SHARE_GRID)
            self.assertIn(params.foreign, c.SHARE_GRID)

    def test_a_days_interval_brackets_its_estimate(self):
        fit = self.fit()
        day = self.days[-1]
        lower, upper = d.interval(fit, day.week, day.headroom.headroom_bn)
        point = d.deployable(day.week, day.headroom.headroom_bn, fit.params)
        self.assertLessEqual(lower, point)
        self.assertGreaterEqual(upper, point)

    def test_no_replications_means_no_interval(self):
        fit = d.refit_d(self.days, self.cutoff, replications=0, episodes=EPISODES, min_scarce=MIN_SCARCE)
        self.assertIsNone(d.interval(fit, self.days[-1].week, self.days[-1].headroom.headroom_bn))


class PathTests(unittest.TestCase):
    """Must-show 4: each refit's real-time path, its served days, the gap to the previous refit, a daily interval."""

    @classmethod
    def setUpClass(cls):
        cls.weeks = _weeks(count=80, breaks=(date(2019, 6, 5),))
        cls.days = _planted_days(cls.weeks, count=300)
        cls.cutoffs = [cls.days[k].day for k in (60, 120, 200)]
        cls.paths = d.real_time_path(cls.days, cls.cutoffs, replications=REPLICATIONS, episodes=EPISODES,
                                     min_scarce=MIN_SCARCE)

    def test_one_path_per_refit_in_order(self):
        self.assertEqual([p.refit.cutoff for p in self.paths], self.cutoffs)

    def test_a_refit_serves_from_the_second_business_day_after_its_cutoff(self):
        for k, p in enumerate(self.paths):
            self.assertTrue(p.estimates)
            self.assertEqual(p.estimates[0].day, next_business_day(self.cutoffs[k], d.SERVING_LAG))
            if k + 1 < len(self.paths):
                self.assertLess(p.estimates[-1].day, next_business_day(self.cutoffs[k + 1], d.SERVING_LAG))

    def test_each_estimate_is_the_deployable_liquidity_of_the_week_and_headroom_its_day_read(self):
        by_day = {x.day: x for x in self.days}
        for p in self.paths:
            for e in p.estimates:
                day = by_day[e.day]
                self.assertAlmostEqual(e.deployable, d.deployable(day.week, day.headroom.headroom_bn, p.refit.params))
                self.assertEqual((e.ratio, e.state), (day.ratio, day.state))
                self.assertLessEqual(e.lower, e.deployable)
                self.assertGreaterEqual(e.upper, e.deployable)

    def test_the_first_refit_has_no_gaps_and_a_later_one_has_the_difference_on_every_day_both_serve(self):
        self.assertEqual(self.paths[0].gaps, {})
        by_day = {x.day: x for x in self.days}
        for k in (1, 2):
            if not (self.paths[k].refit.fitted and self.paths[k - 1].refit.fitted):
                continue
            for e in self.paths[k].estimates:
                day = by_day[e.day]
                before = d.deployable(day.week, day.headroom.headroom_bn, self.paths[k - 1].refit.params)
                self.assertAlmostEqual(self.paths[k].gaps[e.day], abs(e.deployable - before))

    def test_a_refit_that_did_not_fit_is_a_missing_estimate_never_a_fallback(self):
        early = d.real_time_path(self.days, [self.days[10].day, self.days[100].day], replications=0, episodes=EPISODES,
                                 min_scarce=MIN_SCARCE)
        self.assertFalse(early[0].refit.fitted)
        self.assertEqual(early[0].estimates, [])
        self.assertGreater(early[0].missing_days, 0)
        self.assertTrue(early[1].refit.fitted)

    def test_a_served_day_with_no_headroom_is_missing_not_estimated(self):
        gap = [x._replace(headroom=None) if 130 <= i < 140 else x for i, x in enumerate(self.days)]
        path = d.real_time_path(gap, [self.days[120].day], replications=0, episodes=EPISODES, min_scarce=MIN_SCARCE)[0]
        self.assertEqual(path.missing_days, 10 - 0)
        self.assertTrue(all(e.day not in {x.day for x in gap[130:140]} for e in path.estimates))

    def test_a_break_week_is_flagged_never_refused(self):
        flagged = [p for p in self.paths if p.break_days]
        self.assertTrue(flagged)
        by_day = {x.day: x for x in self.days}
        for p in self.paths:
            for day in p.break_days:
                self.assertTrue(by_day[day].week.break_week)
        self.assertEqual(self.paths[-1].refit.break_weeks, (date(2019, 6, 5),))

    def test_a_day_that_reads_an_unknown_exclusion_quarter_is_flagged_never_refused(self):
        marked = [x._replace(headroom=x.headroom._replace(exclusion_unknown=True)) if 150 <= i < 160 else x
                  for i, x in enumerate(self.days)]
        path = d.real_time_path(marked, [self.days[120].day], replications=0, episodes=EPISODES, min_scarce=MIN_SCARCE)[0]
        self.assertEqual(list(path.exclusion_days), [x.day for x in marked[150:160]])
        self.assertTrue(path.estimates)

    def test_unordered_or_repeated_cutoffs_are_refused(self):
        for bad in ([self.cutoffs[1], self.cutoffs[0]], [self.cutoffs[0], self.cutoffs[0]]):
            with self.assertRaises(ValueError):
                d.real_time_path(self.days, bad, replications=0, episodes=EPISODES, min_scarce=MIN_SCARCE)


class LeakageTests(_Measured):
    """Must-show 2: a day reads no week or headroom public after its decision instant, and a refit reads no row after its
    cutoff. Recorded mutations: see the module docstring."""

    def setUp(self):
        super().setUp()
        self.rows = _panel()
        self.weeks = _weeks(first=date(2018, 12, 26), count=60)
        self.days = d.sample_d(self.rows, self.rule(), self.weeks, SLR_ROWS, on_rrp_rate=_rate)

    def test_the_reads_pass_when_every_input_is_public_and_the_latest(self):
        d.check_reads(self.days, self.weeks, SLR_ROWS)

    def test_a_headroom_read_public_after_the_decision_instant_is_refused(self):
        day = next(x for x in self.days if x.headroom is not None and x.headroom.quarter_end == date(2018, 9, 30))
        future = d.read_headroom(SLR_ROWS, datetime(2019, 12, 1, 16, 0, tzinfo=NEW_YORK))
        self.assertGreater(future.public_at, day.instant)
        leaked = [x._replace(headroom=future) if x is day else x for x in self.days]
        with self.assertRaises(LookAheadError):
            d.check_reads(leaked, self.weeks, SLR_ROWS)

    def test_a_headroom_read_that_is_not_the_latest_complete_quarter_is_stale(self):
        day = next(x for x in self.days if x.headroom is not None and x.headroom.quarter_end == date(2018, 12, 31))
        older = d.read_headroom(SLR_ROWS, datetime(2019, 1, 15, 16, 0, tzinfo=NEW_YORK))
        self.assertLess(older.quarter_end, day.headroom.quarter_end)
        stale = [x._replace(headroom=older) if x is day else x for x in self.days]
        with self.assertRaises(StaleReadError):
            d.check_reads(stale, self.weeks, SLR_ROWS)

    def test_a_week_public_after_the_decision_instant_is_still_refused(self):
        day = self.days[50]
        future = next(w for w in self.weeks if w.public_at > day.instant)
        leaked = self.days[:50] + [day._replace(week=future)] + self.days[51:]
        with self.assertRaises(LookAheadError):
            d.check_reads(leaked, self.weeks, SLR_ROWS)

    def test_a_day_with_no_headroom_public_yet_is_not_a_read(self):
        empty = [x._replace(headroom=None) for x in self.days[:3]]
        d.check_reads(empty, self.weeks, [r for r in SLR_ROWS if r.quarter_end > date(2019, 6, 1)])

    def test_a_quarter_filed_later_does_not_move_an_earlier_days_estimate(self):
        params = d.Params(0.05, -0.5, 0.05, 0.05)

        def values(slr_rows):
            days = d.sample_d(self.rows, self.rule(), self.weeks, slr_rows, on_rrp_rate=_rate)
            return {x.day: d.deployable(x.week, x.headroom.headroom_bn, params) for x in days
                    if x.week is not None and x.headroom is not None and x.headroom.headroom_bn is not None}

        before = values(SLR_ROWS)
        changed = [r for r in SLR_ROWS if r.quarter_end < date(2019, 3, 31)] + _quarter_rows(date(2019, 3, 31), 5.0) \
            + [r for r in SLR_ROWS if r.quarter_end > date(2019, 3, 31)]
        after = values(changed)
        cut = date(2019, 3, 31) + timedelta(days=32)
        early = [day for day in before if day < cut]
        self.assertTrue(early)
        for day in early:
            self.assertEqual(before[day], after[day])
        self.assertTrue(any(before[day] != after[day] for day in before if day >= cut))

    def planted(self):
        weeks = _weeks(first=date(2018, 12, 26), count=80)
        rows = _panel(count=300)
        rule = self.rule()
        read = {x.day: x for x in d.sample_d(rows, rule, weeks, SLR_ROWS, on_rrp_rate=_rate)}
        out = [rows[0]]
        for row in rows[1:]:
            values = dict(row.values)
            day = read[row.date]
            if day.week is not None and day.headroom is not None:
                params = PLANTED if len(out) < 150 else d.Params(0.14, -0.5, 0.14, 0.03)
                values["sofr"] = 2.4 + 0.3 * max(0.0, PLANTED_KINK - d.deployable(day.week, day.headroom.headroom_bn, params)) \
                    + 0.3 * _noise(len(out))
            out.append(DailyObservation(row.date, values))
        return weeks, out

    def test_the_refits_pass_when_they_use_nothing_later(self):
        weeks, rows = self.planted()
        rule = self.rule()
        sampled = d.sample_d(rows, rule, weeks, SLR_ROWS, on_rrp_rate=_rate)
        cutoffs = [sampled[k].day for k in (100, 200)]
        path = d.real_time_path(sampled, cutoffs, replications=0, episodes=EPISODES, min_scarce=MIN_SCARCE)
        self.assertTrue(all(p.refit.fitted for p in path))
        d.check_no_future(rows, rule, weeks, SLR_ROWS, path, on_rrp_rate=_rate, replications=0, episodes=EPISODES,
                          min_scarce=MIN_SCARCE)

    def test_a_refit_that_read_later_days_is_refused(self):
        weeks, rows = self.planted()
        rule = self.rule()
        sampled = d.sample_d(rows, rule, weeks, SLR_ROWS, on_rrp_rate=_rate)
        cutoff = sampled[100].day
        honest = d.refit_d(sampled, cutoff, replications=0, episodes=EPISODES, min_scarce=MIN_SCARCE)
        leaked = d.refit_d(sampled, sampled[200].day, replications=0, episodes=EPISODES, min_scarce=MIN_SCARCE)
        leaked = leaked._replace(cutoff=cutoff)
        self.assertNotEqual(leaked.params, honest.params)
        path = [d.PathD(refit=leaked, estimates=[], gaps={}, missing_days=0, break_days=(), exclusion_days=())]
        with self.assertRaises(LookAheadError):
            d.check_no_future(rows, rule, weeks, SLR_ROWS, path, on_rrp_rate=_rate, replications=0, episodes=EPISODES,
                              min_scarce=MIN_SCARCE)


class OutOfSampleTests(unittest.TestCase):
    """Must-show 4: Stage 6's own test for D, fitted on the first episode alone. Constructed data only; nothing is run on
    real days."""

    FIRST = ("first", date(2019, 1, 1), date(2019, 6, 30))
    SECOND = ("second", date(2019, 7, 1), date(2019, 12, 31))
    EPISODES2 = (FIRST, SECOND)

    @classmethod
    def setUpClass(cls):
        cls.weeks = _weeks(first=date(2018, 12, 26), count=80)
        cls.days = _planted_days(cls.weeks, count=240)
        cls.cutoff = cls.FIRST[2]

    def second_episode(self, bend):
        """The first episode as planted; the second with the all-banks ratio linear in D_D, so that D_D reaches its kink at
        the ratio `bend` (D = kink at ratio r* = bend; slope 2.0 ratio points per point of D)."""
        out = []
        for day in self.days:
            if day.day > self.cutoff:
                value = d.deployable(day.week, day.headroom.headroom_bn, PLANTED)
                day = day._replace(ratio=bend + 2.0 * (value - PLANTED_KINK))
            out.append(day)
        return out

    def run_test(self, bend, interval, days=None):
        return d.out_of_sample_2025(self.second_episode(bend) if days is None else days, interval=interval,
                                    replications=0, episodes=self.EPISODES2, min_scarce=MIN_SCARCE)

    def test_a_predicted_bend_inside_the_interval_predicts_it(self):
        result = self.run_test(0.1330, (0.131, 0.1365))
        self.assertTrue(result.fitted)
        # the ratio was built linear in D with D = the planted kink at 0.1330; the fit's kink carries the planted noise
        self.assertAlmostEqual(result.predicted_bend, 0.1330 + 2.0 * (result.kink - PLANTED_KINK), places=9)
        self.assertTrue(result.inside)
        self.assertEqual(result.interval, (0.131, 0.1365))

    def test_a_predicted_bend_outside_the_interval_does_not(self):
        result = self.run_test(0.1000, (0.131, 0.1365))
        self.assertTrue(result.fitted)
        self.assertFalse(result.inside)

    def test_the_fit_uses_the_first_episode_alone(self):
        result = self.run_test(0.1330, (0.131, 0.1365))
        alone = d.refit_d(self.days, self.cutoff, replications=0, episodes=(self.FIRST,), min_scarce=MIN_SCARCE)
        self.assertEqual(result.params, alone.params)
        self.assertEqual(result.kink, alone.kink)

    def test_no_headroom_in_the_first_episode_is_not_fitted_and_predicts_nothing(self):
        bare = [x._replace(headroom=None) if x.day <= self.cutoff else x for x in self.second_episode(0.1330)]
        result = self.run_test(0.1330, (0.131, 0.1365), days=bare)
        self.assertFalse(result.fitted)
        self.assertIsNone(result.predicted_bend)
        self.assertIsNone(result.inside)

    def test_a_flat_ratio_in_the_second_episode_predicts_nothing(self):
        flat = [x._replace(ratio=0.13) if x.day > self.cutoff else x for x in self.second_episode(0.1330)]
        result = self.run_test(0.1330, (0.131, 0.1365), days=flat)
        self.assertTrue(result.fitted)
        self.assertIsNone(result.predicted_bend)
        self.assertIsNone(result.inside)

    def test_stage_2s_2025_interval_is_read_from_its_record(self):
        self.assertEqual(d.stage2_bend_interval(), (0.131, 0.1365))


class TrackedSeriesTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows = d.tracked_rows()

    def test_the_published_snapshot_is_the_one_read(self):
        import hashlib
        import json
        from repo_liquidity import snapshots

        manifest = json.loads((snapshots.ROOT / "snapshots" / "slr_headroom" / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(hashlib.sha256(snapshots.SLR_EXTRACT.read_bytes()).hexdigest(), manifest["sha256"])
        self.assertEqual(d.SNAPSHOT_SHA256, manifest["sha256"])

    def test_a_snapshot_that_is_not_the_published_one_is_refused(self):
        import unittest.mock as mock

        with mock.patch.object(d, "SNAPSHOT_SHA256", "0" * 64):
            with self.assertRaises(ValueError):
                d.tracked_rows()

    def test_nine_banks_in_the_main_measure_and_every_quarter_complete(self):
        self.assertEqual({r.idrssd for r in self.rows}, set(slr.BANKS))
        quarters = {r.quarter_end for r in self.rows}
        self.assertGreater(len(quarters), 20)

    def test_the_first_complete_quarter_is_public_after_the_quarter_ended(self):
        head = d.read_headroom(self.rows, datetime(2026, 9, 3, 16, 0, tzinfo=NEW_YORK))
        self.assertIsNotNone(head)
        self.assertLessEqual(head.public_at, datetime(2026, 9, 3, 16, 0, tzinfo=NEW_YORK))

    def test_no_row_is_public_after_the_development_end(self):
        from repo_liquidity import development

        self.assertTrue(all(not development.is_locked(r.latest_update.date()) for r in self.rows))

    def test_the_module_scores_nothing(self):
        for name in dir(d):
            self.assertNotIn(name.lower(), {"auc", "score", "crps", "roc"}, name)

    def test_the_group_reserves_series_is_reached_only_through_candidate_c(self):
        self.assertFalse(hasattr(d, "group_reserves"))
        self.assertEqual(d.tracked_weeks()[0], c.tracked_weeks()[0])


if __name__ == "__main__":
    unittest.main()
