"""The dispersion- and volume-based liquidity hypothesis, step 1 (#205): its inputs, their guards and the 2027-06-30 break.

`docs/research/dispersion-volume-hypothesis.md` is the draft for Eleonora. Nothing is fitted or scored here: this module
holds the inputs' availability declarations, read through the parent's `asof.InformationRule`, and two guards.
"""

import pathlib
import tempfile
import unittest
from datetime import date, time

from repo_model import contract
from repo_model.asof import InformationRule, StaleReadError
from repo_model.splits import LookAheadError

from repo_liquidity import declaration, dispersion_volume, indicators, panel

SCORED_INDEX = 1500


class InputTableTests(unittest.TestCase):
    def test_there_is_exactly_one_primary_measure_and_it_is_a_dispersion(self):
        primary = [i for i in dispersion_volume.INPUTS if i.role == "primary"]
        self.assertEqual([i.name for i in primary], ["sofr_p75_p25_bp"])
        self.assertEqual(primary[0].family, "dispersion")

    def test_both_families_are_declared_inputs(self):
        self.assertEqual({i.family for i in dispersion_volume.INPUTS}, {"dispersion", "volume"})

    def test_every_input_is_a_declared_feature_with_a_release_lag(self):
        registry = declaration.registry()
        with declaration.phase3_declaration():
            features = dict(contract.FEATURE_FIELDS)
        for item in dispersion_volume.INPUTS:
            with self.subTest(item.name):
                self.assertIn(item.name, features)
                for source, field in features[item.name]:
                    self.assertIn(field, registry[source]["fields"])
                    self.assertIn("release_lag", registry[source])

    def test_the_two_volumes_this_step_switches_on_are_read_from_the_parents_own_sources(self):
        self.assertEqual(declaration.FIELDS["bgcr_volume"], (("nyfed_bgcr", "BGCR_volume"),))
        self.assertEqual(declaration.FIELDS["ofr_dvp_volume"], (("ofr_stfm_repo", "REPO-DVP_TV_OO-F"),))

    def test_sofr_volume_is_the_parents_own_feature_and_is_not_redeclared_here(self):
        self.assertEqual(contract.FEATURE_FIELDS["sofr_volume"], (("nyfed_sofr", "SOFR_volume"),))
        self.assertNotIn("sofr_volume", declaration.FIELDS)

    def test_the_new_volumes_are_not_built_columns_of_any_panel(self):
        for name in ("bgcr_volume", "ofr_dvp_volume"):
            self.assertNotIn(name, declaration.BUILT_COLUMNS_V3)


