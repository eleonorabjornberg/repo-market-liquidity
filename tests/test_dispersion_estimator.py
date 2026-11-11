"""HX step 2, milestone M1 (#210): the as-of estimator W1 over SOFR's interquartile width. Nothing is scored.

W1 is H7m candidate A's kink with one change, the left side (`docs/research/dispersion-estimator.md`): the target day's
`sofr_p75_p25_bp` in place of its SOFR - IORB spread, fitted on calendar-clean days only. These tests cover the estimator's
mechanics on constructed inputs, its three guards, and the descriptive resolution fact. No goalpost is read.

Recorded mutations (11 November 2026; a disposable copy of the tree, CPython 3.11,
parent at the pin 2032de4, `PYTHONDONTWRITEBYTECODE=1`, the module edited by a one-line replacement, the suite module run
against the copy, the copy discarded):

1. `dispersion_estimator.SERVING_LAG = h7.SERVING_LAG` replaced by `SERVING_LAG = 1`. A refit then serves from the next
   business day, before the width of its last training day is public (one business day at 15:00 ET).
   `AvailabilityTests.test_the_serving_day_is_after_the_last_training_width_is_public` fails with
   `repo_model.splits.LookAheadError: sofr_p75_p25_bp of 2024-02-29 is not public when 2024-03-01 is decided`, raised by
   `check_width_public` (`test_the_second_business_day_is_the_first_that_may_serve` also fails, `AssertionError`).
2. `check_width_public`: `if read.row < last_row:` replaced by `if False:`. A width that is not yet public is no longer
   refused; `AvailabilityTests.test_a_serving_day_before_the_width_is_public_is_refused` fails with
   `AssertionError: LookAheadError not raised`.
3. `training_pairs`: `x.day <= cutoff` replaced by `x.day <= next_business_day(cutoff, 60)`. A refit then fits on days after
   its cutoff; `TrainingTests.test_training_pairs_stop_at_the_cutoff` fails with
   `AssertionError: datetime.date(2024, 6, 12) not less than or equal to datetime.date(2024, 3, 18)`
   (`TrainingTests.test_a_pair_after_the_cutoff_is_refused_by_the_fit` is unaffected: it hands the fit a late pair directly).
4. `check_in_force`: `if used < latest:` replaced by `if False:`. A refit older than the one in force is no longer refused;
   `CarryForwardTests.test_an_older_refit_than_the_one_in_force_is_stale` fails with
   `AssertionError: StaleReadError not raised`.
5. `training_pairs`: `if not flags[x.day].dropped():` replaced by `if True:` (every day kept). The calendar spike then moves
   the kink: `TrainingTests.test_calendar_days_do_not_move_the_kink` fails with
   `AssertionError: 0.1 != 0.12 within 3 places`, and `test_a_flag_that_is_a_hole_stops_the_fit` with
   `AssertionError: ValueError not raised`.

Written first, and watched failing: before `repo_liquidity.dispersion_estimator` existed this module did not import:
`ImportError: cannot import name 'dispersion_estimator' from 'repo_liquidity'`.
"""

from __future__ import annotations

import json
import pathlib
import tempfile
import unittest
from datetime import date, time

from repo_model.asof import InformationRule, StaleReadError
from repo_model.data import DailyObservation, next_business_day
from repo_model.splits import LookAheadError

from repo_liquidity import declaration, dispersion_estimator as w1, dispersion_volume, h7_clean, h7_estimator as h7

ROOT = pathlib.Path(__file__).resolve().parents[1]
RECORD = ROOT / "docs" / "research" / "hx-resolution.json"
REPLICATIONS = 30


def _days(start, count):
    out = [start]
    while len(out) < count:
        out.append(next_business_day(out[-1], 1))
    return out


def _pairs(count=500, kink=0.12, spike_every=0):
    """Days carrying a planted kink: width 1 bp at or above it and 6 bp per point of ratio below it. Every `spike_every`
    days at a ratio of 0.13 or more is a calendar day carrying a 40 bp width (the quarter-end spike a clean fit must not learn)."""

    days = _days(date(2023, 1, 4), count)
    out, flags = [], {}
    for index, day in enumerate(days):
        ratio = 0.09 + 0.001 * (index % 71)
        calendar = bool(spike_every) and ratio >= 0.13 and index % spike_every == 0
        width = 40.0 if calendar else 1.0 + 600.0 * max(0.0, kink - ratio) + 0.05 * (index % 3)
        out.append(w1.WidthDay(day, ratio, width))
        flags[day] = h7_clean.Flags(day, 1.0 if calendar else 0.0, 0.0)
    return out, flags


