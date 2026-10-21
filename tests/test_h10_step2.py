"""H10 step 2: the method applied to the development onsets (`docs/stages/h10-step2.md`, `results/h10/development.json`).

Development evidence, never a verdict (`docs/decisions/measurement-protocol.md` section 1). The unit tests run on synthetic
series and hand-made episode dictionaries. The record tests check the tracked record against the parent's onsets at the
pin, against the panel's manifest and against a recomputation of the deterministic part (the point shares, the
placebo windows and the benchmark); one episode's interval is recomputed in full.
"""

import json
import pathlib
import random
import unittest
from datetime import date, datetime, timedelta
from types import SimpleNamespace

from repo_model.splits import LookAheadError

from lockbox_helper import moved_lockbox
from repo_liquidity import PANEL_SHA256, attribution, development, h10_apply, panel
from repo_liquidity.attribution import SPREAD

DRIVERS = attribution.DRIVERS_WITH_ON_RRP
RECORD = pathlib.Path(h10_apply.RECORD)

#: The parent pin these records were made at (L27, #105 moved the tree to a later pin). A published record is never
#: edited in place, so it keeps naming the pin it was made at.
RECORD_PARENT_COMMIT = "53e61af9b4175e854c196908d3c76b228c039667"


def episode(onset, *, status="attributed", residual=0.3, explained=0.7, beats=True, regime="depleted", quarter_end=False):
    attributed = status == "attributed"
    under = attributed and abs(residual) < attribution.RESIDUAL_BAR
    entry = {
        "onset": onset, "status": status, "under_bar": under, "beats_null": attributed and beats,
        "counted": under and attributed and beats, "regime": regime, "quarter_end": quarter_end,
    }
    if attributed:
        entry.update(residual={"point": residual}, explained_share=explained, explained_above_reserves=0.1,
                     placebo={"median_explained": 0.5})
    return entry


class WilsonTests(unittest.TestCase):
    def test_known_values(self):
        z = 1.6448536269514722
        low, high = h10_apply.wilson(0, 10, 0.90)
        self.assertEqual(low, 0.0)
        self.assertAlmostEqual(high, z * z / (10 + z * z), places=9)
        low, high = h10_apply.wilson(5, 10, 0.90)
        self.assertAlmostEqual(low + high, 1.0, places=12)
        self.assertLess(low, 0.5)

    def test_an_empty_group_has_no_interval(self):
        with self.assertRaises(ValueError):
            h10_apply.wilson(0, 0, 0.90)

    def test_the_interval_contains_the_proportion_and_stays_in_unit_range(self):
        for n in (1, 2, 7, 31):
            for k in range(n + 1):
                low, high = h10_apply.wilson(k, n, 0.90)
                self.assertTrue(0.0 <= low <= k / n <= high <= 1.0, (k, n))


class SummaryTests(unittest.TestCase):
    EPISODES = [
        episode("a", residual=0.2, beats=True),
        episode("b", residual=0.4, beats=False),
        episode("c", residual=0.6, beats=True),
        episode("d", residual=-0.7, beats=True, regime="abundant"),
        episode("e", status="not attributable", regime="abundant", quarter_end=True),
        episode("f", residual=0.1, beats=True, quarter_end=True),
    ]

    def test_counts_are_over_every_episode_and_a_not_attributable_one_is_a_miss(self):
        summary = h10_apply.summarise(self.EPISODES)
        self.assertEqual(summary["episodes"], 6)
        self.assertEqual((summary["under_bar"], summary["beats_null"], summary["counted"]), (3, 4, 2))
        self.assertEqual(summary["not_attributable"], 1)
        self.assertEqual(summary["outcome"], "residual dominates")
        self.assertEqual(summary["under_bar_outcome"], "residual dominates")

    def test_each_count_carries_a_wilson_interval(self):
        summary = h10_apply.summarise(self.EPISODES)
        for key in ("under_bar", "beats_null", "counted"):
            low, high = summary["intervals"][key]
            self.assertEqual([low, high], h10_apply.wilson(summary[key], 6, 0.90))

    def test_a_split_is_given_with_its_count(self):
        splits = h10_apply.summarise(self.EPISODES)["splits"]
        self.assertEqual({k: v["episodes"] for k, v in splits["regime"].items()}, {"depleted": 4, "abundant": 2})
        self.assertEqual({k: v["episodes"] for k, v in splits["day_type"].items()}, {"other": 4, "quarter-end": 2})
        self.assertEqual(splits["regime"]["abundant"]["not_attributable"], 1)
        self.assertEqual(splits["day_type"]["quarter-end"]["counted"], 1)
        total = sum(v["episodes"] for v in splits["regime"].values())
        self.assertEqual(total, 6)

    def test_an_empty_split_group_is_reported_with_a_zero_count(self):
        splits = h10_apply.summarise([episode("a")])["splits"]
        self.assertEqual(splits["regime"]["abundant"]["episodes"], 0)
        self.assertIsNone(splits["regime"]["abundant"]["intervals"])

    def test_the_table_is_rendered_from_the_record_alone(self):
        record = {"episodes": [
            {"onset": "2018-05-31", "status": "attributed", "rise_bp": 7.5, "regime": "depleted", "quarter_end": False,
             "shares": {n: {"point": 0.1, "low": 0.0, "high": 0.2} for n in DRIVERS},
             "fixed_shares": {n: 0.1 for n in DRIVERS},
             "residual": {"point": 0.5, "low": 0.4, "high": 0.6}, "explained_share": 0.5,
             "explained_above_reserves": 0.25, "under_bar": False, "beats_null": True, "counted": False,
             "placebo": {"windows": 20, "attributed": 18, "median_explained": 0.2, "share_at_or_above": 0.1}},
            {"onset": "2019-01-15", "status": "not attributable", "reason": "why", "regime": "depleted",
             "quarter_end": False, "rise_bp": None},
        ]}
        text = h10_apply.table_markdown(record)
        self.assertIn("2018-05-31", text)
        self.assertIn("2019-01-15", text)
        self.assertIn("not attributable: why", text)