class GuardTests(unittest.TestCase):
    """Each input is read at its declared lag: a read a row later is leakage, a read a row earlier is stale."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        path = pathlib.Path(cls.tmp.name) / "phase3_panel.csv"
        panel.build(path, version=5)
        from repo_model.data import load_daily_panel

        cls.dates = [row.date for row in load_daily_panel(path)]

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def _read(self, feature, offset=0):
        with declaration.phase3_declaration():
            rule = InformationRule(declaration.registry(), [feature], decision_time=time(16, 0))
            info = rule.information_set(self.dates, SCORED_INDEX)
            rule.check(self.dates, info)
            rows = {r.feature: r.row for r in info.reads}
            moved = info._replace(reads=tuple(r._replace(row=r.row + offset) if r.feature == feature else r
                                              for r in info.reads))
            return rule, rows[feature], moved

    def test_a_volume_or_dispersion_read_moved_one_row_later_is_leakage(self):
        """Leakage guard: each input of the hypothesis is read at the row its declared lag allows, and one row later is
        refused.

        Recorded mutation (9 November 2026): in the parent's `src/repo_model/asof.py` (at the pin), `InformationRule.check`,
        `if available > deadline:` changed to `if False:`. This test then fails with AssertionError (LookAheadError not
        raised) for every input.
        """
        for item in dispersion_volume.INPUTS:
            with self.subTest(item.name):
                rule, _row, moved = self._read(item.name, +1)
                with self.assertRaises(LookAheadError):
                    rule.check(self.dates, moved)

    def test_a_volume_or_dispersion_read_moved_one_row_earlier_is_stale(self):
        """Staleness guard: a read one row earlier than the latest public value is refused.

        Recorded mutation (9 November 2026): in the parent's `src/repo_model/asof.py` (at the pin), `InformationRule.check`,
        `if following < scored and self.availability(dates, read.fields, following) <= deadline:` changed to `if False:`.
        This test then fails with AssertionError (StaleReadError not raised) for every input.
        """
        for item in dispersion_volume.INPUTS:
            with self.subTest(item.name):
                rule, _row, moved = self._read(item.name, -1)
                with self.assertRaises(StaleReadError):
                    rule.check(self.dates, moved)

    def test_the_ofr_volume_is_read_one_row_before_the_one_day_sources(self):
        """The OFR declares two business days at 16:00, SOFR and BGCR one at 15:00: one row apart at a plain date.

        Recorded mutation (9 November 2026): in `src/repo_liquidity/declaration.py`, `"ofr_dvp_volume"` mapped to
        `(("nyfed_bgcr", "BGCR_volume"),)` instead of `(("ofr_stfm_repo", "REPO-DVP_TV_OO-F"),)`. This test then fails
        with AssertionError: 1498 != 1497 (the OFR volume read at the BGCR volume's row).
        """
        _, sofr_row, _ = self._read("sofr_volume")
        _, bgcr_row, _ = self._read("bgcr_volume")
        _, ofr_row, _ = self._read("ofr_dvp_volume")
        self.assertEqual(sofr_row, bgcr_row)
        self.assertEqual(ofr_row, bgcr_row - 1)

    def test_the_dispersion_measures_are_read_where_their_two_percentiles_are(self):
        _, sofr_row, _ = self._read("sofr_volume")
        for name in ("sofr_p75_p25_bp", "sofr_p99_p1_bp"):
            with self.subTest(name):
                self.assertEqual(self._read(name)[1], sofr_row)


class BreakTests(unittest.TestCase):
    BREAK = date(2027, 6, 30)

    def test_the_break_is_the_registers_date(self):
        self.assertEqual(dispersion_volume.BREAK, self.BREAK)
        self.assertEqual(tuple(indicators.MEASUREMENT_BREAKS), (self.BREAK.isoformat(),))

    def test_every_column_the_register_lists_is_kept(self):
        self.assertLessEqual(set(indicators.MEASUREMENT_BREAKS["2027-06-30"]), dispersion_volume.BREAK_COLUMNS)

    def test_both_new_volumes_are_treated_as_broken(self):
        self.assertLessEqual({"bgcr_volume", "ofr_dvp_volume"}, dispersion_volume.BREAK_COLUMNS)

    def test_every_input_of_the_hypothesis_is_handled_across_the_break(self):
        for item in dispersion_volume.INPUTS:
            with self.subTest(item.name):
                self.assertIn(item.name, dispersion_volume.BREAK_COLUMNS)

    def test_a_window_across_the_break_is_refused_for_every_broken_column(self):
        """Data guard (draft default: not read across the break until Eleonora declares a re-based series).

        Recorded mutation (9 November 2026): in `dispersion_volume.check_not_across_break`, `first < BREAK <= last`
        changed to `first < BREAK < last`. `test_a_window_that_ends_on_the_break_day_is_refused` then fails with
        AssertionError (ValueError not raised).
        """
        for column in sorted(dispersion_volume.BREAK_COLUMNS):
            with self.subTest(column):
                with self.assertRaises(ValueError):
                    dispersion_volume.check_not_across_break(column, date(2027, 6, 1), date(2027, 7, 15))

    def test_a_window_that_ends_on_the_break_day_is_refused(self):
        with self.assertRaises(ValueError):
            dispersion_volume.check_not_across_break("sofr_volume", date(2027, 6, 29), self.BREAK)

    def test_windows_wholly_on_one_side_are_read(self):
        dispersion_volume.check_not_across_break("sofr_volume", date(2026, 1, 1), date(2027, 6, 29))
        dispersion_volume.check_not_across_break("sofr_volume", self.BREAK, date(2028, 1, 1))

    def test_a_column_the_break_does_not_touch_is_read_across_it(self):
        dispersion_volume.check_not_across_break("sofr_minus_iorb_bp", date(2027, 6, 1), date(2027, 7, 15))

    def test_a_window_that_runs_backwards_is_refused(self):
        with self.assertRaises(ValueError):
            dispersion_volume.check_not_across_break("sofr_volume", date(2027, 7, 1), date(2027, 6, 1))


class FirstUsableTests(unittest.TestCase):
    def test_the_ofr_volume_before_real_time_publication_is_refused(self):
        """Leakage guard: OFR values dated before 2020-09-09 were filled in after the OFR began publishing in real time
        (`sources.json`, `ofr_stfm_repo`, at the pin), so they were not public on their day.

        Recorded mutation (9 November 2026): in `dispersion_volume.check_usable`, `day < first` changed to `day <=
        first`. `test_the_first_day_of_real_time_publication_is_read` then fails with LookAheadError (the value dated
        2020-09-09 is refused). With `day < first` changed to `False`, this test fails with AssertionError (LookAheadError
        not raised).
        """
        with self.assertRaises(LookAheadError):
            dispersion_volume.check_usable("ofr_dvp_volume", date(2020, 9, 8))

    def test_the_first_day_of_real_time_publication_is_read(self):
        dispersion_volume.check_usable("ofr_dvp_volume", date(2020, 9, 9))

    def test_a_column_without_a_first_usable_day_is_read_at_any_date(self):
        dispersion_volume.check_usable("sofr_volume", date(2018, 4, 3))


if __name__ == "__main__":
    unittest.main()