class FormTests(unittest.TestCase):
    def test_the_left_side_is_the_primary_measure_of_the_hypothesis(self):
        primary = [i.name for i in dispersion_volume.INPUTS if i.role == "primary"]
        self.assertEqual([w1.LEFT_COLUMN], primary)

    def test_it_serves_on_candidate_as_lag(self):
        self.assertEqual(w1.SERVING_LAG, h7.SERVING_LAG)

    def test_one_variant_is_added_to_the_count_carried(self):
        self.assertEqual(w1.VARIANTS_IN_PLAY, 13)
        self.assertEqual(w1.VARIANTS_IN_PLAY, w1.VARIANTS_CARRIED + 1)


class TrainingTests(unittest.TestCase):
    def test_training_pairs_stop_at_the_cutoff(self):
        days, flags = _pairs()
        cutoff = days[300].day
        pairs = w1.training_pairs(days, cutoff, flags)
        self.assertTrue(pairs)
        self.assertLessEqual(max(p.day for p in pairs), cutoff)
        self.assertEqual(len(pairs), 301)

    def test_a_day_with_no_width_or_no_ratio_is_not_a_pair(self):
        days, flags = _pairs(count=40)
        days[3] = days[3]._replace(width=None)
        days[4] = days[4]._replace(ratio=None)
        pairs = w1.training_pairs(days, days[-1].day, flags)
        self.assertEqual(len(pairs), 38)

    def test_a_planted_kink_is_recovered(self):
        days, flags = _pairs()
        fit = w1.refit(days, days[-1].day, flags, replications=0)
        self.assertTrue(fit.fitted)
        self.assertAlmostEqual(fit.level, 0.12, places=3)

    def test_calendar_days_do_not_move_the_kink(self):
        """The calendar days carry a 40 bp spike at high ratios. Fitted on every day the spike drags the kink away from the
        planted 0.12; fitted on the clean days it does not."""
        days, flags = _pairs(spike_every=2)
        everything = {d: f._replace(settlement_day=0.0) for d, f in flags.items()}
        spiked = w1.refit(days, days[-1].day, everything, replications=0)
        clean = w1.refit(days, days[-1].day, flags, replications=0)
        self.assertAlmostEqual(clean.level, 0.12, places=3)
        self.assertGreater(abs(spiked.level - 0.12), 0.003)

    def test_a_pair_after_the_cutoff_is_refused_by_the_fit(self):
        days, flags = _pairs(count=100)
        late = w1.WidthDay(next_business_day(days[-1].day, 5), 0.1, 3.0)
        with self.assertRaises(LookAheadError):
            w1.fit_pairs(w1.training_pairs(days, days[-1].day, flags) + [late], days[-1].day, replications=0)

    def test_the_estimate_is_the_ratio_less_the_kink_in_points(self):
        days, flags = _pairs()
        fit = w1.refit(days, days[-1].day, flags, replications=0)
        today = w1.WidthDay(date(2024, 6, 3), 0.15, None)
        estimate = w1.estimate(today, fit)
        self.assertAlmostEqual(h7.points(estimate.deployable), 100.0 * (0.15 - fit.level))

    def test_a_flag_that_is_a_hole_stops_the_fit(self):
        days, flags = _pairs(count=60)
        flags[days[5].day] = h7_clean.Flags(days[5].day, None, 0.0)
        with self.assertRaises(ValueError):
            w1.training_pairs(days, days[-1].day, flags)

    def test_a_window_across_the_2027_break_is_refused(self):
        days = _days(date(2027, 6, 1), 40)
        pairs = [w1.WidthDay(d, 0.1 + 0.001 * i, 5.0 + i % 4) for i, d in enumerate(days)]
        flags = {d: h7_clean.Flags(d, 0.0, 0.0) for d in days}
        with self.assertRaises(ValueError):
            w1.refit(pairs, days[-1], flags, replications=0)
        # a window wholly before it is read as usual
        w1.refit(pairs, date(2027, 6, 29), flags, replications=0)


