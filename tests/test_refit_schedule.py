"""H7m, groundwork: the refit-schedule analysis (`docs/research/h7-refit-schedule.md`, directive #161). Read-only: nothing is fitted.

`repo_liquidity.refit_schedule` takes, for each estimator, only what its training sample would be at a cutoff (which days, which
episodes or regimes count, whether the estimator's own input rule lets it fit) and compares candidate refit schedules on it. What is
covered, on synthetic days (the real inputs are read by `scripts/h7_refit_schedule.py`, which needs the branches of #150 and #154):

* `ServingTests` -- a refit serves from the second business day after its cutoff; a refit that serves no scored day (the final
  refit on the last row) is listed but does not count (her ruling of 21 October, addition 1).
* `CountingTests` -- distinct training samples and the refit-to-refit transitions in which the sample changes, counted over the
  serving refits only; a unit (episode, regime) enters only through a refit early enough to serve.
* `EntryTests`, `ScheduleTests` -- the entry date of a unit, the anchored grids (S2, S3r), the additive rules (S1, S3, S3f, S4, S5) and the
  dead refit (a regime under its floor).
* `ComparisonTests` -- what a candidate changes against a declared schedule: the refits added and removed, and the scored days
  whose serving refit changes.
* `NoFutureTests` -- a schedule built from the days up to a probe date is the full schedule's refits up to that date; a rule that
  looks ahead raises `LookAheadError`.

**Recorded mutation** (CLAUDE.md), 22 October 2026, CPython 3.11, the parent at the pin (08ff67e), in the working tree, applied by a
one-line replacement and the line restored afterwards:

1. `refit_schedule.entry_dates`: replace `estimator.sample_at(c)` by `estimator.sample_at(ctx.days[min(i + 5, len(ctx.days) - 1)])`
   (a unit enters five scored days before its count reaches the floor, a date chosen from rows not yet public). Seven tests failed.
   `NoFutureTests.test_every_rule_passes_when_it_reads_only_the_days_up_to_a_cutoff` raised
   `repo_model.splits.LookAheadError: the schedule S2 built from the days up to 2020-09-07 differs from the full schedule's refits up to it`
   from `check_schedule_no_future`; the other six (`EntryTests`, `ScheduleTests`, `ComparisonTests`) failed with `AssertionError`,
   and `ScheduleTests.test_s2_restarts_the_stride_at_the_entry_date` raised `ValueError` (`list.index`).
"""

import importlib.util
import json
import pathlib
import unittest
from datetime import date, timedelta
from typing import List

from repo_model.splits import LookAheadError

from repo_liquidity import refit_schedule as rs

ROOT = pathlib.Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("h7_refit_schedule", ROOT / "scripts" / "h7_refit_schedule.py")
script = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(script)


def weekdays(first: date, count: int) -> List[date]:
    out, day = [], first
    while len(out) < count:
        if day.weekday() < 5:
            out.append(day)
        day += timedelta(days=1)
    return out


def plus_two_weekdays(c: date) -> date:
    day, n = c, 2
    while n:
        day += timedelta(days=1)
        if day.weekday() < 5:
            n -= 1
    return day


DAYS = weekdays(date(2020, 1, 6), 260)
START = DAYS[20]


def episode_estimator(name, scarce, floor, window, always=()):
    """An estimator that trains on the scarce days up to the cutoff of each counted episode. The episode `window` counts once
    `floor` of its `scarce` days are on or before the cutoff; `always` episodes' days are included whatever the count."""
    first, last = window

    def sample_at(c):
        inside = tuple(d for d in scarce if first <= d <= min(c, last))
        counted = len(inside) >= floor
        units = frozenset({"episode:E2"} if counted else ())
        trained = tuple(always) + (inside if counted else ())
        return rs.Sample(trained, units, True, len(trained))

    return rs.Estimator(name, "C", ("episode:E2",), sample_at)


def context(estimators, days=DAYS, boundaries=(), every=21, dense=5):
    return rs.Context(days=tuple(days), start=START, serving_start=plus_two_weekdays, every=every,
                      boundaries=tuple(boundaries), estimators=tuple(estimators), dense=dense)


