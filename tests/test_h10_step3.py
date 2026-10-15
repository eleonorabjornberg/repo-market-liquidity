"""H10 step 3: the published development table and the ON RRP interaction sensitivity (#77).

`docs/research/h10-development-table.md` is generated from `results/h10/development.json` by `scripts/emit_h10_table.py`
and never hand-written; `results/h10/sensitivity_onrrp_interaction.json` is the step 2 application re-run with ON RRP
entering as `on_rrp x 1(on_rrp < 100 bn)` in place of its window change (her answer 5 on #69). Development evidence,
never a verdict (`docs/decisions/measurement-protocol.md` section 1). The sensitivity is reported only: the published
outcome and the method record's decided driver set do not change.

The unit tests use hand-made records. The record tests check the tracked sensitivity record against the parent's
onsets, the panel manifest and a recomputation of its deterministic part, check that the page is the one the script
renders, and pin the bytes of the step 2 record (it is a published record and is never edited in place).

No new availability or leakage guard is added: the sensitivity reads the same spread and the same ON RRP column through
`attribution.attribute`, which asks the parent's as-of rule, and `h10_apply.load_development`, which refuses a locked day,
so the mutations recorded in `tests/test_h10_step2.py` cover it too.

Recorded mutations of the one new function, `h10_apply.interaction_series` (15 October 2026), each run on
`InteractionSeriesTests`, then restored:

* `v if v < break_bn else 0.0` replaced with `v if v <= break_bn else 0.0`: `test_on_rrp_enters_only_while_it_is_below_the_break`
  and `test_the_break_is_strict_and_a_missing_day_stays_missing` failed with AssertionError.
* the same expression replaced with `v` (the plain series): the same two tests failed with AssertionError. The record tests
  (`test_the_sensitivity_series_is_the_interaction`) would also fail on a record regenerated under either mutation.
"""

import hashlib
import json
import pathlib
import unittest
from datetime import date

from repo_liquidity import PANEL_SHA256, PARENT_COMMIT, attribution, development, h10_apply, h10_publish, panel

ROOT = pathlib.Path(__file__).resolve().parents[1]
DEVELOPMENT = ROOT / "results" / "h10" / "development.json"
SENSITIVITY = ROOT / "results" / "h10" / "sensitivity_onrrp_interaction.json"
PAGE = ROOT / "docs" / "research" / "h10-development-table.md"
#: The published step 2 record is never edited in place: its bytes are pinned here (merged in PR #73).
DEVELOPMENT_SHA256 = "21fa38197d75822024a121106510a6b340cb842ddd2cbf5c643226e34b8dd8af"
DRIVERS = attribution.DRIVERS_WITH_ON_RRP


class InteractionSeriesTests(unittest.TestCase):
    def series(self):
        return {attribution.SPREAD: [1.0, 2.0, 3.0, 4.0, 5.0], "on_rrp": [250.0, 100.0, 99.9, 0.0, None],
                "tga": [1.0, 2.0, 3.0, 4.0, 5.0]}

    def test_on_rrp_enters_only_while_it_is_below_the_break(self):
        out = h10_apply.interaction_series(self.series(), 100.0)
        self.assertEqual(out["on_rrp"], [0.0, 0.0, 99.9, 0.0, None])

    def test_the_break_is_strict_and_a_missing_day_stays_missing(self):
        out = h10_apply.interaction_series({"on_rrp": [100.0, None, 99.0]}, 100.0)
        self.assertEqual(out["on_rrp"], [0.0, None, 99.0])

    def test_nothing_else_changes_and_the_input_is_not_mutated(self):
        series = self.series()
        out = h10_apply.interaction_series(series, 100.0)
        self.assertEqual(series["on_rrp"], [250.0, 100.0, 99.9, 0.0, None])
        for name in (attribution.SPREAD, "tga"):
            self.assertEqual(out[name], series[name])
        self.assertIsNot(out["tga"], series["tga"])


def share(point=0.1):
    return {"point": point, "low": point - 0.1, "high": point + 0.1}


def episode(onset, *, regime="depleted", residual=0.3, beats=True, quarter_end=False):
    under = abs(residual) < attribution.RESIDUAL_BAR
    return {
        "onset": onset, "index": 1, "status": "attributed", "rise_bp": 5.0, "regime": regime, "quarter_end": quarter_end,
        "shares": {n: share() for n in DRIVERS}, "fixed_shares": {n: 0.1 for n in DRIVERS}, "residual": share(residual),
        "explained_share": 1 - residual, "explained_above_reserves": 0.1, "under_bar": under, "beats_null": beats,
        "counted": under and beats, "placebo": {"windows": 20, "attributed": 10, "median_explained": 0.2, "share_at_or_above": 0.3},
    }


