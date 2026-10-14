"""Phase 3's inputs read through the parent's as-of guards.

`tests/test_scheduled.py` holds the scheduled inputs' leakage guard. This module holds the H.4.1 declaration's
leakage guard and the end-to-end check that every Phase 3 column passes the parent's `asof.InformationRule` on every
row of the measurement panel.
"""

import pathlib
import tempfile
import unittest
from datetime import date, datetime, time, timedelta

from repo_model.asof import KIND_SCHEDULED, InformationRule
from repo_model.splits import LookAheadError, SplitError

from repo_liquidity import declaration, h41, h8, panel, slr

ROOT = pathlib.Path(__file__).resolve().parents[1]
EXTRACT = ROOT / "tests" / "fixtures" / "snapshots" / "h41" / "h41_treasury_first_print.csv"
MBS_EXTRACT = ROOT / "tests" / "fixtures" / "snapshots" / "h41" / "h41_mbs_first_print.csv"
SLR_EXTRACT = ROOT / "tests" / "fixtures" / "snapshots" / "slr_headroom" / slr.EXTRACT_NAME
AGENCY_EXTRACT = ROOT / "tests" / "fixtures" / "snapshots" / "h41" / "h41_agency_first_print.csv"


class H41DeclarationTests(unittest.TestCase):
    def test_no_release_is_published_after_its_declared_availability(self):
        """Leakage guard: the declared lag covers every release in the extract.

        Recorded mutation (6 October 2026): in `metadata/sources_phase3.json`, `frb_h41_treasury.release_lag.days`
        changed from 5 to 1. This test then fails with LookAheadError: the week ended 2018-11-21 was released
        2018-11-23 16:30, after its declared availability of 2018-11-22 16:30.
        """
        h41.check_declared_lag(declaration.registry()["frb_h41_treasury"], h41.load_extract(EXTRACT))

    def test_a_release_later_than_declared_is_refused(self):
        entry = dict(declaration.registry()["frb_h41_treasury"])
        entry["release_lag"] = dict(entry["release_lag"], days=1)
        with self.assertRaises(LookAheadError):
            h41.check_declared_lag(entry, h41.load_extract(EXTRACT))

    def test_the_extract_is_consecutive_weeks(self):
        releases = h41.load_extract(EXTRACT)
        self.assertEqual(releases[0].week_ended.isoformat(), "2017-12-27")


class MbsDeclarationTests(unittest.TestCase):
    def test_no_mbs_release_is_published_after_its_declared_availability(self):
        """Leakage guard: the declared lag covers every release in the MBS extract.

        Recorded mutation (6 October 2026): in `metadata/sources_phase3.json`, `frb_h41_mbs.release_lag.days` changed
        from 5 to 1. This test then fails with LookAheadError: the week ended 2018-11-21 was released 2018-11-23
        16:30:00, after its declared availability 2018-11-22 16:30:00.
        """
        h41.check_declared_lag(declaration.registry()["frb_h41_mbs"], h41.load_extract(MBS_EXTRACT))

    def test_the_mbs_extract_reads_the_same_releases_as_the_treasury_extract(self):
        treasury = [(r.week_ended, r.release_date) for r in h41.load_extract(EXTRACT)]
        mbs = [(r.week_ended, r.release_date) for r in h41.load_extract(MBS_EXTRACT)]
        self.assertEqual(mbs, treasury)


