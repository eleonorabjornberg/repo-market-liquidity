"""H7m, development step 5: the three goalposts on development days (`docs/stages/h7-step5.md`, directive #178).

Each estimator already declared and recorded gets its readings of goalposts 1 to 3, and R, S and R+S are scored on the same days,
with the splits beside every pooled figure. Nothing is a verdict. All inputs here are synthetic. What is covered:

* `AurocTests` -- the AUROC the module reports through the bootstrap machinery is `deployable.auc`, and the stratified one is the
  event-weighted mean of the levels' (R+S is R within an S level).
* `ReadingTests` -- R scores 0 against R, a planted signal gains against R, S and R+S, the gain against R+S is `goalposts.stratified_gain`
  and against R `goalposts.unstratified_gain`, a missing estimate takes R's place and cannot gain (protocol section 11), the gain against S
  is read on the days the estimator serves, and an interval is placed against the MME in words only.
* `AlignTests` -- a record's daily columns become shares (R's scale) and widths in points; a day it does not serve is missing; a served day
  outside the window is `ValueError`.
* `GuardTests` -- an estimate read for a day before its refit's serving day, or a window day after the development window, is
  `LookAheadError`.
* `SplitTests` -- the regimes and the pressure-day types each partition the window, the standing-facility split is the days from 2021.
* `WidthTests` -- a missing day counts as over the bar for the median, the median over the served days is beside it.
* `GoalpostOneTests` -- A's restated record is passed through as recorded, C's is "unreadable on development data" and never computed.
* `ScoreAllTests` -- an estimator that serves no day is "not scorable" with its reason and no gain, the others carry three readings on
  every split, the same seed gives the same record, and the record has no verdict key.

**Recorded mutation** (CLAUDE.md), 24 October 2026, in a disposable copy of the tree, CPython 3.11.17, the parent at the pin
(08ff67e), applied by a one-line replacement and confirmed by `grep`, the suite run against the copy, the copy discarded:

1. `check_cutoffs`: replace `if served < first:` by `if served < made:` (the refit's cutoff; an estimate may be read on any day after its refit's cutoff
   rather than from its serving day, two business days on). `GuardTests.test_an_estimate_before_its_serving_day_is_look_ahead` and
   `GuardTests.test_align_runs_the_cutoff_guard` fail with `AssertionError: LookAheadError not raised` (the day after the cutoff is
   accepted); the other 35 tests of the module pass.

Written first, and watched failing: before `repo_liquidity.h7_step5` existed the module did not import:
`ImportError: cannot import name 'h7_step5' from 'repo_liquidity'`.
"""

from __future__ import annotations

import json
import random
import unittest
from datetime import date, timedelta

from repo_model.data import next_business_day
from repo_model.splits import LookAheadError

from repo_liquidity import deployable
from repo_liquidity import goalposts as gp
from repo_liquidity import h7_step5 as s5


def _business_days(start, count):
    out = [start]
    while len(out) < count:
        out.append(next_business_day(out[-1], 1))
    return out


def _window(n=160, seed=3, plant=0.0):
    """A synthetic window: R with noise, an S level that tracks R, events that sit where R is low; `plant` lowers an estimate more."""
    rng = random.Random(seed)
    days = _business_days(date(2021, 1, 4), n)
    ratio = [0.12 + rng.gauss(0.0, 0.02) for _ in range(n)]
    state = [float(min(3, max(0, int((0.14 - r) / 0.015)))) for r in ratio]
    event = [int(rng.random() < 0.05 + 4.0 * max(0.0, 0.11 - r)) for r in ratio]
    return s5.Window(days, ratio, state, event)


def _planted(window, c, seed=5):
    rng = random.Random(seed)
    return [r + rng.gauss(0.0, 0.0005) - c * y for r, y in zip(window.ratio, window.event)]


def _indices(n, draws=200, seed=11):
    from repo_model.metrics import stationary_bootstrap_indices

    rng = random.Random(seed)
    return [stationary_bootstrap_indices(n, gp.BLOCK_LENGTH, rng) for _ in range(draws)]


