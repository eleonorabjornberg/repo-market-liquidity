"""Stage 3: the latent buffer, filtered by an extended Kalman filter (`docs/stages/stage-3.md`)."""

import math
import random
import unittest
from datetime import date, timedelta

from repo_model.splits import LookAheadError

from repo_liquidity import latent


def simulate(n=500, jump_at=None, jump=0.02, seed=3):
    jump_at = n // 2 if jump_at is None else jump_at
    rng = random.Random(seed)
    day = date(2019, 1, 1)
    obs, truth, b = [], [], 0.11
    for t in range(n):
        while day.weekday() >= 5:
            day += timedelta(days=1)
        b += rng.gauss(0, 0.0003) + (jump if t == jump_at else 0.0)
        x = 0.12 + 0.03 * math.sin(t / 60.0) + rng.gauss(0, 0.003)
        g = latent.softplus(b - x, latent.SCALE)
        y = (0.4 + 60 * g + rng.gauss(0, 0.15),
             2.0 + 300 * g + rng.gauss(0, 1.0),
             3.0 + 40 * (x - b) + rng.gauss(0, 0.3),
             None if t < 100 else 0.1 + 80 * g + rng.gauss(0, 0.3))
        obs.append(latent.Observation(day, x, y))
        truth.append(b)
        day += timedelta(days=1)
    return obs, truth, obs[jump_at].day


class FilterTests(unittest.TestCase):
    def test_the_filter_tracks_a_known_buffer_through_a_jump(self):
        obs, truth, jump_day = simulate()
        fit = latent.fit(obs, jump_days=[jump_day], cutoff=obs[-1].day)
        path = latent.filter_path(obs, fit.params, jump_days=[jump_day])
        errors = [abs(p.mean - b) for p, b in zip(path[150:], truth[150:])]
        self.assertLess(sum(errors) / len(errors), 0.005)
        before = sum(p.mean for p in path[200:250]) / 50
        after = sum(p.mean for p in path[300:350]) / 50
        self.assertGreater(after - before, 0.01)

    def test_a_missing_observation_is_skipped_not_filled(self):
        obs, _, jump_day = simulate(n=120)
        params = latent.start_params(obs)
        with_missing = latent.filter_path(obs, params, jump_days=[jump_day])
        self.assertTrue(all(o.y[3] is None for o in obs[:100]))
        self.assertEqual(len(with_missing), len(obs))

    def test_softplus_is_stable_and_smooth(self):
        self.assertAlmostEqual(latent.softplus(0.0, 0.005), 0.005 * math.log(2))
        self.assertAlmostEqual(latent.softplus(1.0, 0.005), 1.0)
        self.assertEqual(latent.softplus(-1.0, 0.005), 0.0)


class GuardTests(unittest.TestCase):
    def test_a_fit_given_an_observation_after_its_cutoff_is_refused(self):
        """Leakage guard: a refit reads nothing after its cutoff.

        Recorded mutation: see `latent.require_before`.
        """
        obs, _, jump_day = simulate(n=60)
        with self.assertRaises(LookAheadError):
            latent.fit(obs, jump_days=[jump_day], cutoff=obs[30].day)

    def test_the_forecast_state_for_day_t_is_the_filter_through_t_minus_2(self):
        obs, _, jump_day = simulate(n=60)
        path = latent.filter_path(obs, latent.start_params(obs), jump_days=[jump_day])
        days = [o.day for o in obs]
        self.assertEqual(latent.forecast_state(path, days, days[40]).day, days[38])


if __name__ == "__main__":
    unittest.main()
