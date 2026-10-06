"""Phase 3's inputs read through the parent's as-of guards.

`tests/test_scheduled.py` holds the scheduled inputs' leakage guard. This module holds the H.4.1 declaration's
leakage guard and the end-to-end check that every Phase 3 column passes the parent's `asof.InformationRule` on every
row of the measurement panel.
"""

import pathlib
import tempfile
import unittest
from datetime import time

from repo_model.asof import InformationRule
from repo_model.splits import LookAheadError, SplitError

from repo_liquidity import declaration, fed_repo, h41, panel

ROOT = pathlib.Path(__file__).resolve().parents[1]
EXTRACT = ROOT / "tests" / "fixtures" / "snapshots" / "h41" / "h41_treasury_first_print.csv"
MBS_EXTRACT = ROOT / "tests" / "fixtures" / "snapshots" / "h41" / "h41_mbs_first_print.csv"


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


class TemporaryRepoDeclarationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        path = pathlib.Path(cls.tmp.name) / "phase3_panel_v2.csv"
        panel.build(path, version=2)
        from repo_model.data import load_daily_panel

        cls.dates = [row.date for row in load_daily_panel(path)]
        operations, sha = fed_repo.load_snapshots()
        cls.observations = [
            obs for term, series in (("Overnight", fed_repo.SERIES), ("Term", fed_repo.TERM_SERIES))
            for obs in fed_repo.observations(fed_repo.daily_take_up(operations, term=term), series=series,
                                             source_sha=sha)]

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_no_operation_is_public_before_its_declared_availability(self):
        """Leakage guard: each day's results are read no earlier than the declaration allows.

        Recorded mutation (6 October 2026): in `metadata/sources_phase3.json`, `nyfed_temp_repo.release_lag.days`
        changed from 1 to 0. This test then fails with LookAheadError: temp_repo_take_up for 2019-09-17 is public at
        2019-09-18 16:00, after its declared availability of 2019-09-17 16:00.
        """
        fed_repo.check_declared_lag(declaration.registry(), self.dates, self.observations)

    def test_a_declaration_earlier_than_publication_is_refused(self):
        registry = declaration.registry()
        entry = dict(registry["nyfed_temp_repo"])
        entry["release_lag"] = dict(entry["release_lag"], days=0)
        with self.assertRaises(LookAheadError):
            fed_repo.check_declared_lag({**registry, "nyfed_temp_repo": entry}, self.dates, self.observations)


class EndToEndTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.path = pathlib.Path(cls.tmp.name) / "phase3_panel_v2.csv"
        cls.manifest = panel.build(cls.path, version=2)
        from repo_model.data import load_daily_panel

        cls.rows = load_daily_panel(cls.path)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_every_phase3_column_passes_the_parent_guards_on_every_row(self):
        dates = [row.date for row in self.rows]
        features = list(declaration.FIELDS)
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


if __name__ == "__main__":
    unittest.main()
