"""H10 with new drivers, step 1 (#204): the second declaration's driver set, its inputs' guards and the 30 June 2027 break.

Nothing is attributed and nothing is scored here. The registered method (`h10-method.md`, `attribution.DRIVERS*`,
`h10_apply`, `h10_live`, its digest) is untouched, and the tests below say so.
"""

import copy
import json
import pathlib
import unittest
from datetime import date, datetime, timedelta

from repo_model.asof import InformationRule, StaleReadError, declared_availability
from repo_model.splits import LookAheadError

from repo_liquidity import attribution, declaration, h10_apply, h10_drivers_2 as d2, h10_live, h10_registration

ROOT = pathlib.Path(__file__).resolve().parents[1]
RECORD = ROOT / "docs" / "decisions" / "h10-method-2.md"
PARENT_MEASUREMENT = "metadata/sources_measurement.json"


def weekdays(first: date, count: int):
    out, day = [], first
    while len(out) < count:
        if day.weekday() < 5:
            out.append(day)
        day += timedelta(days=1)
    return out


class RegisteredMethodUntouchedTests(unittest.TestCase):
    def test_the_registered_driver_sets_are_as_registered(self):
        self.assertEqual(attribution.DRIVERS, ("treasury_settlement", "tga", "reserve_balances", "quarter_end"))
        self.assertEqual(attribution.DRIVERS_WITH_ON_RRP, attribution.DRIVERS + ("on_rrp",))

    def test_the_second_declaration_is_the_registered_set_plus_four_new_names(self):
        self.assertEqual(d2.DRIVERS_2[: len(attribution.DRIVERS_WITH_ON_RRP)], attribution.DRIVERS_WITH_ON_RRP)
        self.assertEqual(d2.NEW_DRIVERS, ("srf_material_use", "sofr_volume", "sofr_p99_p1_bp", "pd_fails_deliver_ust"))
        self.assertEqual(d2.DRIVERS_2, attribution.DRIVERS_WITH_ON_RRP + d2.NEW_DRIVERS)

    def test_the_method_digest_is_still_the_registered_one(self):
        """The registered method digest does not cover the new module, the new record or the new declaration."""
        self.assertEqual(h10_live.method_digest(), h10_registration.REGISTERED_DIGEST)
        covered = {name for name, _ in h10_live.METHOD_FILES}
        self.assertFalse([name for name in covered if "drivers_2" in name or "method-2" in name])

    def test_the_registered_rule_reads_none_of_the_new_names(self):
        with h10_apply.real_rule() as rule:
            read = {group.feature for group in rule.groups}
        self.assertFalse(read & set(d2.NEW_DRIVERS))


class FailsDeclarationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.entry = declaration.registry()[d2.FAILS_SOURCE]
        cls.dates = weekdays(date(2026, 1, 5), 120)

    def test_the_overlay_passes_the_parents_validators(self):
        self.assertEqual(declaration.validate(), [])

    def test_the_columns_read_the_two_fails_series(self):
        self.assertEqual(declaration.FIELDS["pd_fails_deliver_ust"], ((d2.FAILS_SOURCE, "PDFTD-UST"),))
        self.assertEqual(declaration.FIELDS["pd_fails_receive_ust"], ((d2.FAILS_SOURCE, "PDFTR-UST"),))
        self.assertEqual(set(self.entry["field_frequencies"].values()), {"weekly"})

    def test_the_lag_is_the_parents(self):
        """The parent's `nyfed_pd_financing` at the pin declares the same export; the lag here is copied, not chosen."""
        parent = json.loads((declaration.parent_root() / PARENT_MEASUREMENT).read_text(encoding="utf-8"))["nyfed_pd_financing"]
        keys = ("available_time", "basis", "days", "timezone", "unit", "worst_case_calendar_days")
        self.assertEqual({k: self.entry["release_lag"][k] for k in keys}, {k: parent["release_lag"][k] for k in keys})
        self.assertEqual(self.entry["fields"], ["PDFTD-UST", "PDFTR-UST"])

    def test_a_week_is_not_declared_public_before_the_published_schedule(self):
        """Leakage guard: the Wednesday as-of week is published on the Thursday of the following week at 16:30.

        Recorded mutation (9 November 2026): in `declarations/nyfed_pd_fails.json`, `nyfed_pd_fails.release_lag.days`
        changed from 6 to 5. This test then fails with LookAheadError: the week of Wednesday 2026-01-07 is declared
        available 2026-01-14 16:30, before its published 2026-01-15 16:30.
        """
        d2.check_declared_fails_lag(self.entry, self.dates)

    def test_a_declared_lag_earlier_than_the_schedule_is_refused(self):
        entry = copy.deepcopy(self.entry)
        entry["release_lag"]["days"] = 5
        with self.assertRaises(LookAheadError):
            d2.check_declared_fails_lag(entry, self.dates)

    def test_a_declared_lag_later_than_the_schedule_is_stale(self):
        """Staleness guard: the lag is the schedule's and not above it.

        Recorded mutation (9 November 2026): in `declarations/nyfed_pd_fails.json`, `nyfed_pd_fails.release_lag.days`
        changed from 6 to 8. This test then fails with StaleReadError: the declared 2026-01-19 16:30 is later than the
        published 2026-01-15 16:30 for the week of 2026-01-07.
        """
        entry = copy.deepcopy(self.entry)
        entry["release_lag"]["days"] = 8
        with self.assertRaises(StaleReadError):
            d2.check_declared_fails_lag(entry, self.dates)
        d2.check_declared_fails_lag(self.entry, self.dates)

    def test_the_published_instant_is_the_thursday_of_the_following_week(self):
        self.assertEqual(d2.published_fails_instant(date(2026, 1, 7)), datetime(2026, 1, 15, 16, 30))
        with self.assertRaises(ValueError):
            d2.published_fails_instant(date(2026, 1, 8))

    def test_the_row_availability_is_six_panel_rows_later_at_1630(self):
        registry = {d2.FAILS_SOURCE: self.entry}
        moment = declared_availability(registry, d2.FAILS_SOURCE, "PDFTD-UST", self.dates, 10)
        self.assertEqual(moment, datetime.combine(self.dates[16], datetime.min.time()).replace(hour=16, minute=30))