# E2 has its scarce days on the last 30 of the first 200 days; the floor is 10 of them.
SCARCE = tuple(DAYS[170:200])
ENTRY = DAYS[179]  # the 10th scarce day


def make(floor=10):
    return episode_estimator("E", SCARCE, floor, (DAYS[150], DAYS[259]), always=(DAYS[0],))


class ServingTests(unittest.TestCase):
    def test_a_refit_serves_from_the_second_business_day_after_its_cutoff(self):
        ctx = context([make()])
        served = dict(rs.served(ctx, [DAYS[40], DAYS[61]]))
        self.assertEqual(served[DAYS[40]][0], DAYS[42])
        self.assertEqual(served[DAYS[40]][-1], DAYS[62])  # up to the day before the next refit serves from (DAYS[63])
        self.assertEqual(served[DAYS[61]][0], DAYS[63])

    def test_a_refit_on_the_last_row_serves_no_scored_day_and_does_not_count(self):
        ctx = context([make()])
        cutoffs = [DAYS[40], DAYS[259]]
        served = dict(rs.served(ctx, cutoffs))
        self.assertEqual(served[DAYS[259]], ())
        result = rs.evaluate(ctx, make(), cutoffs)
        self.assertEqual((result["refits"], result["serving"]), (2, 1))
        self.assertEqual(result["not_serving"], [DAYS[259].isoformat()])

    def test_the_penultimate_row_serves_nothing_and_the_row_before_serves_the_last_day(self):
        ctx = context([make()])
        self.assertEqual(rs.served(ctx, [DAYS[258]])[0][1], ())
        self.assertEqual(rs.served(ctx, [DAYS[257]])[0][1], (DAYS[259],))

    def test_the_last_servable_cutoff_is_the_latest_that_serves_a_day(self):
        self.assertEqual(rs.last_servable(context([make()])), DAYS[257])


class CountingTests(unittest.TestCase):
    def test_a_constant_sample_is_one_fit_repeated(self):
        est = make(floor=10_000)  # the episode never counts
        ctx = context([est])
        cutoffs = rs.SCHEDULES["S0"].build(ctx).cutoffs
        result = rs.evaluate(ctx, est, cutoffs)
        self.assertEqual(result["distinct_samples"], 1)
        self.assertEqual(result["transitions_changed"], 0)

    def test_an_episode_that_counts_after_the_last_serving_refit_never_enters(self):
        est = make(floor=30)  # the 30th scarce day is DAYS[199]
        ctx = context([est], days=DAYS[:201])  # the window ends the day after it
        cutoffs = rs.SCHEDULES["S0"].build(ctx).cutoffs
        self.assertEqual(cutoffs[-1], DAYS[188])
        result = rs.evaluate(ctx, est, cutoffs)
        self.assertIsNone(result["units"]["episode:E2"]["first_serving_refit"])
        self.assertEqual(result["distinct_samples"], 1)

    def test_a_unit_enters_at_the_first_serving_refit_that_counts_it_and_the_sample_changes_there(self):
        est = make()
        ctx = context([est])
        cutoffs = rs.SCHEDULES["S0"].build(ctx).cutoffs
        result = rs.evaluate(ctx, est, cutoffs)
        first = next(c for c in cutoffs if c >= ENTRY)
        self.assertEqual(result["units"]["episode:E2"]["first_serving_refit"], first.isoformat())
        # the scarce days stop at DAYS[199]: the refits after it share one sample, so the sample changes at the first
        # refit on or after ENTRY, and again at the first on or after DAYS[199] if that is a different refit
        self.assertGreaterEqual(result["distinct_samples"], 2)
        self.assertEqual(result["transitions_changed"], result["distinct_samples"] - 1)

    def test_a_refit_that_cannot_fit_is_counted_apart(self):
        def sample_at(c):
            return rs.Sample((c,), frozenset(), c >= DAYS[100], 1)  # a new sample each refit; fits from DAYS[100]
        est = rs.Estimator("R", "A", (), sample_at)
        ctx = context([est])
        cutoffs = rs.SCHEDULES["S0"].build(ctx).cutoffs
        result = rs.evaluate(ctx, est, cutoffs)
        dead = [c for c in cutoffs if c < DAYS[100]]
        self.assertEqual(result["dead_serving"], len(dead))
        self.assertEqual(result["transitions_changed"], result["serving"] - 1)
        both = sum(1 for a, b in zip(cutoffs, cutoffs[1:]) if a >= DAYS[100] and b >= DAYS[100])
        self.assertEqual(result["transitions_fittable"], both)
        self.assertEqual(result["distinct_fittable"], len([c for c in cutoffs if c >= DAYS[100]]))


