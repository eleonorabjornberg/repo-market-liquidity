"""H7m, groundwork G6: the goalpost module (`docs/stages/h7-g6.md`, `docs/decisions/measurement-protocol.md` §3-§6, §9, §11, §13).

What is covered, on synthetic estimators of known quality (protocol §13 item 1) and hand-computed cases:

* `StabilityAndSharpnessTests` -- goalposts 1 and 2: the bar is strict, a missing refit is a breach, a missing day is over the bar.
* `StatisticTests` -- goalpost 3's statistic (§5): R scores exactly 0; a planted signal is recovered; holding S fixed removes
  what S alone carries; the pooling is event-weighted; a missing estimate takes R's place and cannot gain.
* `SyntheticEstimatorTests` -- the five estimators of §13 item 1: stable and sharp, jumpy, wide, R itself, and one with
  planted information beyond R.
* `BootstrapTests` -- the vectorised resampling gives the scalar statistic on every draw; the nominal levels are the
  parent's; a level the draws cannot resolve is refused; the same seed gives the same bound.
* `VerdictTests` -- supported, killed, inconclusive and not shown (§9), and the upper bound's level is never defaulted.
* `MissingTests` -- more than 5% missing days voids the registration (§11).
* `PowerStudyTests` -- the planting is calibrated to its target; windows, eras and the Wilson interval.
* `ReaderTests` -- the days the study reads: nothing after 2026-09-03 (`LookAheadError`), the event is the parent's
  `fed_repo_accepted >= 1.0`, and a day without a label is dropped and counted.

**Recorded mutations** (CLAUDE.md), 14 October 2026, in a disposable copy of the tree, CPython 3.11, the parent at the pin
(53e61af), `PYTHONDONTWRITEBYTECODE=1`, applied by `sed` and confirmed by `grep`, the suite run against the copy, the copy
discarded. They are in the docstrings of the two `ReaderTests` tests they are killed by: the late-day guard
(`AssertionError: LookAheadError not raised`) and the event's threshold.

Written first, and watched failing: before `repo_liquidity.goalposts` existed this module did not import:
`ImportError: cannot import name 'goalposts' from 'repo_liquidity'`.
"""

from __future__ import annotations

import random
import unittest
from datetime import date

from repo_model import scoring_protocol
from repo_model.metrics import stationary_bootstrap_indices
from repo_model.splits import LookAheadError

from repo_liquidity import goalposts as gp


def _world(n=900, seed=7):
    """R depends on S; events sit at low R and, independently, at low `hidden`, which R does not carry."""

    rng = random.Random(seed)
    state = [float(rng.randrange(4)) for _ in range(n)]
    hidden = [rng.gauss(0.0, 1.0) for _ in range(n)]
    ratio = [0.16 - 0.02 * s + rng.gauss(0.0, 0.012) for s in state]
    event = []
    for r, s, h in zip(ratio, state, hidden):
        score = -90.0 * (r - 0.12) - 1.0 * h + rng.gauss(0.0, 0.7)
        event.append(1 if score > 1.6 else 0)
    return ratio, state, event, hidden


class StabilityAndSharpnessTests(unittest.TestCase):
    def test_every_gap_under_the_bar_holds(self):
        result = gp.stability_goalpost({date(2024, 1, 3): 0.001, date(2024, 1, 4): 0.0049}, missing_refits=0)
        self.assertTrue(result["holds"])

    def test_a_gap_exactly_on_the_bar_is_a_breach(self):
        result = gp.stability_goalpost({date(2024, 1, 3): 0.005}, missing_refits=0)
        self.assertFalse(result["holds"])
        self.assertEqual(result["breaches"], 1)

    def test_a_missing_refit_is_a_breach_with_no_fallback(self):
        self.assertFalse(gp.stability_goalpost({date(2024, 1, 3): 0.0}, missing_refits=1)["holds"])

    def test_the_median_width_under_the_bar_holds(self):
        self.assertTrue(gp.sharpness_goalpost([0.02, 0.025, 0.029])["holds"])
        self.assertFalse(gp.sharpness_goalpost([0.03, 0.03, 0.03])["holds"])

    def test_a_missing_day_counts_as_over_the_bar(self):
        widths = [0.01, 0.01, 0.01, None, None, None]
        result = gp.sharpness_goalpost(widths)
        self.assertFalse(result["holds"])
        self.assertEqual(result["missing"], 3)


