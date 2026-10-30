"""The results site (#170): a page built only from records and tracked files, and the checks that keep it so.

Tests first (CLAUDE.md): this module was written before `scripts/emit_site.py` and failed with ModuleNotFoundError
(the generator did not exist). The four tests the directive names are `TypedNumberTests`, `ReaderTests`,
`StaleCheckTests` and `BuiltFileTests`; the rest cover the panel digest check, the three findings and the registration.

Recorded mutations (CLAUDE.md: a new guard gets one mutation that kills it):

* `Records.figure` (the reader that refuses a figure no record carries): the `raise FigureError(...)` on a missing key
  replaced by `return None`. `ReaderTests.test_a_figure_no_record_carries_is_refused` then failed with
  `AssertionError: FigureError not raised`.
* `load_panel` (the digest check on the parent's published panel): the comparison `digest != expected` replaced by
  `False`. `PanelDigestTests.test_a_panel_that_is_not_the_published_one_is_refused` then failed with
  `AssertionError: ValueError not raised`.
"""

import copy
import importlib.util
import json
import pathlib
import re
import subprocess
import sys
import tempfile
import unittest
from decimal import Decimal

from repo_liquidity import h10_registration

ROOT = pathlib.Path(__file__).resolve().parents[1]


def _load(name, relative):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


emit_site = _load("emit_site", "scripts/emit_site.py")
check_built = _load("check_built_outputs_liquidity", "scripts/check_built_outputs.py")

_PANEL = {}


def published_panel():
    """The parent's published panel, built once (a few seconds), digest-checked by `load_panel`."""
    if "rows" not in _PANEL:
        _PANEL["rows"] = emit_site.load_panel()
    return _PANEL["rows"]


def synthetic_panel(first_year=2021, last_year=2025, spread_bp=-10):
    """One row per weekday of the given years: SOFR `spread_bp` below a 1.00 IORB, reserves in $bn, no calendar flags."""
    import datetime

    rows = []
    day = datetime.date(first_year, 1, 1)
    while day.year <= last_year:
        if day.weekday() < 5:
            rows.append({"date": day.isoformat(), "sofr": str(Decimal("1.00") + Decimal(spread_bp) / 100),
                         "iorb": "1.00", "reserve_balances": "3000.0", "quarter_end": "0", "days_to_month_end": "5"})
        day += datetime.timedelta(days=1)
    return rows


class TypedNumberTests(unittest.TestCase):
    """Nothing on the page is typed: the template carries no figure, every figure is a placeholder."""

    def test_the_template_carries_no_typed_number(self):
        text = (ROOT / "site" / "template.html").read_text(encoding="utf-8")
        self.assertEqual(emit_site.typed_numbers(text), [])

    def test_a_typed_number_in_the_template_is_found(self):
        self.assertEqual(emit_site.typed_numbers("<p>H10 is a name, but 46% of days is a figure.</p>"), ["46"])

    def test_numbers_in_markup_and_style_are_not_typed_figures(self):
        text = '<style>p{margin:0 16px}</style><a href="https://x.org/a1">link</a><h2 id="h7m">H7m</h2>'
        self.assertEqual(emit_site.typed_numbers(text), [])


class RenderTests(unittest.TestCase):
    def test_a_placeholder_left_unfilled_is_an_error(self):
        with self.assertRaises(ValueError):
            emit_site.render("<p>{{a}} {{b}}</p>", {"a": "x"})

    def test_a_value_the_template_does_not_use_is_an_error(self):
        with self.assertRaises(ValueError):
            emit_site.render("<p>{{a}}</p>", {"a": "x", "b": "y"})

    def test_a_filled_template_is_returned(self):
        self.assertEqual(emit_site.render("<p>{{a}}</p>", {"a": "x"}), "<p>x</p>")


