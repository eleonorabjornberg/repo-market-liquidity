"""H10 step 3: the ON RRP sensitivity with two regime-specific terms (#86, finding #79).

The sensitivity of PR #78 took the window change of a truncated level (`v if v < 100 else 0`), which gives the wrong sign
to a window that straddles the $100 bn break and holds the abundant regime's coefficient at 0. This one fixes each
window's regime by its **baseline** mean ON RRP against the parent's `ON_RRP_DEPLETION_BREAK_BN` and enters
`change x 1(depleted)` and `change x 1(abundant)` as two drivers, each with its own coefficient. It is a sensitivity
(development evidence, never a verdict; `docs/decisions/measurement-protocol.md` section 1) and changes no outcome.

The tracked record is `results/h10/sensitivity_onrrp_regimes.json`; `results/h10/development.json` and
`results/h10/sensitivity_onrrp_interaction.json` (PR #78) are published records and stay byte for byte as merged.

No new availability or leakage guard is added: the regime term reads only the ON RRP column of the window's own baseline and
window days, which `attribution.check_window_public` already asks the parent's as-of rule about at the report day, so the
mutations recorded in `tests/test_h10_step2.py` cover it. The new functions are `attribution.window_change` and
`attribution.day_value`.

Recorded mutations of `attribution.window_change` / `_in_regime` (15 October 2026), each run on `WindowChangeTests`,
`DayValueTests` and `FitTests`, then restored:

* `_in_regime`: `baseline_mean < ON_RRP_DEPLETION_BREAK_BN` replaced with `<=`:
  `test_the_baseline_mean_at_the_break_is_abundant` failed with AssertionError.
* the regime read from the window's days (`series[ON_RRP][start : start + WINDOW_DAYS]`) instead of the baseline's:
  `test_a_window_that_straddles_the_break_keeps_the_sign_of_its_change` and
  `test_the_baseline_mean_at_the_break_is_abundant` failed with AssertionError.
* the abundant term held at 0 (as the superseded sensitivity did): `test_an_abundant_baseline_puts_it_on_the_abundant_term_only`,
  `test_a_window_that_straddles_the_break_keeps_the_sign_of_its_change` and `test_the_baseline_mean_at_the_break_is_abundant`
  failed with AssertionError, and `test_planted_coefficients_per_regime_are_recovered` with an error from a singular fit.
"""

import hashlib
import json
import pathlib
import random
import unittest
from datetime import date

from repo_liquidity import PANEL_SHA256, attribution, development, h10_apply, h10_publish, panel

ROOT = pathlib.Path(__file__).resolve().parents[1]
DEVELOPMENT = ROOT / "results" / "h10" / "development.json"
INTERACTION = ROOT / "results" / "h10" / "sensitivity_onrrp_interaction.json"
REGIMES = ROOT / "results" / "h10" / "sensitivity_onrrp_regimes.json"
PAGE = ROOT / "docs" / "research" / "h10-development-table.md"
#: The published records are never edited in place: their bytes are pinned here (merged in PRs #73 and #78).
DEVELOPMENT_SHA256 = "21fa38197d75822024a121106510a6b340cb842ddd2cbf5c643226e34b8dd8af"
INTERACTION_SHA256 = "b20e9b087c24573a64488d5453e2ddc18944995fb4bcc2f119fdd64e8fcfbcb0"

BREAK = 100.0
DEP, ABU = attribution.ON_RRP_DEPLETED, attribution.ON_RRP_ABUNDANT

#: The parent pin these records were made at (L27, #105 moved the tree to a later pin). A published record is never
#: edited in place, so it keeps naming the pin it was made at.
RECORD_PARENT_COMMIT = "53e61af9b4175e854c196908d3c76b228c039667"


def flat(values, spread=None):
    n = len(values)
    return {attribution.SPREAD: list(spread) if spread is not None else [0.0] * n, attribution.ON_RRP: list(values)}