class EntryTests(unittest.TestCase):
    def test_the_entry_date_is_the_first_day_the_count_reaches_the_floor(self):
        ctx = context([make()])
        self.assertEqual(rs.entry_dates(ctx, make()), {"episode:E2": ENTRY})

    def test_a_unit_that_never_counts_has_no_entry(self):
        ctx = context([make(floor=10_000)])
        self.assertEqual(rs.entry_dates(ctx, make(floor=10_000)), {"episode:E2": None})


class ScheduleTests(unittest.TestCase):
    def setUp(self):
        self.est = make()
        self.ctx = context([self.est])

    def test_s0_is_a_stride_from_the_first_cutoff(self):
        cutoffs = rs.SCHEDULES["S0"].build(self.ctx).cutoffs
        self.assertEqual(cutoffs[0], START)
        self.assertEqual([DAYS.index(c) for c in cutoffs], list(range(20, 260, 21)))

    def test_s1_adds_the_last_row_and_s1b_the_last_servable_cutoff(self):
        s0 = rs.SCHEDULES["S0"].build(self.ctx).cutoffs
        s1 = rs.SCHEDULES["S1"].build(self.ctx)
        self.assertEqual(s1.cutoffs, tuple(sorted(set(s0) | {DAYS[259]})))
        self.assertEqual(s1.window_dependent, frozenset({DAYS[259]}))
        s1b = rs.SCHEDULES["S1b"].build(self.ctx)
        self.assertIn(DAYS[257], s1b.cutoffs)
        self.assertEqual(s1b.window_dependent, frozenset({DAYS[257]}))

    def test_s2_restarts_the_stride_at_the_entry_date(self):
        s2 = rs.SCHEDULES["S2"].build(self.ctx).cutoffs
        i = s2.index(ENTRY)
        self.assertEqual([DAYS.index(c) for c in s2[i:i + 3]], [DAYS.index(ENTRY) + 21 * m for m in range(3)])
        self.assertNotIn(DAYS[20 + 21 * 8], s2[i:])  # the old grid's date after the anchor is gone unless it coincides

    def test_s2_with_no_entry_is_s0(self):
        ctx = context([make(floor=10_000)])
        self.assertEqual(rs.SCHEDULES["S2"].build(ctx).cutoffs, rs.SCHEDULES["S0"].build(ctx).cutoffs)

    def test_s3_is_s0_plus_the_boundaries(self):
        ctx = context([self.est], boundaries=[DAYS[60], DAYS[130]])
        s0 = set(rs.SCHEDULES["S0"].build(ctx).cutoffs)
        self.assertEqual(set(rs.SCHEDULES["S3"].build(ctx).cutoffs), s0 | {DAYS[60], DAYS[130]})

    def test_s3r_restarts_the_stride_at_each_boundary(self):
        ctx = context([self.est], boundaries=[DAYS[60], DAYS[130]])
        s3 = rs.SCHEDULES["S3r"].build(ctx).cutoffs
        self.assertIn(DAYS[60], s3)
        self.assertIn(DAYS[130], s3)
        self.assertIn(DAYS[60 + 21], s3)
        self.assertNotIn(DAYS[20 + 21 * 3], s3)  # the old grid's DAYS[83] is gone: it is not 21 days after a boundary

    def test_a_boundary_at_or_before_the_start_is_the_start(self):
        ctx = context([self.est], boundaries=[DAYS[5], START])
        for rid in ("S3", "S3r"):
            self.assertEqual(rs.SCHEDULES[rid].build(ctx).cutoffs, rs.SCHEDULES["S0"].build(ctx).cutoffs)

    def test_s4_keeps_every_s0_refit_and_adds_the_entry(self):
        s0 = set(rs.SCHEDULES["S0"].build(self.ctx).cutoffs)
        s4 = set(rs.SCHEDULES["S4"].build(self.ctx).cutoffs)
        self.assertTrue(s0 <= s4)
        self.assertIn(ENTRY, s4)

    def test_s5_adds_a_short_cadence_after_each_entry(self):
        s5 = rs.SCHEDULES["S5"].build(self.ctx).cutoffs
        i = DAYS.index(ENTRY)
        for m in range(1, 5):
            self.assertIn(DAYS[i + 5 * m], s5)

    def test_s6_is_a_denser_stride(self):
        s6 = rs.SCHEDULES["S6"].build(self.ctx).cutoffs
        self.assertEqual([DAYS.index(c) for c in s6][:3], [20, 30, 40])

    def test_every_schedule_is_strictly_increasing_scored_days_from_the_start(self):
        for rule in rs.SCHEDULES.values():
            cutoffs = rule.build(context([self.est], boundaries=[DAYS[60]])).cutoffs
            self.assertEqual(list(cutoffs), sorted(set(cutoffs)), rule.id)
            self.assertGreaterEqual(cutoffs[0], START, rule.id)
            self.assertTrue(set(cutoffs) <= set(DAYS), rule.id)

    def test_a_regime_under_its_floor_makes_the_refit_dead_and_the_floor_date_is_the_entry(self):
        regime_start = DAYS[100]

        def sample_at(c):
            n = sum(1 for d in DAYS if regime_start <= d <= c)
            units = frozenset({"regime:1"} if n >= 50 else ())
            return rs.Sample((min(n, 50) if n else 0, c if n < 50 else "ok"), units, n == 0 or n >= 50, n)
        est = rs.Estimator("R", "A", ("regime:1",), sample_at)
        ctx = context([est], boundaries=[regime_start])
        floor_date = DAYS[149]
        self.assertEqual(rs.entry_dates(ctx, est)["regime:1"], floor_date)
        literal = rs.SCHEDULES["S3"].build(ctx).cutoffs  # at the boundary itself: 1 pair, dead
        result = rs.evaluate(ctx, est, literal)
        self.assertTrue(result["dead_serving"] >= 1)
        self.assertGreater(result["dead_days"], 0)
        self.assertEqual(len(rs.live_days(ctx, est, literal)), result["served_days"] - result["dead_days"])
        floored = rs.SCHEDULES["S3f"].build(ctx).cutoffs
        self.assertIn(floor_date, floored)
        self.assertEqual(rs.evaluate(ctx, est, floored)["units"]["regime:1"]["first_serving_refit"], floor_date.isoformat())