class AurocTests(unittest.TestCase):
    def test_the_unstratified_auroc_is_deployable_auc(self):
        w = _window()
        got = s5.own_auroc(w.ratio, [0.0] * len(w.ratio), w.event, _indices(len(w.ratio), 20))
        self.assertAlmostEqual(got.point, deployable.auc(w.ratio, w.event), places=12)

    def test_the_stratified_auroc_is_the_event_weighted_mean_of_the_levels(self):
        w = _window()
        total = events = 0.0
        for level in sorted(set(w.state)):
            rows = [i for i, s in enumerate(w.state) if s == level]
            labels = [w.event[i] for i in rows]
            a = deployable.auc([w.ratio[i] for i in rows], labels)
            if a is not None:
                total += sum(labels) * a
                events += sum(labels)
        got = s5.own_auroc(w.ratio, w.state, w.event, _indices(len(w.ratio), 20))
        self.assertAlmostEqual(got.point, total / events, places=12)

    def test_a_single_class_has_no_auroc_and_reads_one_half(self):
        got = s5.own_auroc([0.1, 0.2, 0.3], [0.0, 0.0, 0.0], [0, 0, 0], _indices(3, 5))
        self.assertEqual(got.events, 0)
        self.assertEqual(got.point, 0.5)


class ReadingTests(unittest.TestCase):
    def test_r_against_r_is_zero_with_a_degenerate_interval(self):
        w = _window()
        r = s5.readings(w, list(w.ratio), _indices(len(w.ratio)))
        for name in ("vs_r", "vs_rs", "vs_s"):
            if name == "vs_s":
                continue
            self.assertEqual(r[name].point, 0.0, name)
            self.assertEqual((r[name].lower, r[name].upper), (0.0, 0.0), name)

    def test_a_planted_signal_gains_against_r_and_against_r_plus_s(self):
        w = _window()
        r = s5.readings(w, _planted(w, 0.03), _indices(len(w.ratio), 300))
        for name in ("vs_r", "vs_rs"):
            self.assertGreater(r[name].point, 0.05, name)
            self.assertGreater(r[name].lower, 0.0, name)

    def test_the_gain_against_r_plus_s_is_the_stratified_gain_and_against_r_the_unstratified(self):
        w = _window()
        est = _planted(w, 0.01)
        r = s5.readings(w, est, _indices(len(w.ratio), 10))
        self.assertAlmostEqual(r["vs_rs"].point, gp.stratified_gain(est, w.ratio, w.state, w.event).value, places=12)
        self.assertAlmostEqual(r["vs_r"].point, gp.unstratified_gain(est, w.ratio, w.event), places=12)

    def test_the_gain_against_s_is_read_on_the_served_days_with_s_ranked_high_is_stress(self):
        w = _window()
        est = _planted(w, 0.02)
        served = [i for i in range(len(est)) if i % 5 != 0]
        part = [None if i % 5 == 0 else e for i, e in enumerate(est)]
        r = s5.readings(w, part, _indices(len(w.ratio), 10), served_indices=_indices(len(served), 10))
        scores = [est[i] for i in served]
        want = deployable.auc(scores, [w.event[i] for i in served]) - deployable.auc([-w.state[i] for i in served],
                                                                                     [w.event[i] for i in served])
        self.assertAlmostEqual(r["vs_s"].point, want, places=12)

    def test_a_missing_estimate_takes_r_and_cannot_gain(self):
        w = _window()
        r = s5.readings(w, [None] * len(w.ratio), _indices(len(w.ratio), 10), served_indices=_indices(1, 10))
        self.assertEqual(r["vs_r"].point, 0.0)
        self.assertEqual(r["vs_rs"].point, 0.0)
        part = _planted(w, 0.03)
        for i in range(0, len(part), 3):
            part[i] = None
        filled = [w.ratio[i] if v is None else v for i, v in enumerate(part)]
        kept = sum(v is not None for v in part)
        a = s5.readings(w, part, _indices(len(w.ratio), 10), served_indices=_indices(kept, 10))
        b = s5.readings(w, filled, _indices(len(w.ratio), 10))
        self.assertEqual(a["vs_rs"].point, b["vs_rs"].point)
        self.assertEqual(a["vs_r"].point, b["vs_r"].point)
        with self.assertRaises(ValueError):
            s5.readings(w, part, _indices(len(w.ratio), 10))

    def test_the_interval_is_the_5th_and_95th_percentiles_of_the_resamples(self):
        w = _window()
        est = _planted(w, 0.02)
        idx = _indices(len(w.ratio), 400)
        r = s5.readings(w, est, idx)
        import numpy as np

        draws = gp.bootstrap_gains(est, w.ratio, w.state, w.event, idx)
        self.assertAlmostEqual(r["vs_rs"].lower, float(np.quantile(draws, 0.05)), places=12)
        self.assertAlmostEqual(r["vs_rs"].upper, float(np.quantile(draws, 0.95)), places=12)

    def test_position_against_the_mme_is_in_words_and_never_a_pass(self):
        mk = lambda lo, hi: s5.Reading(0.0, lo, hi, 10, 4, 0)  # noqa: E731
        self.assertEqual(s5.position(mk(-0.2, 0.04)), "below the MME")
        self.assertEqual(s5.position(mk(0.05, 0.2)), "at or above the MME")
        self.assertEqual(s5.position(mk(-0.1, 0.2)), "straddles the MME")
        self.assertEqual(s5.position(mk(0.01, 0.2)), "straddles the MME")


