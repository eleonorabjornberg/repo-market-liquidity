"""Stage 3b: the buffer on a fixed curve (`docs/stages/stage-3b.md`)."""

import math
import random
import unittest
from datetime import date, timedelta

from repo_model.splits import LookAheadError

from repo_liquidity import anchored, latent

ANCHOR = anchored.Anchor(intercept=1.0, slope=120.0, last_day=date(2019, 1, 1))


def simulate(n=500, jump_at=None, jump=0.02, seed=5):
    jump_at = n // 2 if jump_at is None else jump_at
    rng = random.Random(seed)
    day = date(2019, 1, 1)
    obs, truth, b = [], [], 0.11
    for t in range(n):
        while day.weekday() >= 5:
            day += timedelta(days=1)
        b += rng.gauss(0, 0.0003) + (jump if t == jump_at else 0.0)
        x = 0.12 + 0.03 * math.sin(t / 60.0) + rng.gauss(0, 0.003)
        kind = "quarter_end" if t % 63 == 62 else "month_end" if t % 21 == 20 else "ordinary"
        bump = 2.0 if kind == "quarter_end" else 0.0
        g = latent.softplus(b - x, latent.SCALE)
        y = (ANCHOR.intercept + ANCHOR.slope * g + 0.1 * bump + rng.gauss(0, 0.15),
             2.0 + 300 * g + bump + rng.gauss(0, 1.0))
        obs.append(anchored.Observation(day, x, y, kind))
        truth.append(b)
        day += timedelta(days=1)
    return obs, truth, obs[jump_at].day


class FilterTests(unittest.TestCase):
    def test_the_filter_tracks_a_known_buffer_through_a_jump(self):
        obs, truth, jump_day = simulate()
        fit = anchored.fit(obs, anchor=ANCHOR, jump_days=[jump_day], cutoff=obs[-1].day)
        path = anchored.filter_path(obs, fit.params, anchor=ANCHOR, jump_days=[jump_day])
        errors = [abs(p.mean - b) for p, b in zip(path[150:], truth[150:])]
        self.assertLess(sum(errors) / len(errors), 0.005)
        before = sum(p.mean for p in path[200:250]) / 50
        after = sum(p.mean for p in path[300:350]) / 50
        self.assertGreater(after - before, 0.01)

    def test_the_buffer_stays_between_0_and_its_maximum(self):
        obs, _, jump_day = simulate(n=200)
        wild = [anchored.Observation(o.day, o.x, (50.0 if i % 2 else -50.0, o.y[1]), o.kind)
                for i, o in enumerate(obs)]
        path = anchored.filter_path(wild, anchored.start_params(wild, ANCHOR), anchor=ANCHOR, jump_days=[jump_day])
        self.assertTrue(all(0.0 < p.mean < anchored.BUFFER_MAX for p in path))

    def test_the_corridor_curve_is_not_estimated(self):
        obs, _, jump_day = simulate(n=200)
        fit = anchored.fit(obs, anchor=ANCHOR, jump_days=[jump_day], cutoff=obs[-1].day, maxiter=50)
        self.assertNotIn("a_corridor_position", anchored.PARAM_NAMES)
        self.assertNotIn("b_corridor_position", anchored.PARAM_NAMES)
        self.assertEqual(len(fit.params), len(anchored.PARAM_NAMES))

    def test_a_point_that_overflows_scores_as_impossible(self):
        obs, _, jump_day = simulate(n=60)
        params = list(anchored.start_params(obs, ANCHOR))
        params[anchored.PARAM_NAMES.index("b_sofr_dispersion_bp")] = 1e6
        self.assertEqual(anchored.objective(obs, params, anchor=ANCHOR, jump_days=[jump_day]), anchored.IMPOSSIBLE)

    def test_held_parameters_stay_where_they_are_held(self):
        obs, _, jump_day = simulate(n=200)
        held = {anchored.PARAM_NAMES.index("drift_sd"): anchored.HELD_OFF}
        fit = anchored.fit(obs, anchor=ANCHOR, jump_days=[jump_day], cutoff=obs[-1].day, held=held, maxiter=50)
        self.assertEqual(fit.params[anchored.PARAM_NAMES.index("drift_sd")], anchored.HELD_OFF)
        self.assertLess(anchored.natural(fit.params)[1], 1e-12)


class AnchorTests(unittest.TestCase):
    def test_the_anchor_is_stage_2s_2018_to_march_2020_curve(self):
        anchor, digest = anchored.load_anchor()
        self.assertEqual((anchor.intercept, anchor.slope), (1.057938, 133.2055))
        self.assertEqual(anchor.last_day, date(2020, 3, 13))
        self.assertEqual(len(digest), 64)


