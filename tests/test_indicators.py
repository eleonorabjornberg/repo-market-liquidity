"""Stage 1b's first-wave indicators (`docs/stages/stage-1b.md`): pricing and the Fed's facilities, on each row."""

import unittest
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from repo_model.data import DailyObservation
from repo_model.splits import LookAheadError

from repo_liquidity import indicators, scheduled

NY = ZoneInfo("America/New_York")


def publication(announced, effective, rate):
    return scheduled.Publication(announced_at=announced, effective=effective, values=(rate,), raw_values=(str(rate),),
                                 page="test")


FLOORS = [publication(datetime(2019, 7, 31, 14, 0, tzinfo=NY), date(2019, 8, 1), 2.0),
          publication(datetime(2019, 9, 18, 14, 0, tzinfo=NY), date(2019, 9, 19), 1.7)]
CEILINGS = [publication(datetime(2021, 7, 28, 14, 0, tzinfo=NY), date(2021, 7, 29), 0.25)]


class RateKnownByCloseTests(unittest.TestCase):
    def test_the_rate_in_force_is_read_by_effective_date(self):
        self.assertEqual(indicators.rate_known_by_close(FLOORS, date(2019, 9, 18)), 2.0)
        self.assertEqual(indicators.rate_known_by_close(FLOORS, date(2019, 9, 19)), 1.7)
        self.assertIsNone(indicators.rate_known_by_close(FLOORS, date(2019, 7, 31)))

    def test_a_rate_announced_after_the_day_it_applies_to_is_refused(self):
        """Leakage guard: a day's spread may use only a rate public by that day's close.

        Recorded mutation (6 October 2026): in `indicators.rate_known_by_close`, `if row.announced_at > close:`
        replaced by `if False:`. This test then fails with AssertionError: LookAheadError not raised.
        """
        late = FLOORS + [publication(datetime(2019, 10, 2, 9, 0, tzinfo=NY), date(2019, 10, 1), 1.55)]
        with self.assertRaises(LookAheadError):
            indicators.rate_known_by_close(late, date(2019, 10, 1))

    def test_a_rate_announced_during_its_first_day_is_accepted(self):
        same_day = [publication(datetime(2020, 3, 15, 17, 0, tzinfo=NY), date(2020, 3, 15), 0.0)]
        self.assertEqual(indicators.rate_known_by_close(same_day, date(2020, 3, 15)), 0.0)


def row(day, **values):
    return DailyObservation(date=day, values=values)


class IndicatorTests(unittest.TestCase):
    def compute(self, rows):
        return indicators.with_indicators(rows, floors=FLOORS, ceilings=CEILINGS)

    def test_pricing_spreads_are_in_basis_points(self):
        out = self.compute([row(date(2019, 9, 19), sofr=2.0, iorb=1.8, tgcr=1.95, bgcr=1.96, sofr_p1=1.9,
                                sofr_p25=1.97, sofr_p75=2.05, sofr_p99=2.5, effr=1.9)])[0].values
        self.assertAlmostEqual(out["sofr_minus_iorb_bp"], 20.0)
        self.assertAlmostEqual(out["tgcr_minus_sofr_bp"], -5.0)
        self.assertAlmostEqual(out["bgcr_minus_sofr_bp"], -4.0)
        self.assertAlmostEqual(out["sofr_p75_p25_bp"], 8.0)
        self.assertAlmostEqual(out["sofr_p99_p1_bp"], 60.0)
        self.assertAlmostEqual(out["sofr_p1_minus_bgcr_bp"], -6.0)
        self.assertAlmostEqual(out["sofr_minus_effr_bp"], 10.0)
        self.assertAlmostEqual(out["tgcr_minus_on_rrp_bp"], 25.0)

    def test_a_missing_input_leaves_the_indicator_missing(self):
        out = self.compute([row(date(2019, 9, 19), sofr=2.0, iorb=None, tgcr=1.95)])[0].values
        self.assertIsNone(out["sofr_minus_iorb_bp"])
        self.assertIsNone(out["sofr_minus_effr_bp"])

    def test_the_ceiling_distance_is_missing_before_the_facility(self):
        before = self.compute([row(date(2021, 7, 28), sofr=0.05)])[0].values
        after = self.compute([row(date(2021, 7, 29), sofr=0.05)])[0].values
        self.assertIsNone(before["sofr_minus_srf_bp"])
        self.assertAlmostEqual(after["sofr_minus_srf_bp"], -20.0)

    def test_the_on_rrp_buffer_flag_follows_the_parents_rule(self):
        out = self.compute([row(date(2022, 1, 3), on_rrp=1500.0), row(date(2025, 6, 2), on_rrp=99.9),
                            row(date(2025, 6, 3), on_rrp=None)])
        self.assertEqual([r.values["on_rrp_buffer_gone"] for r in out], [0.0, 1.0, None])

    def test_soma_flows_add_treasuries_and_mbs(self):
        out = self.compute([row(date(2023, 1, 4), soma_treasury_weekly_change=-12.0, soma_mbs_weekly_change=-4.0),
                            row(date(2023, 1, 5), soma_treasury_weekly_change=-12.0)])
        self.assertEqual([r.values["soma_weekly_change_total"] for r in out], [-16.0, None])

    def test_the_tga_change_is_from_the_previous_row(self):
        start = date(2023, 1, 2)
        rows = [row(start + timedelta(days=i), tga=v) for i, v in enumerate((400.0, 400.0, 380.5, None, 390.0))]
        self.assertEqual([r.values["tga_change_bn"] for r in self.compute(rows)], [None, 0.0, -19.5, None, None])

    def test_every_declared_column_is_written(self):
        out = self.compute([row(date(2019, 9, 19))])[0].values
        self.assertEqual(set(indicators.COLUMNS) - set(out), set())

    def test_existing_columns_are_never_overwritten(self):
        with self.assertRaises(ValueError):
            self.compute([row(date(2019, 9, 19), sofr_minus_iorb_bp=1.0)])


if __name__ == "__main__":
    unittest.main()
