"""Stage 4: the curve-implied spread (`docs/stages/stage-4.md`).

The constrained curve, the scheduled IORB it converts with, the feature on training rows and at a forecast, and the
three leakage guards the plan names, each with its recorded mutation.
"""

import functools
import tempfile
import unittest
from datetime import date, datetime, time
from pathlib import Path

from repo_model.asof import FieldRead, InformationRule, InformationSet
from repo_model.data import DailyObservation, load_daily_panel
from repo_model.splits import LookAheadError

from repo_liquidity import curve_feature, demand_curve, panel, scheduled

DECISION = time(16, 0)


def _panel_rows():
    if not hasattr(_panel_rows, "rows"):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "phase3_panel.csv"
            panel.build(path, version=curve_feature.PANEL_VERSION)
            _panel_rows.rows = curve_feature.with_stage4_columns(load_daily_panel(path))
    return _panel_rows.rows


class ConstrainedFitTests(unittest.TestCase):
    GRID = tuple(round(0.06 + 0.005 * i, 4) for i in range(33))

    def test_a_rising_curve_is_recovered(self):
        xs = [0.06 + 0.002 * i for i in range(80)]
        ys = [0.1 + 8.0 * max(0.12 - x, 0.0) for x in xs]
        fit = curve_feature.fit_constrained(xs, ys, grid=self.GRID)
        self.assertAlmostEqual(fit.kink, 0.12, places=6)
        self.assertAlmostEqual(fit.slope, 8.0, places=6)
        self.assertAlmostEqual(fit.intercept, 0.1, places=6)

    def test_it_matches_stage_2_when_the_slope_is_positive(self):
        xs = [0.06 + 0.0013 * i for i in range(120)]
        ys = [0.2 + 5.0 * max(0.11 - x, 0.0) + 0.01 * ((i * 7) % 5 - 2) for i, x in enumerate(xs)]
        constrained = curve_feature.fit_constrained(xs, ys, grid=self.GRID)
        free = demand_curve.fit_broken_stick(xs, ys, grid=self.GRID)
        self.assertGreater(free.slope, 0)
        self.assertEqual((constrained.kink, constrained.slope), (free.kink, free.slope))

    def test_a_falling_curve_fails_rather_than_flattening(self):
        """Eleonora, 7 October 2026: a curve that lands on b = 0 is a failed curve, diagnosed and remedied."""
        xs = [0.06 + 0.002 * i for i in range(80)]
        ys = [0.5 - 3.0 * max(0.12 - x, 0.0) for x in xs]
        with self.assertRaises(curve_feature.CurveFailure) as caught:
            curve_feature.fit_constrained(xs, ys, grid=self.GRID)
        self.assertIn("slope", str(caught.exception))

    def test_a_sample_the_grid_cannot_split_fails(self):
        with self.assertRaises(curve_feature.CurveFailure):
            curve_feature.fit_constrained([0.30, 0.31], [0.1, 0.2], grid=self.GRID)

    def test_a_failure_is_a_value_error(self):
        self.assertTrue(issubclass(curve_feature.CurveFailure, ValueError))


class ConversionTests(unittest.TestCase):
    CURVE = curve_feature.Curve(kink=0.12, intercept=0.2, slope=10.0)

    def test_corridor_position_is_flat_above_the_bend(self):
        self.assertAlmostEqual(self.CURVE.corridor_at(0.15), 0.2)
        self.assertAlmostEqual(self.CURVE.corridor_at(0.10), 0.4)

    def test_implied_spread_is_in_basis_points_of_sofr_minus_iorb(self):
        # At position 1 SOFR sits on IORB; at 0 on the ON RRP rate, one corridor width below.
        top = curve_feature.Curve(kink=0.12, intercept=1.0, slope=0.0)
        floor = curve_feature.Curve(kink=0.12, intercept=0.0, slope=0.0)
        self.assertAlmostEqual(top.implied_spread_bp(0.2, iorb=4.40, on_rrp_rate=4.25), 0.0)
        self.assertAlmostEqual(floor.implied_spread_bp(0.2, iorb=4.40, on_rrp_rate=4.25), -15.0)
        self.assertAlmostEqual(self.CURVE.implied_spread_bp(0.10, iorb=2.40, on_rrp_rate=2.25), -9.0)

    def test_a_row_missing_an_input_carries_no_feature(self):
        values = {"reserve_balances": 3000.0, "bank_total_assets": 23000.0, "on_rrp_rate": 4.25,
                  curve_feature.IORB_COLUMN: None}
        self.assertIsNone(curve_feature.feature_value(self.CURVE, values))
        values[curve_feature.IORB_COLUMN] = 4.40
        self.assertAlmostEqual(curve_feature.feature_value(self.CURVE, values),
                               self.CURVE.implied_spread_bp(3000.0 / 23000.0, iorb=4.40, on_rrp_rate=4.25))