class ComparisonTests(unittest.TestCase):
    def test_an_additive_rule_keeps_every_declared_refit_and_changes_one_serving_window_per_insertion(self):
        ctx = context([make()])
        declared = rs.SCHEDULES["S0"].build(ctx).cutoffs
        s4 = rs.SCHEDULES["S4"].build(ctx).cutoffs
        diff = rs.compare_to_declared(ctx, s4, declared)
        self.assertEqual(diff["removed"], [])
        self.assertEqual(diff["added"], [ENTRY.isoformat()] if ENTRY not in declared else [])
        self.assertGreater(diff["days_with_a_new_serving_refit"], 0)

    def test_a_restarted_stride_changes_every_later_serving_refit(self):
        ctx = context([make()])
        declared = rs.SCHEDULES["S0"].build(ctx).cutoffs
        s2 = rs.SCHEDULES["S2"].build(ctx).cutoffs
        diff = rs.compare_to_declared(ctx, s2, declared)
        self.assertTrue(diff["removed"])
        later = [d for d in ctx.days if d >= plus_two_weekdays(ENTRY)]
        self.assertGreaterEqual(diff["days_with_a_new_serving_refit"], len(later) - 21)

    def test_the_same_schedule_changes_nothing(self):
        ctx = context([make()])
        declared = rs.SCHEDULES["S0"].build(ctx).cutoffs
        diff = rs.compare_to_declared(ctx, declared, declared)
        self.assertEqual((diff["added"], diff["removed"], diff["days_with_a_new_serving_refit"]), ([], [], 0))


