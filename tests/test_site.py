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

import importlib.util
import json
import pathlib
import subprocess
import sys
import tempfile
import unittest
from decimal import Decimal

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
        self.assertEqual(registration["parent"], emit_site.repo_liquidity.PARENT_COMMIT)

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


if __name__ == "__main__":
    unittest.main()