class AgencyDeclarationTests(unittest.TestCase):
    """The agency-securities inputs (#30; `frb_h41_agency`, `docs/decisions/data-meaning.md`, answer 15)."""

    def test_no_agency_release_is_published_after_its_declared_availability(self):
        """Leakage guard: the declared lag covers every release in the agency-debt extract.

        Recorded mutation (13 October 2026): in `declarations/h41_agency.json`, `release_lag.days` changed from 5 to
        1. This test then fails with LookAheadError: the week ended 2018-11-21 was released 2018-11-23 16:30:00,
        after its declared availability 2018-11-22 16:30:00.
        """
        h41.check_declared_lag(declaration.registry()["frb_h41_agency"], h41.load_extract(AGENCY_EXTRACT))

    def test_a_release_later_than_declared_is_refused(self):
        entry = dict(declaration.registry()["frb_h41_agency"])
        entry["release_lag"] = dict(entry["release_lag"], days=1)
        with self.assertRaises(LookAheadError):
            h41.check_declared_lag(entry, h41.load_extract(AGENCY_EXTRACT))

    def test_the_agency_extract_reads_the_same_releases_as_the_mbs_extract(self):
        agency = [(r.week_ended, r.release_date) for r in h41.load_extract(AGENCY_EXTRACT)]
        mbs = [(r.week_ended, r.release_date) for r in h41.load_extract(MBS_EXTRACT)]
        self.assertEqual(agency, mbs)

    def test_the_derived_measure_is_read_under_both_sources_declarations(self):
        self.assertEqual(
            {source for source, _field in declaration.FIELDS["soma_agency_securities_weekly_change"]},
            {"frb_h41_agency", "frb_h41_mbs"},
        )

    def test_the_agency_source_declares_its_own_lag_not_the_mbs_ones(self):
        """The release lag is declared on the source the series is read from, so it cannot be inherited by accident."""
        registry = declaration.registry()
        self.assertIn("release_lag", registry["frb_h41_agency"])
        self.assertIn("soma_agency_debt_weekly_change", registry["frb_h41_agency"]["fields"])