class ScheduledIorbTests(unittest.TestCase):
    def test_a_note_announced_after_the_decision_instant_is_never_read(self):
        """The scheduled IORB is keyed on the announcement, so a note made after T's decision instant cannot reach T.

        Recorded mutation (7 October 2026): in `scheduled._in_force`, `row.announced_at <= instant and` deleted, so a
        rate is read by effective date alone. This test failed with AssertionError (Lists differ: [None, 2.2, 2.4] !=
        [None, 2.2, 2.2]): the 18:00 note was read for the next day.
        """
        notes = [scheduled.Publication(datetime(2018, 9, 26, 14, 0), date(2018, 9, 27), (2.20,), ("2.20",), "a"),
                 scheduled.Publication(datetime(2018, 9, 27, 18, 0), date(2018, 9, 28), (2.40,), ("2.40",), "b")]
        dates = [date(2018, 9, 26), date(2018, 9, 27), date(2018, 9, 28)]
        values = scheduled.iorb_in_force_values(dates, decision_time=DECISION, rows=notes)
        self.assertEqual(values, [None, 2.20, 2.20])

    def test_the_table_is_the_parents_own(self):
        rows = scheduled.load_iorb_rates()
        self.assertGreater(len(rows), 0)
        self.assertTrue(all(row.announced_at.date() < row.effective for row in rows))

    def test_it_equals_the_realized_rate_except_where_a_note_came_after_the_decision(self):
        rows = [row for row in _panel_rows() if row.date <= date(2025, 12, 31)]
        differs = [row.date for row in rows[1:]
                   if row.values.get("iorb") is not None
                   and abs(row.values[curve_feature.IORB_COLUMN] - row.values["iorb"]) > 1e-9]
        # The Sunday 15 March 2020 cut, effective Monday 16 March, was announced after Friday's 16:00 decision.
        self.assertEqual(differs, [date(2020, 3, 16)])


class StageFourColumnsTests(unittest.TestCase):
    def test_the_published_v3_panel_is_unchanged(self):
        manifest = panel.load_manifest(version=curve_feature.PANEL_VERSION)
        rows = _panel_rows()
        self.assertTrue(all(curve_feature.IORB_COLUMN in row.values for row in rows))
        self.assertNotIn(curve_feature.IORB_COLUMN, manifest["columns"])

    def test_a_row_already_carrying_the_column_is_refused(self):
        rows = _panel_rows()[:3]
        with self.assertRaises(ValueError):
            curve_feature.with_stage4_columns(rows)

    def test_the_overlay_passes_the_parents_validators(self):
        self.assertEqual(curve_feature.validate_overlay(), [])