class MedianTests(unittest.TestCase):
    def test_the_median_interval_is_the_order_statistics_of_the_sign_test(self):
        values = list(range(1, 32))
        result = h10_apply.median_interval(values, 0.90)
        self.assertEqual(result["n"], 31)
        self.assertEqual(result["median"], 16)
        # For n = 31 and a 90% level, P(Bin(31, 1/2) <= 10) = 0.0354 and P(... <= 11) = 0.0750: ranks 11 and 21.
        self.assertEqual(result["interval"], [11, 21])

    def test_a_small_sample_gets_the_whole_range(self):
        result = h10_apply.median_interval([0.2, 0.9, 0.4], 0.90)
        self.assertEqual(result["median"], 0.4)
        self.assertEqual(result["interval"], [0.2, 0.9])

    def test_no_values_gives_no_median(self):
        self.assertEqual(h10_apply.median_interval([], 0.90), {"n": 0, "median": None, "interval": None})

    def test_the_summary_reports_the_plans_progress_markers(self):
        entries = []
        for i, (residual, above, gap) in enumerate([(0.2, 0.1, 0.3), (0.6, 0.0, 0.1), (0.4, 0.2, -0.1)]):
            e = episode(f"d{i}", residual=residual)
            e.update(residual={"point": residual}, explained_above_reserves=above, explained_share=1 - residual,
                     placebo={"median_explained": 1 - residual - gap})
            entries.append(e)
        entries.append(episode("n", status="not attributable"))
        markers = h10_apply.summarise(entries)["markers"]
        self.assertEqual(markers["median_residual_share"]["median"], 0.4)
        self.assertEqual(markers["median_residual_share"]["n"], 3)
        self.assertEqual(markers["median_explained_above_reserves"]["median"], 0.1)
        self.assertAlmostEqual(markers["median_placebo_gap"]["median"], 0.1)


