"""H7m, development step 2: candidate C, the buffer set by H.8 bank group (`docs/stages/h7-step2.md`, directive #41).

Aggregate deployable liquidity on day T is the sum over the three H.8 groups of max(group reserves - share x group assets, 0),
over the groups' total assets; the three shares are fitted through Stage 2's broken stick on the counted scarce episodes, on
training rows only. Nothing is scored here. What is covered:

* `DeployableTests` -- the formula, the clip at zero, the unit, the group-by-group terms.
* `NotRPlusAConstantTests` (must-show 3) -- with aggregate reserves flat, a shift of their composition moves C's estimate;
  C and the all-banks ratio rank a pair of weeks in opposite orders.
* `DistributionTests` (must-show 5) -- the three declared alternatives of protocol section 8.
* `FitTests` -- planted shares are recovered; no counted episode is not fitted; a day after the cutoff is refused; a later
  scarce day does not make an episode count.
* `IntervalTests`, `PathTests` (must-show 4) -- the bootstrap interval, each refit's real-time path, the gap to the previous
  refit, and the days that read an H.8 break week (flagged, not refused).
* `ReadTests` and `LeakageTests` (must-show 2) -- the group week read for a day is the latest one public at its decision
  instant; a week public after it is `LookAheadError`, a week that is not the latest public is `StaleReadError`; a refit that
  read a later row is refused.
* `TrackedSeriesTests` -- the tracked group-reserves series loads through its own checks and C reads it as weeks.

**Recorded mutations** (CLAUDE.md), 19 October 2026, in a disposable copy of the tree, CPython 3.11, the parent at the pin
(8fd2cf8), `PYTHONDONTWRITEBYTECODE=1`, applied by a one-line replacement and confirmed by `grep`, the suite run against the
copy, the copy discarded:

1. `read_week`: replace `w.public_at <= instant` by `w.week_ending <= instant.date()` (a week is read from its Wednesday, not from
   its release). `LeakageTests.test_a_week_public_after_the_decision_instant_is_refused`, and ten more tests that build days,
   raise `repo_model.splits.LookAheadError: 2019-01-03 read the week ending 2019-01-02, public at 2019-01-11 16:15:00-05:00,
   after its decision instant 2019-01-02 16:00:00-05:00` from `check_reads`; `ReadTests.test_a_week_published_after_the_instant_is_not_read`,
   `test_before_the_first_release_nothing_is_read` and `IntervalTests.test_a_different_seed_gives_different_draws` fail with
   `AssertionError` (14 of 58 fail).
2. `check_reads`: replace `d.week is None or d.week.week_ending < latest.week_ending` by `False`. A week older than the latest
   public one is no longer refused; `LeakageTests.test_a_week_that_is_not_the_latest_public_is_stale` fails with
   `AssertionError: StaleReadError not raised` (the only failure).
3. `check_reads`: replace `if d.week is not None and d.week.public_at > d.instant:` by `if False:`. A week public after the
   decision instant is no longer refused; `LeakageTests.test_a_week_public_after_the_decision_instant_is_refused` fails with
   `AssertionError: LookAheadError not raised` (the only failure).
4. `training_days`: replace `d.day <= cutoff` by `d.day <= next_business_day(cutoff, 60)`. A refit then fits on days up to sixty
   business days after its cutoff; `FitTests.test_only_days_up_to_the_cutoff_count_toward_an_episode` fails with `AssertionError`,
   and four tests that fit a refit (`LeakageTests.test_a_refit_that_read_later_days_is_refused` and
   `test_the_refits_pass_when_they_use_nothing_later` among them, and `PathTests`' class setup) raise
   `repo_model.splits.LookAheadError: the shares for the refit at ... would be fitted on ..., after its cutoff` from `fit_refit`.
5. `check_no_future`: replace `if again.fitted != p.refit.fitted or again.shares != p.refit.shares:` by `if False:`. A refit that
   differs from the cut panel's is no longer refused; `LeakageTests.test_a_refit_that_read_later_days_is_refused` fails with
   `AssertionError: LookAheadError not raised` (the only failure).

Written first, and watched failing: before `repo_liquidity.h7_candidate_c` existed the module did not import:
`ImportError: cannot import name 'h7_candidate_c' from 'repo_liquidity'`.
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
from repo_liquidity import h7_estimator as h7

NEW_YORK = ZoneInfo("America/New_York")
REPLICATIONS = 6
ASSETS = (9500.0, 5000.0, 2300.0)
#: The planted shares and kink (the kink is on `c.KINK_GRID`).
PLANTED = (0.06, 0.14, 0.03)
PLANTED_KINK = 0.03
#: The shares the corridor position follows from the 150th day on, in the tests that need the fit to move.
LATER = (0.12, 0.14, 0.03)
EPISODE = ("test episode", date(2019, 1, 1), date(2019, 12, 31))
EPISODES = (EPISODE,)
MIN_SCARCE = 30


def _days(start, count):
    out = [start]
    while len(out) < count:
        out.append(next_business_day(out[-1], 1))
    return out


def _release(wednesday):
    """The Friday of the week after, 16:15 New York: the H.8 first print of the week ending `wednesday`."""
    friday = wednesday + timedelta(days=9)
    return datetime.combine(friday, time(16, 15), tzinfo=NEW_YORK)


def _week(wednesday, reserves, assets=ASSETS, brk=False):
    return c.GroupWeek(wednesday, _release(wednesday), tuple(reserves), tuple(assets), brk)


def _wednesday_on_or_before(day):
    return day - timedelta(days=(day.weekday() - 2) % 7)


def _cycle(index, modulus, step):
    return ((index * step) % modulus) / (modulus - 1)


def _planted_reserves(index):
    """Each group sits between 3 points below and 8 points above its planted buffer, on three different cycles."""
    return tuple(a * (s - 0.03 + 0.11 * _cycle(index, m, p))
                 for a, s, m, p in zip(ASSETS, PLANTED, (13, 11, 7), (5, 3, 2)))


def _weeks(first=date(2018, 12, 26), count=70, reserves=_planted_reserves, breaks=()):
    out = []
    for index in range(count):
        wednesday = first + timedelta(weeks=index)
        out.append(_week(wednesday, reserves(index), brk=wednesday in breaks))
    return out


def _noise(index):
    """A deterministic wiggle of up to 0.02, so that the bootstrap's draws are not all the same."""
    return 0.02 * (((index * 7919) % 13) - 6) / 6.0