def record(episodes, *, sensitivity=False):
    out = {
        "record": "H10 step 3: sensitivity" if sensitivity else "H10 step 2",
        "directive": "eleonorabjornberg/repo-market-liquidity#77" if sensitivity else "eleonorabjornberg/repo-market-liquidity#70",
        "tier": "development", "parent_commit": "p" * 40, "parent_panel_sha256": "q" * 64,
        "panel": {"version": 1, "sha256": "r" * 64, "rows": 10, "first": "2018-04-03", "last": "2026-09-03"},
        "last_day_read": "2026-09-03",
        "settings": {"seed": 20261013, "draws": 10000, "null_draws": 1000, "null_quantile": 0.95, "placebo_windows": 20,
                     "drivers": list(DRIVERS)},
        "null": {"bar": 0.234, "draws": 1000, "episodes": 22401},
        "summary": h10_apply.summarise(episodes), "episodes": episodes,
    }
    if sensitivity:
        out["sensitivity"] = {"on_rrp_term": "on_rrp x 1(on_rrp < 100.0 bn)", "regime_break_bn": 100.0}
    return out


class PageTests(unittest.TestCase):
    EPISODES = [episode("2018-05-31"), episode("2018-06-29", residual=0.7), episode("2024-09-30", regime="abundant", quarter_end=True),
                episode("2024-12-26", regime="abundant", beats=False)]

    def page(self, sensitivity=None):
        return h10_publish.render(record(self.EPISODES), record(self.EPISODES if sensitivity is None else sensitivity, sensitivity=True),
                                  development_sha256="d" * 64, method_sha256="m" * 64)

    def test_the_header_names_the_pin_the_panel_and_the_seeds(self):
        text = self.page()
        for needle in ("p" * 40, "q" * 64, "r" * 64, "20261013", "10000", "1000", "d" * 64, "m" * 64):
            self.assertIn(needle, text)

    def test_the_tables_are_the_records_own_rendering(self):
        text = self.page()
        development_record = record(self.EPISODES)
        self.assertIn(h10_apply.table_markdown(development_record), text)
        self.assertIn(h10_apply.summary_markdown(development_record), text)

    def test_it_says_what_the_development_table_shows_and_that_it_is_not_a_verdict(self):
        text = self.page()
        self.assertIn("What the development table shows", text)
        self.assertIn("not a verdict", text)
        self.assertIn("no registration", text.lower())

    def test_the_sensitivity_is_labelled_and_states_the_abundant_regimes_size(self):
        text = self.page()
        self.assertIn("Sensitivity", text)
        self.assertIn("on_rrp x 1(on_rrp < 100.0 bn)", text)
        self.assertIn("The abundant regime has 2 onsets", text)
        self.assertIn("does not change the published outcome", text)

    def test_the_sensitivity_lists_episodes_whose_outcome_differs(self):
        other = [dict(e) for e in self.EPISODES]
        other[0] = episode("2018-05-31", residual=0.9, beats=True)
        text = self.page(other)
        self.assertIn("2018-05-31", text.split("Episodes whose outcome differs", 1)[1])

    def test_a_different_episode_list_is_refused(self):
        with self.assertRaises(ValueError):
            h10_publish.render(record(self.EPISODES), record(self.EPISODES[:2], sensitivity=True),
                               development_sha256="d" * 64, method_sha256="m" * 64)

    def test_a_sensitivity_record_that_is_not_marked_so_is_refused(self):
        with self.assertRaises(ValueError):
            h10_publish.render(record(self.EPISODES), record(self.EPISODES), development_sha256="d" * 64,
                               method_sha256="m" * 64)

    def test_the_page_is_deterministic(self):
        self.assertEqual(self.page(), self.page())