class ApplyEpisodeTests(unittest.TestCase):
    """`attribute_episode` on a synthetic series with a stub rule: the report day, the guard and the 'never dropped' rule."""

    @staticmethod
    def stub_rule(late_for=None):
        def availability(dates, fields, i):
            return datetime(2026, 1, 1) if late_for is None or i not in late_for else datetime(2099, 1, 1)

        return SimpleNamespace(
            groups=[SimpleNamespace(feature=SPREAD, kind="data", fields=("s",))],
            decision_instant=lambda d, i: datetime(2026, 6, 1),
            availability=availability,
        )

    def series(self):
        rng = random.Random(3)
        n = 300
        columns = {name: [rng.gauss(0, 1) for _ in range(n)] for name in DRIVERS}
        columns["quarter_end"] = [1.0 if t % 40 == 7 else 0.0 for t in range(n)]
        columns[SPREAD] = [sum(columns[name][t] for name in DRIVERS) + rng.gauss(0, 0.3) for t in range(n)]
        for t in range(100, 105):
            columns[SPREAD][t] += 5.0
        dates = [date(2025, 1, 1) + timedelta(days=i) for i in range(n)]
        return columns, dates

    def test_the_report_day_is_ten_panel_days_after_the_onset(self):
        self.assertEqual(h10_apply.REPORT_DAYS, 10)
        self.assertEqual(h10_apply.report_index(100, 300), 110)

    def test_a_report_day_past_the_sample_is_refused(self):
        with self.assertRaises(ValueError):
            h10_apply.report_index(295, 300)

    def test_an_episode_is_attributed_through_the_real_entry_point(self):
        series, dates = self.series()
        result = h10_apply.attribute_episode(series, dates, self.stub_rule(), 100, draws=20)
        self.assertEqual(result.status, "attributed")
        self.assertIsNotNone(result.intervals)

    def test_a_window_not_public_at_the_report_is_leakage_and_is_not_swallowed(self):
        """Leakage guard: `attribute_episode` calls `attribute` (which checks the window) and does not catch the error.

        Recorded mutation (14 October 2026): in `h10_apply.attribute_episode`, the call to `attribution.attribute` replaced
        by `attribution.attribute_synthetic`. This test then fails with AssertionError: LookAheadError not raised.
        """
        series, dates = self.series()
        with self.assertRaises(LookAheadError):
            h10_apply.attribute_episode(series, dates, self.stub_rule(late_for=set(range(95, 105))), 100, draws=5)

    def test_an_episode_whose_report_day_is_past_the_sample_is_not_attributable_not_dropped(self):
        series, dates = self.series()
        result = h10_apply.attribute_episode(series, dates, self.stub_rule(), 295, draws=5)
        self.assertEqual(result.status, "not attributable")
        self.assertIn("report day", result.reason)

    def test_the_rows_end_where_the_parents_lockbox_says(self):
        with moved_lockbox(date(2026, 3, 1)):
            rows, _ = h10_apply.load_development()
        self.assertEqual(rows[-1].date, date(2026, 2, 27))

    def test_a_locked_day_in_the_rows_is_leakage(self):
        """Leakage guard: `load_development` checks the rows it returns against the parent's lockbox, whatever end it was
        given. Here the end is forced past a locked tier.

        Recorded mutation (14 October 2026): in `h10_apply.load_development`, the call `attribution.check_development(dates)`
        replaced by `pass`. This test then fails with AssertionError: LookAheadError not raised.
        """
        from unittest import mock

        with moved_lockbox(date(2026, 3, 1)), mock.patch.object(development, "development_end", return_value=date(2026, 9, 3)):
            with self.assertRaises(LookAheadError):
                h10_apply.load_development()


class PlaceboTests(unittest.TestCase):
    def test_the_summary_counts_windows_that_explain_at_least_as_much_as_the_episode(self):
        results = [attribution.Attribution(i, "attributed", explained_share=v, residual_share=1 - v)
                   for i, v in enumerate((0.1, 0.5, 0.9))]
        results.append(attribution.Attribution(9, "not attributable", "x"))
        summary = h10_apply.placebo_summary(results, episode_explained=0.5)
        self.assertEqual((summary["windows"], summary["attributed"]), (4, 3))
        self.assertAlmostEqual(summary["share_at_or_above"], 2 / 3)
        self.assertAlmostEqual(summary["median_explained"], 0.5)

    def test_no_attributable_placebo_window_gives_no_summary_figures(self):
        summary = h10_apply.placebo_summary([attribution.Attribution(9, "not attributable", "x")], episode_explained=0.5)
        self.assertEqual(summary["attributed"], 0)
        self.assertIsNone(summary["median_explained"])