def _planted_days(weeks, start=date(2019, 1, 7), count=230, kink=PLANTED_KINK, shares=PLANTED, later=None):
    """Days that read the latest public week, with the corridor position planted on D_C at the planted shares (and, from
    day `later[0]`, at the shares `later[1]`)."""
    out = []
    for index, day in enumerate(_days(start, count)):
        instant = datetime.combine(day - timedelta(days=1), time(16, 0), tzinfo=NEW_YORK)
        week = c.read_week(weeks, instant)
        if week is None:
            continue
        deployable = c.deployable(week, later[1] if later and index >= later[0] else shares)
        ratio = 0.10 + 0.0001 * (index % 7)
        corridor = 0.10 + 8.0 * max(0.0, kink - deployable) + _noise(index)
        out.append(c.DayC(day, instant, ratio, corridor, 1.0, week))
    return out


class DeployableTests(unittest.TestCase):
    def test_the_sum_of_each_groups_reserves_above_its_buffer_over_the_groups_assets(self):
        week = _week(date(2023, 1, 4), (1000.0, 300.0, 400.0))
        shares = (0.05, 0.04, 0.10)
        want = ((1000.0 - 0.05 * 9500.0) + (300.0 - 0.04 * 5000.0) + (400.0 - 0.10 * 2300.0)) / sum(ASSETS)
        self.assertAlmostEqual(c.deployable(week, shares), want)

    def test_a_group_below_its_buffer_contributes_zero_not_a_negative_number(self):
        week = _week(date(2023, 1, 4), (1000.0, 100.0, 400.0))
        shares = (0.05, 0.04, 0.10)
        self.assertEqual(c.group_contributions(week, shares)[1], 0.0)
        want = ((1000.0 - 475.0) + (400.0 - 230.0)) / sum(ASSETS)
        self.assertAlmostEqual(c.deployable(week, shares), want)

    def test_zero_shares_leave_all_the_groups_reserves(self):
        week = _week(date(2023, 1, 4), (1000.0, 300.0, 400.0))
        self.assertAlmostEqual(c.deployable(week, (0.0, 0.0, 0.0)), 1700.0 / sum(ASSETS))

    def test_group_terms_sum_to_the_aggregate(self):
        week = _week(date(2023, 1, 4), (1000.0, 100.0, 400.0))
        shares = (0.05, 0.04, 0.10)
        self.assertAlmostEqual(sum(c.group_contributions(week, shares)), c.deployable(week, shares))

    def test_points_are_a_hundred_times_the_share(self):
        self.assertEqual(c.points(0.0125), 1.25)

    def test_a_share_outside_zero_and_one_is_refused(self):
        week = _week(date(2023, 1, 4), (1000.0, 300.0, 400.0))
        for bad in ((-0.01, 0.0, 0.0), (0.0, 1.0, 0.0)):
            with self.assertRaises(ValueError):
                c.deployable(week, bad)