class StatisticTests(unittest.TestCase):
    def test_r_scores_exactly_zero(self):
        ratio, state, event, _ = _world()
        result = gp.stratified_gain(list(ratio), ratio, state, event)
        self.assertEqual(result.value, 0.0)

    def test_hand_computed_event_weighted_pooling(self):
        # Stratum 0: one event. E: event 1.0, others 2.0 and 0.0 -> AUROC 0.5. R: event 1.0, others 2.0 and 3.0 -> 1.0.
        # Stratum 1: two events. E: events 0.0 and 1.0, other 2.0 -> 1.0. R: events 0.5 and 0.6, other 0.4 -> 0.0.
        # gains -0.5 (weight 1) and 1.0 (weight 2): (-0.5 + 2.0) / 3.
        estimate = [1.0, 2.0, 0.0, 0.0, 1.0, 2.0]
        ratio = [1.0, 2.0, 3.0, 0.5, 0.6, 0.4]
        state = [0.0, 0.0, 0.0, 1.0, 1.0, 1.0]
        event = [1, 0, 0, 1, 1, 0]
        result = gp.stratified_gain(estimate, ratio, state, event)
        self.assertAlmostEqual(result.value, 0.5)
        self.assertEqual(result.strata, 2)
        self.assertEqual(result.events, 3)

    def test_a_stratum_without_an_event_or_without_another_day_is_dropped_and_counted(self):
        estimate = [1.0, 2.0, 0.0, 5.0, 6.0]
        ratio = [1.0, 2.0, 3.0, 5.0, 6.0]
        state = [0.0, 0.0, 0.0, 1.0, 2.0]
        event = [1, 0, 0, 0, 1]
        result = gp.stratified_gain(estimate, ratio, state, event)
        self.assertEqual(result.strata, 1)
        self.assertEqual(result.dropped, 2)

    def test_holding_s_fixed_removes_what_s_alone_carries(self):
        ratio, state, event, _ = _world()
        shifted = [r + 0.05 * s for r, s in zip(ratio, state)]  # a function of S added to R: no new information
        self.assertEqual(gp.stratified_gain(shifted, ratio, state, event).value, 0.0)
        self.assertNotEqual(gp.unstratified_gain(shifted, ratio, event), 0.0)

    def test_a_planted_signal_is_recovered(self):
        ratio, state, event, hidden = _world()
        informed = [r + 0.004 * h for r, h in zip(ratio, hidden)]
        self.assertGreater(gp.stratified_gain(informed, ratio, state, event).value, 0.02)

    def test_a_missing_estimate_takes_rs_place_and_cannot_gain(self):
        ratio, state, event, hidden = _world()
        informed = [r + 0.004 * h for r, h in zip(ratio, hidden)]
        full = gp.stratified_gain(informed, ratio, state, event).value
        none = gp.stratified_gain([None] * len(ratio), ratio, state, event)
        self.assertEqual(none.value, 0.0)
        half = [e if i % 2 else None for i, e in enumerate(informed)]
        self.assertLess(gp.stratified_gain(half, ratio, state, event).value, full)

    def test_input_lengths_must_agree(self):
        with self.assertRaises(ValueError):
            gp.stratified_gain([1.0], [1.0, 2.0], [0.0, 0.0], [1, 0])


class SyntheticEstimatorTests(unittest.TestCase):
    """Protocol §13 item 1."""

    def setUp(self):
        self.ratio, self.state, self.event, self.hidden = _world(n=300)

    def test_stable_and_sharp_passes_goalposts_1_and_2(self):
        self.assertTrue(gp.stability_goalpost({date(2024, 1, 2 + i % 20): 0.0003 for i in range(100)})["holds"])
        self.assertTrue(gp.sharpness_goalpost([0.015] * 100)["holds"])

    def test_a_jumpy_estimator_breaches_goalpost_1(self):
        gaps = {date(2024, 1, 2 + i % 20): 0.0003 for i in range(100)}
        gaps[date(2024, 2, 1)] = 0.0061
        self.assertFalse(gp.stability_goalpost(gaps)["holds"])

    def test_a_wide_estimator_fails_goalpost_2(self):
        self.assertFalse(gp.sharpness_goalpost([0.05] * 100)["holds"])

    def test_r_itself_scores_zero_and_its_upper_bound_kills_it(self):
        test = gp.information_test(list(self.ratio), self.ratio, self.state, self.event, look=2, seed=3, draws=2000,
                                  futility_level=0.05)
        self.assertEqual(test.point, 0.0)
        self.assertEqual(gp.verdict(test, look=2, goalposts_held=True, futility_level=0.05), scoring_protocol.KILLED)

    def test_planted_information_is_recovered_with_a_positive_lower_bound(self):
        informed = [r + 0.012 * h for r, h in zip(self.ratio, self.hidden)]
        test = gp.information_test(informed, self.ratio, self.state, self.event, look=2, seed=3, draws=2000)
        self.assertGreater(test.point, 0.05)
        self.assertGreater(test.lower, 0.0)