class AnchorFromTests(unittest.TestCase):
    def test_the_broken_stick_curve_is_recovered_from_its_training_days(self):
        rng = random.Random(11)
        day, obs = date(2018, 4, 17), []
        for t in range(400):
            while day.weekday() >= 5:
                day += timedelta(days=1)
            x = 0.07 + 0.06 * rng.random()
            y = 1.05 + 130.0 * max(0.092 - x, 0.0) + rng.gauss(0, 0.02)
            obs.append(anchored.Observation(day, x, (y, None), "ordinary"))
            day += timedelta(days=1)
        last = obs[299].day
        anchor = anchored.anchor_from(obs, last)
        self.assertEqual(anchor.last_day, last)
        self.assertAlmostEqual(anchor.intercept, 1.05, delta=0.02)
        self.assertAlmostEqual(anchor.slope, 130.0, delta=10.0)

    def test_only_sofr_or_tgcr_can_be_read_as_the_corridor(self):
        with self.assertRaises(ValueError):
            anchored.assemble([], rate="bgcr")


class CalendarTests(unittest.TestCase):
    def test_a_days_type_follows_the_parents_declaration(self):
        declaration = anchored.split_declaration()
        quarter = {"quarter_end": 1.0, "tax_date": 0.0, "days_to_month_end": 0.0}
        month = {"quarter_end": 0.0, "tax_date": 0.0, "days_to_month_end": 1.0}
        tax = {"quarter_end": 0.0, "tax_date": 1.0, "days_to_month_end": 10.0}
        plain = {"quarter_end": 0.0, "tax_date": 0.0, "days_to_month_end": 10.0}
        self.assertEqual([declaration.day_type(v) for v in (quarter, month, tax, plain)],
                         ["quarter_end", "month_end", "tax_date", "ordinary"])


class GuardTests(unittest.TestCase):
    def test_a_refit_before_the_curves_last_day_is_refused(self):
        """Leakage guard: the fixed curve uses data to its last day, so no refit may be dated earlier.

        Recorded mutation (6 October 2026): replacing `if cutoff < anchor.last_day:` in
        `anchored.require_anchor_before` with `if False:` makes this test fail with
        AssertionError: LookAheadError not raised.
        """
        obs, _, jump_day = simulate(n=60)
        late = anchored.Anchor(ANCHOR.intercept, ANCHOR.slope, last_day=obs[-1].day + timedelta(days=1))
        with self.assertRaises(LookAheadError):
            anchored.fit(obs, anchor=late, jump_days=[jump_day], cutoff=obs[-1].day)

    def test_a_fit_given_an_observation_after_its_cutoff_is_refused(self):
        """Leakage guard reused from Stage 3 (`latent.require_before`, whose mutation is recorded there)."""
        obs, _, jump_day = simulate(n=60)
        with self.assertRaises(LookAheadError):
            anchored.fit(obs, anchor=ANCHOR, jump_days=[jump_day], cutoff=obs[30].day)


class MultiStartTests(unittest.TestCase):
    def test_the_start_grid_sets_each_declared_initial_buffer(self):
        obs, _, _ = simulate(n=200)
        starts = anchored.start_grid(obs, ANCHOR)
        buffers = sorted(round(anchored.natural(s)[0], 6) for s in starts[1:])
        self.assertEqual(buffers, list(anchored.START_BUFFERS))
        self.assertEqual(starts[0], anchored.start_params(obs, ANCHOR))

    def test_the_best_start_is_kept_and_every_start_is_reported(self):
        obs, _, jump_day = simulate(n=200)
        best, tried = anchored.fit_best(obs, anchor=ANCHOR, jump_days=[jump_day], cutoff=obs[-1].day, maxiter=40)
        self.assertEqual(len(tried), 1 + len(anchored.START_BUFFERS))
        self.assertEqual(best.loglike, max(fit.loglike for _, fit in tried))

    def test_a_previous_answer_is_tried_first(self):
        obs, _, jump_day = simulate(n=200)
        previous = anchored.start_params(obs, ANCHOR)
        _, tried = anchored.fit_best(obs, anchor=ANCHOR, jump_days=[jump_day], cutoff=obs[-1].day, maxiter=40,
                                     previous=previous)
        self.assertEqual(tried[0][0], "previous")
        self.assertEqual(len(tried), 2 + len(anchored.START_BUFFERS))


if __name__ == "__main__":
    unittest.main()