class NoFutureTests(unittest.TestCase):
    def setUp(self):
        self.est = make()
        self.probes = DAYS[25:259:3]

    def make_context(self, prefix):
        return context([self.est], days=prefix, boundaries=[DAYS[60], DAYS[130]])

    def test_every_rule_passes_when_it_reads_only_the_days_up_to_a_cutoff(self):
        for rule in rs.SCHEDULES.values():
            rs.check_schedule_no_future(rule, self.make_context, DAYS, self.probes)

    def test_a_window_end_refit_is_the_declared_exception(self):
        self.assertTrue(rs.SCHEDULES["S1"].window_end_dependent)
        self.assertTrue(rs.SCHEDULES["S1b"].window_end_dependent)
        self.assertFalse(rs.SCHEDULES["S2"].window_end_dependent)

    def test_a_rule_that_looks_ahead_is_refused(self):
        def looks_ahead(ctx):
            # a rule that anchors at the entry of the unit read on the last day of the data: the full data count it earlier
            final = ctx.estimators[0].sample_at(ctx.days[-1]).units
            anchor = START + timedelta(days=7) if final else START
            idx = ctx.days.index(anchor) if anchor in ctx.days else 0
            return rs.Schedule(tuple(ctx.days[max(idx, 20)::21]), frozenset())
        bad = rs.Rule("X", "looks ahead", looks_ahead, False)
        with self.assertRaises(LookAheadError):
            rs.check_schedule_no_future(bad, self.make_context, DAYS, self.probes)


class ScriptTests(unittest.TestCase):
    """The script reads inputs and fits nothing; its page is printed from its record."""

    def synthetic(self):
        a = rs.Estimator("B", "A", (), lambda c: rs.Sample(c, frozenset(), True, 1))
        ctx = context([a, make()._replace(name="C")], boundaries=[DAYS[60]])
        inputs = {"pins": {"parent_commit": "p", "panel_sha256": "d"}, "input_code_sha256": {"x.py": "0" * 64},
                  "window": {"first_scored_day": "a", "last_scored_day": "b", "scored_days": len(DAYS), "first_cutoff": "c",
                             "refit_every": 21},
                  "regime_table": [], "regime_floor": 50, "kink_minimum_pairs": 20, "episodes": [], "episode_floor": 60}
        return ctx, inputs

    def test_the_analysis_runs_on_inputs_alone_and_the_page_prints_from_it(self):
        ctx, inputs = self.synthetic()
        record = script.analyse(ctx, inputs, probe_every=7)
        self.assertEqual(set(record["rules"]), {r.id for r in rs.RULES})
        self.assertEqual(record["tier"], "development")
        text = script.markdown(json.loads(json.dumps(record)))
        for heading in ("## Candidates", "## Distinct training samples", "## What each schedule changes"):
            self.assertIn(heading, text)

    def test_the_declared_schedules_are_a_s0_and_c_s1(self):
        self.assertEqual(script.DECLARED, {"A": "S0", "C": "S1"})

    def test_nothing_in_the_script_or_the_module_calls_a_fitter(self):
        for path in (ROOT / "scripts" / "h7_refit_schedule.py", ROOT / "src" / "repo_liquidity" / "refit_schedule.py"):
            text = path.read_text(encoding="utf-8")
            for name in ("real_time_path", "refit_on", "fit_kink", "fit_refit", "refit_c", "lad_curve", "fit_shares", "path_c", "baseline_path"):
                self.assertNotIn(name, text, f"{path.name} refers to {name}")

    def test_the_committed_page_is_the_committed_record_printed(self):
        output, page = script.OUTPUT, script.PAGE
        self.assertTrue(output.is_file() and page.is_file())
        self.assertEqual(page.read_text(encoding="utf-8"), script.markdown(json.loads(output.read_text(encoding="utf-8"))))

    def test_without_the_code_of_150_and_154_the_inputs_cannot_be_read(self):
        try:
            import repo_liquidity.h7_kink  # noqa: F401
            import repo_liquidity.h7_clean  # noqa: F401
        except ImportError:
            with self.assertRaises(ImportError):
                script.read_inputs()
            self.assertEqual(script.main(["--output", "/nonexistent/none.json"]), 2)


if __name__ == "__main__":
    unittest.main()