class AlignTests(unittest.TestCase):
    def setUp(self):
        self.days = _business_days(date(2022, 3, 1), 12)

    def _daily(self, served, cutoff=None):
        cutoff = cutoff or self.days[0] - timedelta(days=10)
        return {"days": [d.isoformat() for d in served], "cutoff": [cutoff.isoformat()] * len(served),
                "as_observed": {"aggregate": [round(2.0 + i * 0.5, 4) for i in range(len(served))],
                                "lower": [round(1.0 + i * 0.5, 4) for i in range(len(served))],
                                "upper": [round(4.5 + i * 0.5, 4) for i in range(len(served))]},
                "missing": {}}

    def test_points_become_shares_and_a_width_is_upper_minus_lower_in_points(self):
        got = s5.align(self._daily(self.days[2:6]), self.days)
        self.assertEqual(got.estimate[:2], [None, None])
        self.assertAlmostEqual(got.estimate[2], 0.02)
        self.assertAlmostEqual(got.estimate[3], 0.025)
        self.assertAlmostEqual(got.width[2], 3.5)
        self.assertEqual(got.served, [2, 3, 4, 5])
        self.assertEqual(got.estimate[6:], [None] * 6)

    def test_a_record_with_no_served_day_is_all_missing(self):
        got = s5.align(self._daily([]), self.days)
        self.assertEqual(got.served, [])
        self.assertEqual(set(got.estimate), {None})

    def test_a_served_day_outside_the_window_is_value_error(self):
        with self.assertRaises(ValueError):
            outside = self.days[0] - timedelta(days=30)
            s5.align(self._daily([outside], cutoff=outside - timedelta(days=20)), self.days)

    def test_an_interval_missing_on_a_served_day_is_a_missing_width(self):
        daily = self._daily(self.days[:2])
        daily["as_observed"]["lower"][1] = None
        daily["as_observed"]["upper"][1] = None
        got = s5.align(daily, self.days)
        self.assertIsNone(got.width[1])
        self.assertIsNotNone(got.estimate[1])


class GuardTests(unittest.TestCase):
    def test_an_estimate_before_its_serving_day_is_look_ahead(self):
        cutoff = date(2022, 3, 1)
        first = next_business_day(cutoff, s5.SERVING_LAG)
        s5.check_cutoffs({"days": [first.isoformat()], "cutoff": [cutoff.isoformat()]})
        early = next_business_day(cutoff, 1)
        with self.assertRaises(LookAheadError):
            s5.check_cutoffs({"days": [early.isoformat()], "cutoff": [cutoff.isoformat()]})
        with self.assertRaises(LookAheadError):
            s5.check_cutoffs({"days": [cutoff.isoformat()], "cutoff": [cutoff.isoformat()]})

    def test_align_runs_the_cutoff_guard(self):
        days = _business_days(date(2022, 3, 1), 5)
        daily = {"days": [days[1].isoformat()], "cutoff": [days[0].isoformat()],
                 "as_observed": {"aggregate": [1.0], "lower": [0.5], "upper": [1.5]}, "missing": {}}
        with self.assertRaises(LookAheadError):
            s5.align(daily, days)

    def test_a_window_day_after_the_development_window_is_look_ahead(self):
        s5.check_window([date(2025, 12, 31)], last_day=date(2025, 12, 31))
        with self.assertRaises(LookAheadError):
            s5.check_window([date(2025, 12, 31), date(2026, 1, 2)], last_day=date(2025, 12, 31))

    def test_a_locked_day_is_refused(self):
        with self.assertRaises(LookAheadError):
            s5.check_window([date(2026, 9, 4)], last_day=date(2026, 12, 31))