class WindowChangeTests(unittest.TestCase):
    def test_a_depleted_baseline_puts_the_window_change_on_the_depleted_term_only(self):
        series = flat([50.0] * 5 + [70.0] * 5)
        self.assertAlmostEqual(attribution.window_change(series, DEP, 5), 20.0)
        self.assertEqual(attribution.window_change(series, ABU, 5), 0.0)

    def test_an_abundant_baseline_puts_it_on_the_abundant_term_only(self):
        series = flat([300.0] * 5 + [250.0] * 5)
        self.assertEqual(attribution.window_change(series, DEP, 5), 0.0)
        self.assertAlmostEqual(attribution.window_change(series, ABU, 5), -50.0)

    def test_a_window_that_straddles_the_break_keeps_the_sign_of_its_change(self):
        # Baseline 120 (abundant), window 80 (below the break): the change is -40 and it belongs to the abundant term.
        series = flat([120.0] * 5 + [80.0] * 5)
        self.assertAlmostEqual(attribution.window_change(series, ABU, 5), -40.0)
        self.assertEqual(attribution.window_change(series, DEP, 5), 0.0)
        # Baseline 80 (depleted), window 120: +40 on the depleted term.
        series = flat([80.0] * 5 + [120.0] * 5)
        self.assertAlmostEqual(attribution.window_change(series, DEP, 5), 40.0)
        self.assertEqual(attribution.window_change(series, ABU, 5), 0.0)

    def test_the_baseline_mean_at_the_break_is_abundant(self):
        series = flat([BREAK] * 5 + [90.0] * 5)
        self.assertEqual(attribution.window_change(series, DEP, 5), 0.0)
        self.assertAlmostEqual(attribution.window_change(series, ABU, 5), -10.0)

    def test_a_missing_day_or_an_incomplete_window_gives_none(self):
        series = flat([50.0, None, 50.0, 50.0, 50.0] + [70.0] * 5)
        self.assertIsNone(attribution.window_change(series, DEP, 5))
        self.assertIsNone(attribution.window_change(flat([50.0] * 7), ABU, 5))
        self.assertIsNone(attribution.window_change(flat([50.0] * 10), DEP, 3))

    def test_a_plain_driver_is_its_window_change(self):
        series = {attribution.SPREAD: [0.0] * 10, "tga": [1.0] * 5 + [4.0] * 5, attribution.ON_RRP: [0.0] * 10}
        self.assertAlmostEqual(attribution.window_change(series, "tga", 5), 3.0)

    def test_the_two_terms_are_named_and_the_input_is_not_modified(self):
        series = flat([50.0] * 5 + [70.0] * 5)
        before = list(series[attribution.ON_RRP])
        attribution.window_change(series, DEP, 5)
        self.assertEqual(series[attribution.ON_RRP], before)
        self.assertEqual(attribution.REGIME_TERMS, (DEP, ABU))
        self.assertEqual(attribution.DRIVERS_REGIME_TERMS, attribution.DRIVERS + (DEP, ABU))


class DayValueTests(unittest.TestCase):
    """The day-level value the selection null removes: the level while the day's trailing baseline is in the term's regime."""

    def test_the_level_counts_only_in_the_regime_of_the_days_trailing_baseline(self):
        series = flat([50.0] * 5 + [60.0, 70.0])
        self.assertEqual(attribution.day_value(series, DEP, 5), 60.0)
        self.assertEqual(attribution.day_value(series, ABU, 5), 0.0)
        series = flat([200.0] * 5 + [60.0])
        self.assertEqual(attribution.day_value(series, ABU, 5), 60.0)
        self.assertEqual(attribution.day_value(series, DEP, 5), 0.0)

    def test_a_day_without_a_full_baseline_or_a_level_is_none(self):
        series = flat([50.0, 50.0, 50.0, 50.0, 50.0, None])
        self.assertIsNone(attribution.day_value(series, DEP, 2))
        self.assertIsNone(attribution.day_value(series, DEP, 5))

    def test_a_plain_driver_is_its_level(self):
        self.assertEqual(attribution.day_value({"tga": [1.0, 2.0]}, "tga", 1), 2.0)