class AvailabilityTests(unittest.TestCase):
    """The width of a refit's last training day is public (one business day, 15:00 ET) before the refit serves."""

    def setUp(self):
        self.dates = _days(date(2024, 1, 2), 80)
        context = declaration.phase3_declaration()
        context.__enter__()
        self.addCleanup(context.__exit__, None, None, None)
        self.rule = InformationRule(declaration.registry(), [w1.LEFT_COLUMN], decision_time=time(16, 0))

    def test_the_serving_day_is_after_the_last_training_width_is_public(self):
        """Recorded mutation 1 kills this one."""
        cutoff = self.dates[40]
        w1.check_width_public(self.dates, self.rule, cutoff, served=w1.served_from(cutoff))

    def test_a_serving_day_before_the_width_is_public_is_refused(self):
        """Recorded mutation 2 kills this one."""
        cutoff = self.dates[40]
        with self.assertRaises(LookAheadError):
            w1.check_width_public(self.dates, self.rule, cutoff, served=next_business_day(cutoff, 1))

    def test_the_second_business_day_is_the_first_that_may_serve(self):
        cutoff = self.dates[40]
        self.assertEqual(w1.served_from(cutoff), next_business_day(cutoff, 2))


class CarryForwardTests(unittest.TestCase):
    """A refit's kink is carried forward until the next refit serves; carrying an older one, or a later one, is refused."""

    def setUp(self):
        self.cutoffs = [date(2024, 1, 5), date(2024, 2, 2), date(2024, 3, 1)]

    def test_the_refit_in_force_is_the_latest_that_has_begun_to_serve(self):
        self.assertIsNone(w1.refit_in_force(self.cutoffs, date(2024, 1, 8)))
        self.assertEqual(w1.refit_in_force(self.cutoffs, date(2024, 1, 9)), self.cutoffs[0])
        self.assertEqual(w1.refit_in_force(self.cutoffs, date(2024, 2, 6)), self.cutoffs[1])

    def test_an_older_refit_than_the_one_in_force_is_stale(self):
        with self.assertRaises(StaleReadError):
            w1.check_in_force(self.cutoffs, self.cutoffs[0], date(2024, 2, 6))

    def test_a_refit_that_has_not_begun_to_serve_is_look_ahead(self):
        with self.assertRaises(LookAheadError):
            w1.check_in_force(self.cutoffs, self.cutoffs[1], date(2024, 1, 9))

    def test_the_refit_in_force_passes(self):
        w1.check_in_force(self.cutoffs, self.cutoffs[1], date(2024, 2, 6))


class ResolutionTests(unittest.TestCase):
    def test_distinct_values_and_the_modal_share(self):
        fact = w1.resolution([5.0, 5.0, 6.0, None, 8.0, 5.0])
        self.assertEqual(fact["days"], 5)
        self.assertEqual(fact["distinct"], 3)
        self.assertEqual(fact["modal_value"], 5.0)
        self.assertAlmostEqual(fact["modal_share"], 0.6)
        self.assertEqual(fact["missing"], 1)

    def test_a_locked_day_is_refused(self):
        w1.check_development([date(2026, 9, 3)])
        with self.assertRaises(LookAheadError):
            w1.check_development([date(2026, 9, 3), date(2026, 9, 4)])


class RecordTests(unittest.TestCase):
    """The committed resolution fact is what the panel gives. Descriptive only: no goalpost, no score."""

    @classmethod
    def setUpClass(cls):
        from repo_model.data import load_daily_panel

        from repo_liquidity import panel

        cls.tmp = tempfile.TemporaryDirectory()
        path = pathlib.Path(cls.tmp.name) / "phase3_panel.csv"
        panel.build(path, version=5)
        cls.rows = load_daily_panel(path)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_the_record_is_what_the_panel_gives(self):
        self.assertEqual(json.loads(RECORD.read_text(encoding="utf-8")), w1.resolution_record(self.rows))

    def test_the_record_scores_nothing(self):
        record = json.loads(RECORD.read_text(encoding="utf-8"))
        self.assertEqual(record["scored"], False)
        self.assertLessEqual(date.fromisoformat(record["last_day"]), date(2026, 9, 3))


if __name__ == "__main__":
    unittest.main()