class EndToEndTests(unittest.TestCase):
    """The guards read only the panel's dates and the declaration. The dates are the published panel's in every
    version (`panel.build` refuses any other), so version 1 is built here: versions 2 and 3 are records since
    12 October 2026, and this module ran on version 3 at the record commit (`scripts/verify_records.py`)."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.path = pathlib.Path(cls.tmp.name) / "phase3_panel.csv"
        cls.manifest = panel.build(cls.path, version=1)
        from repo_model.data import load_daily_panel

        cls.rows = load_daily_panel(cls.path)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_every_phase3_column_passes_the_parent_guards_on_every_row(self):
        dates = [row.date for row in self.rows]
        # The SLR fields (#63) are declared at a worst-case lag of years, so the panel's first rows have none; their own
        # test below holds them to the same guards.
        features = [name for name in declaration.FIELDS if name not in slr.FIELDS]
        with declaration.phase3_declaration():
            rule = InformationRule(declaration.registry(), features, decision_time=time(16, 0))
            skipped = []
            for index in range(len(dates)):
                try:
                    info = rule.information_set(dates, index)
                except SplitError:
                    skipped.append(index)
                    continue
                rule.check(dates, info)
        # Only the panel's first rows, before any weekly value is observable, have no information set.
        self.assertEqual(skipped, list(range(len(skipped))))
        self.assertLess(len(skipped), 15)

    def test_a_read_moved_one_row_later_is_leakage(self):
        dates = [row.date for row in self.rows]
        with declaration.phase3_declaration():
            rule = InformationRule(declaration.registry(), ["soma_treasury_weekly_change"], decision_time=time(16, 0))
            info = rule.information_set(dates, 1500)
            read = next(r for r in info.reads if r.feature == "soma_treasury_weekly_change")
            moved = info._replace(reads=tuple(r._replace(row=r.row + 1) if r is read else r for r in info.reads))
            with self.assertRaises(LookAheadError):
                rule.check(dates, moved)

    def test_an_effr_read_moved_one_row_later_is_leakage(self):
        """The parent's guard on an input Stage 1b switches on (`effr`, the parent's own `nyfed_effr` declaration)."""
        dates = [row.date for row in self.rows]
        with declaration.phase3_declaration():
            rule = InformationRule(declaration.registry(), ["effr"], decision_time=time(16, 0))
            info = rule.information_set(dates, 1500)
            moved = info._replace(reads=tuple(r._replace(row=r.row + 1) if r.feature == "effr" else r
                                              for r in info.reads))
            with self.assertRaises(LookAheadError):
                rule.check(dates, moved)

    def test_a_read_moved_one_row_earlier_is_stale(self):
        from repo_model.asof import StaleReadError

        dates = [row.date for row in self.rows]
        with declaration.phase3_declaration():
            rule = InformationRule(declaration.registry(), ["on_rrp"], decision_time=time(16, 0))
            info = rule.information_set(dates, 1500)
            moved = info._replace(reads=tuple(r._replace(row=r.row - 1) if r.feature == "on_rrp" else r
                                              for r in info.reads))
            with self.assertRaises(StaleReadError):
                rule.check(dates, moved)

    AGENCY_FEATURES = ("soma_agency_debt_weekly_change", "soma_agency_securities_weekly_change")

    def _agency_read(self, feature, offset):
        """The information set for `feature` at a row in 2024, and the same with its read moved by `offset` rows.

        The unmoved read must be the row the MBS series is read at: both are the same weekly release, with the same
        declared lag, so the agency series is never read earlier or later than the MBS one it is added to.
        """
        dates = [row.date for row in self.rows]
        with declaration.phase3_declaration():
            rule = InformationRule(declaration.registry(), [feature, "soma_mbs_weekly_change"],
                                   decision_time=time(16, 0))
            info = rule.information_set(dates, 1500)
            rule.check(dates, info)
            rows = {r.feature: r.row for r in info.reads}
            self.assertEqual(rows[feature], rows["soma_mbs_weekly_change"], feature)
            moved = info._replace(reads=tuple(r._replace(row=r.row + offset) if r.feature == feature else r
                                              for r in info.reads))
            return rule, dates, moved

    def test_an_agency_read_moved_one_row_later_is_leakage(self):
        """Leakage guard for the agency inputs (#30): a weekly value is read at the row after its release, and a read
        one row later is refused.

        Recorded mutation (13 October 2026): in `declarations/h41_agency.json`, `release_lag.days` changed from 5 to
        1. This test then fails with AssertionError: 1497 != 1496 : soma_agency_debt_weekly_change (the agency series
        read one row later than the MBS series, which keeps the 5-day lag).
        """
        for feature in self.AGENCY_FEATURES:
            with self.subTest(feature=feature):
                rule, dates, moved = self._agency_read(feature, +1)
                with self.assertRaises(LookAheadError):
                    rule.check(dates, moved)

    def test_an_agency_read_moved_one_row_earlier_is_stale(self):
        """Staleness guard for the agency inputs (#30): a read one row earlier than the latest public value is
        refused as stale.

        Recorded mutation (13 October 2026): in `declarations/h41_agency.json`, `release_lag.days` changed from 5 to
        1. This test then fails with AssertionError: 1497 != 1496 : soma_agency_debt_weekly_change (the agency series
        read one row later than the MBS series, which keeps the 5-day lag).
        """
        from repo_model.asof import StaleReadError

        for feature in self.AGENCY_FEATURES:
            with self.subTest(feature=feature):
                rule, dates, moved = self._agency_read(feature, -1)
                with self.assertRaises(StaleReadError):
                    rule.check(dates, moved)

    def test_every_h8_group_column_passes_the_parent_guards_on_every_row(self):
        """#26: the six group lines, read at every row of the panel under `frb_h8_groups`'s declaration."""
        dates = [row.date for row in self.rows]
        with declaration.phase3_declaration():
            rule = InformationRule(declaration.registry(), list(h8.FIELDS), decision_time=time(16, 0))
            skipped = []
            for index in range(len(dates)):
                try:
                    info = rule.information_set(dates, index)
                except SplitError:
                    skipped.append(index)
                    continue
                self.assertLessEqual(set(h8.FIELDS), {r.feature for r in info.reads})
                rule.check(dates, info)
        # Only the panel's first rows, before the first print of the extract's first week is public, have none.
        self.assertEqual(skipped, list(range(len(skipped))))
        self.assertLess(len(skipped), 15)

    def test_an_h8_group_read_moved_one_row_later_is_leakage(self):
        """The parent's guard on the H.8 group lines (#26): all six read one declaration, `frb_h8_groups`. A first print
        read at the row after the one the declaration allows is not yet public at the decision instant."""
        dates = [row.date for row in self.rows]
        feature = "h8_small_domestic_cash_assets"
        with declaration.phase3_declaration():
            rule = InformationRule(declaration.registry(), [feature], decision_time=time(16, 0))
            info = rule.information_set(dates, 1500)
            reads = [r for r in info.reads if r.feature == feature]
            self.assertEqual(len(reads), 1)
            moved = info._replace(reads=tuple(r._replace(row=r.row + 1) if r.feature == feature else r
                                              for r in info.reads))
            with self.assertRaises(LookAheadError):
                rule.check(dates, moved)

    def test_an_h8_group_read_moved_one_row_earlier_is_stale(self):
        from repo_model.asof import StaleReadError

        dates = [row.date for row in self.rows]
        feature = "h8_foreign_related_total_assets"
        with declaration.phase3_declaration():
            rule = InformationRule(declaration.registry(), [feature], decision_time=time(16, 0))
            info = rule.information_set(dates, 1500)
            moved = info._replace(reads=tuple(r._replace(row=r.row - 1) if r.feature == feature else r
                                              for r in info.reads))
            with self.assertRaises(StaleReadError):
                rule.check(dates, moved)

    def _slr_read(self, feature, offset, index=1500):
        """The information set for an SLR field at a row in 2024, and the same with its read moved by `offset` rows.

        The unmoved read must be the latest row whose quarter-end plus the extract's own measured worst-case lag (not
        the declaration's number) is at or before the decision instant, so the declared lag cannot drift from the data.
        """
        dates = [row.date for row in self.rows]
        worst = slr.worst_case_lag_days(slr.load_extract(SLR_EXTRACT))
        with declaration.phase3_declaration():
            rule = InformationRule(declaration.registry(), [feature], decision_time=time(16, 0))
            info = rule.information_set(dates, index)
            rule.check(dates, info)
            reads = [r for r in info.reads if r.feature == feature]
            self.assertEqual(len(reads), 1)
            deadline = rule.decision_instant(dates, index)
            expected = max(p for p in range(index) if datetime.combine(dates[p] + timedelta(days=worst), time.min) <= deadline)
            self.assertEqual(reads[0].row, expected, feature)
            moved = info._replace(reads=tuple(r._replace(row=r.row + offset) if r.feature == feature else r
                                              for r in info.reads))
            return rule, dates, moved

    def test_every_slr_column_passes_the_parent_guards_on_every_row(self):
        """#63: the four SLR fields, read at every row of the panel under `ffiec_call_slr`'s declaration."""
        dates = [row.date for row in self.rows]
        with declaration.phase3_declaration():
            rule = InformationRule(declaration.registry(), list(slr.FIELDS), decision_time=time(16, 0))
            skipped = []
            for index in range(len(dates)):
                try:
                    info = rule.information_set(dates, index)
                except SplitError:
                    skipped.append(index)
                    continue
                self.assertLessEqual(set(slr.FIELDS), {r.feature for r in info.reads})
                rule.check(dates, info)
        # The worst-case lag is years: the rows before the first figure is declared public have none.
        self.assertEqual(skipped, list(range(len(skipped))))
        self.assertLess(len(skipped), len(dates))

    def test_an_slr_read_moved_one_row_later_is_leakage(self):
        """Leakage guard for the SLR fields (#63): a figure is read at the row its declared lag allows, and a read one
        row later is refused.

        Recorded mutation (14 October 2026): in `declarations/ffiec_call_slr.json`, `release_lag.days` changed from 1714
        to 1700. This test then fails with AssertionError: 338 != 328 : slr_tier1_capital (the unmoved read is ten rows
        later than the extract's own worst-case lag puts it, for each field in turn).
        """
        for feature in slr.FIELDS:
            with self.subTest(feature=feature):
                rule, dates, moved = self._slr_read(feature, +1)
                with self.assertRaises(LookAheadError):
                    rule.check(dates, moved)

    def test_an_slr_read_moved_one_row_earlier_is_stale(self):
        from repo_model.asof import StaleReadError

        for feature in slr.FIELDS:
            with self.subTest(feature=feature):
                rule, dates, moved = self._slr_read(feature, -1)
                with self.assertRaises(StaleReadError):
                    rule.check(dates, moved)

    SCHEDULED_FEATURES = ("srf_rate", "on_rrp_rate", "runoff_cap_treasury_bn", "runoff_cap_mbs_bn")

    def _moved(self, feature, offset):
        """The information set for `feature` on a row after the facility began, and the same with its read moved by
        `offset` rows. The parent reads a scheduled value at the scored row, dated by the announcement one business
        day before at 16:00; the unmoved read is checked to be that."""
        dates = [row.date for row in self.rows]
        index = next(i for i, day in enumerate(dates) if day >= date(2024, 1, 2))
        with declaration.phase3_declaration():
            rule = InformationRule(declaration.registry(), [feature], decision_time=time(16, 0))
            info = rule.information_set(dates, index)
            reads = [r for r in info.reads if r.feature == feature]
            self.assertEqual([(r.kind, r.row) for r in reads], [(KIND_SCHEDULED, index)], feature)
            moved = info._replace(reads=tuple(r._replace(row=r.row + offset) if r.feature == feature else r
                                              for r in info.reads))
            return rule, dates, info, moved

    def test_a_scheduled_rate_or_cap_read_moved_one_row_later_is_leakage(self):
        """Leakage guard for the three FOMC series (#25): each is read at the row of the previous business day's
        decision instant, and a read one row later is refused.

        Recorded mutation (13 October 2026): in `metadata/sources_phase3.json`, `scheduled_availability.available_time`
        of `fed_srf_rate`, `fed_on_rrp_rate` and `fomc_runoff_caps` changed from "16:00" to "17:00" (an
        announcement counted as public only after the decision instant). This test then fails with LookAheadError
        from `rule.check` on the unmoved read: "first observable at ... 17:00, after the ... 16:00 decision", for
        every feature in turn.
        """
        for feature in self.SCHEDULED_FEATURES:
            with self.subTest(feature=feature):
                rule, dates, info, moved = self._moved(feature, +1)
                rule.check(dates, info)
                with self.assertRaises(LookAheadError):
                    rule.check(dates, moved)

    def test_a_scheduled_rate_or_cap_read_moved_one_row_earlier_is_stale(self):
        """Staleness guard for the three FOMC series (#25): a value is read at the row it became public, and a read
        one row earlier is refused as stale.

        Recorded mutation (13 October 2026): in `metadata/sources_phase3.json`, the `scheduled_availability` block of
        `fed_srf_rate`, `fed_on_rrp_rate` and `fomc_runoff_caps` deleted (the series read as an observed one). This
        test then fails with AssertionError: the read is no longer of kind "scheduled" at the scored row, for every
        feature in turn.
        """
        from repo_model.asof import StaleReadError

        for feature in self.SCHEDULED_FEATURES:
            with self.subTest(feature=feature):
                rule, dates, info, moved = self._moved(feature, -1)
                with self.assertRaises(StaleReadError):
                    rule.check(dates, moved)


if __name__ == "__main__":
    unittest.main()