class FitTests(unittest.TestCase):
    def stretched(self):
        """Stretches of 60 days alternately depleted (20 to 80) and abundant (200 to 400); the spread moves 2 bp per unit of
        ON RRP when depleted and -3 when abundant. Ten missing days between stretches drop every window that straddles a
        boundary, so each kept window lies inside one stretch and is exact."""
        rng = random.Random(7)
        on_rrp, spread = [], []
        for k in range(8):
            depleted = k % 2 == 0
            for _ in range(60):
                level = rng.uniform(20, 80) if depleted else rng.uniform(200, 400)
                on_rrp.append(level)
                spread.append((2.0 if depleted else -3.0) * level)
            on_rrp += [None] * 10
            spread += [0.0] * 10
        return {attribution.SPREAD: spread, attribution.ON_RRP: on_rrp}

    def test_planted_coefficients_per_regime_are_recovered(self):
        beta = attribution.coefficients(self.stretched(), (DEP, ABU))
        self.assertAlmostEqual(beta[DEP], 2.0, delta=0.15)
        self.assertAlmostEqual(beta[ABU], -3.0, delta=0.15)

    def test_the_abundant_regime_has_a_coefficient_of_its_own(self):
        beta = attribution.coefficients(self.stretched(), (DEP, ABU))
        self.assertGreater(abs(beta[ABU]), 1.0)
        self.assertNotAlmostEqual(beta[ABU], beta[DEP], delta=1.0)

    def test_the_selection_null_runs_on_the_two_terms(self):
        series = self.stretched()
        null = attribution.selection_null(series, (DEP, ABU), draws=5, seed=3)
        self.assertEqual(null.draws, 5)
        self.assertGreater(null.episodes, 0)


def share(point=0.1):
    return {"point": point, "low": point - 0.1, "high": point + 0.1}


def episode(onset, *, terms, regime="depleted", residual=0.3, beats=True):
    under = abs(residual) < attribution.RESIDUAL_BAR
    return {
        "onset": onset, "index": 1, "status": "attributed", "rise_bp": 5.0, "regime": regime, "quarter_end": False,
        "shares": {n: share() for n in terms}, "fixed_shares": {n: 0.1 for n in terms}, "residual": share(residual),
        "explained_share": 1 - residual, "explained_above_reserves": 0.1, "under_bar": under, "beats_null": beats,
        "counted": under and beats, "placebo": {"windows": 20, "attributed": 10, "median_explained": 0.2, "share_at_or_above": 0.3},
    }


def record(episodes, *, terms, kind=None):
    out = {
        "record": "H10", "tier": "development", "parent_commit": "p" * 40, "parent_panel_sha256": "q" * 64,
        "panel": {"version": 1, "sha256": "r" * 64, "rows": 10, "first": "2018-04-03", "last": "2026-09-03"},
        "last_day_read": "2026-09-03",
        "settings": {"seed": 20261013, "draws": 10000, "null_draws": 1000, "null_quantile": 0.95, "placebo_windows": 20,
                     "drivers": list(terms)},
        "null": {"bar": 0.234, "draws": 1000, "episodes": 22401},
        "summary": h10_apply.summarise(episodes), "episodes": episodes,
    }
    if kind == "interaction":
        out["sensitivity"] = {"on_rrp_term": "on_rrp x 1(on_rrp < 100.0 bn)", "regime_break_bn": 100.0}
    if kind == "regimes":
        out["sensitivity"] = {"on_rrp_terms": ["depleted term", "abundant term"], "regime_break_bn": 100.0}
    return out