class RecordTests(unittest.TestCase):
    """The tracked records and page against what the parent and the panel say."""

    @classmethod
    def setUpClass(cls):
        cls.development = json.loads(DEVELOPMENT.read_text(encoding="utf-8"))
        cls.sensitivity = json.loads(SENSITIVITY.read_text(encoding="utf-8"))
        cls.rows, cls.manifest = h10_apply.load_development()
        cls.dates = [row.date for row in cls.rows]

    def test_the_published_step_2_record_is_byte_unchanged(self):
        self.assertEqual(hashlib.sha256(DEVELOPMENT.read_bytes()).hexdigest(), DEVELOPMENT_SHA256)

    def test_the_sensitivity_has_the_same_episodes_pin_panel_and_seeds(self):
        a, b = self.development, self.sensitivity
        self.assertEqual([e["onset"] for e in b["episodes"]], [e["onset"] for e in a["episodes"]])
        self.assertEqual([e["regime"] for e in b["episodes"]], [e["regime"] for e in a["episodes"]])
        self.assertEqual(b["parent_commit"], PARENT_COMMIT)
        self.assertEqual(b["parent_panel_sha256"], PANEL_SHA256)
        self.assertEqual(b["panel"], a["panel"])
        self.assertEqual(b["panel"]["sha256"], panel.load_manifest(1)["sha256"])
        for key in ("seed", "draws", "null_draws", "null_quantile", "placebo_windows", "baseline_days", "window_days",
                    "block_length", "residual_bar", "report_days", "decision_time"):
            self.assertEqual(b["settings"][key], a["settings"][key], key)
        self.assertEqual(b["tier"], "development")
        self.assertIn("sensitivity", b)

    def test_it_is_labelled_a_sensitivity_and_names_its_term(self):
        self.assertIn("sensitivity", self.sensitivity["record"].lower())
        self.assertEqual(self.sensitivity["sensitivity"]["regime_break_bn"], 100.0)
        self.assertIn("on_rrp x 1(on_rrp < 100.0 bn)", self.sensitivity["sensitivity"]["on_rrp_term"])
        self.assertEqual(self.sensitivity["settings"]["drivers"], list(DRIVERS))

    def test_no_day_after_the_development_end_is_read(self):
        self.assertLessEqual(date.fromisoformat(self.sensitivity["last_day_read"]), development.development_end())
        self.assertEqual(self.sensitivity["last_day_read"], self.dates[-1].isoformat())

    def test_the_summary_is_the_summary_of_the_episodes(self):
        self.assertEqual(h10_apply.summarise(self.sensitivity["episodes"]), self.sensitivity["summary"])

    def test_the_abundant_regime_has_two_onsets(self):
        self.assertEqual(self.sensitivity["summary"]["splits"]["regime"]["abundant"]["episodes"], 2)

    def test_the_sensitivity_series_is_the_interaction(self):
        series = attribution.series_from_rows(self.rows, DRIVERS)
        plain = [v for v in series["on_rrp"]]
        inter = h10_apply.interaction_series(series, self.sensitivity["sensitivity"]["regime_break_bn"])
        self.assertNotEqual(inter["on_rrp"], plain)
        onsets = [self.dates.index(date.fromisoformat(e["onset"])) for e in self.sensitivity["episodes"]]
        for entry, start in zip(self.sensitivity["episodes"], onsets):
            point = attribution.point_attribution(inter, start, drivers=DRIVERS)
            self.assertEqual(point.status, entry["status"])
            if point.status != "attributed":
                continue
            self.assertAlmostEqual(point.residual_share, entry["residual"]["point"], places=9)
            self.assertAlmostEqual(point.shares["on_rrp"], entry["shares"]["on_rrp"]["point"], places=9)
            self.assertAlmostEqual(attribution.explained_above_reserves(inter, start, DRIVERS),
                                   entry["explained_above_reserves"], places=9)
            self.assertEqual(entry["regime"], "depleted" if series["on_rrp"][start] < 100.0 else "abundant")
            self.assertEqual(entry["on_rrp_at_onset"], series["on_rrp"][start])

    def test_the_sensitivity_goes_through_the_real_entry_point(self):
        series = h10_apply.interaction_series(attribution.series_from_rows(self.rows, DRIVERS), 100.0)
        start = self.dates.index(date.fromisoformat(self.sensitivity["episodes"][0]["onset"]))
        with h10_apply.real_rule() as rule:
            result = h10_apply.attribute_episode(series, self.dates, rule, start, draws=self.sensitivity["settings"]["draws"],
                                                 seed=self.sensitivity["settings"]["seed"])
        entry = self.sensitivity["episodes"][0]
        self.assertEqual(result.intervals["tga"][0], entry["shares"]["tga"]["low"])
        self.assertEqual(result.residual_interval[1], entry["residual"]["high"])

    def test_the_page_is_the_one_the_script_renders_from_the_records(self):
        self.assertEqual(PAGE.read_text(encoding="utf-8"), h10_publish.render_tracked())

    def test_every_number_in_the_page_table_is_the_published_records(self):
        text = PAGE.read_text(encoding="utf-8")
        for e in self.development["episodes"]:
            self.assertIn(f"| {e['onset']} | {e['rise_bp']:.2f} |", text)
            self.assertIn(f"{e['residual']['point']:.3f} [{e['residual']['low']:.3f}, {e['residual']['high']:.3f}]", text)
        self.assertIn(h10_apply.summary_markdown(self.development), text)

    def test_the_page_states_the_digests_of_the_records_it_reads(self):
        text = PAGE.read_text(encoding="utf-8")
        self.assertIn(hashlib.sha256(DEVELOPMENT.read_bytes()).hexdigest(), text)
        self.assertIn(hashlib.sha256((ROOT / "docs" / "decisions" / "h10-method.md").read_bytes()).hexdigest(), text)


if __name__ == "__main__":
    unittest.main()