class NotRPlusAConstantTests(unittest.TestCase):
    """Must-show 3: with aggregate reserves flat, C moves when their composition shifts."""

    SHARES = (0.05, 0.05, 0.05)

    def pair(self):
        # the same total reserves (1500) and the same assets in both weeks; the reserves move from the large group,
        # which has room above its buffer, to the foreign-related group, which has little room
        a = _week(date(2023, 1, 4), (1000.0, 350.0, 150.0))
        b = _week(date(2023, 1, 11), (400.0, 350.0, 750.0))
        return a, b

    def test_aggregate_reserves_are_flat_and_the_estimate_moves(self):
        a, b = self.pair()
        self.assertEqual(sum(a.reserves_bn), sum(b.reserves_bn))
        self.assertNotAlmostEqual(c.deployable(a, self.SHARES), c.deployable(b, self.SHARES), places=4)

    def test_the_estimate_is_not_the_aggregate_ratio_plus_a_constant(self):
        a, b = self.pair()
        ratio = lambda w: sum(w.reserves_bn) / sum(w.assets_bn)  # noqa: E731
        self.assertEqual(ratio(a), ratio(b))
        gap = c.deployable(a, self.SHARES) - c.deployable(b, self.SHARES)
        # a constant offset from the ratio would give the same estimate for weeks with the same ratio
        self.assertGreater(abs(gap), 0.001)

    def test_a_pair_of_weeks_is_ranked_opposite_ways_by_the_ratio_and_the_estimate(self):
        # b holds 1 bn more reserves than a, but most of them sit in groups below their own buffers
        a = _week(date(2023, 1, 4), (1000.0, 400.0, 100.0))
        b = _week(date(2023, 1, 11), (474.0, 249.0, 778.0))
        ratio = lambda w: sum(w.reserves_bn) / sum(w.assets_bn)  # noqa: E731
        self.assertGreater(ratio(b), ratio(a))
        self.assertLess(c.deployable(b, self.SHARES), c.deployable(a, self.SHARES))