class SplitTests(unittest.TestCase):
    def setUp(self):
        self.days = [date(2020, 4, 1), date(2020, 12, 30), date(2021, 1, 4), date(2023, 6, 1), date(2024, 5, 1), date(2025, 12, 31)]
        self.regimes = ["2020", "2020", "2021-23", "2021-23", "2024", "2025-26"]
        self.types = ["ordinary", "quarter_end", "tax_date", "month_end", "ordinary", "quarter_end"]

    def test_each_kind_partitions_the_window(self):
        got = s5.splits(self.days, self.regimes, self.types)
        for kind in ("regime", "day_type"):
            positions = sorted(i for (k, _label), idx in got.items() if k == kind for i in idx)
            self.assertEqual(positions, list(range(len(self.days))), kind)
        self.assertEqual(got[("all", "all")], list(range(len(self.days))))

    def test_the_standing_facility_split_is_the_days_from_2021(self):
        got = s5.splits(self.days, self.regimes, self.types)
        self.assertEqual(got[("era", "2021 on")], [2, 3, 4, 5])

    def test_the_order_is_pooled_first_then_regimes_then_types_then_the_era(self):
        kinds = [k for k, _ in s5.splits(self.days, self.regimes, self.types)]
        self.assertEqual(kinds[0], "all")
        self.assertEqual(kinds, sorted(kinds, key=["all", "regime", "day_type", "era"].index))

    def test_a_length_mismatch_is_value_error(self):
        with self.assertRaises(ValueError):
            s5.splits(self.days, self.regimes[:-1], self.types)


class WidthTests(unittest.TestCase):
    def test_a_missing_day_counts_as_over_the_bar_and_the_served_median_is_beside_it(self):
        got = s5.width_reading([2.0, 2.0, None, None, None])
        self.assertEqual(got["days"], 5)
        self.assertEqual(got["missing"], 3)
        self.assertEqual(got["served_median_points"], 2.0)
        self.assertIsNone(got["median_points"])
        self.assertEqual(got["position"], "not under the bar")
        self.assertEqual(got["served_position"], "under the bar")

    def test_an_estimator_that_is_sharp_on_every_day_is_under_the_bar(self):
        got = s5.width_reading([2.0, 2.9, 1.0])
        self.assertEqual(got["median_points"], 2.0)
        self.assertEqual(got["position"], "under the bar")

    def test_the_bar_is_strict(self):
        self.assertEqual(s5.width_reading([3.0, 3.0])["position"], "not under the bar")

    def test_no_served_day_has_no_served_median(self):
        got = s5.width_reading([None, None])
        self.assertIsNone(got["served_median_points"])
        self.assertIsNone(got["served_position"])


class GoalpostOneTests(unittest.TestCase):
    def test_a_is_the_restated_record_as_recorded(self):
        recorded = {"breaches_note": "not recomputable", "days_compared": 1300, "holds": False, "limit": 0.5, "missing_refits": 4,
                    "worst": {"day": "2022-11-22", "gap": 3.5}}
        got = s5.goalpost_one_a(recorded)
        self.assertEqual(got["reading"], "as in A's restated record (results/h7/kink.json)")
        self.assertEqual(got["recorded"], recorded)

    def test_c_is_unreadable_on_development_data_and_carries_no_number(self):
        got = s5.goalpost_one_c()
        self.assertIn("unreadable on development data, read prospectively", got["reading"])
        self.assertEqual(set(got), {"reading"})