class BootstrapTests(unittest.TestCase):
    def test_each_vectorised_draw_equals_the_scalar_statistic_on_the_same_indices(self):
        ratio, state, event, hidden = _world(n=200)
        informed = [r + 0.012 * h for r, h in zip(ratio, hidden)]
        rng = random.Random(11)
        indices = [stationary_bootstrap_indices(len(ratio), gp.BLOCK_LENGTH, rng) for _ in range(25)]
        vector = gp.bootstrap_gains(informed, ratio, state, event, indices)
        for draw, idx in zip(vector, indices):
            scalar = gp.stratified_gain([informed[i] for i in idx], [ratio[i] for i in idx],
                                        [state[i] for i in idx], [event[i] for i in idx]).value
            self.assertAlmostEqual(float(draw), scalar, places=12)

    def test_the_nominal_levels_are_the_parents(self):
        self.assertEqual(gp.nominal_level(0), scoring_protocol.nominal_levels()[0])
        self.assertEqual(gp.nominal_level(2), scoring_protocol.nominal_levels()[2])

    def test_draws_follow_the_parents_ruling(self):
        self.assertEqual(gp.draws_for(0), scoring_protocol.INTERIM_DRAWS)
        self.assertEqual(gp.draws_for(1), scoring_protocol.INTERIM_DRAWS)
        self.assertEqual(gp.draws_for(2), scoring_protocol.DRAWS)

    def test_a_level_the_draws_cannot_resolve_is_refused(self):
        ratio, state, event, _ = _world(n=120)
        with self.assertRaises(scoring_protocol.UnresolvedLevel):
            gp.information_test(list(ratio), ratio, state, event, look=0, draws=1000, seed=1)

    def test_the_same_seed_gives_the_same_bound(self):
        ratio, state, event, hidden = _world(n=200)
        informed = [r + 0.012 * h for r, h in zip(ratio, hidden)]
        a = gp.information_test(informed, ratio, state, event, look=1, draws=2000, seed=5)
        b = gp.information_test(informed, ratio, state, event, look=1, draws=2000, seed=5)
        self.assertEqual((a.point, a.lower), (b.point, b.lower))


    def test_shared_indices_give_the_same_bound_as_the_seed_that_drew_them(self):
        ratio, state, event, hidden = _world(n=200)
        informed = [r + 0.012 * h for r, h in zip(ratio, hidden)]
        rng = random.Random(5)
        indices = [stationary_bootstrap_indices(len(ratio), gp.BLOCK_LENGTH, rng) for _ in range(2000)]
        a = gp.information_test(informed, ratio, state, event, look=1, draws=2000, seed=5)
        b = gp.information_test(informed, ratio, state, event, look=1, seed=0, indices=indices)
        self.assertEqual((a.point, a.lower, a.draws), (b.point, b.lower, b.draws))