class PageTests(unittest.TestCase):
    ONSETS = ["2018-05-31", "2018-06-29", "2024-09-30", "2024-12-26"]
    PLAIN = attribution.DRIVERS_WITH_ON_RRP

    def page(self, regimes_residual=0.3):
        plain = [episode(o, terms=self.PLAIN, regime="abundant" if o.startswith("2024") else "depleted") for o in self.ONSETS]
        terms = attribution.DRIVERS_REGIME_TERMS
        other = [episode(o, terms=terms, regime="abundant" if o.startswith("2024") else "depleted",
                         residual=regimes_residual if o == "2018-05-31" else 0.3) for o in self.ONSETS]
        return h10_publish.render(record(plain, terms=self.PLAIN), record(plain, terms=self.PLAIN, kind="interaction"),
                                  development_sha256="d" * 64, method_sha256="m" * 64,
                                  regimes=record(other, terms=terms, kind="regimes"))

    def test_the_interaction_sensitivity_is_marked_superseded_with_a_date_and_the_reason(self):
        text = self.page()
        note = text.split("Superseded (", 1)[1].split("\n", 1)[0]
        self.assertIn(h10_publish.SUPERSEDED_ON, note)
        for needle in ("finding #79", "wrong sign", "92 of the 128", "supersedes it"):
            self.assertIn(needle, note)

    def test_the_new_section_reports_counts_with_intervals_labelled_sensitivity_and_states_the_abundant_regime(self):
        text = self.page().split("## Sensitivity: ON RRP as two regime-specific terms", 1)[1]
        self.assertIn("Reported only", text)
        self.assertIn("not a result", text)
        self.assertIn("The abundant regime has 2 onsets", text)
        self.assertIn("fitting sample's abundant windows", text)
        self.assertIn("% to ", text)

    def test_the_new_section_lists_episodes_whose_outcome_differs(self):
        text = self.page(regimes_residual=0.9).split("Episodes whose outcome differs from the published record", 1)[1]
        self.assertIn("2018-05-31", text)

    def test_without_the_new_record_the_page_has_no_supersession_note(self):
        plain = [episode(o, terms=self.PLAIN) for o in self.ONSETS]
        text = h10_publish.render(record(plain, terms=self.PLAIN), record(plain, terms=self.PLAIN, kind="interaction"),
                                  development_sha256="d" * 64, method_sha256="m" * 64)
        self.assertNotIn("Superseded", text)

    def test_a_regime_record_with_other_episodes_is_refused(self):
        plain = [episode(o, terms=self.PLAIN) for o in self.ONSETS]
        terms = attribution.DRIVERS_REGIME_TERMS
        with self.assertRaises(ValueError):
            h10_publish.render(record(plain, terms=self.PLAIN), record(plain, terms=self.PLAIN, kind="interaction"),
                               development_sha256="d" * 64, method_sha256="m" * 64,
                               regimes=record([episode(o, terms=terms) for o in self.ONSETS[:2]], terms=terms, kind="regimes"))

    def test_the_page_is_deterministic(self):
        self.assertEqual(self.page(), self.page())


class BuildRecordTests(unittest.TestCase):
    def test_the_interaction_and_the_regime_terms_are_not_combined(self):
        with self.assertRaises(ValueError):
            h10_apply.build_record([], {"sha256": "x"}, interaction=True, regimes=True)