class DistributionTests(unittest.TestCase):
    """Must-show 5: the protocol's three declared alternatives (section 8), implemented and unit-tested."""

    SHARES = (0.05, 0.04, 0.10)

    def setUp(self):
        self.week = _week(date(2023, 1, 4), (1000.0, 300.0, 400.0))

    def test_the_three_alternatives_are_named(self):
        self.assertEqual(set(c.distribution(self.week, self.SHARES)), {"as_observed", "all_large_domestic", "proportional_to_assets"})

    def test_as_observed_is_the_aggregate(self):
        got = c.distribution(self.week, self.SHARES)["as_observed"]
        self.assertAlmostEqual(got["aggregate"], c.deployable(self.week, self.SHARES))
        self.assertAlmostEqual(sum(got["groups"]), got["aggregate"])

    def test_all_held_by_the_large_domestic_banks(self):
        got = c.distribution(self.week, self.SHARES)["all_large_domestic"]
        moved = self.week._replace(reserves_bn=(1700.0, 0.0, 0.0))
        self.assertAlmostEqual(got["aggregate"], c.deployable(moved, self.SHARES))
        self.assertEqual(got["groups"][1], 0.0)
        self.assertEqual(got["groups"][2], 0.0)

    def test_in_proportion_to_group_assets(self):
        got = c.distribution(self.week, self.SHARES)["proportional_to_assets"]
        total_assets = sum(ASSETS)
        spread = tuple(1700.0 * a / total_assets for a in ASSETS)
        moved = self.week._replace(reserves_bn=spread)
        self.assertAlmostEqual(got["aggregate"], c.deployable(moved, self.SHARES))

    def test_every_alternative_holds_the_same_total_reserves(self):
        for name, got in c.distribution(self.week, self.SHARES).items():
            self.assertAlmostEqual(got["reserves_bn"], 1700.0, msg=name)

    def test_the_alternatives_differ_where_the_composition_matters(self):
        got = c.distribution(self.week, (0.05, 0.08, 0.10))
        values = {round(v["aggregate"], 9) for v in got.values()}
        self.assertEqual(len(values), 3)


class FitTests(unittest.TestCase):
    def setUp(self):
        self.weeks = _weeks()
        self.days = _planted_days(self.weeks)

    def test_the_planted_shares_are_recovered(self):
        fit = c.fit_shares(self.days)
        self.assertEqual(fit.shares, PLANTED)
        self.assertAlmostEqual(fit.kink, PLANTED_KINK, places=9)
        self.assertLess(fit.sse, 0.05)  # the planted wiggle: 230 days of up to 0.02
        self.assertGreater(fit.slope, 0.0)

    def test_the_fit_is_deterministic(self):
        self.assertEqual(c.fit_shares(self.days), c.fit_shares(self.days))

    def test_the_fit_reports_whether_its_starts_agree(self):
        self.assertIn(c.fit_shares(self.days).starts_agree, (True, False))

    def test_a_refit_is_fitted_on_a_counted_episode(self):
        cutoff = self.days[-1].day
        fit = c.refit_c(self.days, cutoff, replications=0, episodes=EPISODES, min_scarce=MIN_SCARCE)
        self.assertTrue(fit.fitted)
        self.assertEqual(fit.shares, PLANTED)
        self.assertEqual(fit.episodes, (EPISODE[0],))
        self.assertEqual(fit.draws, ())

    def test_no_counted_episode_is_not_fitted_and_has_no_interval(self):
        cutoff = self.days[10].day
        fit = c.refit_c(self.days, cutoff, replications=REPLICATIONS, episodes=EPISODES, min_scarce=MIN_SCARCE)
        self.assertFalse(fit.fitted)
        self.assertIsNone(fit.shares)
        self.assertEqual(fit.draws, ())

    def test_only_days_up_to_the_cutoff_count_toward_an_episode(self):
        # 29 scarce days by the cutoff, many more after it: the episode does not count at the cutoff
        cutoff = self.days[28].day
        sample, labels = c.training_days(self.days, cutoff, episodes=EPISODES, min_scarce=MIN_SCARCE)
        self.assertEqual((sample, labels), ([], ()))
        cutoff = self.days[29].day
        sample, labels = c.training_days(self.days, cutoff, episodes=EPISODES, min_scarce=MIN_SCARCE)
        self.assertEqual(labels, (EPISODE[0],))
        self.assertEqual(len(sample), 30)
        self.assertTrue(all(d.day <= cutoff for d in sample))

    def test_a_day_without_a_group_week_or_a_corridor_is_not_a_training_day(self):
        broken = list(self.days)
        broken[5] = broken[5]._replace(week=None)
        broken[6] = broken[6]._replace(corridor=None)
        sample, _ = c.training_days(broken, broken[-1].day, episodes=EPISODES, min_scarce=MIN_SCARCE)
        self.assertEqual(len(sample), len(broken) - 2)

    def test_a_day_after_the_cutoff_is_refused(self):
        cutoff = self.days[100].day
        with self.assertRaises(LookAheadError):
            c.fit_refit(self.days[:150], cutoff, replications=0)

    def test_a_negative_slope_is_not_a_fit(self):
        flipped = [d._replace(corridor=-d.corridor) for d in self.days]
        fit = c.fit_shares(flipped)
        self.assertTrue(fit is None or fit.slope >= 0.0)