class ReaderTests(unittest.TestCase):
    """Every figure is read from a published record through one reader that refuses a figure no record carries."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        (pathlib.Path(self.tmp.name) / "r.json").write_text(json.dumps({"a": {"b": 1.5}, "inf": float("inf")}))

    def test_a_figure_a_record_carries_is_read(self):
        records = emit_site.Records(pathlib.Path(self.tmp.name))
        self.assertEqual(records.figure("r.json", "a", "b"), 1.5)

    def test_a_figure_no_record_carries_is_refused(self):
        records = emit_site.Records(pathlib.Path(self.tmp.name))
        with self.assertRaises(emit_site.FigureError):
            records.figure("r.json", "a", "missing")

    def test_a_record_that_does_not_exist_is_refused(self):
        records = emit_site.Records(pathlib.Path(self.tmp.name))
        with self.assertRaises(emit_site.FigureError):
            records.figure("nope.json", "a")

    def test_the_inputs_read_are_listed_with_their_digests(self):
        records = emit_site.Records(pathlib.Path(self.tmp.name))
        records.figure("r.json", "a")
        (name, digest), = records.inputs()
        self.assertEqual(name, "r.json")
        self.assertRegex(digest, r"^[0-9a-f]{64}$")


class PanelDigestTests(unittest.TestCase):
    def test_a_panel_that_is_not_the_published_one_is_refused(self):
        with self.assertRaises(ValueError):
            emit_site.load_panel(expected_sha="0" * 64)

    def test_the_published_panel_loads_and_ends_at_the_development_tier(self):
        rows = published_panel()
        self.assertEqual(rows[-1]["date"], "2026-09-03")
        self.assertIn("reserve_balances", rows[0])


class FindingTests(unittest.TestCase):
    """Each finding's figures fail the build if the panel or record does not yield them."""

    def test_abundance_counts_days_at_the_floor_and_unchanged_days(self):
        rows = synthetic_panel(2021, 2023, spread_bp=-10)
        found = emit_site.finding_abundance(rows, 2021, 2023)
        self.assertEqual(found["share_at_floor"], Decimal(1))
        self.assertEqual(found["share_unchanged"], Decimal(1))
        self.assertEqual(found["days"], len(rows))

    def test_abundance_refuses_a_panel_that_does_not_cover_the_years(self):
        with self.assertRaises(ValueError):
            emit_site.finding_abundance(synthetic_panel(2022, 2023), 2021, 2023)

    def test_scarcity_yearly_means_and_the_refit_schedule_date(self):
        rows = synthetic_panel(2021, 2025, spread_bp=-3)
        found = emit_site.finding_scarcity(rows, 2022, 2025)
        self.assertEqual([y["year"] for y in found["years"]], [2022, 2023, 2024, 2025])
        self.assertTrue(all(y["mean_bp"] == Decimal(-3) for y in found["years"]))

    def test_scarcity_refuses_a_panel_without_the_last_year(self):
        with self.assertRaises(ValueError):
            emit_site.finding_scarcity(synthetic_panel(2021, 2024), 2022, 2025)

    def test_ceiling_counts_days_above_the_rate_in_force_by_day_type(self):
        rows = synthetic_panel(2021, 2021, spread_bp=0)
        for row in rows:
            if row["date"] == "2021-09-30":
                row["quarter_end"] = "1"
                row["sofr"] = "1.30"
        srf = [("2021-07-29", Decimal("1.10"))]
        found = emit_site.finding_ceiling(rows, srf, "2021-07-29", "2021-12-31")
        self.assertEqual(found["quarter_end"]["above"], 1)
        self.assertEqual(found["quarter_end"]["days"], 1)
        self.assertEqual(found["quarter_end"]["largest"]["margin_bp"], Decimal(20))
        self.assertEqual(found["other"]["above"], 0)

    def test_ceiling_uses_the_rate_in_force_not_a_later_one(self):
        rows = synthetic_panel(2021, 2021, spread_bp=0)
        rows[-1]["quarter_end"] = "1"  # one quarter-end day, so both day types exist
        srf = [("2021-07-29", Decimal("0.50")), ("2021-10-01", Decimal("1.10"))]
        found = emit_site.finding_ceiling(rows, srf, "2021-07-29", "2021-12-31")
        before = [r["date"] for r in rows if "2021-07-29" <= r["date"] < "2021-10-01"]
        self.assertEqual(found["other"]["above"], len(before))
        self.assertEqual(found["quarter_end"]["above"], 0)

    def test_ceiling_refuses_a_window_with_no_rate_in_force(self):
        with self.assertRaises(ValueError):
            emit_site.finding_ceiling(synthetic_panel(2021, 2021), [("2022-01-01", Decimal("1"))], "2021-01-01", "2021-12-31")

    def test_the_published_panel_yields_the_findings(self):
        rows = published_panel()
        found = emit_site.finding_abundance(rows, 2021, 2023)
        self.assertGreater(found["share_at_floor"], Decimal("0.4"))
        self.assertLess(found["reserves_min"]["bn"], found["reserves_max"]["bn"])
        scarcity = emit_site.finding_scarcity(rows, 2022, 2025)
        self.assertEqual(len(scarcity["years"]), 4)