class RecordTests(unittest.TestCase):
    """The tracked records and page against what the parent and the panel say."""

    @classmethod
    def setUpClass(cls):
        cls.development = json.loads(DEVELOPMENT.read_text(encoding="utf-8"))
        cls.interaction = json.loads(INTERACTION.read_text(encoding="utf-8"))
        cls.regimes = json.loads(REGIMES.read_text(encoding="utf-8"))
        cls.rows, cls.manifest = h10_apply.load_development()
        cls.dates = [row.date for row in cls.rows]

    def test_the_published_records_are_byte_unchanged(self):
        self.assertEqual(hashlib.sha256(DEVELOPMENT.read_bytes()).hexdigest(), DEVELOPMENT_SHA256)
        self.assertEqual(hashlib.sha256(INTERACTION.read_bytes()).hexdigest(), INTERACTION_SHA256)

    def test_it_has_the_same_episodes_pin_panel_and_seeds(self):
        a, b = self.development, self.regimes
        self.assertEqual([e["onset"] for e in b["episodes"]], [e["onset"] for e in a["episodes"]])
        self.assertEqual([e["regime"] for e in b["episodes"]], [e["regime"] for e in a["episodes"]])
        self.assertEqual([e["on_rrp_at_onset"] for e in b["episodes"]], [e["on_rrp_at_onset"] for e in a["episodes"]])
        self.assertEqual(b["parent_commit"], RECORD_PARENT_COMMIT)
        self.assertEqual(b["parent_panel_sha256"], PANEL_SHA256)
        self.assertEqual(b["panel"], a["panel"])
        self.assertEqual(b["panel"]["sha256"], panel.load_manifest(a["panel"]["version"])["sha256"])
        for key in ("seed", "draws", "null_draws", "null_quantile", "placebo_windows", "baseline_days", "window_days",
                    "block_length", "residual_bar", "report_days", "decision_time", "regime_break_bn"):
            self.assertEqual(b["settings"][key], a["settings"][key], key)
        self.assertEqual(b["tier"], "development")

    def test_it_is_labelled_a_sensitivity_that_supersedes_the_interaction_and_names_its_terms(self):
        self.assertIn("sensitivity", self.regimes["record"].lower())
        self.assertEqual(self.regimes["directive"], "eleonorabjornberg/repo-market-liquidity#86")
        self.assertEqual(self.regimes["sensitivity"]["supersedes"], "results/h10/sensitivity_onrrp_interaction.json")
        self.assertEqual(self.regimes["sensitivity"]["regime_break_bn"], 100.0)
        self.assertEqual(self.regimes["settings"]["drivers"], list(attribution.DRIVERS_REGIME_TERMS))
        self.assertEqual(len(self.regimes["sensitivity"]["on_rrp_terms"]), 2)

    def test_no_day_after_the_development_end_is_read(self):
        self.assertLessEqual(date.fromisoformat(self.regimes["last_day_read"]), development.development_end())
        self.assertEqual(self.regimes["last_day_read"], self.dates[-1].isoformat())

    def test_the_summary_is_the_summary_of_the_episodes(self):
        self.assertEqual(h10_apply.summarise(self.regimes["episodes"]), self.regimes["summary"])

    def test_the_abundant_regime_has_two_onsets(self):
        self.assertEqual(self.regimes["summary"]["splits"]["regime"]["abundant"]["episodes"], 2)

    def test_the_regime_terms_are_recomputed_from_the_plain_series(self):
        series = attribution.series_from_rows(self.rows, attribution.DRIVERS_WITH_ON_RRP)
        onsets = [self.dates.index(date.fromisoformat(e["onset"])) for e in self.regimes["episodes"]]
        for entry, start in zip(self.regimes["episodes"], onsets):
            point = attribution.point_attribution(series, start, drivers=attribution.DRIVERS_REGIME_TERMS)
            self.assertEqual(point.status, entry["status"])
            if point.status != "attributed":
                continue
            self.assertAlmostEqual(point.residual_share, entry["residual"]["point"], places=9)
            for name in attribution.REGIME_TERMS:
                self.assertAlmostEqual(point.shares[name], entry["shares"][name]["point"], places=9)
            self.assertAlmostEqual(attribution.explained_above_reserves(series, start, attribution.DRIVERS_REGIME_TERMS),
                                   entry["explained_above_reserves"], places=9)

    def test_it_goes_through_the_real_entry_point(self):
        series = attribution.series_from_rows(self.rows, attribution.DRIVERS_WITH_ON_RRP)
        start = self.dates.index(date.fromisoformat(self.regimes["episodes"][0]["onset"]))
        with h10_apply.real_rule() as rule:
            result = h10_apply.attribute_episode(series, self.dates, rule, start, draws=self.regimes["settings"]["draws"],
                                                 seed=self.regimes["settings"]["seed"], drivers=attribution.DRIVERS_REGIME_TERMS)
        entry = self.regimes["episodes"][0]
        self.assertEqual(result.intervals["tga"][0], entry["shares"]["tga"]["low"])
        self.assertEqual(result.residual_interval[1], entry["residual"]["high"])

    def test_the_page_is_the_one_the_script_renders_from_the_records(self):
        text = PAGE.read_text(encoding="utf-8")
        self.assertEqual(text, h10_publish.render_tracked())
        self.assertIn("Superseded (", text)
        self.assertIn(hashlib.sha256(DEVELOPMENT.read_bytes()).hexdigest(), text)


if __name__ == "__main__":
    unittest.main()