class VerdictTests(unittest.TestCase):
    def _test(self, point, lower, upper=0.2, events=20, window_events=None):
        return gp.InformationTest(point=point, lower=lower, upper=upper, level=0.05, draws=10000, events=events,
                                  strata=3, dropped=0, window_events=events if window_events is None else window_events)

    def test_supported_needs_lower_above_zero_point_at_the_mme_and_ten_events(self):
        self.assertEqual(gp.verdict(self._test(0.06, 0.01), look=2, goalposts_held=True, futility_level=0.05),
                         scoring_protocol.SUPPORTED)
        self.assertNotEqual(gp.verdict(self._test(0.04, 0.01), look=2, goalposts_held=True, futility_level=0.05),
                            scoring_protocol.SUPPORTED)
        self.assertNotEqual(gp.verdict(self._test(0.06, 0.0), look=2, goalposts_held=True, futility_level=0.05),
                            scoring_protocol.SUPPORTED)
        self.assertNotEqual(gp.verdict(self._test(0.06, 0.01, events=9), look=2, goalposts_held=True,
                                       futility_level=0.05), scoring_protocol.SUPPORTED)

    def test_the_event_floor_counts_the_events_in_the_window_not_those_in_usable_strata(self):
        """Protocol §9 says "10 stress events logged" and `h7-g6.md` §4 says "events in the window" (finding #95)."""
        self.assertEqual(gp.verdict(self._test(0.06, 0.01, events=0, window_events=10), look=2, goalposts_held=True,
                                    futility_level=0.05), scoring_protocol.SUPPORTED)
        self.assertNotEqual(gp.verdict(self._test(0.06, 0.01, events=30, window_events=9), look=2, goalposts_held=True,
                                       futility_level=0.05), scoring_protocol.SUPPORTED)

    def test_killed_by_a_goalpost_failure_or_an_upper_bound_under_the_mme(self):
        self.assertEqual(gp.verdict(self._test(0.06, 0.01), look=2, goalposts_held=False, futility_level=0.05),
                         scoring_protocol.KILLED)
        self.assertEqual(gp.verdict(self._test(0.01, -0.02, upper=0.04), look=1, goalposts_held=True,
                                    futility_level=0.05), scoring_protocol.KILLED)

    def test_inconclusive_until_the_last_look_then_not_shown(self):
        test = self._test(0.03, -0.01, upper=0.08)
        self.assertEqual(gp.verdict(test, look=1, goalposts_held=True, futility_level=0.05),
                         scoring_protocol.INCONCLUSIVE)
        self.assertEqual(gp.verdict(test, look=2, goalposts_held=True, futility_level=0.05), scoring_protocol.NOT_SHOWN)

    def test_the_futility_level_has_no_default(self):
        with self.assertRaises(TypeError):
            gp.verdict(self._test(0.06, 0.01), look=2, goalposts_held=True)

    def test_an_upper_bound_is_required_to_judge_a_kill(self):
        with self.assertRaises(ValueError):
            gp.verdict(self._test(0.01, -0.02, upper=None), look=1, goalposts_held=True, futility_level=0.05)


class WindowEventTests(unittest.TestCase):
    def test_the_test_reports_the_window_events_beside_the_usable_ones(self):
        """The 60-day window from 2019-09-17 has 60 events in the window and 0 in usable strata (finding #95): its one
        stratum has no day without an event, so it is dropped. Both counts are reported, labelled."""
        n = 60
        result = gp.information_test([0.1] * n, [0.1] * n, [1.0] * n, [1] * n, look=2, seed=3, draws=200)
        self.assertEqual((result.window_events, result.events, result.strata, result.dropped), (60, 0, 0, 1))

    def test_the_two_counts_agree_when_every_stratum_is_usable(self):
        ratio, state, event, _ = _world(n=300)
        result = gp.information_test(ratio, ratio, state, event, look=2, seed=3, draws=200)
        self.assertEqual(result.window_events, sum(event))
        self.assertEqual(result.events, sum(event))


class MissingTests(unittest.TestCase):
    def test_more_than_five_percent_missing_voids_the_registration(self):
        self.assertTrue(gp.registration_void(missing=6, days=100))
        self.assertFalse(gp.registration_void(missing=5, days=100))

    def test_no_days_is_a_data_error(self):
        with self.assertRaises(ValueError):
            gp.registration_void(missing=0, days=0)