class RegistrationTests(unittest.TestCase):
    def test_the_registered_digest_in_the_record_is_the_code_s(self):
        registration = emit_site.registration()
        self.assertEqual(registration["digest"], registration["code_digest"])
        self.assertEqual(registration["code_digest"], h10_registration.REGISTERED_DIGEST)
        self.assertEqual(registration["parent"], h10_registration.REGISTERED_PARENT)

    def test_a_record_digest_the_code_does_not_reproduce_is_refused(self):
        with self.assertRaises(ValueError):
            emit_site.registration(record_text=emit_site.registration_record_text().replace(
                emit_site.registration()["digest"], "a" * 64))


class StaleCheckTests(unittest.TestCase):
    """--check rebuilds the page and fails on any error, and on a page that is not what the inputs build."""

    def test_a_stale_page_fails_the_check(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = pathlib.Path(tmp) / "index.html"
            out.write_text("<html>an old build</html>", encoding="utf-8")
            problems = emit_site.check(published_panel(), output=out)
        self.assertTrue(any("stale" in p for p in problems), problems)

    def test_a_current_page_passes_and_an_absent_page_is_not_an_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = pathlib.Path(tmp) / "index.html"
            self.assertEqual(emit_site.check(published_panel(), output=out), [])
            out.write_text(emit_site.build(published_panel()), encoding="utf-8")
            self.assertEqual(emit_site.check(published_panel(), output=out), [])

    def test_the_page_builds_from_the_records_with_no_placeholder_left(self):
        page = emit_site.build(published_panel())
        self.assertNotIn("{{", page)
        self.assertIn("What the data show", page)
        self.assertIn("development evidence", page.lower())


class BuiltFileTests(unittest.TestCase):
    """A built file in a pull request fails, and none is tracked."""

    def test_the_built_page_is_refused_in_a_change(self):
        self.assertEqual(len(check_built.errors(["site/index.html"])), 1)
        self.assertEqual(check_built.errors(["site/template.html", "scripts/emit_site.py"]), [])

    def test_no_built_file_is_tracked(self):
        tracked = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True, text=True, check=True).stdout
        self.assertEqual(check_built.errors(p for p in tracked.split("\n") if p), [])

    def test_the_built_page_is_ignored_by_git(self):
        ignored = (ROOT / ".gitignore").read_text(encoding="utf-8").split("\n")
        self.assertIn("/site/index.html", ignored)


# ------------------------------------------------------------------------------------------- the design pass (#177)
#
# Tests first: the classes below were written before the chart builders, the glossary and the new template, and failed
# with `AttributeError: module 'emit_site' has no attribute 'chart_data'` (and the glossary file did not exist).
#
# Recorded mutations (CLAUDE.md: a new guard gets one mutation that kills it):
#
# * `chart_h10` (a chart whose data the records cannot yield): the `records.figure(...)` read of the group's intervals
#   replaced by a typed `[0, 1]`. `ChartDataTests.test_a_chart_the_records_cannot_yield_is_refused` then failed with
#   `AssertionError: FigureError not raised`.
# * `check` (every chart's data file is regenerated): the comparison of a chart's data file with its regenerated bytes
#   replaced by `False`. `ChartFileTests.test_a_stale_data_file_fails_the_check` then failed with
#   `AssertionError: False is not true : []` (no "stale" problem was reported).
# * `check_glossary` (a term without a primary source): the `startswith` test against `ALLOWED_SOURCES` replaced by
#   `False`. `GlossaryTests.test_every_term_has_a_definition_and_a_source` then failed with `AssertionError: ValueError
#   not raised` (for the empty source and for the non-primary one).


def _record_root(tmp):
    """A records root holding the real records, copied, so a test can remove one figure."""
    root = pathlib.Path(tmp)
    for relative in ("results/h10/development.json", "results/h7/kink.json", "docs/research/h7-refit-schedule.json"):
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((ROOT / relative).read_bytes())
    return root


