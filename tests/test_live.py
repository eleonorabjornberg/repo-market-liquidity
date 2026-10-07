"""Stage 5a: the daily log's guards (`docs/stages/stage-5a.md`)."""

import gzip
import html
import re
import unittest
from datetime import date, datetime

from repo_liquidity import live, scheduled


class FomcCalendarTests(unittest.TestCase):
    def test_every_statement_is_on_the_saved_page(self):
        calendar = live.load_fomc_calendar()
        raw = gzip.decompress(live.CALENDAR_PAGE.read_bytes()).decode("utf-8", errors="replace")
        text = re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", raw)))
        for statement in calendar:
            meeting = statement.meeting.rsplit(",", 1)[0]
            year = statement.meeting.rsplit(" ", 1)[1]
            section = text[text.index(f"{year} FOMC Meetings"):]
            self.assertIn(meeting, section[:3000], statement.meeting)
            self.assertEqual(statement.instant.time(), live.STATEMENT_TIME)

    def test_the_page_matches_its_manifest(self):
        live.load_fomc_calendar()  # raises ValueError on a mismatch

    def test_the_calendar_is_in_order(self):
        instants = [statement.instant for statement in live.load_fomc_calendar()]
        self.assertEqual(instants, sorted(instants))


class FomcGuardTests(unittest.TestCase):
    STATEMENTS = (live.Statement("September 15-16, 2026", datetime(2026, 9, 16, 14, 0)),
                  live.Statement("October 27-28, 2026", datetime(2026, 10, 28, 14, 0)))

    def test_a_decision_after_an_uncovered_statement_is_refused(self):
        """A day whose decision instant follows a scheduled statement the rate tables do not yet cover is refused.

        Recorded mutation (7 October 2026): in `live.require_tables_cover`, the filter `if last < statement.instant`
        changed to `if False`. This test failed with AssertionError (ValueError not raised).
        """
        tables = {"iorb_rate.csv": datetime(2026, 9, 16, 14, 0), "on_rrp_rate.csv": datetime(2026, 9, 16, 14, 0)}
        with self.assertRaises(ValueError) as caught:
            live.require_tables_cover(datetime(2026, 10, 28, 16, 0), tables, statements=self.STATEMENTS)
        self.assertIn("October 27-28, 2026", str(caught.exception))
        self.assertIn("iorb_rate.csv", str(caught.exception))

    def test_a_decision_before_the_statement_passes(self):
        tables = {"iorb_rate.csv": datetime(2026, 9, 16, 14, 0), "on_rrp_rate.csv": datetime(2026, 9, 16, 14, 0)}
        live.require_tables_cover(datetime(2026, 10, 27, 16, 0), tables, statements=self.STATEMENTS)

    def test_one_table_behind_is_enough_to_refuse(self):
        tables = {"iorb_rate.csv": datetime(2026, 10, 28, 14, 0), "on_rrp_rate.csv": datetime(2026, 9, 16, 14, 0)}
        with self.assertRaises(ValueError) as caught:
            live.require_tables_cover(datetime(2026, 10, 29, 16, 0), tables, statements=self.STATEMENTS)
        self.assertIn("on_rrp_rate.csv", str(caught.exception))
        tables["on_rrp_rate.csv"] = datetime(2026, 10, 28, 14, 0)
        live.require_tables_cover(datetime(2026, 10, 29, 16, 0), tables, statements=self.STATEMENTS)

    def test_the_tracked_tables_cover_today(self):
        live.require_tables_cover(datetime(2026, 10, 7, 16, 0), live.table_coverage())

    def test_table_coverage_reads_both_tables(self):
        coverage = live.table_coverage()
        self.assertEqual(set(coverage), {"iorb_rate.csv", "on_rrp_rate.csv"})
        self.assertEqual(coverage["iorb_rate.csv"], scheduled.load_iorb_rates()[-1].announced_at)


class LoggableTests(unittest.TestCase):
    def test_a_development_day_is_never_logged(self):
        """No day on or before the development window's end is logged (`docs/stages/stage-5a.md`, must-show 3).

        Recorded mutation (7 October 2026): in `live.require_loggable`, `if day <= LAST_DEVELOPMENT_DAY:` changed to
        `if False:`. This test failed with AssertionError (ValueError not raised).
        """
        with self.assertRaises(ValueError):
            live.require_loggable(date(2025, 12, 31))
        live.require_loggable(date(2026, 10, 8))


if __name__ == "__main__":
    unittest.main()