class CutoffGuardTests(unittest.TestCase):
    def test_rows_after_the_cutoff_do_not_move_the_curve(self):
        rows = [row for row in _panel_rows() if row.date <= date(2020, 3, 13)]
        cutoff = date(2019, 12, 31)
        with curve_feature.stage4_declaration():
            rule = curve_feature.curve_rule()
            truncated = curve_feature.fit_curve([row for row in rows if row.date <= cutoff], rule, cutoff=cutoff)
            poisoned = [row if row.date <= cutoff else DailyObservation(row.date, {**row.values, "sofr": 99.0})
                        for row in rows]
            full = curve_feature.fit_curve(poisoned, rule, cutoff=cutoff)
        self.assertEqual(truncated, full)

    def test_a_pair_after_the_cutoff_is_refused(self):
        """The curve is fitted only on rows at or before the refit's cutoff (must-show 2, first guard).

        Recorded mutation (7 October 2026): in `curve_feature.require_on_or_before`, `if day > cutoff:` changed to
        `if False:`. This test failed with AssertionError (LookAheadError not raised).
        """
        with self.assertRaises(LookAheadError):
            curve_feature.require_on_or_before([date(2019, 12, 30), date(2020, 1, 2)], date(2019, 12, 31))
        curve_feature.require_on_or_before([date(2019, 12, 30), date(2019, 12, 31)], date(2019, 12, 31))


class AsOfGuardTests(unittest.TestCase):
    def _info(self, read_row, available):
        read = FieldRead(feature="bank_total_assets", kind="observed",
                         fields=(("frb_h8", "TLAACBW027SBOG"),), row=read_row, available_at=available,
                         rows=10 - read_row, hours=None)
        return InformationSet(scored_index=10, decision_instant=datetime(2019, 1, 15, 16, 0), anchor=8,
                              reads=(read,))

    def test_a_read_at_or_after_the_row_it_feeds_is_refused(self):
        """The feature's inputs are read as of the forecast day's decision instant (must-show 2, second guard).

        Recorded mutation (7 October 2026): in `curve_feature.require_as_of`, `if read.kind == KIND_OBSERVED and
        read.row >= info.scored_index` changed to `if False`. This test failed with AssertionError (LookAheadError not
        raised).
        """
        with self.assertRaises(LookAheadError):
            curve_feature.require_as_of(self._info(10, datetime(2019, 1, 15, 9, 0)))

    def test_a_read_published_after_the_decision_instant_is_refused(self):
        with self.assertRaises(LookAheadError):
            curve_feature.require_as_of(self._info(8, datetime(2019, 1, 15, 16, 15)))

    def test_an_admissible_read_passes(self):
        curve_feature.require_as_of(self._info(8, datetime(2019, 1, 14, 16, 15)))

    def test_training_rows_carry_the_as_of_ratio_not_the_rows_own(self):
        rows = [row for row in _panel_rows() if row.date <= date(2019, 6, 28)]
        with curve_feature.stage4_declaration():
            rule = curve_feature.curve_rule()
            curve = curve_feature.Curve(kink=0.14, intercept=0.3, slope=6.0)
            augmented = curve_feature.with_training_feature(rows, rule, curve)
            index = len(rows) - 1
            info = rule.information_set([row.date for row in rows], index)
            seen = rule.observation(rows, info).values
        expected = curve_feature.feature_value(curve, seen)
        own = curve_feature.feature_value(curve, rows[index].values)
        self.assertAlmostEqual(augmented[index].values[curve_feature.FEATURE], expected)
        self.assertNotAlmostEqual(expected, own)
        self.assertIsNone(augmented[0].values[curve_feature.FEATURE])


class WrapperTests(unittest.TestCase):
    """The wrapper fitter inside the parent's fold loop (must-show 2, third guard)."""

    END = date(2018, 11, 30)

    def _backtest(self, features):
        from repo_model import baseline

        rows = [row for row in _panel_rows() if row.date <= self.END]
        with curve_feature.stage4_declaration():
            return baseline.rolling_persistence_backtest(
                rows, features=features, registry=curve_feature.registry(), decision_time=DECISION,
                minimum_history=61, refit_every=63, end=self.END,
                fit_model=curve_feature.CurveFeatureFitter(curve_feature.published_fitter()))

    def test_it_runs_inside_the_declaration(self):
        result = self._backtest(curve_feature.DECLARED_FEATURES)
        self.assertGreater(len(result.forecasts), 0)

    def test_a_curve_input_left_out_of_the_declaration_is_refused(self):
        """The parent's `baseline._check_fitter_stayed_inside` sees every column the curve reads.

        Recorded mutation (7 October 2026): in `CurveFeatureModel.features_read`, the curve's inputs dropped (the inner
        gbm's reads returned without `CURVE_READS`). This test failed with AssertionError (LookAheadError not raised).
        """
        without = tuple(name for name in curve_feature.DECLARED_FEATURES if name != "bank_total_assets")
        with self.assertRaises(LookAheadError):
            self._backtest(without)

    def test_the_fitted_model_reads_the_curve_inputs_not_the_feature(self):
        fitter = curve_feature.CurveFeatureFitter(curve_feature.published_fitter())
        rows = [row for row in _panel_rows() if row.date <= self.END]
        with curve_feature.stage4_declaration():
            rule = InformationRule(curve_feature.registry(), curve_feature.DECLARED_FEATURES, decision_time=DECISION)
            model = fitter(rows[:62], minimum_history=61, information=rule)
        self.assertNotIn(curve_feature.FEATURE, model.features_read)
        for name in curve_feature.CURVE_READS:
            self.assertIn(name, model.features_read)
        self.assertIn(curve_feature.FEATURE, model.inner.features_read)