class ChartDataTests(unittest.TestCase):
    """Every plotted value comes from a record or from the published panel through a tested function."""

    def test_the_abundance_chart_carries_each_panel_day_of_the_window(self):
        rows = synthetic_panel(2021, 2023, spread_bp=-10)
        chart = emit_site.chart_abundance(rows, 2021, 2023)
        self.assertEqual(len(chart["points"]), len(rows))
        self.assertEqual(chart["floor_bp"], -10)
        date, reserves, spread = chart["points"][0]
        self.assertEqual((date, reserves, spread), (rows[0]["date"], 3000.0, -10.0))

    def test_the_abundance_chart_refuses_a_panel_that_does_not_cover_the_years(self):
        with self.assertRaises(ValueError):
            emit_site.chart_abundance(synthetic_panel(2022, 2023), 2021, 2023)

    def test_the_scarcity_chart_has_yearly_means_and_the_marker_from_the_record(self):
        rows = synthetic_panel(2021, 2025, spread_bp=-3)
        chart = emit_site.chart_scarcity(rows, 2022, 2025, "2025-12-05")
        self.assertEqual([y["year"] for y in chart["years"]], [2022, 2023, 2024, 2025])
        self.assertTrue(all(y["mean_bp"] == -3.0 for y in chart["years"]))
        self.assertEqual(chart["marker"]["date"], "2025-12-05")

    def test_the_ceiling_chart_marks_quarter_ends_and_days_above_the_rate_in_force(self):
        rows = synthetic_panel(2021, 2021, spread_bp=0)
        for row in rows:
            if row["date"] == "2021-09-30":
                row["quarter_end"] = "1"
                row["sofr"] = "1.30"
        srf = [("2021-07-29", Decimal("1.10"))]
        chart = emit_site.chart_ceiling(rows, srf, "2021-07-29", "2021-12-31")
        by_date = {p[0]: p for p in chart["points"]}
        self.assertEqual(by_date["2021-09-30"][1:], [1.3, 1.1, 1, 1])
        self.assertEqual(by_date["2021-09-29"][1:], [1.0, 1.1, 0, 0])
        self.assertNotIn("2021-07-28", by_date)

    def test_the_ceiling_chart_refuses_a_window_with_no_rate_in_force(self):
        with self.assertRaises(ValueError):
            emit_site.chart_ceiling(synthetic_panel(2021, 2021), [("2022-01-01", Decimal("1"))], "2021-01-01", "2021-12-31")

    def test_the_published_records_yield_every_chart(self):
        charts = emit_site.chart_data(published_panel(), emit_site.Records())
        self.assertEqual(sorted(charts), ["abundance", "ceiling", "h10", "h7m", "scarcity"])
        self.assertGreater(len(charts["abundance"]["points"]), 500)
        self.assertEqual(len(charts["scarcity"]["years"]), 4)
        self.assertTrue(any(p[4] for p in charts["ceiling"]["points"]))
        self.assertEqual(charts["h10"]["groups"][0]["label"], "All development onsets")
        self.assertEqual(charts["h7m"]["estimators"][0]["name"], "Baseline B")

    def test_a_chart_the_records_cannot_yield_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _record_root(tmp)
            self.assertEqual(emit_site.chart_h10(emit_site.Records(root))["groups"][0]["episodes"], 31)
            record = json.loads((root / "results/h10/development.json").read_text())
            del record["summary"]["intervals"]
            (root / "results/h10/development.json").write_text(json.dumps(record))
            with self.assertRaises(emit_site.FigureError):
                emit_site.chart_h10(emit_site.Records(root))

    def test_the_h7m_chart_is_refused_without_the_kink_record(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _record_root(tmp)
            (root / "results/h7/kink.json").unlink()
            with self.assertRaises(emit_site.FigureError):
                emit_site.chart_h7m(emit_site.Records(root))


def _verdict_root(tmp, verdict=None):
    """A records root for the H7m verdict and the status table: the real results and plan, copied, so a test can change one."""
    import shutil

    root = pathlib.Path(tmp)
    shutil.copytree(ROOT / "results", root / "results")
    for relative in ("docs/research/plan.md", "docs/stages/h7m-verdict.md"):
        (root / relative).parent.mkdir(parents=True, exist_ok=True)
        (root / relative).write_bytes((ROOT / relative).read_bytes())
    for relative in ("docs/decisions/h10-method.md",):
        (root / relative).parent.mkdir(parents=True, exist_ok=True)
        (root / relative).write_bytes((ROOT / relative).read_bytes())
    if verdict is not None:
        path = root / "results/h7/verdict.json"
        record = json.loads(path.read_text())
        record["verdict"] = verdict
        path.write_text(json.dumps(record))
    return root


FORBIDDEN_PHRASES = ("decides nothing", "post hoc", "held out", "lockbox", "blind tier", "live record")


class H7mVerdictTests(unittest.TestCase):
    """Directive #194: the page shows H7m's recorded end (steps 4 and 5 and the stage verdict), read from the records.

    Written before the generator changed. They failed first: `section_verdict` did not exist (`AttributeError`), and
    the status table had no row for step 4 or 5 or for the stage outcome.

    Recorded mutation: in `section_verdict`, `records.figure(VERDICT_RECORD, "verdict")` replaced by the typed string
    `"not testable as stated"`. `test_the_verdict_follows_the_record` then failed with `AssertionError: 'inconclusive'
    not found in ...` (the page kept printing the typed verdict after the record changed).
    """

    def test_the_built_page_carries_the_verdict_the_record_holds(self):
        record = json.loads((ROOT / "results/h7/verdict.json").read_text())
        page = emit_site.build(published_panel())
        self.assertIn(emit_site.esc(record["verdict"]), page)
        self.assertEqual(record["verdict"], "not testable as stated")
        self.assertIn(emit_site.esc(record["not_claimed"]), page)
        self.assertIn("docs/stages/h7m-verdict.md", page)

    def test_the_verdict_follows_the_record(self):
        with tempfile.TemporaryDirectory() as tmp:
            records = emit_site.Records(_verdict_root(tmp, verdict="inconclusive"))
            values = emit_site.section_verdict(records)
        self.assertIn("inconclusive", " ".join(values.values()))
        self.assertNotIn("not testable as stated", " ".join(values.values()))

    def test_a_missing_verdict_record_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _verdict_root(tmp)
            (root / "results/h7/verdict.json").unlink()
            with self.assertRaises(emit_site.FigureError):
                emit_site.section_verdict(emit_site.Records(root))
            with self.assertRaises(emit_site.FigureError):
                emit_site.section_status(emit_site.Records(root))

    def test_the_plan_rule_is_quoted_from_the_record(self):
        with tempfile.TemporaryDirectory() as tmp:
            values = emit_site.section_verdict(emit_site.Records(_verdict_root(tmp)))
        text = " ".join(values.values())
        self.assertIn("Not testable as stated:", text)
        self.assertIn("so nothing can be registered", text)
        self.assertIn("docs/research/plan.md", text)

    def test_the_status_table_has_the_h7m_rows_for_steps_four_and_five_and_the_stage_outcome(self):
        with tempfile.TemporaryDirectory() as tmp:
            table = emit_site.section_status(emit_site.Records(_verdict_root(tmp)))["status_table"]
        rows = re.findall(r"<tr>(.*?)</tr>", table)
        h7m = [re.findall(r"<td>(.*?)</td>", r) for r in rows if r.startswith("<td>H7m</td>")]
        by_step = {r[1]: r for r in h7m}
        self.assertIn("results/h7/distribution-account.json", by_step["4"][3])
        self.assertIn("results/h7/step5-scores.json", by_step["5"][3])
        outcome = by_step["Stage outcome"]
        self.assertIn("not testable as stated", outcome[3])
        self.assertIn("docs/stages/h7m-verdict.md", outcome[3])
        self.assertIn("repo-market-liquidity#187", outcome[3])

    def test_the_page_makes_no_claim_beyond_the_record_and_carries_no_forbidden_phrase_or_count(self):
        page = emit_site.build(published_panel())
        visible = re.sub(r"(?is)<(style|script)\b.*?</\1>", " ", page)
        visible = re.sub(r"(?s)<[^>]*>", " ", visible).lower().replace("-", " ")
        for phrase in FORBIDDEN_PHRASES:
            with self.subTest(phrase=phrase):
                self.assertNotIn(phrase, visible)
        self.assertNotRegex(visible, r"\b\d[\d,]*\s+(unit\s+)?tests?\b")
        section = page[page.index('<section id="h7m">'):page.index('<section id="status">')]
        self.assertNotIn("whether scarcity can be measured is", section.lower())

    def test_the_wording_that_said_nothing_here_is_a_verdict_is_gone_for_h7m(self):
        page = emit_site.build(published_panel())
        self.assertNotIn("Nothing here is a verdict", page)
        self.assertIn("No forecast or measurement claim is confirmed here", page)


class ChartFileTests(unittest.TestCase):
    """Each chart's data is a file the page reads; --check regenerates it and fails on a stale one."""

    def test_each_chart_is_written_as_a_data_file_and_the_page_embeds_the_same_data(self):
        charts = emit_site.chart_data(published_panel(), emit_site.Records())
        with tempfile.TemporaryDirectory() as tmp:
            emit_site.write_chart_files(charts, pathlib.Path(tmp))
            self.assertEqual(sorted(p.name for p in pathlib.Path(tmp).iterdir()), sorted(n + ".json" for n in charts))
            for name, chart in charts.items():
                self.assertEqual(json.loads((pathlib.Path(tmp) / (name + ".json")).read_text()), chart)
        page = emit_site.build(published_panel())
        self.assertIn(emit_site.chart_json(charts), page)

    def test_a_stale_data_file_fails_the_check(self):
        charts = emit_site.chart_data(published_panel(), emit_site.Records())
        with tempfile.TemporaryDirectory() as tmp:
            data = pathlib.Path(tmp) / "data"
            emit_site.write_chart_files(charts, data)
            self.assertEqual(emit_site.check(published_panel(), output=pathlib.Path(tmp) / "index.html", data_dir=data), [])
            (data / "abundance.json").write_text("{}", encoding="utf-8")
            problems = emit_site.check(published_panel(), output=pathlib.Path(tmp) / "index.html", data_dir=data)
        self.assertTrue(any("abundance.json" in p and "stale" in p for p in problems), problems)

    def test_absent_data_files_are_not_an_error_and_a_tracked_one_is(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(emit_site.check(published_panel(), output=pathlib.Path(tmp) / "index.html",
                                             data_dir=pathlib.Path(tmp) / "none"), [])
        self.assertEqual(len(check_built.errors(["site/data/abundance.json"])), 1)
        ignored = (ROOT / ".gitignore").read_text(encoding="utf-8").split("\n")
        self.assertIn("/site/data/", ignored)


class TemplateGuardTests(unittest.TestCase):
    def test_a_typed_number_in_the_template_fails_the_build(self):
        text = (ROOT / "site" / "template.html").read_text(encoding="utf-8")
        broken = text.replace("<h1>", "<p>Spread was 46% of days.</p><h1>", 1)
        self.assertNotEqual(text, broken)
        with self.assertRaises(ValueError) as caught:
            emit_site.build(synthetic_panel(), template_text=broken)
        self.assertIn("typed numbers", str(caught.exception))

    def test_a_typed_number_in_a_caption_is_found(self):
        self.assertEqual(emit_site.typed_numbers('<figcaption><span class="t">Spread, 2021</span></figcaption>'), ["2021"])

    def test_the_template_has_a_host_and_a_caption_for_every_chart(self):
        text = (ROOT / "site" / "template.html").read_text(encoding="utf-8")
        for name in ("abundance", "scarcity", "ceiling", "h10", "h7m"):
            with self.subTest(chart=name):
                self.assertIn('id="chart-%s"' % name, text)
                self.assertIn("{{caption_%s}}" % name, text)

    def test_every_chart_and_finding_is_labelled_development_evidence(self):
        page = emit_site.build(published_panel())
        self.assertGreaterEqual(page.lower().count("descriptive development evidence"), 5)
        # The one allowed use of "confirmed" is the draft byline's negation (directive #194, a marked question for her).
        lowered = page.lower().replace("no forecast or measurement claim is confirmed here", "")
        self.assertNotRegex(lowered, r"\bconfirmed\b|\bverdict:")

    def test_the_charts_use_only_the_model_templates_library_at_its_pinned_version(self):
        text = (ROOT / "site" / "template.html").read_text(encoding="utf-8")
        scripts = re.findall(r'<script[^>]*src="([^"]+)"', text)
        self.assertEqual(scripts, ["https://cdnjs.cloudflare.com/ajax/libs/d3/7.9.0/d3.min.js"])


class GlossaryTests(unittest.TestCase):
    """The pattern of the model repo's `docs/visual/glossary.json`: a term, its definition, a primary source."""

    glossary = json.loads((ROOT / "docs" / "visual" / "glossary.json").read_text(encoding="utf-8"))

    def test_every_term_has_a_definition_and_a_source(self):
        emit_site.check_glossary(self.glossary)
        for field, value in (("definition", ""), ("src", ""), ("src", "https://example.com/x")):
            broken = copy.deepcopy(self.glossary)
            broken["terms"][0][field] = value
            with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                emit_site.check_glossary(broken)

    def test_keys_are_unique(self):
        broken = copy.deepcopy(self.glossary)
        broken["terms"].append(copy.deepcopy(broken["terms"][0]))
        with self.assertRaises(ValueError):
            emit_site.check_glossary(broken)

    def test_each_term_matches_its_own_printed_form(self):
        for entry in self.glossary["terms"]:
            with self.subTest(term=entry["key"]):
                self.assertTrue(any(re.search(p, entry["text"]) for p in entry["match"]))

    def test_every_glossary_term_is_used_in_the_template_and_every_dfn_is_defined(self):
        text = (ROOT / "site" / "template.html").read_text(encoding="utf-8")
        used = set(re.findall(r"\{\{dfn_(\w+)\}\}", text))
        self.assertEqual(used, {t["key"] for t in self.glossary["terms"]})


class StartHereTests(unittest.TestCase):
    """The newcomer layer: three to five sentences above the chapters, each term a <dfn> at its first use."""

    glossary = json.loads((ROOT / "docs" / "visual" / "glossary.json").read_text(encoding="utf-8"))

    @classmethod
    def setUpClass(cls):
        cls.page = emit_site.build(published_panel())

    def block(self):
        start, end = self.page.index("<!-- start-here -->"), self.page.index("<!-- /start-here -->")
        return self.page[start:end]

    def test_the_block_sits_above_the_chapters(self):
        self.assertLess(self.page.index("<!-- start-here -->"), self.page.index('<section id="show">'))

    def test_the_block_is_three_to_five_sentences(self):
        paragraph = re.search(r'<div class="prose">(.*?)</div>', self.block(), re.S).group(1)
        text = re.sub(r"<span class=\"def\".*?</span><!--/def-->", " ", paragraph, flags=re.S)
        text = re.sub(r"<[^>]+>", "", text)
        sentences = [s for s in re.split(r"(?<=[.?!])\s+", text.strip()) if s]
        self.assertTrue(3 <= len(sentences) <= 5, sentences)

    def test_every_glossary_term_in_the_block_is_a_dfn_at_its_first_use(self):
        uses = term_uses(self.block(), self.glossary)
        self.assertTrue(uses, "the block uses no glossary term")
        for key, (_, owner) in uses.items():
            with self.subTest(term=key):
                self.assertEqual(owner, key, "the first use of %r is not inside its <dfn>" % key)

    def test_a_term_used_before_its_dfn_is_caught(self):
        block = self.block()
        first_dfn = block.index("<dfn")
        broken = block[:first_dfn] + "<p>SOFR</p>" + block[first_dfn:]
        self.assertIsNone(term_uses(broken, self.glossary)["sofr"][1])

    def test_a_definition_is_in_the_page_not_in_a_title(self):
        self.assertIn('role="note" hidden', self.block())
        self.assertNotIn('title="', self.block())


def term_uses(block, glossary):
    """{key: (position of first use, key of the <dfn> it falls in or None)} (the model repo's test helper, adapted)."""
    block = re.sub(r"<span class=\"def\"[^>]*>.*?</span><!--/def-->", " ", block, flags=re.S)
    block = re.sub(r"<script.*?</script>", " ", block, flags=re.S)
    flat, owner, inside, pos = "", [], [], 0
    for m in re.finditer(r"<dfn[^>]*data-term=\"(\w+)\"[^>]*>|</dfn>|<[^>]+>", block):
        chunk = block[pos:m.start()]
        flat += chunk + " "
        owner += [inside[-1] if inside else None] * (len(chunk) + 1)
        if m.group(0).startswith("<dfn"):
            inside.append(m.group(1))
        elif m.group(0) == "</dfn>":
            inside.pop()
        pos = m.end()
    flat += block[pos:]
    owner += [None] * len(block[pos:])
    found = {}
    for entry in glossary["terms"]:
        hits = [m.start() for pattern in entry["match"] for m in re.finditer(pattern, flat)]
        if hits:
            found[entry["key"]] = (min(hits), owner[min(hits)])
    return found


class PhoneWidthTests(unittest.TestCase):
    """The page must not scroll sideways at phone width. A browser render is the proof (the PR shows it); these are the
    static guards the CSS and the chart code must keep, so a change that would break it fails without a browser."""

    text = (ROOT / "site" / "template.html").read_text(encoding="utf-8")

    def test_the_viewport_is_declared(self):
        self.assertIn('<meta name="viewport" content="width=device-width, initial-scale=1', self.text)

    def test_the_gutter_is_sixteen_pixels_at_phone_width(self):
        phone = re.search(r"@media \(max-width:560px\)\{(.*?)\n\}", self.text, re.S) or \
            re.search(r"@media \(max-width:560px\)\{(.*?)\}\s*\n", self.text)
        self.assertIsNotNone(phone)
        self.assertRegex(phone.group(0), r"\.wrap\{[^}]*padding:0 16px")

    def test_wide_content_scrolls_inside_its_own_box(self):
        self.assertRegex(self.text, r"\.scroll\{[^}]*overflow-x:auto")
        self.assertRegex(self.text, r"\.chart svg\{[^}]*max-width:100%")

    def test_a_chart_is_sized_from_its_container_and_has_a_view_box(self):
        script = self.text[self.text.index("<script>"):]
        self.assertIn("clientWidth", script)
        self.assertIn("viewBox", script)
        self.assertNotRegex(script, r'\.attr\("width", ?\d{4,}')


class LaptopWidthTests(unittest.TestCase):
    """The page uses a laptop screen (#188): the wrap is at least 64rem, running text keeps its caps, the phone rules
    are untouched, and the charts redraw at the container's width.

    Tests first: written before the template changed, `test_the_built_page_wrap_is_not_narrower_than_64rem` failed with
    `AssertionError: 44.0 not greater than or equal to 64` (the wrap was 44rem).

    Recorded mutation (a new guard on the layout): the `.wrap` rule's `max-width:72rem` put back to `max-width:44rem`.
    `test_the_built_page_wrap_is_not_narrower_than_64rem` then failed with `AssertionError: 44.0 not greater than or
    equal to 64`.
    """

    #: The two phone rules as they stood before this directive; a change to either is a change to the phones.
    PHONE_RULES = (
        "@media (max-width:720px){ .toc li small{display:block;margin-left:0} .toc li small::before{content:\"\"} }",
        "@media (max-width:560px){ body{font-size:1.04rem} .wrap{padding:0 16px} .masthead{margin-top:44px} "
        ".dek{font-size:1.14rem} section{margin-top:72px} #start{padding:16px 16px 18px} dl{grid-template-columns:1fr} }",
    )
    page = None

    @classmethod
    def setUpClass(cls):
        cls.page = emit_site.build(published_panel())

    def rule(self, selector):
        found = re.search(r"(?m)^" + re.escape(selector) + r"\{([^}]*)\}", self.page)
        self.assertIsNotNone(found, selector)
        return found.group(1)

    def test_the_built_page_wrap_is_not_narrower_than_64rem(self):
        width = re.search(r"max-width:([\d.]+)rem", self.rule(".wrap"))
        self.assertIsNotNone(width)
        self.assertGreaterEqual(float(width.group(1)), 64)

    def test_the_phone_media_rules_are_unchanged(self):
        for rule in self.PHONE_RULES:
            with self.subTest(rule=rule[:24]):
                self.assertIn(rule, self.page)

    def test_running_text_keeps_its_caps(self):
        self.assertIn("max-width:66ch", self.rule(".prose"))
        self.assertIn("max-width:16ch", self.rule("h1"))
        self.assertIn("max-width:36em", self.rule(".dek"))
        for selector in (".note", "details", "ul.guards", "footer"):
            with self.subTest(selector=selector):
                self.assertIn("max-width:74ch", self.rule(selector))

    def test_text_that_would_run_the_full_width_is_capped(self):
        for selector in (".byline", "#start", ".lede", "#built>p"):
            with self.subTest(selector=selector):
                self.assertRegex(self.rule(selector), r"max-width:\d+ch")

    def test_wide_blocks_are_not_capped(self):
        self.assertIn("max-width:none", self.rule("details.wide"))
        self.assertNotIn("max-width", self.rule("table"))
        self.assertNotIn("max-width", self.rule(".chart"))

    def test_the_charts_redraw_at_the_container_width_not_a_fixed_one(self):
        script = self.page[self.page.index("<script>"):]
        self.assertIn("host.node().clientWidth", script)
        self.assertIn('addEventListener("resize"', script)
        self.assertNotRegex(script, r"\b(?:W|width) ?= ?(?:7\d\d|6\d\d)\b")


if __name__ == "__main__":
    unittest.main()