class ForecastCoreTests(unittest.TestCase):
    """The forecast core on a short panel: both arms, persistence and the benchmarks, for the last row."""

    def test_it_forecasts_every_arm_for_the_last_row(self):
        from test_curve_feature import _panel_rows

        from repo_liquidity import curve_feature

        rows = [row for row in _panel_rows() if row.date <= date(2018, 9, 28)]
        with curve_feature.stage4_declaration():
            out = live.forecast(rows)
        self.assertEqual(set(out["distributions"]), {"levels", "persistence", "model_a", "model_b"})
        for name in ("persistence", "model_a", "model_b"):
            self.assertEqual(len(out["distributions"][name]["quantiles_bps"]), len(out["distributions"]["levels"]))
        self.assertEqual(set(out["probabilities"]),
                         {"model_a", "model_b", "calendar_climatology", "persistence_logistic"})
        for cells in out["probabilities"].values():
            self.assertEqual(set(cells), {"+5bp", "+10bp", "+20bp", "+50bp"})
            self.assertTrue(all(0.0 <= value <= 1.0 for value in cells.values()))
        self.assertGreater(out["curve"]["slope"], 0)


class PlaceholderGuardTests(unittest.TestCase):
    """Nothing but a calendar or scheduled column is read off a row after the last real one (must-show 3)."""

    def _rows_and_rule(self, features):
        from repo_model.asof import InformationRule

        from test_curve_feature import _panel_rows

        from repo_liquidity import curve_feature

        rows = [row for row in _panel_rows() if row.date <= date(2018, 9, 28)]
        rule = InformationRule(curve_feature.registry(), features, decision_time=live.DECISION_TIME)
        return rows, rule

    def test_the_scheduled_rates_may_be_read_on_a_placeholder(self):
        from repo_liquidity import curve_feature

        with curve_feature.stage4_declaration():
            rows, rule = self._rows_and_rule(("on_rrp_rate", "iorb_in_force"))
            live.require_reads_on_real_rows(rows, rule, len(rows) - 1, len(rows) - 2)

    def test_an_observed_read_on_a_placeholder_is_refused(self):
        """Recorded mutation (7 October 2026): in `live.require_reads_on_real_rows`, the call
        `module.require_reads_on_real_rows(rows, rule, index, last_real)` replaced by `pass`. This test failed with
        AssertionError (LookAheadError not raised).
        """
        from repo_model.splits import LookAheadError

        from repo_liquidity import curve_feature

        with curve_feature.stage4_declaration():
            rows, rule = self._rows_and_rule(("bank_total_assets", "on_rrp_rate"))
            with self.assertRaises(LookAheadError):
                live.require_reads_on_real_rows(rows, rule, len(rows) - 1, len(rows) - 30)


class WriteOnceTests(unittest.TestCase):
    def test_a_day_is_written_once(self):
        """Recorded mutation (7 October 2026): in `live.write_record`, the open mode `"xb"` changed to `"wb"`. This
        test failed with AssertionError (ValueError not raised).
        """
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as tmp:
            first = live.write_record(Path(tmp), date(2026, 10, 8), {"decision_day": "2026-10-08"})
            self.assertTrue(first.path.exists())
            with self.assertRaises(ValueError):
                live.write_record(Path(tmp), date(2026, 10, 8), {"decision_day": "2026-10-08", "again": True})
            self.assertNotIn("again", first.path.read_text(encoding="utf-8"))

    def test_the_record_must_name_its_day(self):
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as tmp, self.assertRaises(ValueError):
            live.write_record(Path(tmp), date(2026, 10, 8), {"decision_day": "2026-10-09"})


class LiveBuildTests(unittest.TestCase):
    """The live build path reproduces the development panel on every column the frozen declaration reads."""

    def test_the_tracked_fixtures_rebuild_the_development_columns(self):
        import json
        import tempfile
        from datetime import datetime
        from pathlib import Path

        from test_curve_feature import _panel_rows

        from repo_liquidity import curve_feature, parent_root

        snapshots = parent_root() / "tests" / "fixtures" / "snapshots"
        cutoff = datetime.fromisoformat(json.loads(
            (parent_root() / "metadata" / "funding_panel_manifest.json").read_text(encoding="utf-8"))["build_cutoff"])
        with tempfile.TemporaryDirectory() as tmp:
            rows, pit_path, recorded = live.build_rows(
                [snapshots / "funding_inputs", snapshots / "h8_inputs"], cutoff, Path(tmp))
            self.assertTrue(pit_path.exists())
        rows = live.with_scheduled_rates(rows)
        development = _panel_rows()
        self.assertEqual([row.date for row in rows], [row.date for row in development])
        columns = (set(curve_feature.DECLARED_FEATURES) - {"spread_bps"}) | {"sofr", "iorb"}
        for ours, theirs in zip(rows, development):
            for column in sorted(columns):
                self.assertEqual(ours.values.get(column), theirs.values.get(column), (ours.date, column))
        self.assertTrue(all(entry["source_id"] for entry in recorded))