class PowerStudyTests(unittest.TestCase):
    def test_the_planting_is_calibrated_to_its_target(self):
        ratio, state, event, _ = _world()
        sigma = gp.sd(ratio)
        for target in (0.02, 0.05):
            c = gp.calibrate(target, ratio, state, event, sigma=sigma, seed=9)
            estimate = gp.plant(ratio, event, c, sigma=sigma, seed=9)
            self.assertAlmostEqual(gp.stratified_gain(estimate, ratio, state, event).value, target, delta=2e-4)

    def test_zero_target_plants_nothing_but_the_tie_breaking_noise(self):
        ratio, state, event, _ = _world()
        sigma = gp.sd(ratio)
        self.assertEqual(gp.calibrate(0.0, ratio, state, event, sigma=sigma, seed=9), 0.0)
        estimate = gp.plant(ratio, event, 0.0, sigma=sigma, seed=9)
        self.assertLess(max(abs(e - r) for e, r in zip(estimate, ratio)), 0.5 * sigma)

    def test_an_unreachable_target_is_reported_as_none(self):
        ratio, state, event, _ = _world()
        self.assertIsNone(gp.calibrate(0.9, ratio, state, event, sigma=gp.sd(ratio), seed=9))

    def test_a_target_the_data_cannot_meet_to_the_declared_tolerance_is_refused(self):
        """`h7-g6.md` §5: the calibration meets 1e-4 or refuses. Six events among 60 days move the statistic in steps of
        about 3e-3, so no shift lands within 1e-4 of 0.0137 and a midpoint of the last bracket (the old rule) was returned."""
        rng = random.Random(5)
        ratio = [0.1 + 0.001 * rng.random() for _ in range(60)]
        state = [0.0] * 60
        event = [1 if i % 10 == 3 else 0 for i in range(60)]
        with self.assertRaises(ValueError):
            gp.calibrate(0.0137, ratio, state, event, sigma=gp.sd(ratio), seed=4)

    def test_a_calibrated_gain_is_within_the_declared_tolerance(self):
        ratio, state, event, _ = _world()
        sigma = gp.sd(ratio)
        for target in (0.02, 0.035, 0.05, 0.065, 0.1):
            c = gp.calibrate(target, ratio, state, event, sigma=sigma, seed=9)
            realised = gp.stratified_gain(gp.plant(ratio, event, c, sigma=sigma, seed=9), ratio, state, event).value
            self.assertLessEqual(abs(realised - target), gp.CALIBRATION_TOLERANCE)

    def test_the_window_seed_is_the_declared_seed_plus_the_windows_first_index(self):
        self.assertEqual(gp.STUDY_SEED, 20261014)
        self.assertEqual(gp.window_seed(0), 20261014)
        self.assertEqual(gp.window_seed(40), 20261054)

    def test_power_is_a_wilson_interval_at_the_effective_number_of_windows(self):
        """Finding #95: 10 of 13 overlapping 250-day windows carry the information of 1.04 windows; the interval is 13%
        to 99% and the share beneath it is 10 of 13."""
        power = gp.power(10, 13, 250, 20)
        self.assertAlmostEqual(power.effective, 1.04)
        self.assertAlmostEqual(power.share, 10 / 13)
        self.assertAlmostEqual(power.low, 0.13, places=2)
        self.assertAlmostEqual(power.high, 0.99, places=2)

    def test_power_with_no_windows_is_a_data_error(self):
        with self.assertRaises(ValueError):
            gp.power(0, 0, 250, 20)

    def test_a_count_above_the_windows_is_a_data_error(self):
        with self.assertRaises(ValueError):
            gp.power(14, 13, 250, 20)

    def test_the_two_state_event_process_is_fitted_from_its_transitions(self):
        fit = gp.fit_event_process([0, 0, 1, 1, 1, 0, 1, 0])
        self.assertEqual((fit.start, fit.stay), (2 / 3, 1 / 2))
        self.assertEqual((fit.transitions_from_quiet, fit.transitions_from_event), (3, 4))
        self.assertAlmostEqual(fit.stationary, (2 / 3) / (1 - 1 / 2 + 2 / 3))

    def test_a_process_with_a_state_never_left_is_not_fitted(self):
        with self.assertRaises(ValueError):
            gp.fit_event_process([0, 0, 0, 0])
        with self.assertRaises(ValueError):
            gp.fit_event_process([1])

    def test_the_simulated_process_has_the_fitted_long_run_share_and_is_seeded(self):
        fit = gp.EventProcess(start=0.05, stay=0.8, transitions_from_quiet=100, transitions_from_event=100)
        a = gp.simulate_events(fit, 20000, random.Random(1))
        self.assertEqual(a, gp.simulate_events(fit, 20000, random.Random(1)))
        self.assertNotEqual(a, gp.simulate_events(fit, 20000, random.Random(2)))
        self.assertAlmostEqual(sum(a) / len(a), fit.stationary, delta=0.02)
        stays = sum(1 for x, y in zip(a, a[1:]) if x == 1 and y == 1) / sum(a[:-1])
        self.assertAlmostEqual(stays, 0.8, delta=0.03)

    def test_windows_start_every_step_and_fit_inside(self):
        self.assertEqual(gp.windows(100, 60, 20), [(0, 60), (20, 80), (40, 100)])
        self.assertEqual(gp.windows(59, 60, 20), [])

    def test_the_era_is_that_of_the_first_day(self):
        self.assertEqual(gp.era(date(2020, 12, 31)), "to 2020")
        self.assertEqual(gp.era(date(2021, 1, 4)), "2021-24")
        self.assertEqual(gp.era(date(2024, 12, 31)), "2021-24")
        self.assertEqual(gp.era(date(2025, 1, 2)), "2025 on")

    def test_wilson_interval(self):
        low, high = gp.wilson(0, 10)
        self.assertEqual(low, 0.0)
        self.assertAlmostEqual(high, 0.2775, places=3)
        low, high = gp.wilson(5, 10)
        self.assertAlmostEqual(low, 0.2366, places=3)
        self.assertAlmostEqual(high, 0.7634, places=3)

    def test_the_effective_count_shrinks_with_overlap(self):
        self.assertEqual(gp.effective_windows(70, 60, 20), 70 * 20 / 60)
        self.assertEqual(gp.effective_windows(70, 10, 20), 70)

    def test_days_to_the_event_floor(self):
        event = [0, 1, 0, 0, 1, 1, 0, 0, 0, 1]
        self.assertEqual(gp.days_to_events(event, 0, floor=3), 6)
        self.assertEqual(gp.days_to_events(event, 5, floor=3), None)