class CarryForwardTests(unittest.TestCase):
    """The curve-pass remedy (Eleonora, 7 October 2026): a refit whose curve fails uses the last fitted curve."""

    def _fit(self, fitter, last_day):
        rows = [row for row in _panel_rows() if row.date <= last_day]
        with curve_feature.stage4_declaration():
            rule = InformationRule(curve_feature.registry(), curve_feature.DECLARED_FEATURES, decision_time=DECISION)
            return fitter(rows, minimum_history=61, information=rule)

    def test_a_failed_refit_carries_the_last_fitted_curve(self):
        fitter = curve_feature.CurveFeatureFitter(curve_feature.published_fitter())
        first = self._fit(fitter, date(2018, 6, 27))
        second = self._fit(fitter, date(2018, 7, 27))
        self.assertEqual(second.curve, first.curve)
        self.assertEqual([entry.carried_from for entry in fitter.curves], [None, date(2018, 6, 27)])

    def test_a_first_refit_that_fails_stops_the_run(self):
        fitter = curve_feature.CurveFeatureFitter(curve_feature.published_fitter())
        with self.assertRaises(curve_feature.CurveFailure):
            self._fit(fitter, date(2018, 7, 27))

    def test_a_carried_curve_from_a_later_cutoff_is_refused(self):
        """A carried curve must have been fitted at or before the refit's cutoff.

        Recorded mutation (7 October 2026): in `CurveFeatureFitter.__call__`, the line
        `require_on_or_before([fitted[-1].cutoff], cutoff)` replaced by `pass`. This test failed with AssertionError
        (LookAheadError not raised).
        """
        fitter = curve_feature.CurveFeatureFitter(curve_feature.published_fitter())
        fitter.curves.append(curve_feature.RefitCurve(cutoff=date(2018, 8, 31), curve=ConversionTests.CURVE,
                                                      carried_from=None))
        with self.assertRaises(LookAheadError):
            self._fit(fitter, date(2018, 7, 27))


class DeclarationTests(unittest.TestCase):
    def test_the_published_features_are_the_records(self):
        import json

        from repo_liquidity import parent_root

        record = json.loads((parent_root() / curve_feature.PUBLISHED_RECORD).read_text(encoding="utf-8"))
        declared = record["declaration"]
        self.assertEqual(list(curve_feature.PUBLISHED_FEATURES), declared["model_b"]["features"])
        self.assertEqual(declared["model_b"]["calibration"], "conformal_pid_nested")
        self.assertEqual((declared["minimum_history"], declared["refit_every"], declared["decision_time"]),
                         (curve_feature.MINIMUM_HISTORY, curve_feature.REFIT_EVERY, "16:00"))

    def test_the_declared_features_add_only_the_curves_inputs(self):
        added = set(curve_feature.DECLARED_FEATURES) - set(curve_feature.PUBLISHED_FEATURES)
        self.assertEqual(added, {"bank_total_assets", "on_rrp_rate", curve_feature.IORB_COLUMN})


if __name__ == "__main__":
    unittest.main()