class TheOtherInputsDeclarationsTests(unittest.TestCase):
    """The three inputs the parent already declares: their lags are what the report-window figures rest on."""

    def test_the_declared_lags(self):
        registry = declaration.registry()
        srf = registry["nyfed_srf"]["release_lag"]
        sofr = registry["nyfed_sofr"]["release_lag"]
        self.assertEqual((srf["days"], srf["unit"], srf["available_time"]), (1, "business_days", "16:00"))
        self.assertEqual((sofr["days"], sofr["unit"], sofr["available_time"]), (1, "business_days", "15:00"))

    def test_the_new_drivers_are_all_declared_in_phase_3s_map(self):
        from repo_model import contract

        known = {**contract.FEATURE_FIELDS, **declaration.FIELDS}
        for name in d2.NEW_DRIVERS:
            self.assertIn(name, known)


class ReportWindowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dates = weekdays(date(2026, 1, 5), 120)

    def rule(self, name):
        with declaration.phase3_declaration():
            return InformationRule(declaration.registry(), [name], decision_time=h10_apply.DECISION_TIME)

    def test_each_new_input_is_reported_after_the_expected_panel_days(self):
        expected = {"srf_material_use": 6, "sofr_volume": 6, "sofr_p99_p1_bp": 6, "pd_fails_deliver_ust": 11}
        for name, days in expected.items():
            with self.subTest(name):
                self.assertEqual(d2.report_panel_days(self.rule(name), self.dates, 40), days)

    def test_fails_push_an_onset_past_the_report_days_and_the_others_do_not(self):
        over = {name for name in d2.NEW_DRIVERS
                if d2.report_panel_days(self.rule(name), self.dates, 40) > h10_apply.REPORT_DAYS}
        self.assertEqual(over, {"pd_fails_deliver_ust"})

    def test_the_window_is_public_at_the_returned_day_and_not_before(self):
        """Leakage and staleness guard for the report day: `attribution.check_window_public` accepts the day
        `report_panel_days` returns and refuses the day before it.

        Recorded mutation (9 November 2026), leakage: in `h10_drivers_2.report_panel_days`, `return report - start`
        changed to `return report - start - 1`. `test_the_window_is_public_at_the_returned_day_and_not_before` then
        fails with LookAheadError, from `check_window_public` at the returned day. Staleness: the same line changed
        to `return report - start + 1`; the test fails with AssertionError (LookAheadError not raised at the day
        before the returned one).
        """
        for name in d2.NEW_DRIVERS:
            rule = self.rule(name)
            days = d2.report_panel_days(rule, self.dates, 40)
            with self.subTest(name):
                attribution.check_window_public(rule, self.dates, 40, 40 + days)
                with self.assertRaises(LookAheadError):
                    attribution.check_window_public(rule, self.dates, 40, 40 + days - 1)

    def test_a_window_never_public_on_the_sample_has_no_report_day(self):
        self.assertIsNone(d2.report_panel_days(self.rule("pd_fails_deliver_ust"), self.dates, len(self.dates) - 6))


class RealPanelReportDaysTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        rows, _ = h10_apply.load_development()
        cls.dates = [row.date for row in rows]

    def test_the_summary_over_every_onset_position_of_the_development_panel(self):
        summary = d2.report_days_summary(self.dates)
        for name in ("srf_material_use", "sofr_volume", "sofr_p99_p1_bp"):
            with self.subTest(name):
                self.assertLessEqual(summary[name]["max"], h10_apply.REPORT_DAYS)
                self.assertEqual(summary[name]["over_report_days"], 0)
        fails = summary["pd_fails_deliver_ust"]
        self.assertGreater(fails["min"], h10_apply.REPORT_DAYS)
        self.assertEqual(fails["over_report_days"], fails["onsets"])

    def test_the_registered_drivers_are_read_the_same_way(self):
        summary = d2.report_days_summary(self.dates)
        self.assertLessEqual(summary["tga"]["max"], h10_apply.REPORT_DAYS)


class BreakTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dates = weekdays(date(2027, 6, 1), 40)  # 1 June to 26 July 2027
        cls.break_index = cls.dates.index(date(2027, 6, 30))
        n = len(cls.dates)
        cls.series = {name: [1.0 + i for i in range(n)] for name in (attribution.SPREAD, *d2.DRIVERS_2)}

    def test_the_break_is_the_one_the_indicators_carry(self):
        from repo_liquidity import indicators

        self.assertEqual(d2.BREAK_DATE, date(2027, 6, 30))
        self.assertEqual(set(indicators.MEASUREMENT_BREAKS), {d2.BREAK_DATE.isoformat()})
        self.assertEqual(set(d2.BREAK_DRIVERS), {"sofr_volume", "sofr_p99_p1_bp"})
        self.assertLessEqual(set(d2.BREAK_DRIVERS), set(indicators.MEASUREMENT_BREAKS[d2.BREAK_DATE.isoformat()]))

    def test_a_window_touching_the_break_day_is_flagged_and_one_before_it_is_not(self):
        """The break day itself is on the far side of the break.

        Recorded mutation (9 November 2026): in `h10_drivers_2.touches_break`, `day >= BREAK_DATE` changed to
        `day > BREAK_DATE`. This test then fails with AssertionError: a window whose last day is 2027-06-30 is not
        flagged.
        """
        b = self.break_index
        # a window starting at s spans rows s-5 .. s+4 (baseline and window)
        self.assertTrue(d2.touches_break(self.dates, b - 4))     # last row s+4 is the break day
        self.assertTrue(d2.touches_break(self.dates, b + 3))     # inside the post-break rows
        self.assertFalse(d2.touches_break(self.dates, b - 5))    # last row s+4 is the day before
        self.assertFalse(d2.touches_break(self.dates, 6))

    def test_the_baseline_days_count_as_part_of_the_window(self):
        b = self.break_index
        self.assertTrue(d2.touches_break(self.dates, b + 5))     # the break day is in the baseline only
        self.assertTrue(d2.touches_break(self.dates, b + 9))     # every later window is on the far side

    def test_the_mask_removes_the_break_series_on_and_after_the_break_day_and_nothing_else(self):
        masked = d2.mask_across_break(self.series, self.dates)
        b = self.break_index
        for name in d2.BREAK_DRIVERS:
            self.assertEqual(masked[name][:b], self.series[name][:b])
            self.assertTrue(all(v is None for v in masked[name][b:]))
        for name in set(self.series) - set(d2.BREAK_DRIVERS):
            self.assertEqual(masked[name], self.series[name])
        self.assertEqual(self.series["sofr_volume"][b], 1.0 + b)  # the input is not modified

    def test_an_onset_whose_window_touches_the_break_is_not_attributable_with_the_reason(self):
        for attributed in (d2.break_refusal(self.dates, self.break_index),
                           d2.attribute_2(self.series, self.break_index, dates=self.dates)):
            self.assertEqual(attributed.status, "not attributable")
            self.assertIn("2027-06-30", attributed.reason)
            self.assertIn("mandatory clearing", attributed.reason)
            self.assertEqual(attributed.start, self.break_index)

    def test_the_break_does_not_apply_to_a_driver_set_that_does_not_read_the_series(self):
        self.assertIsNone(d2.break_refusal(self.dates, self.break_index, drivers=attribution.DRIVERS_WITH_ON_RRP))

    def test_a_window_before_the_break_is_not_refused_for_it(self):
        self.assertIsNone(d2.break_refusal(self.dates, 8))

    def test_the_break_is_taken_from_dates_not_from_a_counter(self):
        with self.assertRaises(ValueError):
            d2.mask_across_break(self.series, self.dates[:-1])


class RecordTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = RECORD.read_text(encoding="utf-8")

    def test_the_record_is_a_draft_for_her_to_merge(self):
        self.assertIn("Status: DRAFT", self.text.split("\n", 4)[2])
        self.assertIn("in force only once she merges", self.text)

    def test_the_record_names_the_drivers_the_break_and_the_untouched_method(self):
        for needle in (*d2.NEW_DRIVERS, "2027-06-30", "54b5f151", "REPORT_DAYS", "panel version 6", "row 11", "row 8", "row 13"):
            with self.subTest(needle):
                self.assertIn(needle.lower(), self.text.lower())

    def test_the_record_reports_the_fails_lag_against_the_report_days(self):
        self.assertRegex(self.text, r"11 panel days")


if __name__ == "__main__":
    unittest.main()