class ReaderTests(unittest.TestCase):
    """The days the study reads (`docs/stages/h7-g6.md` §2)."""

    @staticmethod
    def _days(*dates, ratio=0.12, state=1.0):
        from repo_liquidity.h7_estimator import Day

        return [Day(d, ratio, 0.0, state) for d in dates]

    def test_a_day_after_the_development_end_is_refused(self):
        """Recorded mutation (14 October 2026): in `goalposts.labelled_days`, replace
        `if late:` by `if False:`. A day on 2026-09-04 is then read; this test fails with
        `AssertionError: LookAheadError not raised`. (The parent's lockbox would also refuse a blind-tier day when
        `asof_days` builds it; this guard is the module's own, for days handed in from elsewhere.)"""
        days = self._days(date(2026, 9, 3), date(2026, 9, 4))
        with self.assertRaises(LookAheadError):
            gp.labelled_days(days, {date(2026, 9, 3): 0.0, date(2026, 9, 4): 0.0}, last_day=date(2026, 9, 3))

    def test_the_last_development_day_is_read(self):
        days = self._days(date(2025, 12, 30), date(2025, 12, 31))
        out = gp.labelled_days(days, {date(2025, 12, 30): 0.0, date(2025, 12, 31): 2.0})
        self.assertEqual([d.event for d in out.days], [0, 1])

    def test_the_event_is_an_accepted_amount_of_at_least_one_billion(self):
        """Recorded mutation (14 October 2026): in `goalposts.is_material_use`, replace `>=` by `>`. This test
        fails with `AssertionError: Lists differ: [0, 0, 1, 1] != [0, 1, 1, 1]`."""
        days = self._days(date(2020, 3, 2), date(2020, 3, 3), date(2020, 3, 4), date(2020, 3, 5))
        accepted = {date(2020, 3, 2): 0.999, date(2020, 3, 3): 1.0, date(2020, 3, 4): 1.0001, date(2020, 3, 5): 50.0}
        self.assertEqual([d.event for d in gp.labelled_days(days, accepted).days], [0, 1, 1, 1])

    def test_days_before_the_first_event_day_are_not_scored(self):
        days = self._days(date(2019, 9, 13), date(2019, 9, 16), date(2019, 9, 17))
        out = gp.labelled_days(days, {d.day: 0.0 for d in days})
        self.assertEqual([d.day for d in out.days], [date(2019, 9, 17)])

    def test_a_day_without_a_label_a_ratio_or_a_state_is_dropped_and_counted(self):
        from repo_liquidity.h7_estimator import Day

        days = [Day(date(2020, 3, 2), 0.12, 0.0, 1.0), Day(date(2020, 3, 3), 0.12, 0.0, 1.0),
                Day(date(2020, 3, 4), None, 0.0, 1.0), Day(date(2020, 3, 5), 0.12, 0.0, None)]
        accepted = {date(2020, 3, 2): 2.0, date(2020, 3, 4): 2.0, date(2020, 3, 5): 2.0}
        out = gp.labelled_days(days, accepted)
        self.assertEqual([d.day for d in out.days], [date(2020, 3, 2)])
        self.assertEqual(out.dropped, {"no label": 1, "no ratio": 1, "no state": 1})


if __name__ == "__main__":
    unittest.main()