@unittest.skipUnless(RECORD.exists(), "the development record is not yet written")
class RecordTests(unittest.TestCase):
    """The tracked record against what the parent and the panel say."""

    @classmethod
    def setUpClass(cls):
        cls.record = json.loads(RECORD.read_text(encoding="utf-8"))
        cls.rows, cls.manifest = h10_apply.load_development()
        cls.dates = [row.date for row in cls.rows]
        cls.series = attribution.series_from_rows(cls.rows, DRIVERS)

    def test_the_episode_list_is_the_model_repos_and_the_cross_check_holds(self):
        found = attribution.cross_check_onsets(self.rows)
        self.assertEqual([e["onset"] for e in self.record["episodes"]], [self.dates[i].isoformat() for i in found])
        self.assertEqual(self.record["episode_source"]["cross_check"], "held")

    def test_every_episode_is_in_the_table_attributed_or_not(self):
        for entry in self.record["episodes"]:
            self.assertIn(entry["status"], ("attributed", "not attributable"))
            if entry["status"] == "not attributable":
                self.assertTrue(entry["reason"])
        summary = self.record["summary"]
        self.assertEqual(summary["episodes"], len(self.record["episodes"]))

    def test_the_record_names_its_pin_its_panel_and_its_seeds(self):
        self.assertEqual(self.record["parent_commit"], RECORD_PARENT_COMMIT)
        self.assertEqual(self.record["parent_panel_sha256"], PANEL_SHA256)
        # The record names the version it was made on (1), and its manifest is unchanged. The application now reads version 4
        # (#149; Eleonora, 21 October 2026), whose manifest names version 1 and differs in `srf_take_up` alone.
        self.assertEqual(self.record["panel"]["version"], 1)
        self.assertEqual(self.record["panel"]["sha256"], panel.load_manifest(self.record["panel"]["version"])["sha256"])
        self.assertEqual(self.record["panel"]["sha256"], self.manifest["v1_sha256"])
        self.assertEqual(self.manifest["version"], h10_apply.PANEL_VERSION)
        for key in ("seed", "draws", "null_draws", "null_quantile", "report_days", "placebo_windows", "drivers"):
            self.assertIn(key, self.record["settings"])
        self.assertEqual(self.record["tier"], "development")

    def test_no_day_after_the_development_end_is_read(self):
        end = development.development_end()
        self.assertLessEqual(date.fromisoformat(self.record["last_day_read"]), end)
        self.assertLessEqual(self.dates[-1], end)
        self.assertEqual(self.record["last_day_read"], self.dates[-1].isoformat())

    def test_the_counts_in_the_summary_are_the_counts_of_the_table(self):
        self.assertEqual(h10_apply.summarise(self.record["episodes"]), self.record["summary"])

    def test_the_outcome_counts_agree_with_the_methods_own_functions(self):
        attributions = [h10_apply.as_attribution(e) for e in self.record["episodes"]]
        null = attribution.SelectionNull(
            bar=self.record["null"]["bar"], quantile=self.record["null"]["quantile"],
            draws=self.record["null"]["draws"], episodes=self.record["null"]["episodes"], explained=())
        method = attribution.outcome_with_null(attributions, null)
        for key in ("episodes", "under_bar", "beats_null", "counted", "not_attributable", "outcome"):
            self.assertEqual(method[key], self.record["summary"][key], key)
        self.assertEqual(attribution.outcome(attributions)["outcome"], self.record["summary"]["under_bar_outcome"])

    def test_the_point_shares_the_benchmark_and_the_placebo_are_reproduced(self):
        settings = self.record["settings"]
        onsets = [self.dates.index(date.fromisoformat(e["onset"])) for e in self.record["episodes"]]
        placebo = attribution.placebo_starts(self.series, onsets, settings["placebo_windows"], settings["seed"])
        for entry, start in zip(self.record["episodes"], onsets):
            point = attribution.point_attribution(self.series, start, drivers=DRIVERS)
            self.assertEqual(point.status, entry["status"])
            if point.status != "attributed":
                continue
            self.assertAlmostEqual(point.residual_share, entry["residual"]["point"], places=9)
            for name in DRIVERS:
                self.assertAlmostEqual(point.shares[name], entry["shares"][name]["point"], places=9)
                self.assertAlmostEqual(point.fixed_shares[name], entry["fixed_shares"][name], places=9)
            self.assertAlmostEqual(
                attribution.explained_above_reserves(self.series, start, DRIVERS), entry["explained_above_reserves"], places=9)
            windows = [attribution.point_attribution(self.series, s, drivers=DRIVERS) for s in placebo[start]]
            again = h10_apply.placebo_summary(windows, point.explained_share)
            self.assertEqual(again, entry["placebo"])

    def test_the_first_episodes_interval_is_reproduced_in_full(self):
        entry = next(e for e in self.record["episodes"] if e["status"] == "attributed")
        start = self.dates.index(date.fromisoformat(entry["onset"]))
        with h10_apply.real_rule() as rule:
            result = h10_apply.attribute_episode(self.series, self.dates, rule, start,
                                                 draws=self.record["settings"]["draws"], seed=self.record["settings"]["seed"])
        self.assertEqual(result.intervals["tga"][0], entry["shares"]["tga"]["low"])
        self.assertEqual(result.residual_interval[1], entry["residual"]["high"])

    def test_the_stage_document_carries_the_records_table(self):
        stage = pathlib.Path(h10_apply.STAGE_DOC).read_text(encoding="utf-8")
        self.assertIn(h10_apply.table_markdown(self.record), stage)


if __name__ == "__main__":
    unittest.main()