class IntervalTests(unittest.TestCase):
    def setUp(self):
        self.weeks = _weeks()
        self.days = _planted_days(self.weeks)
        self.cutoff = self.days[-1].day

    def fit(self, **kw):
        return c.refit_c(self.days, self.cutoff, replications=REPLICATIONS, episodes=EPISODES, min_scarce=MIN_SCARCE, **kw)

    def test_the_draws_are_reproducible(self):
        self.assertEqual(self.fit().draws, self.fit().draws)

    def test_a_different_seed_gives_different_draws(self):
        self.assertNotEqual(self.fit().draws, self.fit(seed=7).draws)

    def test_each_draw_is_a_share_vector_on_the_grid(self):
        draws = self.fit().draws
        self.assertTrue(draws)
        for shares in draws:
            self.assertEqual(len(shares), 3)
            self.assertTrue(all(s in c.SHARE_GRID for s in shares))

    def test_a_days_interval_brackets_its_estimate(self):
        fit = self.fit()
        week = self.days[-1].week
        lower, upper = c.interval(fit, week)
        point = c.deployable(week, fit.shares)
        self.assertLessEqual(lower, point)
        self.assertGreaterEqual(upper, point)

    def test_no_replications_means_no_interval(self):
        fit = c.refit_c(self.days, self.cutoff, replications=0, episodes=EPISODES, min_scarce=MIN_SCARCE)
        self.assertIsNone(c.interval(fit, self.days[-1].week))