class ScoreAllTests(unittest.TestCase):
    def _estimates(self, w):
        n = len(w.ratio)
        full = s5.Estimates(_planted(w, 0.03), [2.0] * n, list(range(n)))
        part_est = [None if i % 4 == 0 else e for i, e in enumerate(_planted(w, 0.01, seed=9))]
        part = s5.Estimates(part_est, [None if e is None else 3.5 for e in part_est], [i for i, e in enumerate(part_est) if e is not None])
        none = s5.Estimates([None] * n, [None] * n, [])
        return {"X": full, "Y": part, "Z": none}

    def _run(self, draws=40):
        w = _window(220)
        regimes = ["2021-23" if d.year < 2022 else "2024" for d in w.days]
        types = [("quarter_end" if i % 30 == 0 else "ordinary") for i in range(len(w.days))]
        out = s5.score_all(w, regimes, types, self._estimates(w), draws=draws, seed=7,
                           reasons={"Z": "the refit in force did not fit at 69 of 70 refits"})
        return w, out

    def test_an_estimator_that_serves_no_day_is_not_scorable_with_its_reason_and_no_gain(self):
        _w, out = self._run()
        z = out["estimators"]["Z"]
        self.assertEqual(z["status"], "not scorable")
        self.assertEqual(z["reason"], "the refit in force did not fit at 69 of 70 refits")
        self.assertNotIn("goalpost_3", z)

    def test_a_scorable_estimator_has_three_readings_on_every_split(self):
        w, out = self._run()
        for name in ("X", "Y"):
            e = out["estimators"][name]
            self.assertEqual(e["status"], "scored")
            self.assertEqual(set(e["goalpost_3"]), {"vs_r", "vs_s", "vs_rs"})
            labels = list(out["splits"])
            for kind in ("vs_r", "vs_s", "vs_rs"):
                self.assertEqual(list(e["goalpost_3"][kind]), labels, (name, kind))
                for row in e["goalpost_3"][kind].values():
                    self.assertIn(row["position"], ("below the MME", "at or above the MME", "straddles the MME"))

    def test_r_s_and_r_plus_s_are_scored_on_the_same_days_with_every_split(self):
        w, out = self._run()
        self.assertEqual(set(out["benchmarks"]), {"R", "S", "R+S"})
        for name, rows in out["benchmarks"].items():
            self.assertEqual(list(rows), list(out["splits"]), name)
        pooled = out["splits"]["all: all"]
        self.assertEqual(pooled["days"], len(w.days))
        self.assertEqual(pooled["events"], sum(w.event))
        self.assertAlmostEqual(out["benchmarks"]["R"]["all: all"]["point"], deployable.auc(w.ratio, w.event), places=12)
        self.assertAlmostEqual(out["benchmarks"]["S"]["all: all"]["point"], deployable.auc([-s for s in w.state], w.event), places=12)

    def test_a_split_under_the_event_floor_is_labelled_not_dropped(self):
        _w, out = self._run()
        for label, row in out["splits"].items():
            self.assertEqual(row["under_event_floor"], row["events"] < gp.EVENT_FLOOR, label)
        self.assertTrue(any(row["under_event_floor"] for row in out["splits"].values()))

    def test_the_same_seed_gives_the_same_record_and_a_different_seed_other_intervals(self):
        w = _window(220)
        regimes = ["2021-23"] * len(w.days)
        types = ["ordinary"] * len(w.days)
        est = self._estimates(w)
        a = s5.score_all(w, regimes, types, est, draws=60, seed=7, reasons={})
        b = s5.score_all(w, regimes, types, est, draws=60, seed=7, reasons={})
        c = s5.score_all(w, regimes, types, est, draws=60, seed=8, reasons={})
        self.assertEqual(json.dumps(a, sort_keys=True), json.dumps(b, sort_keys=True))
        self.assertNotEqual(a["estimators"]["X"]["goalpost_3"]["vs_rs"]["all: all"]["lower"],
                            c["estimators"]["X"]["goalpost_3"]["vs_rs"]["all: all"]["lower"])
        self.assertEqual(a["estimators"]["X"]["goalpost_3"]["vs_rs"]["all: all"]["point"],
                         c["estimators"]["X"]["goalpost_3"]["vs_rs"]["all: all"]["point"])

    def test_goalpost_two_is_beside_every_split(self):
        _w, out = self._run()
        for name in ("X", "Y"):
            self.assertEqual(list(out["estimators"][name]["goalpost_2"]), list(out["splits"]))
        self.assertEqual(out["estimators"]["Y"]["goalpost_2"]["all: all"]["missing"], 55)

    def test_missing_share_is_reported_and_not_applied(self):
        _w, out = self._run()
        self.assertAlmostEqual(out["estimators"]["Y"]["missing_share"], 55 / 220)
        self.assertEqual(out["estimators"]["X"]["missing_share"], 0.0)

    def test_the_record_gives_no_verdict(self):
        _w, out = self._run()
        text = json.dumps(out).lower()
        for word in ("verdict", "supported", "killed", "\"pass\"", "\"fail\"", "eligible"):
            self.assertNotIn(word, text)


class TimingTests(unittest.TestCase):
    def test_a_synthetic_window_of_the_real_size_has_its_events(self):
        w = s5.synthetic_window(1447, 98, seed=1)
        self.assertEqual(len(w.ratio), 1447)
        self.assertEqual(sum(w.event), 98)
        self.assertEqual(len(set(w.state)), 4)


if __name__ == "__main__":
    unittest.main()