class PathTests(unittest.TestCase):
    """Must-show 4: each refit's real-time path, its served days, the gap to the previous refit, a daily interval."""

    @classmethod
    def setUpClass(cls):
        cls.weeks = _weeks(count=80, breaks=(date(2019, 6, 5),))
        cls.days = _planted_days(cls.weeks, count=300)
        cls.cutoffs = [cls.days[k].day for k in (60, 120, 200)]
        cls.cached = c.real_time_path(cls.days, cls.cutoffs, replications=REPLICATIONS, episodes=EPISODES,
                                      min_scarce=MIN_SCARCE)

    def path(self):
        return self.cached

    def test_one_path_per_refit_in_order(self):
        self.assertEqual([p.refit.cutoff for p in self.path()], self.cutoffs)

    def test_a_refit_serves_from_the_second_business_day_after_its_cutoff_to_the_next_serving_start(self):
        paths = self.path()
        for k, p in enumerate(paths):
            first = next_business_day(self.cutoffs[k], c.SERVING_LAG)
            self.assertTrue(p.estimates)
            self.assertEqual(p.estimates[0].day, first)
            if k + 1 < len(paths):
                self.assertLess(p.estimates[-1].day, next_business_day(self.cutoffs[k + 1], c.SERVING_LAG))

    def test_each_estimate_is_the_deployable_liquidity_of_the_week_its_day_read(self):
        by_day = {d.day: d for d in self.days}
        for p in self.path():
            for e in p.estimates:
                day = by_day[e.day]
                self.assertAlmostEqual(e.deployable, c.deployable(day.week, p.refit.shares))
                self.assertEqual(e.ratio, day.ratio)
                self.assertEqual(e.state, day.state)
                self.assertLessEqual(e.lower, e.deployable)
                self.assertGreaterEqual(e.upper, e.deployable)

    def test_the_first_refit_has_no_gaps_and_a_later_one_has_the_difference_on_every_day_both_serve(self):
        paths = self.path()
        self.assertEqual(paths[0].gaps, {})
        by_day = {d.day: d for d in self.days}
        for k in (1, 2):
            if not (paths[k].refit.fitted and paths[k - 1].refit.fitted):
                continue
            for e in paths[k].estimates:
                before = c.deployable(by_day[e.day].week, paths[k - 1].refit.shares)
                self.assertAlmostEqual(paths[k].gaps[e.day], abs(e.deployable - before))

    def test_a_refit_that_did_not_fit_is_a_missing_estimate_never_a_fallback(self):
        early = c.real_time_path(self.days, [self.days[10].day, self.days[100].day], replications=0, episodes=EPISODES,
                                 min_scarce=MIN_SCARCE)
        self.assertFalse(early[0].refit.fitted)
        self.assertEqual(early[0].estimates, [])
        self.assertGreater(early[0].missing_days, 0)
        self.assertTrue(early[1].refit.fitted)

    def test_a_break_week_is_flagged_never_refused(self):
        paths = self.path()
        flagged = [p for p in paths if p.break_days]
        self.assertTrue(flagged)
        for p in paths:
            self.assertTrue(p.estimates)
            for day in p.break_days:
                self.assertTrue(next(d for d in self.days if d.day == day).week.break_week)
        later = paths[-1].refit
        self.assertEqual(later.break_weeks, (date(2019, 6, 5),))
        self.assertEqual(paths[0].refit.break_weeks, ())

    def test_unordered_or_repeated_cutoffs_are_refused(self):
        for bad in ([self.cutoffs[1], self.cutoffs[0]], [self.cutoffs[0], self.cutoffs[0]]):
            with self.assertRaises(ValueError):
                c.real_time_path(self.days, bad, replications=0, episodes=EPISODES, min_scarce=MIN_SCARCE)

    def test_points_and_dollars_are_the_estimate_scaled(self):
        self.assertEqual(c.points(0.0125), 1.25)
        self.assertEqual(c.dollars(0.01, 16800.0), 168.0)


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


class ReadTests(_Measured):
    def setUp(self):
        super().setUp()
        self.rows = _panel()
        self.weeks = _weeks(first=date(2018, 12, 26), count=60)

    def days(self, rows=None, weeks=None):
        return c.sample_c(self.rows if rows is None else rows, self.rule(), self.weeks if weeks is None else weeks,
                          on_rrp_rate=_rate)

    def test_each_day_reads_the_latest_week_public_at_its_decision_instant(self):
        for d in [d for d in self.days() if d.week is not None]:
            self.assertLessEqual(d.week.public_at, d.instant)
            later = [w for w in self.weeks if w.public_at <= d.instant and w.public_at > d.week.public_at]
            self.assertEqual(later, [])

    def test_the_decision_instant_is_the_parents_16_00_on_the_panel_day_before(self):
        days = self.days()
        by_date = {r.date: i for i, r in enumerate(self.rows)}
        for d in days[:20]:
            previous = self.rows[by_date[d.day] - 1].date
            self.assertEqual(d.instant, datetime.combine(previous, time(16, 0), tzinfo=NEW_YORK))

    def test_ratio_and_state_are_the_estimators_own_as_of_days(self):
        own = {d.day: d for d in h7.asof_days(self.rows, self.rule())}
        for d in self.days():
            self.assertEqual(d.ratio, own[d.day].ratio)
            self.assertEqual(d.state, own[d.day].state)

    def test_the_corridor_position_is_stage_2s(self):
        d = self.days()[40]
        row = next(r for r in self.rows if r.date == d.day)
        want = round((row.values["sofr"] - 2.25) / (row.values["iorb"] - 2.25), 9)
        self.assertAlmostEqual(d.corridor, want)

    def test_a_week_published_after_the_instant_is_not_read(self):
        # the Wednesday itself is not public: the first print is released the Friday after the next
        week = self.weeks[10]
        before = week.public_at - timedelta(minutes=1)
        read = c.read_week(self.weeks, before)
        self.assertLess(read.week_ending, week.week_ending)
        self.assertEqual(c.read_week(self.weeks, week.public_at).week_ending, week.week_ending)

    def test_before_the_first_release_nothing_is_read(self):
        self.assertIsNone(c.read_week(self.weeks, self.weeks[0].public_at - timedelta(days=1)))

    def test_a_locked_day_is_refused(self):
        rows = _panel(start=date(2026, 8, 3), count=45)
        with self.assertRaises(LookAheadError):
            self.days(rows=rows)


class LeakageTests(_Measured):
    """Must-show 2: a day reads no week public after its decision instant, and a refit reads no row after its cutoff.

    Recorded mutations: see the module docstring.
    """

    def setUp(self):
        super().setUp()
        self.rows = _panel()
        self.weeks = _weeks(first=date(2018, 12, 26), count=60)
        self.days = c.sample_c(self.rows, self.rule(), self.weeks, on_rrp_rate=_rate)

    def test_the_reads_pass_when_every_week_is_public_and_the_latest(self):
        c.check_reads(self.days, self.weeks)

    def test_a_week_public_after_the_decision_instant_is_refused(self):
        day = self.days[50]
        future = next(w for w in self.weeks if w.public_at > day.instant)
        leaked = self.days[:50] + [day._replace(week=future)] + self.days[51:]
        with self.assertRaises(LookAheadError):
            c.check_reads(leaked, self.weeks)

    def test_a_week_that_is_not_the_latest_public_is_stale(self):
        day = self.days[50]
        older = next(w for w in reversed(self.weeks) if w.public_at < day.week.public_at)
        stale = self.days[:50] + [day._replace(week=older)] + self.days[51:]
        with self.assertRaises(StaleReadError):
            c.check_reads(stale, self.weeks)

    def test_a_day_with_no_week_public_yet_is_not_a_read(self):
        empty = [d._replace(week=None) for d in self.days]
        c.check_reads(empty[:3], self.weeks)

    def test_a_week_published_later_does_not_move_an_earlier_days_estimate(self):
        shares = (0.05, 0.05, 0.05)
        before = [None if d.week is None else c.deployable(d.week, shares) for d in self.days]
        changed = [w._replace(reserves_bn=(9999.0, 9999.0, 9999.0)) if w.week_ending >= date(2019, 6, 1) else w
                   for w in self.weeks]
        again = c.sample_c(self.rows, self.rule(), changed, on_rrp_rate=_rate)
        cut = date(2019, 6, 1) + timedelta(days=11)
        for d, e, was in zip(self.days, again, before):
            if d.day < cut and was is not None:
                self.assertEqual(c.deployable(e.week, shares), was)

    def planted_rows(self):
        """The panel with the corridor position planted on D_C at the planted shares, for the group weeks each day reads."""
        weeks = _weeks(first=date(2018, 12, 26), count=80)
        rows = _panel(count=300)
        rule = self.rule()
        read = {d.day: d.week for d in c.sample_c(rows, rule, weeks, on_rrp_rate=_rate)}
        planted = [rows[0]]
        for row in rows[1:]:
            values = dict(row.values)
            week = read[row.date]
            if week is not None:
                shares = PLANTED if len(planted) < 150 else LATER
                values["sofr"] = 2.4 + 0.3 * max(0.0, PLANTED_KINK - c.deployable(week, shares)) + 0.3 * _noise(len(planted))
            planted.append(DailyObservation(row.date, values))
        return weeks, planted

    def test_the_refits_pass_when_they_use_nothing_later(self):
        weeks, rows = self.planted_rows()
        rule = self.rule()
        sampled = c.sample_c(rows, rule, weeks, on_rrp_rate=_rate)
        cutoffs = [sampled[k].day for k in (100, 200)]
        path = c.real_time_path(sampled, cutoffs, replications=0, episodes=EPISODES, min_scarce=MIN_SCARCE)
        self.assertTrue(all(p.refit.fitted for p in path))
        c.check_no_future(rows, rule, weeks, path, on_rrp_rate=_rate, replications=0, episodes=EPISODES,
                          min_scarce=MIN_SCARCE)

    def test_a_refit_that_read_later_days_is_refused(self):
        weeks, rows = self.planted_rows()
        rule = self.rule()
        sampled = c.sample_c(rows, rule, weeks, on_rrp_rate=_rate)
        cutoff = sampled[100].day
        honest = c.refit_c(sampled, cutoff, replications=0, episodes=EPISODES, min_scarce=MIN_SCARCE)
        # a refit stamped with this cutoff that was fitted on 100 more days than were public at it
        leaked = c.refit_c(sampled, sampled[200].day, replications=0, episodes=EPISODES, min_scarce=MIN_SCARCE)
        leaked = leaked._replace(cutoff=cutoff)
        self.assertNotEqual(leaked.shares, honest.shares)
        path = [c.PathC(refit=leaked, estimates=[], gaps={}, missing_days=0, break_days=())]
        with self.assertRaises(LookAheadError):
            c.check_no_future(rows, rule, weeks, path, on_rrp_rate=_rate, replications=0, episodes=EPISODES,
                              min_scarce=MIN_SCARCE)


class TrackedSeriesTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.weeks = c.tracked_weeks()

    def test_the_tracked_series_loads_as_weeks_with_three_groups(self):
        self.assertGreater(len(self.weeks), 400)
        for w in self.weeks[:5] + self.weeks[-5:]:
            self.assertEqual(len(w.reserves_bn), 3)
            self.assertEqual(len(w.assets_bn), 3)
            self.assertTrue(all(a > 0 for a in w.assets_bn))
            self.assertIsNotNone(w.public_at.tzinfo)

    def test_weeks_are_in_order_and_unique(self):
        ends = [w.week_ending for w in self.weeks]
        self.assertEqual(ends, sorted(set(ends)))

    def test_group_reserves_are_less_than_the_groups_assets_and_sum_below_total_reserves(self):
        for w in self.weeks:
            self.assertTrue(all(0 < r < a for r, a in zip(w.reserves_bn, w.assets_bn)), w.week_ending)

    def test_the_break_weeks_are_flagged(self):
        flagged = [w.week_ending for w in self.weeks if w.break_week]
        self.assertTrue(flagged)

    def test_no_week_is_public_after_the_development_end(self):
        from repo_liquidity import development

        self.assertTrue(all(not development.is_locked(w.public_at.date()) for w in self.weeks))

    def test_the_total_assets_are_the_h8_first_prints(self):
        from repo_liquidity import h8

        prints = {p.week_ending: p for p in h8.load_extract(c.group_reserves.H8_EXTRACT)}
        for w in self.weeks[::37]:
            want = tuple(prints[w.week_ending].values[f"h8_{g}_total_assets"] for g in c.GROUPS)
            self.assertEqual(w.assets_bn, want)

    def test_the_module_scores_nothing(self):
        for name in dir(c):
            self.assertNotIn(name.lower(), {"auc", "score", "crps", "roc"}, name)


if __name__ == "__main__":
    unittest.main()
